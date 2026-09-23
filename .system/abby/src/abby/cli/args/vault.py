"""CLI argument parsers for vault health, initialization, and note intake."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping


def register_vault_commands(
    subparsers: Any,
    sub_common: argparse.ArgumentParser,
    handlers: Mapping[str, Callable[..., int]],
) -> None:
    """Register check, init, info, list, and new commands."""
    # abby check
    check_parser = subparsers.add_parser(
        "check",
        parents=[sub_common],
        help="Audit vault directories and structure (read-only)",
    )
    if "check" in handlers:
        check_parser.set_defaults(handler=handlers["check"])

    # abby init
    init_parser = subparsers.add_parser(
        "init",
        parents=[sub_common],
        help="Scaffold missing standard vault directories idempotently",
    )
    if "init" in handlers:
        init_parser.set_defaults(handler=handlers["init"])

    # abby new <title> [--body <body>]
    new_parser = subparsers.add_parser(
        "new",
        parents=[sub_common],
        help="Capture a new note in 00 - Inbox conforming to Open Knowledge Format",
    )
    new_parser.add_argument(
        "title",
        nargs="?",
        help="Title of the new note",
    )
    new_parser.add_argument(
        "-b",
        "--body",
        help="Optional note body content (can also be piped via stdin)",
    )
    new_parser.add_argument(
        "-d",
        "--description",
        help="Optional 1-2 sentence executive summary (TL;DR) of the note's intent",
    )
    new_parser.add_argument(
        "-t",
        "--tags",
        help="Optional comma-separated tags to include in frontmatter",
    )
    new_parser.add_argument(
        "--generated-by",
        help="Stamp creation provenance actor (e.g. 'abby/agent:synthesizer')",
    )
    if "new" in handlers:
        new_parser.set_defaults(handler=handlers["new"])

    # abby info
    info_parser = subparsers.add_parser(
        "info",
        parents=[sub_common],
        help="Show system environment and vault diagnostics",
    )
    if "info" in handlers:
        info_parser.set_defaults(handler=handlers["info"])

    # abby list [domain]
    list_parser = subparsers.add_parser(
        "list",
        parents=[sub_common],
        help="List notes in a PARA domain queue (default: inbox)",
    )
    list_parser.add_argument(
        "domain",
        nargs="?",
        default="inbox",
        help="Target PARA domain (inbox, projects, areas, resources, archives). Defaults to inbox.",
    )
    if "list" in handlers:
        list_parser.set_defaults(handler=handlers["list"])

    # abby doctor
    doctor_parser = subparsers.add_parser(
        "doctor",
        parents=[sub_common],
        help="Run comprehensive health and integrity diagnostics on the vault and engine",
    )
    if "doctor" in handlers:
        doctor_parser.set_defaults(handler=handlers["doctor"])

    # abby cache [status|rebuild|prune]
    cache_parser = subparsers.add_parser(
        "cache",
        parents=[sub_common],
        help="Manage SQLite acceleration and FTS5 search cache (status, rebuild, prune)",
    )
    cache_parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "rebuild", "prune"],
        help="Cache management action (status, rebuild, prune; default: status)",
    )
    if "cache" in handlers:
        cache_parser.set_defaults(handler=handlers["cache"])


