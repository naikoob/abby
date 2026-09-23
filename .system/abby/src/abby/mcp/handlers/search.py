"""MCP handler for vault_search tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from abby.core.search import query_notes
from abby.mcp.types import MCPToolCallResult
from abby.models.exceptions import AbbyError
from abby.models.search import SearchFilter


def handle_vault_search(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for vault_search tool."""
    query = args.get("query")
    domain = args.get("domain")
    status = args.get("status")
    type_ = args.get("type")
    tags = args.get("tags") or []
    limit_arg = args.get("limit", 20)
    snippets = bool(args.get("snippets", False))
    trust_tier = args.get("trust_tier")
    fresh_only = bool(args.get("fresh_only", False))
    try:
        limit = min(max(1, int(limit_arg)), 100)
    except (ValueError, TypeError):
        limit = 20

    search_filter = SearchFilter(
        query=query,
        domain=domain,
        status=status,
        type=type_,
        tags=tags if isinstance(tags, list) else [],
        limit=limit,
        snippets=snippets,
        trust=trust_tier,
        fresh_only=fresh_only,
    )

    try:
        items, _ = query_notes(vault_root, search_filter)
    except AbbyError as exc:
        return MCPToolCallResult.error(exc.message)
    except Exception as exc:
        return MCPToolCallResult.error(f"Search query error: {exc}")

    if not items:
        return MCPToolCallResult.success("No matching notes found.")

    if args.get("json", False):
        payload = {
            "query": query,
            "count": len(items),
            "matches": [item.to_dict() for item in items],
        }
        return MCPToolCallResult.success(json.dumps(payload, indent=2))

    lines = [f"Found {len(items)} matching note(s):"]
    for item in items:
        badge = f"[{item.trust_tier}]"
        if item.is_stale:
            badge += " [stale]"
        badge += f" [{item.active_backlinks} links]"
        lines.append(f"  - [{item.domain}] {item.title} -> {item.path} {badge}")
        if snippets:
            if item.description:
                lines.append(f"    Summary: {item.description}")
            if item.snippet:
                lines.append(f'    "{item.snippet}"')

    return MCPToolCallResult.success("\n".join(lines))

