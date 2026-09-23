"""Integration tests for active backlink materialization and archive exclusion.

Feature: 015-cognitive-graph-search
User Story 2: Active Backlink Centrality Materialization (Priority: P1)
"""

from __future__ import annotations

import sys
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
from abby.models.search import SearchFilter


class TestCacheBacklinksIntegration(IsolatedVaultTestCase):
    """Integration tests verifying active backlink computation and archive exclusion."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_backlink_materialization_and_deduplication(self) -> None:
        """Verify active_backlinks counts distinct referring notes across non-archive domains."""
        # 1. Target Hub note
        self.create_note(
            domain="03 - Resources",
            filename="Distributed Systems.md",
            content=(
                "---\n"
                "title: \"Distributed Systems\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "---\n\n"
                "Map of Content for distributed systems concepts.\n"
            ),
        )

        # 2. Source note in Projects with multiple links to same target
        self.create_note(
            domain="01 - Projects",
            filename="Cluster Orchestrator.md",
            content=(
                "---\n"
                "title: \"Cluster Orchestrator\"\n"
                "type: project-note\n"
                "status: active\n"
                "---\n\n"
                "Built upon [[Distributed Systems]]. Check [[Distributed Systems#Overview|overview]] as well.\n"
            ),
        )

        # 3. Source note in Areas with single link
        self.create_note(
            domain="02 - Areas",
            filename="Infrastructure Engineering.md",
            content=(
                "---\n"
                "title: \"Infrastructure Engineering\"\n"
                "type: area-note\n"
                "status: active\n"
                "---\n\n"
                "Reference reading: [[Distributed Systems]].\n"
            ),
        )

        # 4. Source note in Archives (must be ignored)
        self.create_note(
            domain="04 - Archives",
            filename="Old Mesos Setup.md",
            content=(
                "---\n"
                "title: \"Old Mesos Setup\"\n"
                "type: archive-note\n"
                "status: archived\n"
                "---\n\n"
                "Referenced [[Distributed Systems]] frequently in 2021.\n"
            ),
        )

        # Sync cache and query notes
        sync_cache(self.vault_root)
        db_path = get_cache_db_path(self.vault_root)
        conn = get_db_connection(db_path)
        try:
            cursor = conn.execute(
                "SELECT path, active_backlinks FROM notes WHERE path = '03 - Resources/Distributed Systems.md';"
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            # Distinct sources: Projects (1) + Areas (1) = 2. Archives excluded.
            self.assertEqual(row[1], 2)
        finally:
            conn.close()

    def test_archive_backlink_exclusion(self) -> None:
        """Verify notes referenced only by archive notes receive 0 active backlinks."""
        self.create_note(
            domain="03 - Resources",
            filename="Ancient Protocol.md",
            content=(
                "---\n"
                "title: \"Ancient Protocol\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "---\n\n"
                "Obsolete networking specification.\n"
            ),
        )

        self.create_note(
            domain="04 - Archives",
            filename="Legacy Project A.md",
            content="---\ntitle: \"Legacy A\"\ntype: archive-note\nstatus: archived\n---\n\nSee [[Ancient Protocol]].\n",
        )

        self.create_note(
            domain="04 - Archives",
            filename="Legacy Project B.md",
            content="---\ntitle: \"Legacy B\"\ntype: archive-note\nstatus: archived\n---\n\nSee [[Ancient Protocol]].\n",
        )

        sync_cache(self.vault_root)
        db_path = get_cache_db_path(self.vault_root)
        conn = get_db_connection(db_path)
        try:
            cursor = conn.execute(
                "SELECT active_backlinks FROM notes WHERE path = '03 - Resources/Ancient Protocol.md';"
            )
            row = cursor.fetchone()
            self.assertEqual(row[0], 0)
        finally:
            conn.close()

    def test_backlink_ranking_boost(self) -> None:
        """Verify note with active backlinks ranks above note with 0 backlinks under identical BM25 match."""
        # Hub note
        self.create_note(
            domain="03 - Resources",
            filename="Kafka Central Hub.md",
            content=(
                "---\n"
                "title: \"Kafka Streaming Engine\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "---\n\n"
                "Kafka message broker architecture and semantics.\n"
            ),
        )

        # Leaf note with same BM25 relevance
        self.create_note(
            domain="03 - Resources",
            filename="Kafka Client Config.md",
            content=(
                "---\n"
                "title: \"Kafka Streaming Engine\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "---\n\n"
                "Kafka message broker architecture and semantics.\n"
            ),
        )

        # Create 4 referring notes pointing to Kafka Central Hub
        for i in range(4):
            self.create_note(
                domain="01 - Projects",
                filename=f"Pipeline {i}.md",
                content=f"---\ntitle: \"Pipeline {i}\"\ntype: project-note\nstatus: active\n---\n\nPublishes to [[Kafka Central Hub]].\n",
            )

        sf = SearchFilter(query="Kafka Streaming Engine")
        items, count = query_notes(self.vault_root, sf)
        self.assertEqual(count, 2)
        # Central Hub must rank first due to backlink multiplier
        self.assertEqual(items[0].filename, "Kafka Central Hub.md")
        self.assertEqual(items[0].active_backlinks, 4)
        self.assertEqual(items[1].filename, "Kafka Client Config.md")
        self.assertEqual(items[1].active_backlinks, 0)


if __name__ == "__main__":
    import unittest
    unittest.main()

