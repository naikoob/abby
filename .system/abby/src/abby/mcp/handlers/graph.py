"""MCP handlers for link graph inspection and note refactoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abby.core.cache import get_cache_db_path, get_db_connection, sync_cache
from abby.core.lifecycle import resolve_source_note
from abby.core.graph import (
    find_orphan_notes,
    find_unreferenced_notes,
    format_backlinks_text,
    format_broken_links_text,
    format_outbound_links_text,
    query_backlinks,
    query_outbound_links,
    refactor_note,
    resolve_cached_links,
    scan_broken_links,
)
from abby.mcp.types import MCPToolCallResult
from abby.models.exceptions import AbbyError, AmbiguousTargetError


def handle_vault_links(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for vault_links tool."""
    mode = args.get("mode", "outbound")
    note = args.get("note")
    domain = args.get("domain")
    headings = bool(args.get("headings", False))
    try:
        depth = int(args.get("depth", 1)) if args.get("depth") is not None else 1
    except (ValueError, TypeError):
        depth = 1

    db_path = get_cache_db_path(vault_root)
    try:
        sync_cache(vault_root, db_path=db_path)
    except Exception as exc:
        return MCPToolCallResult.error(
            f"Failed to sync cache for link inspection: {exc}"
        )

    conn = get_db_connection(db_path)
    try:
        resolve_cached_links(conn, vault_root)

        if mode == "outbound":
            if not note:
                return MCPToolCallResult.error(
                    "Mode 'outbound' requires 'note' argument."
                )
            note_path = resolve_source_note(vault_root, note)
            rel_path = str(note_path.relative_to(vault_root))
            records = query_outbound_links(
                conn, rel_path, domain_filter=domain, depth=depth
            )
            return MCPToolCallResult.success(
                format_outbound_links_text(records, multihop=(depth > 1))
            )

        elif mode == "backlinks":
            if not note:
                return MCPToolCallResult.error(
                    "Mode 'backlinks' requires 'note' argument."
                )
            note_path = resolve_source_note(vault_root, note)
            rel_path = str(note_path.relative_to(vault_root))
            b_summary = query_backlinks(
                conn, rel_path, note_path.stem, domain_filter=domain, depth=depth
            )
            return MCPToolCallResult.success(
                format_backlinks_text(b_summary, details=True, multihop=(depth > 1))
            )

        elif mode == "broken":
            broken_items, heading_map = scan_broken_links(
                conn, vault_root, check_headings=headings, domain_filter=domain
            )
            text = format_broken_links_text(broken_items, heading_map)
            if not text:
                return MCPToolCallResult.success("No broken links found across vault.")
            return MCPToolCallResult.success(text)

        elif mode in ("orphans", "unreferenced"):
            is_orphan = mode == "orphans"
            finder = find_orphan_notes if is_orphan else find_unreferenced_notes
            items = finder(conn, include_inbox=False, domain_filter=domain)
            label = "orphan" if is_orphan else "unreferenced"
            reason = (
                "all notes have links"
                if is_orphan
                else "all notes have inbound backlinks"
            )
            if not items:
                return MCPToolCallResult.success(f"No {label} notes found ({reason}).")
            return MCPToolCallResult.success(
                "\n".join(
                    [f"Found {len(items)} {label} note(s):"]
                    + [f"  - {i}" for i in items]
                )
            )

        else:
            return MCPToolCallResult.error(
                f"Invalid mode '{mode}'. Expected one of: outbound, backlinks, broken, orphans, unreferenced."
            )

    except Exception as exc:
        return MCPToolCallResult.error(str(exc))
    finally:
        conn.close()


def handle_note_refactor(
    args: dict[str, Any], vault_root: Path
) -> MCPToolCallResult:
    """Handler for note_refactor tool."""
    source = args.get("source")
    target = args.get("target")
    if not source or not isinstance(source, str) or not source.strip():
        return MCPToolCallResult.error("Missing required argument 'source'.")
    if not target or not isinstance(target, str) or not target.strip():
        return MCPToolCallResult.error("Missing required argument 'target'.")

    links_only = bool(args.get("links_only", False))
    dry_run = bool(args.get("dry_run", False))

    db_path = get_cache_db_path(vault_root)
    try:
        sync_cache(vault_root, db_path=db_path)
    except Exception as exc:
        return MCPToolCallResult.error(f"Failed to sync cache for refactoring: {exc}")

    conn = get_db_connection(db_path)
    try:
        res = refactor_note(
            vault_root,
            conn,
            source.strip(),
            target.strip(),
            dry_run=dry_run,
            links_only=links_only,
            cache_syncer=sync_cache,
        )
        prefix = "[DRY-RUN] " if res.is_dry_run else ""
        source_disp = res.source_file or res.old_title
        target_disp = res.file_renamed or res.new_title
        lines = [
            f"{prefix}Refactor Complete:",
            f"  Source: {source_disp}",
            f"  Target: {target_disp}",
            f"  Rewritten Links: {res.total_occurrences} occurrences across {len(res.files_modified)} notes",
        ]
        if res.files_modified:
            lines.append("Affected Files:")
            for fm in res.files_modified:
                lines.append(f"  - {fm.path}")
        return MCPToolCallResult.success("\n".join(lines))
    except AmbiguousTargetError as exc:
        return MCPToolCallResult.error(exc.message)
    except AbbyError as exc:
        return MCPToolCallResult.error(exc.message)
    except Exception as exc:
        return MCPToolCallResult.error(f"Refactor failed: {exc}")
    finally:
        conn.close()

