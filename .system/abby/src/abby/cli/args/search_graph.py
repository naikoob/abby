"""CLI argument parsers for search and graph commands (find, links)."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping


def register_search_and_graph_commands(
    subparsers: Any,
    sub_common: argparse.ArgumentParser,
    handlers: Mapping[str, Callable[..., int]],
) -> None:
    """Register find and links commands."""
    # abby find [query] [options]
    find_parser = subparsers.add_parser(
        "find",
        parents=[sub_common],
        help="Discover and search notes across knowledge domains with FTS5 acceleration",
    )
    find_parser.add_argument(
        "query",
        nargs="?",
        help='Optional text keyword, phrase ("..."), or regular expression',
    )
    scope_group = find_parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "-t",
        "--title-only",
        action="store_true",
        help="Search title and filename only",
    )
    scope_group.add_argument(
        "-c",
        "--content-only",
        action="store_true",
        help="Search note body content only",
    )
    find_parser.add_argument(
        "--status",
        help="Filter by OKF lifecycle status (unprocessed, active, evergreen, archived)",
    )
    find_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Filter by tag (can be specified multiple times)",
    )
    find_parser.add_argument(
        "--any-tag",
        action="store_true",
        help="Match notes with ANY specified tag (logical OR instead of AND)",
    )
    find_parser.add_argument(
        "--domain",
        help="Filter by domain (inbox, projects, areas, resources, archives)",
    )
    find_parser.add_argument(
        "--type",
        help="Filter by OKF type (inbox, project-note, area-note, resource-note, archive-note)",
    )
    find_parser.add_argument(
        "--created-after",
        metavar="DATE",
        help="Filter notes created on or after YYYY-MM-DD",
    )
    find_parser.add_argument(
        "--created-before",
        metavar="DATE",
        help="Filter notes created on or before YYYY-MM-DD",
    )
    find_parser.add_argument(
        "--updated-after",
        metavar="DATE",
        help="Filter notes updated on or after YYYY-MM-DD",
    )
    find_parser.add_argument(
        "--updated-before",
        metavar="DATE",
        help="Filter notes updated on or before YYYY-MM-DD",
    )
    find_parser.add_argument(
        "-n",
        "--limit",
        type=int,
        metavar="LIMIT",
        help="Maximum number of matching notes to return",
    )
    find_parser.add_argument(
        "-r",
        "--rebuild-cache",
        action="store_true",
        help="Purge and rebuild SQLite search cache from disk before searching",
    )
    find_parser.add_argument(
        "--snippets",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Include matching contextual snippets in search results",
    )
    find_parser.add_argument(
        "--trust",
        help="Filter by OKF computed trust tier (unverified, machine-confirmed, human-reviewed)",
    )
    find_parser.add_argument(
        "--fresh-only",
        action="store_true",
        help="Exclude notes whose stale_after date has passed",
    )
    find_parser.add_argument(
        "--stale",
        dest="stale_only",
        action="store_true",
        help="Include only notes whose stale_after date has passed",
    )
    if "find" in handlers:
        find_parser.set_defaults(handler=handlers["find"])

    # abby links [note] [options]
    links_parser = subparsers.add_parser(
        "links",
        parents=[sub_common],
        help="Graph traversal, backlink intelligence, broken link diagnostics, and refactoring",
    )
    links_parser.add_argument(
        "note",
        nargs="?",
        default=None,
        help="Relative path, title, or filename of the note to inspect (or subcommand like 'refactor')",
    )
    links_parser.add_argument(
        "extra",
        nargs="*",
        default=[],
        help="Additional arguments for subcommands (e.g. refactor <new_title>)",
    )
    links_parser.add_argument(
        "-b",
        "--backlinks",
        action="store_true",
        help="List incoming backlinks pointing to the specified note",
    )
    links_parser.add_argument(
        "--broken",
        action="store_true",
        help="Vault-wide scan for unresolved/dangling links",
    )
    links_parser.add_argument(
        "--headings",
        action="store_true",
        help="Validate sub-heading anchors when checking broken links",
    )
    links_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any broken links are detected",
    )
    links_parser.add_argument(
        "--orphans",
        action="store_true",
        help="Vault-wide scan for isolated notes (0 incoming and 0 outgoing links)",
    )
    links_parser.add_argument(
        "--unreferenced",
        action="store_true",
        help="Vault-wide scan for leaf notes (0 incoming links)",
    )
    links_parser.add_argument(
        "--include-inbox",
        action="store_true",
        help="Include 00 - Inbox in orphan and unreferenced scans",
    )
    links_parser.add_argument(
        "--domain",
        help="Filter operations to specified PARA domain (projects, areas, resources, archives)",
    )
    links_parser.add_argument(
        "-v",
        "--details",
        action="store_true",
        help="Display verbose link details (aliases, anchors, line numbers, syntax)",
    )
    links_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview refactoring modifications without altering files on disk",
    )
    links_parser.add_argument(
        "--links-only",
        action="store_true",
        help="Update link syntax only; skip renaming target file on disk",
    )
    links_parser.add_argument(
        "--force",
        action="store_true",
        help="Force refactoring even if target title is ambiguous",
    )
    links_parser.add_argument(
        "--depth",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="Multi-hop graph traversal depth (1 to 3, default: 1)",
    )
    if "links" in handlers:
        links_parser.set_defaults(handler=handlers["links"])

