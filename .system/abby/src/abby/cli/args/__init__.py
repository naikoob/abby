"""CLI argument parser configuration modules."""

from __future__ import annotations

from abby.cli.args.lifecycle import register_lifecycle_commands
from abby.cli.args.lint_mcp import register_lint_and_mcp_commands
from abby.cli.args.search_graph import register_search_and_graph_commands
from abby.cli.args.vault import register_vault_commands

__all__ = [
    "register_lifecycle_commands",
    "register_lint_and_mcp_commands",
    "register_search_and_graph_commands",
    "register_vault_commands",
]

