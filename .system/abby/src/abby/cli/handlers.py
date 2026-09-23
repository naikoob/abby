"""Command-line interface and argument parsing for Abby."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Mapping, Optional

from abby.cli.parser import create_cli_parser
from abby.core.discovery import find_vault_root
from abby.cli.commands import (
    execute_archive,
    execute_cache_command,
    execute_check,
    execute_doctor,
    execute_find,
    execute_info,
    execute_init,
    execute_links,
    execute_lint,
    execute_list,
    execute_move,
    execute_new,
    execute_verify,
)

from abby.mcp.server import run_server
from abby.models.exceptions import AbbyError, AmbiguousTargetError
from abby.models.search import SearchFilter
from abby.utils.io import log_error, output_payload

# Command Handler Type: Callable[[argparse.Namespace, Path], int]
CommandHandler = Callable[[argparse.Namespace, Path], int]


def _handle_lint(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute lint command."""
    return execute_lint(vault_root, args)


def _handle_links(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute links command."""
    return execute_links(vault_root, args)


def _handle_check(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute check command."""
    return execute_check(vault_root, json_mode=getattr(args, "json", False))


def _handle_init(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute init command."""
    return execute_init(vault_root, json_mode=getattr(args, "json", False))


def _handle_new(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute new note capture command."""
    json_mode = getattr(args, "json", False)
    if not args.title or not args.title.strip():
        log_error("Note title is required. Usage: abby new <title> [--body <body>]")
        if json_mode:
            output_payload(
                {"success": False, "error": "Missing note title"}, json_mode=True
            )
        return 2
    raw_tags = getattr(args, "tags", None)
    tags_list = (
        [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else None
    )
    return execute_new(
        vault_root,
        title=args.title,
        body=args.body,
        description=getattr(args, "description", None),
        tags=tags_list,
        json_mode=json_mode,
        generated_by=getattr(args, "generated_by", None),
    )


def _handle_info(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute info command."""
    return execute_info(vault_root, json_mode=getattr(args, "json", False))


def _handle_list(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute list command."""
    return execute_list(
        vault_root, domain=args.domain, json_mode=getattr(args, "json", False)
    )


def _handle_move(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute move command."""
    json_mode = getattr(args, "json", False)
    dry_run = getattr(args, "dry_run", False)
    if not args.note or not args.target:
        log_error("Usage: abby move <note-path> <target-domain>")
        if json_mode:
            output_payload(
                {"success": False, "error": "Missing required arguments"},
                json_mode=True,
            )
        return 2
    description = getattr(args, "description", None)
    return execute_move(
        vault_root,
        note_arg=args.note,
        target_spec=args.target,
        json_mode=json_mode,
        dry_run=dry_run,
        description=description,
    )


def _handle_archive(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute archive command."""
    json_mode = getattr(args, "json", False)
    dry_run = getattr(args, "dry_run", False)
    if not args.note or not args.note.strip():
        log_error("Usage: abby archive <note-path>")
        if json_mode:
            output_payload(
                {"success": False, "error": "Missing required argument <note-path>"},
                json_mode=True,
            )
        return 2
    return execute_archive(
        vault_root,
        note_arg=args.note,
        json_mode=json_mode,
        dry_run=dry_run,
    )


def _handle_verify(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute verify command."""
    return execute_verify(
        vault_root=vault_root,
        note_arg=getattr(args, "note", None),
        actor=getattr(args, "by", None),
        dry_run=getattr(args, "dry_run", False),
        json_mode=getattr(args, "json", False),
    )


def _handle_find(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute find search command."""
    scope = "all"
    if getattr(args, "title_only", False):
        scope = "title"
    elif getattr(args, "content_only", False):
        scope = "content"

    tag_conjunction = "OR" if getattr(args, "any_tag", False) else "AND"

    search_filter = SearchFilter(
        query=args.query,
        scope=scope,
        domain=args.domain,
        status=args.status,
        tags=getattr(args, "tag", []) or [],
        tag_conjunction=tag_conjunction,
        type=args.type,
        created_after=args.created_after,
        created_before=args.created_before,
        updated_after=args.updated_after,
        updated_before=args.updated_before,
        limit=args.limit,
        json_mode=getattr(args, "json", False),
        snippets=getattr(args, "snippets", False),
        trust=getattr(args, "trust", None),
        fresh_only=getattr(args, "fresh_only", False),
        stale_only=getattr(args, "stale_only", False),
    )

    return execute_find(
        vault_root,
        search_filter=search_filter,
        rebuild=getattr(args, "rebuild_cache", False),
    )


def _handle_mcp(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute Model Context Protocol (MCP) server over stdio."""
    return run_server(vault_root=vault_root)


def _handle_doctor(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute doctor command."""
    return execute_doctor(vault_root, json_mode=getattr(args, "json", False))


def _handle_cache(args: argparse.Namespace, vault_root: Path) -> int:
    """Execute cache command."""
    action = getattr(args, "action", "status")
    return execute_cache_command(vault_root, action=action, json_mode=getattr(args, "json", False))


COMMAND_HANDLERS: dict[str, CommandHandler] = {
    "check": _handle_check,
    "init": _handle_init,
    "new": _handle_new,
    "info": _handle_info,
    "list": _handle_list,
    "move": _handle_move,
    "archive": _handle_archive,
    "verify": _handle_verify,
    "find": _handle_find,
    "links": _handle_links,
    "lint": _handle_lint,
    "mcp": _handle_mcp,
    "doctor": _handle_doctor,
    "cache": _handle_cache,
}



def build_parser(
    handlers: Optional[Mapping[str, CommandHandler]] = None,
) -> argparse.ArgumentParser:
    """Construct the command-line argument parser."""
    return create_cli_parser(handlers if handlers is not None else COMMAND_HANDLERS)


def _handle_cli_error(err: Exception, args: argparse.Namespace, json_mode: bool) -> int:
    """Format and output CLI errors with appropriate exit codes."""
    if isinstance(err, AmbiguousTargetError):
        log_error(err.message)
        if json_mode:
            note_arg = getattr(args, "note", "")
            err_label = (
                f"Note '{note_arg}' is ambiguous"
                if note_arg and f"Note '{note_arg}' is ambiguous" in err.message
                else err.message
            )
            output_payload(
                {
                    "success": False,
                    "error": err_label,
                    "candidate_paths": err.candidate_paths,
                },
                json_mode=True,
            )
        return err.exit_code
    elif isinstance(err, AbbyError):
        log_error(err.message)
        if json_mode:
            output_payload({"success": False, "error": err.message}, json_mode=True)
        return err.exit_code
    raise err


def main(argv: Optional[list[str]] = None) -> int:
    """CLI execution entrypoint returning exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handler: Optional[CommandHandler] = getattr(args, "handler", None)
    if not handler:
        parser.print_help(sys.stderr)
        return 0

    json_mode = getattr(args, "json", False)

    try:
        vault_root = find_vault_root()
        return handler(args, vault_root)
    except (AmbiguousTargetError, AbbyError) as err:
        return _handle_cli_error(err, args, json_mode)


if __name__ == "__main__":
    sys.exit(main())
