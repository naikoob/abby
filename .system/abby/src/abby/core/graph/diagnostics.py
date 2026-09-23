"""Link graph diagnostics, broken link detection, orphan analysis, and report formatting."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from abby.constants import DEFAULT_INBOX_DIR
from abby.core.domain import resolve_domain_name
from abby.core.resolution import resolve_note_target as _core_resolve_note_target
from abby.models.links import BacklinkSummary, BrokenLinkItem

__all__ = [
    "find_orphan_notes",
    "find_unreferenced_notes",
    "format_backlinks_text",
    "format_broken_links_text",
    "format_outbound_links_text",
    "get_ambiguous_candidates",
    "resolve_note_target",
    "scan_broken_links",
]


def get_ambiguous_candidates(conn: Any, target_title: str) -> list[str]:
    """Return all matching candidate note paths when target_title matches multiple notes."""
    cursor = conn.execute("SELECT path, title FROM notes;")
    matches: list[str] = []
    target_lower = target_title.lower()
    for path_str, title in cursor.fetchall():
        if Path(path_str).stem.lower() == target_lower or (
            title and title.lower() == target_lower
        ):
            matches.append(path_str)
    return sorted(matches)


def resolve_note_target(
    conn: Any, note_arg: str, domain_filter: Optional[str] = None
) -> tuple[Optional[str], Optional[str], list[str]]:
    """Resolve a user-supplied note argument to (resolved_path, resolved_title, candidate_paths)."""
    return _core_resolve_note_target(conn, note_arg, domain_filter=domain_filter)


def format_outbound_links_text(
    records: list[Any], details: bool = False, multihop: bool = False
) -> str:
    """Format outbound link records as clean plain text, optionally grouped by depth."""
    if not records:
        return ""

    has_multi = multihop or any(getattr(rec, "depth", 1) > 1 for rec in records)

    def _format_item(rec: Any) -> str:
        if rec.resolved_path:
            prefix = rec.resolved_path
        elif rec.is_ambiguous:
            prefix = f"[ambiguous] {rec.target_title}"
        else:
            prefix = f"[unresolved] {rec.target_title}"

        if not details:
            if rec.is_ambiguous:
                return f"{prefix} (candidates: {', '.join(rec.candidate_paths)})"
            return prefix
        else:
            parts = [rec.link_syntax, f"line {rec.line_number}"]
            if rec.target_alias:
                parts.append(f'alias: "{rec.target_alias}"')
            if rec.target_heading:
                parts.append(f'heading: "{rec.target_heading}"')
            if rec.is_embed:
                parts.append("embed")
            if rec.is_ambiguous:
                parts.append(f"candidates: {', '.join(rec.candidate_paths)}")
            return f"{prefix} ({', '.join(parts)})"

    if not has_multi:
        return "\n".join(_format_item(rec) for rec in records)

    sections: list[str] = []
    depths = sorted(set(getattr(rec, "depth", 1) for rec in records))
    for d in depths:
        header = "## Depth 1 (Direct)" if d == 1 else f"## Depth {d} (Transitive)"
        d_recs = [rec for rec in records if getattr(rec, "depth", 1) == d]
        items = [_format_item(r) for r in d_recs]
        sections.append(header + "\n" + "\n".join(items))

    return "\n\n".join(sections)


def format_backlinks_text(
    summary: BacklinkSummary, details: bool = False, multihop: bool = False
) -> str:
    """Format incoming backlinks as clean plain text, optionally grouped by depth."""
    if not summary.backlinks:
        return ""

    has_multi = multihop or any(getattr(b, "depth", 1) > 1 for b in summary.backlinks)

    def _format_item(b: Any) -> str:
        if not details:
            return b.source_path
        else:
            parts = [b.link_syntax, f"line {b.line_number}"]
            if b.alias:
                parts.append(f'alias: "{b.alias}"')
            if b.heading:
                parts.append(f'heading: "{b.heading}"')
            if b.is_embed:
                parts.append("embed")
            return f"{b.source_path} ({', '.join(parts)})"

    if not has_multi:
        return "\n".join(_format_item(b) for b in summary.backlinks)

    sections: list[str] = []
    depths = sorted(set(getattr(b, "depth", 1) for b in summary.backlinks))
    for d in depths:
        header = "## Depth 1 (Direct)" if d == 1 else f"## Depth {d} (Transitive)"
        d_items = [b for b in summary.backlinks if getattr(b, "depth", 1) == d]
        items = [_format_item(b) for b in d_items]
        sections.append(header + "\n" + "\n".join(items))

    return "\n\n".join(sections)


def _reconstruct_raw_link(
    link_syntax: str,
    is_embed: bool,
    target_title: str,
    target_heading: Optional[str],
    target_alias: Optional[str],
) -> str:
    """Reconstruct original Markdown or Wikilink text from link components."""
    if link_syntax == "markdown":
        prefix = "![" if is_embed else "["
        label = target_alias or ""
        url = target_title
        if target_heading:
            url += f"#{target_heading}"
        return f"{prefix}{label}]({url})"

    prefix = "![[" if is_embed else "[["
    inner = target_title
    if target_heading:
        inner += f"#{target_heading}"
    if target_alias:
        inner += f"|{target_alias}"
    return f"{prefix}{inner}]]"


def _extract_file_headings(target_full: Path) -> set[str]:
    """Parse Markdown headings outside code fences from a target file."""
    headings_set: set[str] = set()
    if not target_full.is_file():
        return headings_set
    try:
        content = target_full.read_text(encoding="utf-8")
        in_code = False
        for line in content.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("```") or line_stripped.startswith("~~~"):
                in_code = not in_code
                continue
            if not in_code and re.match(r"^#{1,6}\s+", line_stripped):
                h = line_stripped.lstrip("#").strip().lower()
                if h:
                    headings_set.add(h)
    except (OSError, UnicodeDecodeError):
        pass
    return headings_set


def _fetch_links_for_domain(conn: Any, canonical_domain: Optional[str]) -> list[Any]:
    """Query note_links table filtered optionally by canonical domain."""
    query = """
            SELECT source_path, line_number, target_title, target_heading,
                   target_alias, link_syntax, is_embed, target_path
            FROM note_links
    """
    if canonical_domain:
        return conn.execute(
            query + " WHERE source_path LIKE (? || '/%') ORDER BY source_path ASC, line_number ASC;",
            (canonical_domain,),
        ).fetchall()
    return conn.execute(
        query + " ORDER BY source_path ASC, line_number ASC;"
    ).fetchall()


def scan_broken_links(
    conn: Any,
    vault_root: Path,
    check_headings: bool = False,
    domain_filter: Optional[str] = None,
) -> tuple[list[BrokenLinkItem], dict[str, str]]:
    """Scan vault for broken links (unresolved targets, and missing headings if enabled)."""
    canonical_domain = resolve_domain_name(domain_filter) if domain_filter else None
    rows = _fetch_links_for_domain(conn, canonical_domain)

    broken_items: list[BrokenLinkItem] = []
    heading_target_map: dict[str, str] = {}
    note_headings_cache: dict[str, set[str]] = {}

    for r in rows:
        source_path = r[0]
        line_number = r[1]
        target_title = r[2]
        target_heading = r[3]
        target_alias = r[4]
        link_syntax = r[5]
        is_embed = bool(r[6])
        target_path = r[7]

        raw_text = _reconstruct_raw_link(
            link_syntax, is_embed, target_title, target_heading, target_alias
        )

        if not target_path:
            broken_items.append(
                BrokenLinkItem(
                    source_path=source_path,
                    line_number=line_number,
                    target=target_title,
                    heading=None,
                    link_syntax=link_syntax,
                    raw_text=raw_text,
                )
            )
        elif check_headings and target_heading:
            if target_path not in note_headings_cache:
                note_headings_cache[target_path] = _extract_file_headings(vault_root / target_path)

            if target_heading.strip().lower() not in note_headings_cache[target_path]:
                broken_items.append(
                    BrokenLinkItem(
                        source_path=source_path,
                        line_number=line_number,
                        target=target_title,
                        heading=target_heading,
                        link_syntax=link_syntax,
                        raw_text=raw_text,
                    )
                )
                heading_target_map[target_title] = target_path

    return broken_items, heading_target_map


def format_broken_links_text(
    broken_links: list[BrokenLinkItem],
    target_path_map: Optional[dict[str, str]] = None,
) -> str:
    """Format broken link items as clean line-delimited plain text."""
    lines: list[str] = []
    for item in broken_links:
        if item.heading:
            dest = (target_path_map or {}).get(item.target, item.target)
            lines.append(
                f"{item.source_path}:{item.line_number}: {item.raw_text} -> heading anchor '#{item.heading}' not found in '{dest}'"
            )
        else:
            lines.append(
                f"{item.source_path}:{item.line_number}: {item.raw_text} -> target not found"
            )
    return "\n".join(lines)


def find_orphan_notes(
    conn: Any,
    include_inbox: bool = False,
    domain_filter: Optional[str] = None,
) -> list[str]:
    """Find notes with 0 incoming backlinks AND 0 outgoing links."""
    canonical_domain = None
    if domain_filter:
        canonical_domain = resolve_domain_name(domain_filter)
        if canonical_domain == DEFAULT_INBOX_DIR:
            include_inbox = True

    params: list[Any] = []
    conditions = [
        "path NOT IN (SELECT DISTINCT source_path FROM note_links)",
        "path NOT IN (SELECT DISTINCT target_path FROM note_links WHERE target_path IS NOT NULL)",
        "LOWER(title) NOT IN (SELECT DISTINCT LOWER(target_title) FROM note_links)",
    ]

    if not include_inbox:
        conditions.append("domain != ?")
        params.append(DEFAULT_INBOX_DIR)

    if canonical_domain:
        conditions.append("domain = ?")
        params.append(canonical_domain)

    sql = f"SELECT path FROM notes WHERE {' AND '.join(conditions)} ORDER BY path ASC;"
    cursor = conn.execute(sql, tuple(params))
    return [r[0] for r in cursor.fetchall()]


def find_unreferenced_notes(
    conn: Any,
    include_inbox: bool = False,
    domain_filter: Optional[str] = None,
) -> list[str]:
    """Find notes with 0 incoming backlinks (leaf notes)."""
    canonical_domain = None
    if domain_filter:
        canonical_domain = resolve_domain_name(domain_filter)
        if canonical_domain == DEFAULT_INBOX_DIR:
            include_inbox = True

    params: list[Any] = []
    conditions = [
        "path NOT IN (SELECT DISTINCT target_path FROM note_links WHERE target_path IS NOT NULL)",
        "LOWER(title) NOT IN (SELECT DISTINCT LOWER(target_title) FROM note_links)",
    ]

    if not include_inbox:
        conditions.append("domain != ?")
        params.append(DEFAULT_INBOX_DIR)

    if canonical_domain:
        conditions.append("domain = ?")
        params.append(canonical_domain)

    sql = f"SELECT path FROM notes WHERE {' AND '.join(conditions)} ORDER BY path ASC;"
    cursor = conn.execute(sql, tuple(params))
    return [r[0] for r in cursor.fetchall()]

