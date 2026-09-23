"""Search and discovery execution engine for Abby Knowledge Vault."""

from __future__ import annotations

import dataclasses
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from abby.core.cache import (
    get_cache_db_path,
    get_db_connection,
    rebuild_cache,
    sync_cache,
)
from abby.core.search_builder import (
    FTS_OPERATORS,
    FTS_SPECIAL_CHARS,
    REGEX_METACHARS,
    build_search_sql,
    extract_leading_snippet,
    extract_regex_snippet,
    is_regex_query,
    resolve_search_domain,
    sanitize_fts_query,
    validate_iso_date,
)
from abby.models.exceptions import SearchArgumentError, SearchDomainError
from abby.models.search import SearchFilter, SearchMatchItem
from abby.models.trust import evaluate_staleness

__all__ = [
    "FTS_OPERATORS",
    "FTS_SPECIAL_CHARS",
    "REGEX_METACHARS",
    "build_search_sql",
    "extract_leading_snippet",
    "extract_regex_snippet",
    "is_regex_query",
    "query_notes",
    "resolve_search_domain",
    "sanitize_fts_query",
    "validate_iso_date",
]


def _execute_search_query(
    conn: sqlite3.Connection,
    search_filter: SearchFilter,
) -> tuple[list[Any], int]:
    """Execute search query and count with automatic syntax error escaping fallback."""
    query_sql, query_params = build_search_sql(search_filter, count_only=False)
    count_sql, count_params = build_search_sql(search_filter, count_only=True)

    try:
        total_matches = conn.execute(count_sql, count_params).fetchone()[0]
        rows = conn.execute(query_sql, query_params).fetchall()
        return rows, total_matches
    except sqlite3.OperationalError as sql_err:
        err_msg = str(sql_err).lower()
        is_syntax_err = "fts5" in err_msg or "syntax error" in err_msg or "no such column" in err_msg
        if search_filter.query and not is_regex_query(search_filter.query) and is_syntax_err:
            escaped_literal = f'"{search_filter.query.strip().replace("\"", "")}"'
            fallback_filter = dataclasses.replace(search_filter, query=escaped_literal)
            fb_query_sql, fb_query_params = build_search_sql(fallback_filter, count_only=False)
            fb_count_sql, fb_count_params = build_search_sql(fallback_filter, count_only=True)
            total_matches = conn.execute(fb_count_sql, fb_count_params).fetchone()[0]
            rows = conn.execute(fb_query_sql, fb_query_params).fetchall()
            return rows, total_matches
        raise


def _fetch_tags_for_paths(
    conn: sqlite3.Connection,
    matched_paths: list[str],
) -> dict[str, list[str]]:
    """Fetch all associated tags for a list of note paths in batches."""
    tags_map: dict[str, list[str]] = {p: [] for p in matched_paths}
    batch_size = 500
    for i in range(0, len(matched_paths), batch_size):
        chunk = matched_paths[i : i + batch_size]
        placeholders = ", ".join("?" for _ in chunk)
        tag_cursor = conn.execute(
            f"SELECT path, tag FROM note_tags WHERE path IN ({placeholders}) ORDER BY tag ASC;",
            chunk,
        )
        for path, tag in tag_cursor.fetchall():
            tags_map[path].append(tag)
    return tags_map


def _extract_row_snippet(
    row: Any,
    search_filter: SearchFilter,
    regex_pat: Optional[str],
    description_val: Optional[str],
) -> Optional[str]:
    """Extract snippet representation from FTS snippet, description, or body."""
    if not search_filter.snippets or len(row) <= 13:
        return None

    fts_snip = row[13]
    desc_snip = row[14] if len(row) > 14 else None
    raw_b = row[15] if len(row) > 15 else None

    if regex_pat:
        return extract_regex_snippet(raw_b, regex_pat)
    if fts_snip and fts_snip.strip():
        return re.sub(r"\s+", " ", fts_snip.strip())
    if desc_snip and desc_snip.strip():
        return re.sub(r"\s+", " ", desc_snip.strip())
    if description_val and description_val.strip():
        return description_val.strip()
    return extract_leading_snippet(raw_b)


def _map_row_to_search_item(
    row: Any,
    tags: list[str],
    search_filter: SearchFilter,
    regex_pat: Optional[str],
) -> SearchMatchItem:
    """Map database row to SearchMatchItem model."""
    path = row[0]
    description_val = row[5]
    trust_tier_val = row[10] if len(row) > 10 and row[10] else "unverified"
    stale_after_val = row[11] if len(row) > 11 else None
    active_backlinks_val = int(row[12]) if len(row) > 12 and row[12] is not None else 0
    is_stale_val = evaluate_staleness(stale_after_val)
    snippet_val = _extract_row_snippet(row, search_filter, regex_pat, description_val)

    return SearchMatchItem(
        filename=Path(path).name,
        path=path,
        domain=row[1],
        status=row[2],
        type=row[3],
        title=row[4],
        description=description_val,
        created=row[6],
        updated=row[7],
        tags=tags,
        snippet=snippet_val,
        trust_tier=trust_tier_val,
        is_stale=is_stale_val,
        active_backlinks=active_backlinks_val,
    )


def query_notes(
    vault_root: Path,
    search_filter: SearchFilter,
    rebuild: bool = False,
) -> tuple[list[SearchMatchItem], int]:
    """Execute note search against the SQLite FTS5 acceleration cache.

    Returns:
        tuple of (items, total_matches) where items contains SearchMatchItem models
        with populated metadata, tags, and optional highlighted snippets.
    """
    db_path = get_cache_db_path(vault_root)

    # 1. Sync or rebuild cache
    if rebuild:
        rebuild_cache(vault_root, db_path=db_path)
    else:
        sync_cache(vault_root, db_path=db_path)

    conn = get_db_connection(db_path)
    try:
        rows, total_matches = _execute_search_query(conn, search_filter)
        matched_paths = [row[0] for row in rows]
        tags_map = _fetch_tags_for_paths(conn, matched_paths)

        regex_pat: Optional[str] = None
        if search_filter.query and is_regex_query(search_filter.query):
            pat = search_filter.query.strip()
            if pat.startswith("/") and pat.endswith("/") and len(pat) >= 2:
                pat = pat[1:-1]
            regex_pat = pat

        items = [
            _map_row_to_search_item(
                row, tags_map.get(row[0], []), search_filter, regex_pat
            )
            for row in rows
        ]
        return items, total_matches
    finally:
        conn.close()



