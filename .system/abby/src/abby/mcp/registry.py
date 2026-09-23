"""Tool registry and execution dispatcher for Abby MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from abby.models.exceptions import AbbyError
from abby.mcp.types import MCPTool, MCPToolCallResult


class ToolRegistry:
    """Registry maintaining exposed MCP tools, schemas, and execution handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[[dict[str, Any], Path], MCPToolCallResult],
    ) -> None:
        """Register a new MCP tool with schema and handler."""
        self._tools[name] = MCPTool(
            name=name,
            description=description,
            inputSchema=input_schema,
            handler=handler,
        )

    def register_tool(self, tool: MCPTool) -> None:
        """Register an existing MCPTool instance."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Lookup a registered tool by name."""
        return self._tools.get(name)

    def get_tool_names(self) -> list[str]:
        """Return sorted list of all registered tool names."""
        return sorted(self._tools.keys())

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return JSON schema descriptors for all registered MCP tools."""
        return [t.to_dict() for t in self._tools.values()]

    def execute_tool(
        self, name: str, arguments: dict[str, Any], vault_root: Path
    ) -> MCPToolCallResult:
        """Execute a registered tool by name with arguments within vault root."""
        tool = self._tools.get(name)
        if not tool:
            return MCPToolCallResult.error(
                f"Unrecognized tool '{name}'. Available: {', '.join(self.get_tool_names())}"
            )

        try:
            return tool.handler(arguments or {}, vault_root)
        except (AbbyError, ValueError) as exc:
            msg = exc.message if isinstance(exc, AbbyError) else str(exc)
            return MCPToolCallResult.error(msg)
        except Exception as exc:
            return MCPToolCallResult.error(f"Execution error in tool '{name}': {exc}")
