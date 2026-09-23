"""Integration tests for multi-factor cognitive ranking model in Abby vault search.

Feature: 015-cognitive-graph-search
User Story 1: Multi-Factor Cognitive Search Ranking (Priority: P1 MVP)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import IsolatedVaultTestCase

from abby.core.cache import get_cache_db_path, get_db_connection, sync_cache
from abby.core.search import query_notes
from abby.core.search_builder import build_search_sql
from abby.models.search import SearchFilter


class TestSearchCognitiveIntegration(IsolatedVaultTestCase):
    """Integration tests verifying cognitive rank blending across domains, trust, and freshness."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_search_sql_order_clause(self) -> None:
        """Verify build_search_sql includes COGNITIVE_RANK_MULTIPLIER ordering."""
        sf = SearchFilter(query="consensus")
        sql, params = build_search_sql(sf)
        self.assertIn("COGNITIVE_RANK_MULTIPLIER(notes.domain, notes.trust_tier, notes.stale_after, notes.active_backlinks)", sql)
        self.assertIn("ORDER BY (bm25(notes_fts, 0.0, 10.0, 7.0, 1.0, 5.0) * COGNITIVE_RANK_MULTIPLIER", sql)
        self.assertIn(") ASC", sql)

    def test_archive_zombie_deprioritization(self) -> None:
        """Verify evergreen resource note outranks archive zombie note with higher keyword density."""
        # Archive note has high term frequency for "consensus"
        self.create_note(
            domain="04 - Archives",
            filename="Legacy Consensus Experiments.md",
            content=(
                "---\n"
                "title: \"Legacy Consensus Experiments\"\n"
                "description: \"Archived consensus testing and obsolete experiments.\"\n"
                "type: archive-note\n"
                "status: archived\n"
                "---\n\n"
                "Consensus protocol experiments. Consensus consensus consensus. We tested consensus extensively.\n"
            ),
        )

        # Resource note has single mention of "consensus"
        self.create_note(
            domain="03 - Resources",
            filename="Consensus Overview.md",
            content=(
                "---\n"
                "title: \"Consensus Overview\"\n"
                "description: \"Introduction to distributed consensus systems.\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "verified:\n"
                "  - by: human:bookian\n"
                "    at: \"2026-09-18T10:00:00Z\"\n"
                "---\n\n"
                "Distributed consensus ensures state machine replication.\n"
            ),
        )

        sf = SearchFilter(query="consensus")
        items, count = query_notes(self.vault_root, sf)
        self.assertEqual(count, 2)
        # Resource note must rank first despite archive note having higher term repetition
        self.assertEqual(items[0].filename, "Consensus Overview.md")
        self.assertEqual(items[1].filename, "Legacy Consensus Experiments.md")

    def test_human_reviewed_outranks_unverified(self) -> None:
        """Verify human-reviewed note outranks unverified note in the same domain with identical content."""
        self.create_note(
            domain="03 - Resources",
            filename="Note Unverified.md",
            content=(
                "---\n"
                "title: \"Raft Architecture\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "---\n\n"
                "Understanding the Raft replication engine.\n"
            ),
        )

        self.create_note(
            domain="03 - Resources",
            filename="Note Verified.md",
            content=(
                "---\n"
                "title: \"Raft Architecture\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "verified:\n"
                "  - by: human:reviewer\n"
                "    at: \"2026-09-18T10:00:00Z\"\n"
                "---\n\n"
                "Understanding the Raft replication engine.\n"
            ),
        )

        sf = SearchFilter(query="Raft")
        items, count = query_notes(self.vault_root, sf)
        self.assertEqual(count, 2)
        self.assertEqual(items[0].filename, "Note Verified.md")
        self.assertEqual(items[0].trust_tier, "human-reviewed")
        self.assertEqual(items[1].filename, "Note Unverified.md")
        self.assertEqual(items[1].trust_tier, "unverified")

    def test_stale_note_penalized(self) -> None:
        """Verify expired note is penalized below fresh note in the same domain."""
        past_iso = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.create_note(
            domain="01 - Projects",
            filename="Active Migration.md",
            content=(
                "---\n"
                "title: \"Database Migration Plan\"\n"
                "type: project-note\n"
                "status: active\n"
                "---\n\n"
                "Database migration strategies for sqlite engine.\n"
            ),
        )

        self.create_note(
            domain="01 - Projects",
            filename="Expired Migration.md",
            content=(
                f"---\n"
                f"title: \"Database Migration Plan\"\n"
                f"type: project-note\n"
                f"status: active\n"
                f"stale_after: \"{past_iso}\"\n"
                f"---\n\n"
                f"Database migration strategies for sqlite engine.\n"
            ),
        )

        sf = SearchFilter(query="database migration")
        items, count = query_notes(self.vault_root, sf)
        self.assertEqual(count, 2)
        self.assertEqual(items[0].filename, "Active Migration.md")
        self.assertFalse(items[0].is_stale)
        self.assertEqual(items[1].filename, "Expired Migration.md")
        self.assertTrue(items[1].is_stale)


if __name__ == "__main__":
    import unittest
    unittest.main()

