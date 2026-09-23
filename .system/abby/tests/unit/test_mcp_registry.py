"""Unit tests for modular MCP tool registry, types, and dispatcher."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.mcp.registry import ToolRegistry
from abby.mcp.types import MCPContentItem, MCPToolCallResult


class TestMCPRegistry(unittest.TestCase):
    """Tests for MCP ToolRegistry registration and execution dispatch."""

    def test_mcp_types(self) -> None:
        item = MCPContentItem(type="text", text="sample")
        self.assertEqual(item.to_dict(), {"type": "text", "text": "sample"})

        res = MCPToolCallResult.success("ok")
        self.assertFalse(res.isError)
        self.assertEqual(res.content[0].text, "ok")

        err = MCPToolCallResult.error("bad")
        self.assertTrue(err.isError)
        self.assertEqual(err.content[0].text, "Error: bad")

    def test_registry_registration_and_dispatch(self) -> None:
        reg = ToolRegistry()
        reg.register(
            name="echo",
            description="Echo back input",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
            handler=lambda args, root: MCPToolCallResult.success(args.get("msg", "")),
        )

        defs = reg.get_tool_definitions()
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["name"], "echo")

        # Successful dispatch
        res = reg.execute_tool("echo", {"msg": "hello"}, Path("/dummy"))
        self.assertFalse(res.isError)
        self.assertEqual(res.content[0].text, "hello")

        # Unknown tool dispatch
        bad_res = reg.execute_tool("unknown", {}, Path("/dummy"))
        self.assertTrue(bad_res.isError)
        self.assertIn("Unrecognized tool 'unknown'", bad_res.content[0].text)


if __name__ == "__main__":
    unittest.main()
