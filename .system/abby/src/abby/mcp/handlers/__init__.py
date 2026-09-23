"""Abby Model Context Protocol (MCP) tool execution handlers."""

from __future__ import annotations

from abby.mcp.handlers.graph import handle_note_refactor, handle_vault_links
from abby.mcp.handlers.lint import handle_vault_lint
from abby.mcp.handlers.notes import (
    handle_domain_list,
    handle_note_archive,
    handle_note_capture,
    handle_note_move,
    handle_note_read,
    handle_note_verify,
)
from abby.mcp.handlers.search import handle_vault_search
from abby.mcp.handlers.vault import handle_vault_check, handle_vault_init

__all__ = [
    "handle_domain_list",
    "handle_note_archive",
    "handle_note_capture",
    "handle_note_move",
    "handle_note_read",
    "handle_note_refactor",
    "handle_note_verify",
    "handle_vault_check",
    "handle_vault_init",
    "handle_vault_links",
    "handle_vault_lint",
    "handle_vault_search",
]

