"""Abby Model Context Protocol (MCP) package.

Exposes a zero-dependency JSON-RPC 2.0 stdio server providing structured,
typed access to core Abby vault management operations.
"""

from __future__ import annotations

from abby.mcp.protocol import MCP_PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION
from abby.mcp.server import MCPServer, run_server

__all__ = [
    "MCP_PROTOCOL_VERSION",
    "SERVER_NAME",
    "SERVER_VERSION",
    "MCPServer",
    "run_server",
]
