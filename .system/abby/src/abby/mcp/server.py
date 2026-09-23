"""Stdio JSON-RPC 2.0 event loop for Abby MCP server.

Enforces strict stream isolation (stdout exclusively for JSON-RPC 2.0 frames,
stderr for diagnostics), robust EOF termination, and comprehensive error trapping.
"""

from __future__ import annotations

import signal
import sys
from pathlib import Path
from typing import Any, Optional

from abby.core.discovery import find_vault_root
from abby.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    MCP_PROTOCOL_VERSION,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    SERVER_NAME,
    SERVER_VERSION,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
)
from abby.mcp.tools import execute_tool, get_tool_definitions


def log_debug(message: str) -> None:
    """Log diagnostic information strictly to stderr."""
    sys.stderr.write(f"[abby-mcp] {message}\n")
    sys.stderr.flush()


class MCPServer:
    """Stdio-based Model Context Protocol server."""

    def __init__(self, vault_root: Optional[Path] = None) -> None:
        self.vault_root = vault_root.resolve() if vault_root else find_vault_root()
        self.is_initialized = False

    def emit_response(self, response: JSONRPCResponse) -> None:
        """Write single-line JSON-RPC response to stdout and flush immediately."""
        line = response.to_json() + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()

    def handle_request(self, req: JSONRPCRequest) -> Optional[JSONRPCResponse]:
        """Dispatch incoming JSON-RPC request to appropriate handler."""
        method = req.method
        params = req.params or {}

        if method == "initialize":
            self.is_initialized = True
            log_debug("Client handshake initialized")
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            }
            return JSONRPCResponse.create_success(id=req.id, result=result)

        elif method == "notifications/initialized":
            log_debug("Client sent initialized notification")
            # Notifications do not receive a response
            return None

        elif method == "ping":
            return JSONRPCResponse.create_success(id=req.id, result={})

        elif method == "tools/list":
            tools = get_tool_definitions()
            return JSONRPCResponse.create_success(id=req.id, result={"tools": tools})

        elif method == "tools/call":
            tool_name = params.get("name")
            if not tool_name or not isinstance(tool_name, str):
                if req.id is not None:
                    return JSONRPCResponse.create_error(
                        id=req.id,
                        code=INVALID_PARAMS,
                        message="Member 'params.name' must be a non-empty string.",
                    )
                return None

            tool_args = params.get("arguments") or {}
            if not isinstance(tool_args, dict):
                if req.id is not None:
                    return JSONRPCResponse.create_error(
                        id=req.id,
                        code=INVALID_PARAMS,
                        message="Member 'params.arguments' must be a JSON object dictionary.",
                    )
                return None

            result = execute_tool(tool_name, tool_args, self.vault_root)
            return JSONRPCResponse.create_success(id=req.id, result=result.to_dict())

        else:
            log_debug(f"Unrecognized method '{method}'")
            if req.id is not None:
                return JSONRPCResponse.create_error(
                    id=req.id,
                    code=METHOD_NOT_FOUND,
                    message=f"Method '{method}' not found.",
                )
            return None

    def run(self) -> int:
        """Execute the blocking stdio reading loop until EOF or signal."""
        log_debug(
            f"Starting Abby MCP server v{SERVER_VERSION} (vault: {self.vault_root})"
        )

        # Install signal handlers for clean exit
        def _handle_signal(signum: int, frame: Any) -> None:
            log_debug(f"Received signal {signum}, shutting down.")
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        while True:
            try:
                line = sys.stdin.readline()
            except Exception as exc:
                log_debug(f"Error reading stdin: {exc}")
                break

            # EOF received
            if not line:
                log_debug("Client disconnected (EOF received). Terminating.")
                break

            stripped = line.strip()
            if not stripped:
                continue

            try:
                req = JSONRPCRequest.parse(stripped)
            except JSONRPCError as err:
                log_debug(f"Protocol parse error: {err}")
                err_resp = JSONRPCResponse.create_error(
                    id=err.request_id,
                    code=err.code,
                    message=err.message,
                    data=err.data,
                )
                self.emit_response(err_resp)
                continue
            except Exception as exc:
                log_debug(f"Unexpected parsing failure: {exc}")
                err_resp = JSONRPCResponse.create_error(
                    id=None,
                    code=PARSE_ERROR,
                    message=f"Unexpected error parsing request: {exc}",
                )
                self.emit_response(err_resp)
                continue

            try:
                resp = self.handle_request(req)
                if resp is not None:
                    self.emit_response(resp)
            except Exception as exc:
                log_debug(f"Unhandled exception handling '{req.method}': {exc}")
                if req.id is not None:
                    err_resp = JSONRPCResponse.create_error(
                        id=req.id,
                        code=INTERNAL_ERROR,
                        message=f"Internal server error: {exc}",
                    )
                    self.emit_response(err_resp)

        log_debug("Abby MCP server shutdown complete.")
        return 0


def run_server(vault_root: Optional[Path] = None) -> int:
    """Entrypoint function to run MCP server."""
    server = MCPServer(vault_root=vault_root)
    return server.run()
