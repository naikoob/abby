"""Search CLI command handler: execute_find."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from abby.core.search import query_notes
from abby.models.exceptions import SearchArgumentError, SearchDomainError
from abby.models.search import SearchFilter, SearchResultPayload
from abby.utils.io import log_error, output_payload


def execute_find(
    vault_root: Path,
    search_filter: SearchFilter,
    rebuild: bool = False,
) -> int:
    """Main search presenter executing discovery and formatting stdout/stderr according to stream contracts."""
    try:
        items, total_matches = query_notes(
            vault_root, search_filter=search_filter, rebuild=rebuild
        )
    except SearchDomainError as err:
        log_error(str(err))
        return 1
    except SearchArgumentError as err:
        log_error(str(err))
        return 2
    except sqlite3.OperationalError as err:
        log_error(f"Database query error: {err}")
        return 1
    except Exception as err:
        log_error(f"Failed to synchronize cache: {err}")
        return 1

    if search_filter.json_mode:
        payload = SearchResultPayload(
            query=search_filter.query,
            domain=search_filter.domain,
            status=search_filter.status,
            tags=search_filter.tags,
            count=len(items),
            total_matches=total_matches,
            notes=items,
        )
        output_payload(payload.to_dict(), json_mode=True)
    else:
        for item in items:
            if search_filter.snippets:
                badge = f"[{item.trust_tier}]"
                parts = [item.domain, item.status, item.trust_tier]
                if item.is_stale:
                    badge += " [stale]"
                    parts.append("stale")
                parts.append(f"{item.active_backlinks} links")
                badge = f"[{' | '.join(parts)}]"
                output_payload(f"{item.path} {badge}", json_mode=False)
                if item.description:
                    output_payload(
                        f"  Description: {item.description}", json_mode=False
                    )
                if item.snippet:
                    if item.description:
                        output_payload(f"  Snippet: {item.snippet}", json_mode=False)
                    else:
                        output_payload(f"  {item.snippet}", json_mode=False)
            else:
                output_payload(item.path, json_mode=False)

    return 0

