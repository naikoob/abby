"""Data structures and response wrappers for Abby Model Context Protocol (MCP) server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class MCPContentItem:
    """Individual content item in an MCP tool response."""

    type: str = "text"
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}


@dataclass
class MCPToolCallResult:
    """Structured response from executing an MCP tool."""

    content: list[MCPContentItem]
    isError: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": [c.to_dict() for c in self.content],
            "isError": self.isError,
        }

    @classmethod
    def success(cls, text: str) -> MCPToolCallResult:
        return cls(content=[MCPContentItem(type="text", text=text)], isError=False)

    @classmethod
    def error(cls, message: str) -> MCPToolCallResult:
        return cls(
            content=[MCPContentItem(type="text", text=f"Error: {message}")],
            isError=True,
        )


@dataclass
class MCPTool:
    """Schema and handler definition for an exposed MCP tool."""

    name: str
    description: str
    inputSchema: dict[str, Any]
    handler: Callable[[dict[str, Any], Path], MCPToolCallResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }


@dataclass
class NoteContentPayload:
    """Complete note details returned by note_read."""

    path: str
    title: str
    frontmatter: dict[str, Any]
    body: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "frontmatter": self.frontmatter,
            "body": self.body,
            "content": self.content,
        }

