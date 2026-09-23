"""Tier 3 end-to-end integration tests for Abby MCP stdio server and CLI.

Validates the stdio JSON-RPC 2.0 loop, strict stream isolation (stdout JSON-RPC only,
stderr diagnostics), command-line invocation, and graceful EOF termination.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import Tier3CliTestCase
except ModuleNotFoundError:
    from support import Tier3CliTestCase


class TestMCPCliIntegration(Tier3CliTestCase):
    """Tier 3 tests for the MCP stdio server lifecycle and stream isolation."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_mcp_help_flag(self) -> None:
        code, out, err = self.invoke_cli(["mcp", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("Model Context Protocol", out)

    def test_stdio_handshake_and_tool_call(self) -> None:
        env = dict(os.environ)
        env["ABBY_VAULT_ROOT"] = str(self.vault_root)
        env["PYTHONPATH"] = str(SRC_DIR)

        proc = subprocess.Popen(
            [sys.executable, "-m", "abby.cli", "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            # 1. Initialize
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.flush()

            init_line = proc.stdout.readline()
            self.assertTrue(init_line.strip())
            init_resp = json.loads(init_line)
            self.assertEqual(init_resp["jsonrpc"], "2.0")
            self.assertEqual(init_resp["id"], 1)
            self.assertEqual(init_resp["result"]["serverInfo"]["name"], "abby")

            # 2. Initialized notification
            notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            proc.stdin.write(json.dumps(notif) + "\n")
            proc.stdin.flush()

            # 3. Ping
            ping_req = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
            proc.stdin.write(json.dumps(ping_req) + "\n")
            proc.stdin.flush()
            ping_line = proc.stdout.readline()
            ping_resp = json.loads(ping_line)
            self.assertEqual(ping_resp["id"], 2)
            self.assertEqual(ping_resp["result"], {})

            # 4. List tools
            list_req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
            proc.stdin.write(json.dumps(list_req) + "\n")
            proc.stdin.flush()
            list_line = proc.stdout.readline()
            list_resp = json.loads(list_line)
            tools = list_resp["result"]["tools"]
            self.assertEqual(len(tools), 12)
            tool_names = [t["name"] for t in tools]
            self.assertIn("note_capture", tool_names)
            self.assertIn("vault_search", tool_names)
            self.assertIn("note_verify", tool_names)
            self.assertIn("note_read", tool_names)
            self.assertIn("note_refactor", tool_names)

            # 5. Call note_capture
            call_req = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "note_capture",
                    "arguments": {
                        "title": "CLI Test Note",
                        "body": "Captured from stdio test.",
                    },
                },
            }
            proc.stdin.write(json.dumps(call_req) + "\n")
            proc.stdin.flush()
            call_line = proc.stdout.readline()
            call_resp = json.loads(call_line)
            self.assertEqual(call_resp["id"], 4)
            self.assertFalse(call_resp["result"]["isError"])
            self.assertIn("CLI Test Note", call_resp["result"]["content"][0]["text"])

            # Verify file created on disk
            created_file = self.vault_root / "00 - Inbox" / "CLI Test Note.md"
            self.assertTrue(created_file.exists())

            # 6. Stream isolation: close stdin and verify exit code 0
            proc.stdin.close()
            ret_code = proc.wait(timeout=5)
            self.assertEqual(ret_code, 0)

            # Assert stdout only had single-line JSON items
            stderr_content = proc.stderr.read()
            # stderr should contain server startup/shutdown or diagnostic logging, not stdout JSON
            self.assertNotIn('"jsonrpc": "2.0"', stderr_content)

        finally:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            if proc.poll() is None:
                proc.kill()


class TestAgentDocContract(Tier3CliTestCase):
    """Doc contract tests asserting repository AGENTS.md compliance (US2)."""

    def test_root_agents_md_contract(self) -> None:
        agents_md = Path(__file__).resolve().parents[4] / "AGENTS.md"
        if not agents_md.exists():
            self.skipTest("AGENTS.md not yet created (Phase 4)")

        content = agents_md.read_text(encoding="utf-8")
        self.assertIn("Air-Gap", content)
        self.assertIn("Knowledge Domain", content)
        self.assertIn("System Domain", content)
        self.assertIn("00 - Inbox", content)
        self.assertIn("04 - Archives", content)
        self.assertIn("vault_lint", content)
        self.assertIn("vault_search", content)
