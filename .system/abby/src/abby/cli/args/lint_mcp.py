"""CLI argument parsers for lint and MCP server commands."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping


def register_lint_and_mcp_commands(
    subparsers: Any,
    sub_common: argparse.ArgumentParser,
    handlers: Mapping[str, Callable[..., int]],
) -> None:
    """Register lint and mcp commands."""
    # abby lint [note] [options]
    lint_parser = subparsers.add_parser(
        "lint",
        parents=[sub_common],
        help="Audit vault notes for OKF schema compliance, domain alignment, and automated repair",
    )
    lint_parser.add_argument(
        "note",
        nargs="?",
        default=None,
        help="Relative path, title, or filename of a single note to audit (default: vault-wide)",
    )
    lint_parser.add_argument(
        "--domain",
        help="Filter audit to notes within specified PARA domain (inbox, projects, areas, resources, archives)",
    )
    lint_parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically repair fixable schema defects and domain misalignments",
    )
    lint_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview planned remediation modifications without writing to disk",
    )
    lint_parser.add_argument(
        "--strict",
        action="store_true",
        help="Continuous integration gate: exit with code 1 if any violation (error or warning) is detected",
    )
    if "lint" in handlers:
        lint_parser.set_defaults(handler=handlers["lint"])

    # abby mcp
    mcp_parser = subparsers.add_parser(
        "mcp",
        parents=[sub_common],
        help="Start the Model Context Protocol (MCP) server over standard I/O (stdio)",
        description="Start the Model Context Protocol (MCP) server over standard I/O (stdio)",
    )
    if "mcp" in handlers:
        mcp_parser.set_defaults(handler=handlers["mcp"])

