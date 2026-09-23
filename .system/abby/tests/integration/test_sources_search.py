"""Integration tests for SQLite FTS5 sources search indexing and discovery."""

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
    from tests.support import Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import Tier2FilesystemTestCase

from abby.core.cache import sync_cache
from abby.core.search import query_notes
from abby.models.search import SearchFilter


class TestSourcesSearchIntegration(Tier2FilesystemTestCase):
    """Test full-text search indexing of note sources metadata."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_sources_fts5_indexing(self) -> None:
        content = (
            "---\n"
            'title: "Raft Consensus Algorithm"\n'
            'description: "Distributed state machine replication using leader election."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - consensus\n"
            "  - distributed-systems\n"
            "sources:\n"
            '  - resource: "https://raft.github.io/raft.pdf"\n'
            '    id: "ongaro2014"\n'
            '    title: "In Search of an Understandable Consensus Algorithm"\n'
            '    author: "Diego Ongaro and John Ousterhout"\n'
            "    usage_count: 3\n"
            '    last_modified: "2014-05-20T00:00:00Z"\n'
            "---\n"
            "# Raft Consensus Algorithm\n\n"
            "Raft implements consensus by first electing a distinguished leader.\n"
        )
        self.create_note(
            domain="03 - Resources",
            filename="Raft Consensus.md",
            content=content,
        )

        # Sync cache to populate SQLite FTS5 index
        sync_cache(self.vault_root)

        # 1. Search by author
        items, _ = query_notes(self.vault_root, SearchFilter(query="Ongaro"))
        self.assertTrue(any("Raft Consensus" in item.title for item in items))

        # 2. Search by title keyword in source
        items_title, _ = query_notes(
            self.vault_root, SearchFilter(query="Understandable")
        )
        self.assertTrue(any("Raft Consensus" in item.title for item in items_title))

        # 3. Search by resource url / filename fragment
        items_res, _ = query_notes(self.vault_root, SearchFilter(query="raft.pdf"))
        self.assertTrue(any("Raft Consensus" in item.title for item in items_res))

        # 4. Search by source id
        items_id, _ = query_notes(self.vault_root, SearchFilter(query="ongaro2014"))
        self.assertTrue(any("Raft Consensus" in item.title for item in items_id))


if __name__ == "__main__":
    import unittest

    unittest.main()

