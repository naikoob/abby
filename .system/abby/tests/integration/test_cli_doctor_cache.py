"""Integration tests for 'abby doctor' and 'abby cache' CLI commands."""

from __future__ import annotations

import json
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


class TestCliDoctorAndCache(Tier3CliTestCase):
    """Tier 3 CLI integration tests for diagnostic and cache operations."""

    def test_doctor_command_success(self) -> None:
        self.init_vault()
        self.invoke_cli(["init"])
        code, out, err = self.invoke_cli(["doctor"])
        self.assertEqual(code, 0, f"doctor failed with stderr: {err}")
        self.assertIn("Abby Vault Doctor Diagnostics", out)
        self.assertIn("[PASS] Python Runtime", out)
        self.assertIn("[PASS] PARA+ Directory Taxonomy", out)
        self.assertIn("[PASS] SQLite Cache Integrity", out)
        self.assertIn("Result: All 6 checks passed", out)

    def test_doctor_command_json(self) -> None:
        self.init_vault()
        code, out, err = self.invoke_cli(["doctor", "--json"])
        self.assertEqual(code, 0, f"doctor --json failed with stderr: {err}")
        payload = json.loads(out)
        self.assertTrue(payload["healthy"])
        self.assertEqual(len(payload["checks"]), 6)
        check_names = [c["name"] for c in payload["checks"]]
        self.assertIn("Python Runtime", check_names)
        self.assertIn("PARA+ Directory Taxonomy", check_names)
        self.assertIn("SQLite Cache Integrity", check_names)

    def test_cache_status_and_rebuild(self) -> None:
        self.init_vault()
        self.create_note("00 - Inbox", "Inbox1.md", title="Inbox 1")
        self.create_note("01 - Projects", "Project1.md", title="Project 1")

        # Cache status before rebuild
        code, out, _ = self.invoke_cli(["cache", "status"])
        self.assertEqual(code, 0)
        self.assertIn("Cache Database:", out)
        self.assertIn("Status: uninitialized", out)

        # Cache rebuild
        code, out, _ = self.invoke_cli(["cache", "rebuild"])
        self.assertEqual(code, 0)
        self.assertIn("Cache rebuild complete:", out)

        # Cache status after rebuild
        code, out, _ = self.invoke_cli(["cache", "status"])
        self.assertEqual(code, 0)
        self.assertIn("Schema Version: 1", out)
        self.assertIn("notes: 2 records", out)

        # JSON cache status after rebuild
        code, out, _ = self.invoke_cli(["cache", "status", "--json"])
        self.assertEqual(code, 0)
        stats = json.loads(out)
        self.assertEqual(stats["status"], "operational")
        self.assertEqual(stats["user_version"], 1)
        self.assertEqual(stats["tables"]["notes"], 2)


    def test_cache_prune(self) -> None:
        self.init_vault()
        self.create_note("00 - Inbox", "InboxNote.md", title="Inbox Note")
        self.invoke_cli(["cache", "rebuild"])

        # Prune command
        code, out, _ = self.invoke_cli(["cache", "prune"])
        self.assertEqual(code, 0)
        self.assertIn("Cache maintenance complete:", out)
