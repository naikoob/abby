"""Tier 1 unit tests for JSON-RPC 2.0 protocol models and serialization.

Tests protocol frames, parsing, error codes, notification detection,
and serialization per Model Context Protocol specification.
"""

from __future__ import annotations

import json
import unittest

from abby.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
)


class TestJSONRPCProtocol(unittest.TestCase):
    """Tier 1 tests for pure in-memory JSON-RPC 2.0 frames."""

    def test_parse_valid_request(self) -> None:
        raw = '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}'
        req = JSONRPCRequest.parse(raw)
        self.assertEqual(req.jsonrpc, "2.0")
        self.assertEqual(req.id, 1)
        self.assertEqual(req.method, "initialize")
        self.assertIsNotNone(req.params)
        self.assertEqual(req.params.get("protocolVersion"), "2024-11-05")
        self.assertFalse(req.is_notification)

    def test_parse_notification(self) -> None:
        raw = '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
        req = JSONRPCRequest.parse(raw)
        self.assertEqual(req.jsonrpc, "2.0")
        self.assertIsNone(req.id)
        self.assertEqual(req.method, "notifications/initialized")
        self.assertTrue(req.is_notification)

    def test_parse_invalid_json(self) -> None:
        with self.assertRaises(JSONRPCError) as ctx:
            JSONRPCRequest.parse("not json")
        self.assertEqual(ctx.exception.code, PARSE_ERROR)

    def test_parse_invalid_spec_version(self) -> None:
        raw = '{"jsonrpc": "1.0", "id": 1, "method": "ping"}'
        with self.assertRaises(JSONRPCError) as ctx:
            JSONRPCRequest.parse(raw)
        self.assertEqual(ctx.exception.code, INVALID_REQUEST)

    def test_parse_missing_method(self) -> None:
        raw = '{"jsonrpc": "2.0", "id": 1}'
        with self.assertRaises(JSONRPCError) as ctx:
            JSONRPCRequest.parse(raw)
        self.assertEqual(ctx.exception.code, INVALID_REQUEST)

    def test_create_success_response(self) -> None:
        resp = JSONRPCResponse.create_success(
            id=1, result={"serverInfo": {"name": "abby", "version": "1.0.0"}}
        )
        data = resp.to_dict()
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], 1)
        self.assertIn("result", data)
        self.assertNotIn("error", data)
        self.assertEqual(data["result"]["serverInfo"]["name"], "abby")

        # Serialized JSON should be single-line
        json_str = resp.to_json()
        self.assertNotIn("\n", json_str)
        reparsed = json.loads(json_str)
        self.assertEqual(reparsed["id"], 1)

    def test_create_error_response(self) -> None:
        resp = JSONRPCResponse.create_error(
            id=42,
            code=METHOD_NOT_FOUND,
            message="Method 'unknown_method' not found",
            data={"details": "Unrecognized MCP endpoint"},
        )
        data = resp.to_dict()
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], 42)
        self.assertNotIn("result", data)
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], METHOD_NOT_FOUND)
        self.assertEqual(data["error"]["message"], "Method 'unknown_method' not found")
        self.assertEqual(
            data["error"]["data"], {"details": "Unrecognized MCP endpoint"}
        )

        json_str = resp.to_json()
        self.assertNotIn("\n", json_str)


if __name__ == "__main__":
    unittest.main()
