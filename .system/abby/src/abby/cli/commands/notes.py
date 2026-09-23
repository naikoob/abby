"""Note lifecycle CLI command handlers: new, list, move, archive, verify."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from abby.constants import DOMAIN_DEFAULT_TYPE
from abby.core.intake import capture_note
from abby.core.lifecycle import (
    archive_note,
    list_domain_notes,
    move_note,
    resolve_destination_dir,
)
from abby.core.verify import derive_default_actor, validate_actor_syntax, verify_note
from abby.models.exceptions import LifecycleError
from abby.utils.io import log_error, log_warn, output_payload
from abby.utils.time import now_iso


def execute_new(
    vault_root: Path,
    title: str,
    body: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    json_mode: bool = False,
    generated_by: Optional[str] = None,
    generated: Optional[dict[str, str]] = None,
    verified: Optional[list[dict[str, str]]] = None,
    sources: Optional[list[dict[str, Any]]] = None,
) -> int:
    """Execute 'abby new' command, supporting body arguments, stdin piping, and clean stdout."""
    # Check if standard input was piped into the command
    piped_body: Optional[str] = None
    if not sys.stdin.isatty():
        try:
            piped_body = sys.stdin.read()
        except Exception as err:
            log_warn(f"Failed to read from stdin: {err}")

    # Determine body precedence
    final_body: Optional[str] = None
    if body and piped_body:
        log_warn("Both --body and piped stdin supplied; --body takes precedence.")
        final_body = body
    elif body:
        final_body = body
    elif piped_body:
        final_body = piped_body

    effective_generated = generated
    if generated_by and not effective_generated:
        effective_generated = {"by": generated_by.strip(), "at": now_iso()}

    try:
        note = capture_note(
            vault_root,
            title=title,
            body=final_body,
            description=description,
            tags=tags,
            generated=effective_generated,
            verified=verified,
            sources=sources,
        )
    except Exception as err:
        log_error(f"Failed to create note: {err}")
        if json_mode:
            output_payload({"success": False, "error": str(err)}, json_mode=True)
        return 1

    if json_mode:
        payload = {
            "success": True,
            "path": note.relative_path,
            "title": note.title,
            "filename": note.filename,
            "description": note.frontmatter.description,
            "created": note.frontmatter.created,
        }
        output_payload(payload, json_mode=True)
    else:
        output_payload(note.relative_path, json_mode=False)

    return 0


def execute_list(
    vault_root: Path,
    domain: Optional[str] = "inbox",
    json_mode: bool = False,
) -> int:
    """Execute 'abby list [domain]' command."""
    target_domain = domain or "inbox"
    try:
        canonical_domain, items = list_domain_notes(vault_root, target_domain)
    except ValueError as err:
        log_error(str(err))
        if json_mode:
            output_payload({"success": False, "error": str(err)}, json_mode=True)
        return 1

    if json_mode:
        payload = {
            "domain": target_domain,
            "count": len(items),
            "notes": [item.to_dict() for item in items],
        }
        output_payload(payload, json_mode=True)
    else:
        if items:
            lines = [item.path for item in items]
            output_payload("\n".join(lines), json_mode=False)

    return 0


def execute_move(
    vault_root: Path,
    note_arg: str,
    target_spec: str,
    json_mode: bool = False,
    dry_run: bool = False,
    description: Optional[str] = None,
) -> int:
    """Execute 'abby move <note> <target>' command."""
    try:
        result = move_note(
            vault_root, note_arg, target_spec, dry_run=dry_run, description=description
        )
    except (LifecycleError, FileNotFoundError, ValueError, RuntimeError) as err:
        log_error(str(err))
        if json_mode:
            output_payload({"success": False, "error": str(err)}, json_mode=True)
        return 1

    if json_mode:
        output_payload(result.to_dict(), json_mode=True)
    else:
        if dry_run:
            try:
                _, canonical_domain = resolve_destination_dir(vault_root, target_spec)
                new_type = DOMAIN_DEFAULT_TYPE.get(canonical_domain, "note")
            except (LifecycleError, ValueError):
                new_type = "note"
            output_payload(
                f"[DRY-RUN] Planned move: '{result.source_path}' -> '{result.target_path}' "
                f"(status: {result.new_status}, type: {new_type})",
                json_mode=False,
            )
        else:
            output_payload(result.target_path, json_mode=False)

    return 0


def execute_archive(
    vault_root: Path,
    note_arg: str,
    json_mode: bool = False,
    dry_run: bool = False,
) -> int:
    """Execute 'abby archive <note>' command."""
    try:
        result = archive_note(vault_root, note_arg, dry_run=dry_run)
    except (LifecycleError, FileNotFoundError, ValueError, RuntimeError) as err:
        log_error(str(err))
        if json_mode:
            output_payload({"success": False, "error": str(err)}, json_mode=True)
        return 1

    if json_mode:
        output_payload(result.to_dict(), json_mode=True)
    else:
        if dry_run:
            output_payload(
                f"[DRY-RUN] Planned archive: '{result.source_path}' -> '{result.target_path}' (status: archived)",
                json_mode=False,
            )
        else:
            output_payload(result.target_path, json_mode=False)

    return 0


def execute_verify(
    vault_root: Path,
    note_arg: Optional[str],
    actor: Optional[str] = None,
    dry_run: bool = False,
    json_mode: bool = False,
) -> int:
    """Command handler for 'abby verify <note> [--by <actor>] [--dry-run] [--json]'."""
    if not note_arg or not note_arg.strip():
        log_error(
            "Target note path is required. Usage: abby verify <note-path> [--by <actor>] [--dry-run] [--json]"
        )
        if json_mode:
            output_payload(
                {"success": False, "error": "Target note path is required"},
                json_mode=True,
            )
        return 2

    if actor is not None and not validate_actor_syntax(actor.strip()):
        log_error(
            f"Invalid actor identifier '{actor}'. Must conform to OKF v0.2 actor syntax."
        )
        if json_mode:
            output_payload(
                {"success": False, "error": f"Invalid actor identifier '{actor}'"},
                json_mode=True,
            )
        return 2

    try:
        result = verify_note(
            vault_root=vault_root,
            note_arg=note_arg,
            actor=actor,
            dry_run=dry_run,
        )
    except FileNotFoundError as err:
        log_error(str(err))
        if json_mode:
            output_payload({"success": False, "error": str(err)}, json_mode=True)
        return 1
    except (ValueError, RuntimeError) as err:
        log_error(str(err))
        if json_mode:
            output_payload({"success": False, "error": str(err)}, json_mode=True)
        return 1

    if json_mode:
        output_payload(result.to_dict(), json_mode=True)
    else:
        if dry_run:
            msg = (
                f"[DRY RUN] Verification preview for: {result.path}\n"
                f"  Actor:          {result.actor}\n"
                f"  Timestamp:      {result.timestamp}\n"
                f"  Old Trust Tier: {result.old_trust_tier}\n"
                f"  New Trust Tier: {result.trust_tier}\n"
                f"Zero files modified."
            )
            output_payload(msg, json_mode=False)
        else:
            msg = (
                f"Verified: {result.path}\n"
                f"  Actor:      {result.actor}\n"
                f"  Timestamp:  {result.timestamp}\n"
                f"  Trust Tier: {result.trust_tier}"
            )
            output_payload(msg, json_mode=False)

    return 0

