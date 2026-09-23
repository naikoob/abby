"""Tool definitions, JSON schemas, and execution handlers for Abby MCP server.

Exposes 10 core vault capabilities as standard Model Context Protocol tools.
Delegates directly to modular schemas, handlers, and the ToolRegistry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abby.mcp.handlers import (
    handle_domain_list,
    handle_note_archive,
    handle_note_capture,
    handle_note_move,
    handle_note_read,
    handle_note_refactor,
    handle_note_verify,
    handle_vault_check,
    handle_vault_init,
    handle_vault_links,
    handle_vault_lint,
    handle_vault_search,
)
from abby.mcp.registry import ToolRegistry
from abby.mcp.schemas import TOOL_SCHEMAS
from abby.mcp.types import MCPContentItem, MCPTool, MCPToolCallResult

# Central registry initialization
_DEFAULT_REGISTRY = ToolRegistry()

# Register all 10 tools
_DEFAULT_REGISTRY.register(
    name="vault_check",
    description=TOOL_SCHEMAS["vault_check"]["description"],
    input_schema=TOOL_SCHEMAS["vault_check"]["inputSchema"],
    handler=handle_vault_check,
)
_DEFAULT_REGISTRY.register(
    name="vault_init",
    description=TOOL_SCHEMAS["vault_init"]["description"],
    input_schema=TOOL_SCHEMAS["vault_init"]["inputSchema"],
    handler=handle_vault_init,
)
_DEFAULT_REGISTRY.register(
    name="note_capture",
    description=TOOL_SCHEMAS["note_capture"]["description"],
    input_schema=TOOL_SCHEMAS["note_capture"]["inputSchema"],
    handler=handle_note_capture,
)
_DEFAULT_REGISTRY.register(
    name="domain_list",
    description=TOOL_SCHEMAS["domain_list"]["description"],
    input_schema=TOOL_SCHEMAS["domain_list"]["inputSchema"],
    handler=handle_domain_list,
)
_DEFAULT_REGISTRY.register(
    name="note_move",
    description=TOOL_SCHEMAS["note_move"]["description"],
    input_schema=TOOL_SCHEMAS["note_move"]["inputSchema"],
    handler=handle_note_move,
)
_DEFAULT_REGISTRY.register(
    name="note_archive",
    description=TOOL_SCHEMAS["note_archive"]["description"],
    input_schema=TOOL_SCHEMAS["note_archive"]["inputSchema"],
    handler=handle_note_archive,
)
_DEFAULT_REGISTRY.register(
    name="note_verify",
    description=TOOL_SCHEMAS["note_verify"]["description"],
    input_schema=TOOL_SCHEMAS["note_verify"]["inputSchema"],
    handler=handle_note_verify,
)
_DEFAULT_REGISTRY.register(
    name="vault_search",
    description=TOOL_SCHEMAS["vault_search"]["description"],
    input_schema=TOOL_SCHEMAS["vault_search"]["inputSchema"],
    handler=handle_vault_search,
)
_DEFAULT_REGISTRY.register(
    name="vault_links",
    description=TOOL_SCHEMAS["vault_links"]["description"],
    input_schema=TOOL_SCHEMAS["vault_links"]["inputSchema"],
    handler=handle_vault_links,
)
_DEFAULT_REGISTRY.register(
    name="vault_lint",
    description=TOOL_SCHEMAS["vault_lint"]["description"],
    input_schema=TOOL_SCHEMAS["vault_lint"]["inputSchema"],
    handler=handle_vault_lint,
)
_DEFAULT_REGISTRY.register(
    name="note_read",
    description=TOOL_SCHEMAS["note_read"]["description"],
    input_schema=TOOL_SCHEMAS["note_read"]["inputSchema"],
    handler=handle_note_read,
)
_DEFAULT_REGISTRY.register(
    name="note_refactor",
    description=TOOL_SCHEMAS["note_refactor"]["description"],
    input_schema=TOOL_SCHEMAS["note_refactor"]["inputSchema"],
    handler=handle_note_refactor,
)

# Backward-compatible references
TOOL_REGISTRY = _DEFAULT_REGISTRY._tools


def get_tool_names() -> list[str]:
    """Return sorted list of all registered tool names."""
    return _DEFAULT_REGISTRY.get_tool_names()


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return JSON schema descriptors for all registered MCP tools."""
    return _DEFAULT_REGISTRY.get_tool_definitions()


def execute_tool(
    name: str, arguments: dict[str, Any], vault_root: Path
) -> MCPToolCallResult:
    """Execute a registered tool by name with arguments within vault root."""
    return _DEFAULT_REGISTRY.execute_tool(name, arguments, vault_root)


execute_tool_call = execute_tool

__all__ = [
    "MCPContentItem",
    "MCPTool",
    "MCPToolCallResult",
    "TOOL_REGISTRY",
    "TOOL_SCHEMAS",
    "execute_tool",
    "execute_tool_call",
    "get_tool_definitions",
    "get_tool_names",
]
