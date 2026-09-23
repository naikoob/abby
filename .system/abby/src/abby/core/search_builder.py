"""Query builder, sanitization, and snippet extraction for SQLite FTS5 search engine."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Final, Optional

from abby.core.domain import canonicalize_domain
from abby.models.exceptions import SearchArgumentError, SearchDomainError
from abby.models.search import SearchFilter

FTS_OPERATORS: Final[tuple[str, ...]] = ("AND", "OR", "NOT", "NEAR")
FTS_SPECIAL_CHARS: Final[str] = r'()":*^+-:'
REGEX_METACHARS: Final[tuple[str, ...]] = (
    r"\d",
    r"\D",
    r"\w",
    r"\W",
    r"\s",
    r"\S",
    ".*",
    ".+",
    "^",
    "$",
    "(?",
    "[",
    "]",
    "{",
    "}",
    "|",
)


def resolve_search_domain(domain_str: Optional[str]) -> Optional[str]:
    """Resolve a domain alias or name to canonical folder name (e.g. 'projects' -> '01 - Projects')."""
    if not domain_str or not domain_str.strip():
        return None
    canonical = canonicalize_domain(domain_str)
    if canonical:
        return canonical
    raise SearchDomainError(
        f"Unrecognized domain: '{domain_str}'. Valid domains: inbox, projects, areas, resources, archives."
    )


def validate_iso_date(date_str: Optional[str], field_name: str) -> Optional[str]:
    """Validate ISO calendar date format YYYY-MM-DD."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
        raise SearchArgumentError(
            f"Invalid date format for {field_name}: '{date_str}'. Expected YYYY-MM-DD."
        )
    try:
        datetime.strptime(cleaned, "%Y-%m-%d")
    except ValueError as err:
        raise SearchArgumentError(
            f"Invalid calendar date for {field_name}: '{date_str}' ({err})."
        )
    return cleaned


def is_regex_query(query: str) -> bool:
    """Determine whether the search query should be evaluated as a regular expression."""
    stripped = query.strip()
    if stripped.startswith("/") and stripped.endswith("/") and len(stripped) >= 2:
        return True
    return any(meta in stripped for meta in REGEX_METACHARS)


def sanitize_fts_query(query: str) -> str:
    """Sanitize and format query for SQLite FTS5 matching."""
    stripped = query.strip()
    if not stripped:
        return ""
    # If user provided an entire quoted phrase, preserve it with escaped internal quotes
    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        inner = stripped[1:-1].replace('"', '""')
        return f'"{inner}"'

    tokens = re.findall(r'"[^"]*"|\S+', stripped)
    sanitized_tokens: list[str] = []
    for token in tokens:
        token_upper = token.upper()
        if token.startswith('"') and token.endswith('"') and len(token) >= 2:
            inner = token[1:-1].replace('"', '""')
            sanitized_tokens.append(f'"{inner}"')
        elif (
            token.endswith("*")
            and len(token) > 1
            and not any(c in token[:-1] for c in FTS_SPECIAL_CHARS)
        ):
            # Valid prefix token like arch*
            sanitized_tokens.append(token)
        elif token_upper in FTS_OPERATORS or any(c in token for c in FTS_SPECIAL_CHARS):
            # Escape inner double quotes and quote token
            escaped = token.replace('"', '""')
            sanitized_tokens.append(f'"{escaped}"')
        else:
            sanitized_tokens.append(token)
    return " ".join(sanitized_tokens)


def extract_leading_snippet(body: Optional[str], max_chars: int = 120) -> Optional[str]:
    """Extract clean leading text from note body when no term match is present."""
    if not body:
        return None
    cleaned = re.sub(r"\s+", " ", body.strip())
    if not cleaned:
        return None
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[:max_chars]}..."


def extract_regex_snippet(
    body: Optional[str],
    pattern: str,
    max_chars: int = 120,
) -> Optional[str]:
    """Extract a windowed snippet around a regular expression match with bold markers."""
    if not body:
        return None
    cleaned = re.sub(r"\s+", " ", body.strip())
    if not cleaned:
        return None
    try:
        match = re.search(pattern, cleaned, re.IGNORECASE)
    except re.error:
        match = None
    if not match:
        return extract_leading_snippet(cleaned, max_chars)

    start_idx, end_idx = match.span()
    half = max_chars // 2
    window_start = max(0, start_idx - half)
    window_end = min(len(cleaned), end_idx + half)

    before = cleaned[window_start:start_idx]
    matched_text = cleaned[start_idx:end_idx]
    after = cleaned[end_idx:window_end]

    prefix = "..." if window_start > 0 else ""
    suffix = "..." if window_end < len(cleaned) else ""
    return f"{prefix}{before}**{matched_text}**{after}{suffix}".strip()


def _build_match_conditions(
    query_text: str, scope: str
) -> tuple[list[str], list[Any], list[str], bool]:
    """Compile search query matching clauses, parameters, and required joins."""
    where_clauses: list[str] = []
    params: list[Any] = []
    joins: list[str] = []
    use_regex = False

    if is_regex_query(query_text):
        use_regex = True
        regex_pat = query_text
        if regex_pat.startswith("/") and regex_pat.endswith("/") and len(regex_pat) >= 2:
            regex_pat = regex_pat[1:-1]
        try:
            re.compile(regex_pat)
        except re.error as err:
            raise SearchArgumentError(
                f"Malformed regular expression '{query_text}': {err}"
            )

        if scope == "title":
            where_clauses.append("REGEXP(?, notes.title)")
            params.append(regex_pat)
        elif scope == "content":
            joins.append("JOIN notes_fts ON notes.path = notes_fts.path")
            where_clauses.append("REGEXP(?, notes_fts.body)")
            params.append(regex_pat)
        else:
            joins.append("JOIN notes_fts ON notes.path = notes_fts.path")
            where_clauses.append(
                "(REGEXP(?, notes.title) OR REGEXP(?, notes_fts.body))"
            )
            params.extend([regex_pat, regex_pat])
    else:
        joins.append("JOIN notes_fts ON notes.path = notes_fts.path")
        fts_query = sanitize_fts_query(query_text)
        if scope == "title":
            fts_expr = f"title: ({fts_query})"
        elif scope == "content":
            fts_expr = f"body: ({fts_query})"
        else:
            fts_expr = fts_query

        where_clauses.append("notes_fts MATCH ?")
        params.append(fts_expr)

    return where_clauses, params, joins, use_regex


def _build_faceted_filters(
    search_filter: SearchFilter,
) -> tuple[list[str], list[Any]]:
    """Assemble domain, status, type, date, tag, trust, and staleness SQL filter clauses."""
    where_clauses: list[str] = []
    params: list[Any] = []

    resolved_domain = resolve_search_domain(search_filter.domain)
    created_after = validate_iso_date(search_filter.created_after, "--created-after")
    created_before = validate_iso_date(search_filter.created_before, "--created-before")
    updated_after = validate_iso_date(search_filter.updated_after, "--updated-after")
    updated_before = validate_iso_date(search_filter.updated_before, "--updated-before")

    if resolved_domain:
        where_clauses.append("notes.domain = ?")
        params.append(resolved_domain)

    if search_filter.status:
        where_clauses.append("LOWER(notes.status) = LOWER(?)")
        params.append(search_filter.status.strip())

    if search_filter.type:
        where_clauses.append("LOWER(notes.type) = LOWER(?)")
        params.append(search_filter.type.strip())

    if created_after:
        where_clauses.append("SUBSTR(notes.created, 1, 10) >= ?")
        params.append(created_after)
    if created_before:
        where_clauses.append("SUBSTR(notes.created, 1, 10) <= ?")
        params.append(created_before)
    if updated_after:
        where_clauses.append("SUBSTR(COALESCE(notes.updated, notes.created), 1, 10) >= ?")
        params.append(updated_after)
    if updated_before:
        where_clauses.append("SUBSTR(COALESCE(notes.updated, notes.created), 1, 10) <= ?")
        params.append(updated_before)

    clean_tags = list(dict.fromkeys(t.strip().lower() for t in search_filter.tags if t.strip()))
    if clean_tags:
        placeholders = ", ".join("?" for _ in clean_tags)
        if search_filter.tag_conjunction.upper() == "OR":
            where_clauses.append(
                f"notes.path IN (SELECT path FROM note_tags WHERE LOWER(tag) IN ({placeholders}))"
            )
            params.extend(clean_tags)
        else:
            where_clauses.append(
                f"notes.path IN (SELECT path FROM note_tags WHERE LOWER(tag) IN ({placeholders}) "
                f"GROUP BY path HAVING COUNT(DISTINCT LOWER(tag)) = {len(clean_tags)})"
            )
            params.extend(clean_tags)

    if search_filter.trust:
        valid_tiers = ("unverified", "machine-confirmed", "human-reviewed")
        clean_trust = search_filter.trust.strip().lower()
        if clean_trust not in valid_tiers:
            raise SearchArgumentError(
                f"Invalid trust tier: '{search_filter.trust}'. Must be one of: {', '.join(valid_tiers)}."
            )
        where_clauses.append("LOWER(notes.trust_tier) = ?")
        params.append(clean_trust)

    if search_filter.fresh_only:
        where_clauses.append("IS_STALE(notes.stale_after) = 0")
    elif search_filter.stale_only:
        where_clauses.append("IS_STALE(notes.stale_after) = 1")

    return where_clauses, params


def _build_projection_and_order(
    search_filter: SearchFilter,
    has_query: bool,
    use_regex: bool,
) -> tuple[str, str, str]:
    """Generate select columns, ORDER BY, and LIMIT SQL fragments."""
    select_fields = (
        "notes.path, notes.domain, notes.status, notes.type, notes.title, "
        "notes.description, notes.created, notes.updated, notes.file_mtime, notes.file_size, "
        "notes.trust_tier, notes.stale_after, notes.active_backlinks"
    )
    if search_filter.snippets:
        if has_query and not use_regex:
            select_fields += (
                ", snippet(notes_fts, 3, '**', '**', '...', 20) AS fts_snippet, "
                "snippet(notes_fts, 2, '**', '**', '...', 20) AS desc_snippet, "
                "notes_fts.body AS raw_body"
            )
        else:
            select_fields += ", NULL AS fts_snippet, NULL AS desc_snippet, notes_fts.body AS raw_body"

    if has_query and not use_regex:
        order_by = (
            "ORDER BY (bm25(notes_fts, 0.0, 10.0, 7.0, 1.0, 5.0) * "
            "COGNITIVE_RANK_MULTIPLIER(notes.domain, notes.trust_tier, notes.stale_after, notes.active_backlinks)) ASC, "
            "COALESCE(notes.updated, notes.created) DESC, notes.file_mtime DESC, notes.path ASC"
        )
    else:
        order_by = "ORDER BY COALESCE(notes.updated, notes.created) DESC, notes.file_mtime DESC, notes.path ASC"

    limit_sql = f" LIMIT {int(search_filter.limit)}" if search_filter.limit is not None else ""
    return select_fields, order_by, limit_sql


def build_search_sql(
    search_filter: SearchFilter,
    count_only: bool = False,
) -> tuple[str, list[Any]]:
    """Construct SQL query and bound parameters based on SearchFilter criteria."""
    if search_filter.limit is not None and search_filter.limit <= 0:
        raise SearchArgumentError(
            f"Limit must be a positive integer, got: {search_filter.limit}"
        )

    where_clauses: list[str] = []
    params: list[Any] = []
    joins: list[str] = []
    has_query = bool(search_filter.query and search_filter.query.strip())
    use_regex = False

    if has_query:
        query_text = search_filter.query.strip()
        match_where, match_params, match_joins, use_regex = _build_match_conditions(
            query_text, search_filter.scope
        )
        where_clauses.extend(match_where)
        params.extend(match_params)
        joins.extend(match_joins)

    facet_where, facet_params = _build_faceted_filters(search_filter)
    where_clauses.extend(facet_where)
    params.extend(facet_params)

    if search_filter.snippets and not count_only:
        if not any("notes_fts" in j for j in joins):
            joins.append("LEFT JOIN notes_fts ON notes.path = notes_fts.path")

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    join_sql = (" " + " ".join(joins)) if joins else ""

    if count_only:
        return f"SELECT COUNT(*) FROM notes{join_sql}{where_sql};", params

    select_fields, order_by, limit_sql = _build_projection_and_order(
        search_filter, has_query, use_regex
    )
    sql = f"SELECT {select_fields} FROM notes{join_sql}{where_sql} {order_by}{limit_sql};"
    return sql, params

