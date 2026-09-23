"""Graph traversal, outbound links, and backlink querying engine."""

from __future__ import annotations

from typing import Any, Optional

from abby.core.domain import resolve_domain_name
from abby.core.graph.diagnostics import get_ambiguous_candidates
from abby.models.links import BacklinkOccurrence, BacklinkSummary, NoteLinkRecord

__all__ = [
    "query_backlinks",
    "query_outbound_links",
]


def query_outbound_links(
    conn: Any,
    source_path: str,
    domain_filter: Optional[str] = None,
    depth: int = 1,
) -> list[NoteLinkRecord]:
    """Query outbound links from source note, traversing up to depth hops with cycle detection."""
    max_depth = max(1, depth)
    canonical_domain = None
    if domain_filter:
        canonical_domain = resolve_domain_name(domain_filter)

    records: list[NoteLinkRecord] = []
    visited_notes: set[str] = {source_path}
    queue: list[tuple[str, int]] = [(source_path, 1)]

    while queue:
        curr_source, curr_depth = queue.pop(0)

        cursor = conn.execute(
            """SELECT target_title, target_heading, target_alias, target_path,
                      link_syntax, is_embed, line_number
               FROM note_links
               WHERE source_path = ?
               ORDER BY line_number ASC;""",
            (curr_source,),
        )
        rows = cursor.fetchall()
        for r in rows:
            target_title = r[0]
            target_heading = r[1]
            target_alias = r[2]
            target_path = r[3]
            link_syntax = r[4]
            is_embed = bool(r[5])
            line_number = r[6]

            resolved_path = target_path
            is_ambiguous = False
            candidates: list[str] = []

            if not resolved_path:
                cands = get_ambiguous_candidates(conn, target_title)
                if len(cands) > 1:
                    is_ambiguous = True
                    candidates = cands

            if canonical_domain:
                if resolved_path:
                    if not resolved_path.startswith(canonical_domain + "/"):
                        continue
                elif is_ambiguous:
                    domain_cands = [
                        c for c in candidates if c.startswith(canonical_domain + "/")
                    ]
                    if not domain_cands:
                        continue
                    candidates = domain_cands
                else:
                    continue

            records.append(
                NoteLinkRecord(
                    source_path=curr_source,
                    target_title=target_title,
                    target_heading=target_heading,
                    target_alias=target_alias,
                    link_syntax=link_syntax,
                    is_embed=is_embed,
                    line_number=line_number,
                    resolved_path=resolved_path,
                    is_ambiguous=is_ambiguous,
                    candidate_paths=candidates,
                    depth=curr_depth,
                )
            )

            if curr_depth < max_depth and resolved_path:
                if resolved_path not in visited_notes:
                    visited_notes.add(resolved_path)
                    queue.append((resolved_path, curr_depth + 1))

    return records


def query_backlinks(
    conn: Any,
    target_path: str,
    target_title: str,
    domain_filter: Optional[str] = None,
    depth: int = 1,
) -> BacklinkSummary:
    """Query incoming backlinks pointing to target_path across the vault, traversing up to depth hops."""
    max_depth = max(1, depth)
    canonical_domain = None
    if domain_filter:
        canonical_domain = resolve_domain_name(domain_filter)

    occurrences: list[BacklinkOccurrence] = []
    visited_notes: set[str] = {target_path}
    queue: list[tuple[str, int]] = [(target_path, 1)]

    while queue:
        curr_target, curr_depth = queue.pop(0)

        if canonical_domain:
            cursor = conn.execute(
                """SELECT source_path, line_number, target_alias, target_heading, link_syntax, is_embed
                   FROM note_links
                   WHERE target_path = ? AND source_path != ? AND source_path LIKE (? || '/%')
                   ORDER BY source_path ASC, line_number ASC;""",
                (curr_target, curr_target, canonical_domain),
            )
        else:
            cursor = conn.execute(
                """SELECT source_path, line_number, target_alias, target_heading, link_syntax, is_embed
                   FROM note_links
                   WHERE target_path = ? AND source_path != ?
                   ORDER BY source_path ASC, line_number ASC;""",
                (curr_target, curr_target),
            )

        for r in cursor.fetchall():
            source_p = r[0]
            occurrences.append(
                BacklinkOccurrence(
                    source_path=source_p,
                    line_number=r[1],
                    alias=r[2],
                    heading=r[3],
                    link_syntax=r[4],
                    is_embed=bool(r[5]),
                    depth=curr_depth,
                )
            )

            if curr_depth < max_depth and source_p:
                if source_p not in visited_notes:
                    visited_notes.add(source_p)
                    queue.append((source_p, curr_depth + 1))

    return BacklinkSummary(
        target_note=target_path,
        target_title=target_title,
        backlinks=occurrences,
    )

