"""Command-line argument parser configuration for Abby Knowledge Vault CLI."""

from __future__ import annotations

import argparse
from typing import Callable, Mapping, Optional

from abby import __version__
from abby.cli.args import (
    register_lifecycle_commands,
    register_lint_and_mcp_commands,
    register_search_and_graph_commands,
    register_vault_commands,
)

# Backward-compatible aliases for private registration functions
_register_vault_commands = register_vault_commands
_register_lifecycle_commands = register_lifecycle_commands
_register_search_and_graph_commands = register_search_and_graph_commands
_register_lint_and_mcp_commands = register_lint_and_mcp_commands


def create_cli_parser(
    handlers: Optional[Mapping[str, Callable[..., int]]] = None,
) -> argparse.ArgumentParser:
    """Construct the command-line argument parser.

    Args:
        handlers: Optional mapping of subcommand names to command handler callables.
                  If provided, `set_defaults(handler=...)` is attached to each subcommand.

    Returns:
        Configured `argparse.ArgumentParser` instance.
    """
    handlers_map = handlers or {}

    # Shared parent parser for top-level parser
    root_common = argparse.ArgumentParser(add_help=False)
    root_common.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as machine-readable JSON on stdout",
    )
    root_common.add_argument(
        "--snippets",
        action="store_true",
        default=False,
        help="Include matching contextual snippets in search results",
    )

    # Shared parent parser for subparsers with default=SUPPRESS to avoid overwriting top-level flags
    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Output results as machine-readable JSON on stdout",
    )

    parser = argparse.ArgumentParser(
        prog="abby",
        description="Abby Knowledge Vault CLI - Health inspection, scaffolding, and rapid note intake.",
        parents=[root_common],
        add_help=True,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"abby {__version__}",
        help="Show abby version and exit",
    )

    subparsers = parser.add_subparsers(
        dest="subcommand", title="Commands", metavar="<command>"
    )

    register_vault_commands(subparsers, sub_common, handlers_map)
    register_lifecycle_commands(subparsers, sub_common, handlers_map)
    register_search_and_graph_commands(subparsers, sub_common, handlers_map)
    register_lint_and_mcp_commands(subparsers, sub_common, handlers_map)

    return parser
