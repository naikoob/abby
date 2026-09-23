"""MCP handlers for note lifecycle, triage, and read operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from abby.core.cache import get_cache_db_path, get_db_connection, sync_cache
from abby.core.intake import capture_note
from abby.core.lifecycle import (
    archive_note,
    list_domain_notes,
    move_note,
    resolve_source_note,
)
from abby.core.resolution import resolve_note_target
from abby.core.verify import verify_note
from abby.mcp.types import MCPToolCallResult, NoteContentPayload
from abby.services.okf_parser import parse_okf_frontmatter, tokenize_frontmatter


def handle_note_capture(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for note_capture tool."""
    title = args.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        return MCPToolCallResult.error("Missing required argument 'title'.")

    body = args.get("body")
    description = args.get("description")
    tags = args.get("tags")
    generated = args.get("generated")
    verified = args.get("verified")
    sources = args.get("sources")

    desc_str = str(description) if description is not None else None
    note = capture_note(
        vault_root,
        title.strip(),
        body=body,
        description=desc_str,
        tags=tags if isinstance(tags, list) else None,
        generated=generated if isinstance(generated, dict) else None,
        verified=verified if isinstance(verified, list) else None,
        sources=sources if isinstance(sources, list) else None,
    )

    summary_lines = [f"Captured note: {note.relative_path}", f"Title: {note.title}"]
    if note.frontmatter.description:
        summary_lines.append(f"Description: {note.frontmatter.description}")
    summary_lines.extend(
        [
            f"Type: {note.frontmatter.type}",
            f"Status: {note.frontmatter.status}",
            f"Tags: {', '.join(note.frontmatter.tags)}",
        ]
    )
    return MCPToolCallResult.success("\n".join(summary_lines))


def handle_domain_list(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for domain_list tool."""
    domain = args.get("domain", "inbox")
    try:
        canonical_domain, items = list_domain_notes(vault_root, domain)
    except Exception as exc:
        return MCPToolCallResult.error(str(exc))

    if not items:
        return MCPToolCallResult.success(f"Domain '{domain}' queue is empty (0 notes).")

    lines = [f"Domain '{domain}' contains {len(items)} note(s):"]
    for item in items:
        lines.append(f"  - {item.title} ({item.path})")

    return MCPToolCallResult.success("\n".join(lines))


def handle_note_move(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for note_move tool."""
    note = args.get("note")
    target = args.get("target")
    dry_run = bool(args.get("dry_run", False))
    if not note or not isinstance(note, str):
        return MCPToolCallResult.error("Missing required argument 'note'.")
    if not target or not isinstance(target, str):
        return MCPToolCallResult.error("Missing required argument 'target'.")

    description = args.get("description")
    res = move_note(
        vault_root,
        note,
        target,
        dry_run=dry_run,
        description=str(description) if description is not None else None,
    )

    prefix = "[DRY-RUN] " if dry_run else ""
    action_verb = "Planned move" if dry_run else "Moved note successfully"
    lines = [
        f"{prefix}{action_verb}.",
        f"Title: {res.title}",
        f"Source: {res.source_path}",
        f"Destination: {res.target_path}",
        f"Previous Status: {res.previous_status}",
        f"New Status: {res.new_status}",
    ]
    if res.description:
        lines.append(f"Description: {res.description}")
    return MCPToolCallResult.success("\n".join(lines))


def handle_note_archive(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for note_archive tool."""
    note = args.get("note")
    dry_run = bool(args.get("dry_run", False))
    if not note or not isinstance(note, str):
        return MCPToolCallResult.error("Missing required argument 'note'.")

    res = archive_note(vault_root, note, dry_run=dry_run)

    prefix = "[DRY-RUN] " if dry_run else ""
    action_verb = "Planned archive" if dry_run else "Archived note successfully"
    summary = (
        f"{prefix}{action_verb}.\n"
        f"Title: {res.title}\n"
        f"Source: {res.source_path}\n"
        f"Destination: {res.target_path}\n"
        f"Status: archived"
    )
    return MCPToolCallResult.success(summary)


def handle_note_verify(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for note_verify tool."""
    note_path = args.get("note") or args.get("note_path")
    if not note_path or not isinstance(note_path, str):
        return MCPToolCallResult.error("Missing required argument 'note' or 'note_path'.")
    actor = args.get("actor")
    dry_run = bool(args.get("dry_run", False))
    res = verify_note(vault_root, note_path, actor=actor, dry_run=dry_run)
    return MCPToolCallResult.success(json.dumps(res.to_dict(), indent=2))


def handle_note_read(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for note_read tool."""
    note = args.get("note")
    if not note or not isinstance(note, str) or not note.strip():
        return MCPToolCallResult.error("Missing required argument 'note'.")

    cleaned = note.strip()
    db_path = get_cache_db_path(vault_root)
    try:
        sync_cache(vault_root, db_path=db_path)
    except Exception as exc:
        return MCPToolCallResult.error(f"Failed to sync cache: {exc}")

    conn = get_db_connection(db_path)
    try:
        resolved_path, resolved_title, candidate_paths = resolve_note_target(
            conn, cleaned
        )
        if candidate_paths:
            cand_lines = "\n".join(f"  - {c}" for c in sorted(candidate_paths))
            return MCPToolCallResult.error(
                f"Note '{cleaned}' is ambiguous. Candidates:\n{cand_lines}\nPlease qualify with a domain prefix."
            )

        if not resolved_path:
            try:
                found = resolve_source_note(vault_root, cleaned, conn=conn)
                resolved_path = str(found.relative_to(vault_root)).replace("\\", "/")
                resolved_title = found.stem
            except Exception:
                return MCPToolCallResult.error(f"Note '{cleaned}' not found in vault.")

        full_path = vault_root / resolved_path
        if not full_path.is_file():
            return MCPToolCallResult.error(f"Note '{cleaned}' not found in vault.")

        raw_content = full_path.read_text(encoding="utf-8")
        parsed = tokenize_frontmatter(raw_content)
        fm_dict = parse_okf_frontmatter(
            raw_content, default_title=resolved_title or full_path.stem
        )
        title = fm_dict.get("title") or resolved_title or full_path.stem

        payload = NoteContentPayload(
            path=resolved_path,
            title=title,
            frontmatter=fm_dict,
            body=parsed.body_content,
            content=raw_content,
        )
        return MCPToolCallResult.success(json.dumps(payload.to_dict(), indent=2))
    finally:
        conn.close()

