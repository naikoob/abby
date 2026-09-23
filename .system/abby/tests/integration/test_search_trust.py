"""Integration tests for trust-aware search, freshness filtering, and snippet badging.

Covers User Story 3 (T019) of OKF 0.2 Trust Model.
Validates SQLite schema migration, FTS5 querying, and MCP parameter handling.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import CliRunner, IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import CliRunner, IsolatedVaultTestCase

from abby.core.cache import get_cache_db_path, get_db_connection, sync_cache
from abby.mcp.tools import execute_tool
from abby.models.trust import TrustTier


class TestSearchTrustIntegration(IsolatedVaultTestCase):
    """Integration tests for trust tier and staleness search capabilities."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def _seed_test_notes(self) -> None:
        """Seed a diverse set of notes with varied trust tiers and staleness states."""
        past_iso = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        future_iso = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Human-reviewed evergreen note
        self.create_note(
            domain="03 - Resources",
            filename="Raft.md",
            content="---\ntitle: \"Raft\"\ndescription: \"Leader election and log replication in Raft.\"\ntype: resource-note\nstatus: evergreen\ntags:\n  - consensus\nverified:\n  - by: human:alice\n    at: \"2026-09-18T10:00:00Z\"\n---\n\nRaft consensus guarantees safety.\n",
        )

        # 2. Machine-confirmed stale project note
        self.create_note(
            domain="01 - Projects",
            filename="Alpha Telemetry.md",
            content=f"---\ntitle: \"Alpha Telemetry\"\ndescription: \"Ingestion pipeline metrics.\"\ntype: project-note\nstatus: active\ntags:\n  - telemetry\ngenerated:\n  by: abby/agent:synthesizer\n  at: \"2026-01-01T00:00:00Z\"\nverified:\n  - by: agent:synthesizer\n    at: \"2026-01-01T00:00:00Z\"\nstale_after: \"{past_iso}\"\n---\n\nTelemetry pipeline implementation.\n",
        )

        # 3. Unverified fresh inbox note
        self.create_note(
            domain="00 - Inbox",
            filename="Raw Thought.md",
            content=f"---\ntitle: \"Raw Thought\"\ndescription: \"Quick brain dump.\"\ntype: inbox\nstatus: unprocessed\ntags:\n  - idea\nstale_after: \"{future_iso}\"\n---\n\nUnstructured capture.\n",
        )

    def test_schema_migration_adds_trust_columns(self) -> None:
        db_path = get_cache_db_path(self.vault_root)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Create legacy table without trust_tier or stale_after
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE notes (
                path TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                created TEXT,
                updated TEXT,
                file_mtime REAL NOT NULL,
                file_size INTEGER NOT NULL
            );
        """)
        conn.close()

        # Run sync_cache - should migrate schema cleanly
        sync_cache(self.vault_root, db_path=db_path)

        conn = get_db_connection(db_path)
        cursor = conn.execute("PRAGMA table_info(notes);")
        cols = {row[1] for row in cursor.fetchall()}
        conn.close()

        self.assertIn("trust_tier", cols)
        self.assertIn("stale_after", cols)

    def test_search_trust_filter_human_reviewed(self) -> None:
        self._seed_test_notes()
        code, out, err = CliRunner.invoke(["find", "--trust", "human-reviewed", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.strip())
        paths = [n["path"] for n in data["notes"]]
        self.assertIn("03 - Resources/Raft.md", paths)
        self.assertNotIn("01 - Projects/Alpha Telemetry.md", paths)
        self.assertNotIn("00 - Inbox/Raw Thought.md", paths)

    def test_search_trust_filter_machine_confirmed(self) -> None:
        self._seed_test_notes()
        code, out, err = CliRunner.invoke(["find", "--trust", "machine-confirmed", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.strip())
        paths = [n["path"] for n in data["notes"]]
        self.assertIn("01 - Projects/Alpha Telemetry.md", paths)
        self.assertNotIn("03 - Resources/Raft.md", paths)

    def test_search_trust_filter_unverified(self) -> None:
        self._seed_test_notes()
        code, out, err = CliRunner.invoke(["find", "--trust", "unverified", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.strip())
        paths = [n["path"] for n in data["notes"]]
        self.assertIn("00 - Inbox/Raw Thought.md", paths)
        self.assertNotIn("03 - Resources/Raft.md", paths)

    def test_search_trust_invalid_tier_returns_exit_2(self) -> None:
        self._seed_test_notes()
        code, out, err = CliRunner.invoke(["find", "--trust", "invalid-tier"])
        self.assertEqual(code, 2)

    def test_search_fresh_only_excludes_stale(self) -> None:
        self._seed_test_notes()
        code, out, err = CliRunner.invoke(["find", "--fresh-only", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.strip())
        paths = [n["path"] for n in data["notes"]]
        self.assertIn("03 - Resources/Raft.md", paths)
        self.assertIn("00 - Inbox/Raw Thought.md", paths)
        self.assertNotIn("01 - Projects/Alpha Telemetry.md", paths)

    def test_search_stale_only_includes_only_stale(self) -> None:
        self._seed_test_notes()
        code, out, err = CliRunner.invoke(["find", "--stale", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.strip())
        paths = [n["path"] for n in data["notes"]]
        self.assertIn("01 - Projects/Alpha Telemetry.md", paths)
        self.assertNotIn("03 - Resources/Raft.md", paths)
        self.assertNotIn("00 - Inbox/Raw Thought.md", paths)

    def test_search_snippets_renders_trust_badges(self) -> None:
        self._seed_test_notes()
        code, out, err = CliRunner.invoke(["find", "--snippets"])
        self.assertEqual(code, 0)
        self.assertIn("03 - Resources/Raft.md [03 - Resources | evergreen | human-reviewed | 0 links]", out)
        self.assertIn("01 - Projects/Alpha Telemetry.md [01 - Projects | active | machine-confirmed | stale | 0 links]", out)
        self.assertIn("00 - Inbox/Raw Thought.md [00 - Inbox | unprocessed | unverified | 0 links]", out)

    def test_mcp_vault_search_with_trust_tier(self) -> None:
        self._seed_test_notes()
        res = execute_tool(
            name="vault_search",
            arguments={"trust_tier": "human-reviewed"},
            vault_root=self.vault_root,
        )
        self.assertFalse(res.isError)
        self.assertIn("03 - Resources/Raft.md", res.content[0].text)
        self.assertNotIn("01 - Projects/Alpha Telemetry.md", res.content[0].text)
