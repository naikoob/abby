"""JSON-RPC 2.0 protocol models and framing for Abby MCP server.

Adheres strictly to the JSON-RPC 2.0 specification and Model Context Protocol.
100% Python standard library with zero external pip dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional, Union

# Standard JSON-RPC 2.0 Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Model Context Protocol Metadata
MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "abby"
SERVER_VERSION = "1.0.0"


class JSONRPCError(Exception):
    """Exception and payload descriptor for JSON-RPC 2.0 protocol errors."""

    def __init__(
        self,
        code: int,
        message: str,
        data: Optional[Any] = None,
        request_id: Union[str, int, None] = None,
    ) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data
        self.request_id = request_id

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            res["data"] = self.data
        return res


@dataclass
class JSONRPCRequest:
    """Incoming JSON-RPC 2.0 request or notification message."""

    jsonrpc: str
    method: str
    id: Union[str, int, None] = None
    params: Optional[dict[str, Any]] = None

    @property
    def is_notification(self) -> bool:
        """A notification is a request without an 'id' member."""
        return self.id is None

    @classmethod
    def from_dict(cls, data: Any) -> JSONRPCRequest:
        """Validate and parse a dictionary into a JSONRPCRequest."""
        if not isinstance(data, dict):
            raise JSONRPCError(INVALID_REQUEST, "Request payload must be a JSON object")

        version = data.get("jsonrpc")
        if version != "2.0":
            raise JSONRPCError(
                INVALID_REQUEST,
                f"Invalid jsonrpc protocol version '{version}'. Expected '2.0'.",
            )

        method = data.get("method")
        if not isinstance(method, str) or not method.strip():
            raise JSONRPCError(
                INVALID_REQUEST, "Member 'method' must be a non-empty string"
            )

        req_id = data.get("id")
        if req_id is not None and not isinstance(req_id, (str, int)):
            raise JSONRPCError(
                INVALID_REQUEST, "Member 'id' must be a string, integer, or null"
            )

        params = data.get("params")
        if params is not None and not isinstance(params, dict):
            raise JSONRPCError(
                INVALID_PARAMS, "Member 'params' must be a JSON object dictionary"
            )

        return cls(
            jsonrpc="2.0",
            method=method,
            id=req_id,
            params=params,
        )

    @classmethod
    def parse(cls, raw: str) -> JSONRPCRequest:
        """Parse a single JSON-RPC line string into a request."""
        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise JSONRPCError(
                PARSE_ERROR, f"Invalid JSON string received: {exc}"
            ) from exc

        return cls.from_dict(payload)


@dataclass
class JSONRPCResponse:
    """Outgoing JSON-RPC 2.0 response message."""

    jsonrpc: str = "2.0"
    id: Union[str, int, None] = None
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert response to a serializable dictionary conforming to JSON-RPC 2.0."""
        res: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self.id,
        }
        if self.error is not None:
            res["error"] = self.error.to_dict()
        else:
            res["result"] = self.result
        return res

    def to_json(self) -> str:
        """Serialize single-line JSON string without trailing newline."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def create_success(cls, id: Union[str, int, None], result: Any) -> JSONRPCResponse:
        """Factory for a successful response."""
        return cls(id=id, result=result, error=None)

    @classmethod
    def create_error(
        cls,
        id: Union[str, int, None],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> JSONRPCResponse:
        """Factory for an error response."""
        err = JSONRPCError(code=code, message=message, data=data, request_id=id)
        return cls(id=id, result=None, error=err)
