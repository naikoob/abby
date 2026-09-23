"""Link graph CLI command handlers: links, broken, orphans, refactor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abby.constants import DEFAULT_CACHE_DB
from abby.core.cache import get_db_connection, sync_cache
from abby.core.domain import resolve_domain_name
from abby.core.graph import (
    find_orphan_notes,
    find_unreferenced_notes,
    format_backlinks_text,
    format_broken_links_text,
    format_outbound_links_text,
    query_backlinks,
    query_outbound_links,
    refactor_note,
    scan_broken_links,
)
from abby.core.resolution import resolve_note_target
from abby.models.exceptions import (
    AbbyError,
    AmbiguousTargetError,
    DestinationCollisionError,
    LinkError,
    RefactorError,
)
from abby.utils.io import log_error, log_warn, output_payload


def execute_broken(
    vault_root: Path,
    conn: Any,
    args: Any,
    json_mode: bool,
) -> int:
    """Execute abby links --broken command."""
    check_headings = getattr(args, "headings", False)
    strict = getattr(args, "strict", False)
    domain_filter = getattr(args, "domain", None)

    broken_items, heading_map = scan_broken_links(
        conn, vault_root, check_headings=check_headings, domain_filter=domain_filter
    )

    if json_mode:
        payload = {
            "total_broken": len(broken_items),
            "broken_links": [item.to_dict() for item in broken_items],
        }
        output_payload(payload, json_mode=True)
    else:
        text = format_broken_links_text(broken_items, heading_map)
        if text:
            output_payload(text, json_mode=False)

    if strict and len(broken_items) > 0:
        return 1
    return 0


def execute_orphans(
    vault_root: Path,
    conn: Any,
    args: Any,
    json_mode: bool,
) -> int:
    """Execute abby links --orphans and/or --unreferenced command."""
    include_inbox = getattr(args, "include_inbox", False)
    domain_filter = getattr(args, "domain", None)
    is_orphans = getattr(args, "orphans", False)
    is_unreferenced = getattr(args, "unreferenced", False)

    orphans = (
        find_orphan_notes(
            conn, include_inbox=include_inbox, domain_filter=domain_filter
        )
        if is_orphans
        else []
    )
    unreferenced = (
        find_unreferenced_notes(
            conn, include_inbox=include_inbox, domain_filter=domain_filter
        )
        if is_unreferenced
        else []
    )

    if json_mode:
        payload: dict[str, Any] = {}
        if is_orphans:
            payload["total_orphans"] = len(orphans)
            payload["orphans"] = orphans
        if is_unreferenced:
            payload["total_unreferenced"] = len(unreferenced)
            payload["unreferenced"] = unreferenced
        output_payload(payload, json_mode=True)
    else:
        results: list[str] = []
        if is_orphans:
            results.extend(orphans)
        if is_unreferenced:
            for u in unreferenced:
                if u not in results:
                    results.append(u)
        if results:
            output_payload("\n".join(results), json_mode=False)

    return 0


def execute_refactor(
    vault_root: Path,
    conn: Any,
    extra_args: list[str],
    args: Any,
    json_mode: bool,
) -> int:
    """Execute abby links refactor <source> <target> command."""
    if len(extra_args) < 2:
        msg = "Usage: abby links refactor <old-title> <new-title> [options]"
        log_error(msg)
        if json_mode:
            output_payload({"success": False, "error": msg}, json_mode=True)
        return 2

    old_title = extra_args[0].strip()
    new_title = extra_args[1].strip()
    dry_run = getattr(args, "dry_run", False)
    links_only = getattr(args, "links_only", False)
    force = getattr(args, "force", False)

    try:
        result = refactor_note(
            vault_root,
            conn,
            old_title,
            new_title,
            dry_run=dry_run,
            links_only=links_only,
            force=force,
            cache_syncer=sync_cache,
        )
    except AmbiguousTargetError as err:
        log_error(err.message)
        if json_mode:
            output_payload(
                {
                    "success": False,
                    "error": err.message,
                    "candidate_paths": err.candidate_paths,
                },
                json_mode=True,
            )
        return err.exit_code
    except (DestinationCollisionError, RefactorError, AbbyError) as err:
        log_error(err.message)
        if json_mode:
            output_payload({"success": False, "error": err.message}, json_mode=True)
        return err.exit_code
    except Exception as err:
        log_error(f"Refactor failed: {err}")
        if json_mode:
            output_payload({"success": False, "error": str(err)}, json_mode=True)
        return 1

    new_stem = new_title[:-3] if new_title.lower().endswith(".md") else new_title

    if json_mode:
        output_payload(result.to_dict(), json_mode=True)
    else:
        if dry_run:
            lines = [
                f'[DRY-RUN] Planned refactor: "{old_title}" -> "{new_title}"',
                "File rename:",
            ]
            if result.file_renamed:
                source_label = result.source_file or old_title
                lines.append(
                    f'  {source_label} -> {result.file_renamed} (title: "{new_stem}")'
                )
            else:
                lines.append("  (skipped)")
            lines.append("Occurrences to rewrite:")
            if result.files_modified:
                for fmod in result.files_modified:
                    lines.append(
                        f"  {fmod.path}: {fmod.occurrences_replaced} occurrence(s) on line(s) {fmod.lines_modified}"
                    )
            else:
                lines.append("  (none)")
            lines.append(
                f"Total occurrences: {result.total_occurrences} across {len(result.files_modified)} files"
            )
            output_payload("\n".join(lines), json_mode=False)
        else:
            lines = [f'Refactored: "{old_title}" -> "{new_title}"']
            if result.file_renamed:
                lines.append(f"Renamed file: {result.file_renamed}")
            else:
                lines.append("File rename: skipped (--links-only)")
            lines.append(
                f"Updated {result.total_occurrences} link occurrences across {len(result.files_modified)} files"
            )
            output_payload("\n".join(lines), json_mode=False)

    return 0


def _resolve_links_target(
    conn: Any, note_arg: str, domain_arg: Optional[str]
) -> tuple[str, Optional[str]]:
    """Resolve note target for links inspection or raise appropriate LinkError/AmbiguousTargetError."""
    resolved_path, resolved_title, candidate_paths = resolve_note_target(
        conn, note_arg, domain_filter=domain_arg
    )
    if candidate_paths:
        msg = f"Note '{note_arg}' is ambiguous. Matching candidates: {', '.join(candidate_paths)}"
        raise AmbiguousTargetError(msg, candidate_paths)
    if not resolved_path:
        msg = f"Note '{note_arg}' not found in vault"
        raise LinkError(msg)
    return resolved_path, resolved_title


def _execute_note_links(
    conn: Any,
    resolved_path: str,
    resolved_title: Optional[str],
    domain_arg: Optional[str],
    args: Any,
    json_mode: bool,
) -> int:
    """Execute backlinks or outbound links query and output results."""
    depth_val = getattr(args, "depth", 1)
    try:
        depth = int(depth_val) if depth_val is not None else 1
    except (ValueError, TypeError):
        depth = 1

    if getattr(args, "backlinks", False):
        summary = query_backlinks(
            conn,
            resolved_path,
            resolved_title or Path(resolved_path).stem,
            domain_filter=domain_arg,
            depth=depth,
        )
        if json_mode:
            output_payload(summary.to_dict(), json_mode=True)
        else:
            text = format_backlinks_text(
                summary,
                details=getattr(args, "details", False),
                multihop=(depth > 1),
            )
            if text:
                output_payload(text, json_mode=False)
        return 0

    records = query_outbound_links(
        conn, resolved_path, domain_filter=domain_arg, depth=depth
    )
    if json_mode:
        payload = {
            "source_note": resolved_path,
            "total_outbound": len(records),
            "links": [r.to_dict() for r in records],
        }
        output_payload(payload, json_mode=True)
    else:
        text = format_outbound_links_text(
            records,
            details=getattr(args, "details", False),
            multihop=(depth > 1),
        )
        if text:
            output_payload(text, json_mode=False)
    return 0


def execute_links(vault_root: Path, args: Any) -> int:
    """Entry point for abby links CLI commands."""
    json_mode = getattr(args, "json", False)

    # 1. Synchronize SQLite cache with vault state
    try:
        sync_cache(vault_root)
    except Exception as err:
        log_warn(f"Cache sync warning: {err}")

    db_path = vault_root / DEFAULT_CACHE_DB
    conn = get_db_connection(db_path)

    try:
        # Validate domain if provided
        domain_arg = getattr(args, "domain", None)
        if domain_arg:
            try:
                resolve_domain_name(domain_arg)
            except ValueError as err:
                log_error(str(err))
                if json_mode:
                    output_payload(
                        {"success": False, "error": str(err)}, json_mode=True
                    )
                return 2

        # Check subcommands / modes
        note_arg = getattr(args, "note", None)
        extra_args = getattr(args, "extra", [])

        if note_arg == "refactor":
            return execute_refactor(vault_root, conn, extra_args, args, json_mode)

        if getattr(args, "broken", False):
            return execute_broken(vault_root, conn, args, json_mode)

        if getattr(args, "orphans", False) or getattr(args, "unreferenced", False):
            return execute_orphans(vault_root, conn, args, json_mode)

        if not note_arg:
            log_error(
                "Note path or title is required. Usage: abby links <note> [options]"
            )
            if json_mode:
                output_payload(
                    {"success": False, "error": "Missing required note argument"},
                    json_mode=True,
                )
            return 2

        resolved_path, resolved_title = _resolve_links_target(
            conn, note_arg, domain_arg
        )
        return _execute_note_links(
            conn, resolved_path, resolved_title, domain_arg, args, json_mode
        )

    finally:
        conn.close()

