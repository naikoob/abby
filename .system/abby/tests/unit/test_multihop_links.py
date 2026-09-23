"""Unit tests for multi-hop graph traversal with cycle detection (User Story 6, T026)."""

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

from abby.constants import DEFAULT_CACHE_DB
from abby.core.cache import get_db_connection, sync_cache
from abby.core.graph import (
    format_backlinks_text,
    format_outbound_links_text,
    query_backlinks,
    query_outbound_links,
)
from abby.models.links import BacklinkOccurrence, BacklinkSummary, NoteLinkRecord


class TestMultihopTraversal(IsolatedVaultTestCase):
    """Test multi-hop outbound and backlink traversal with cycle detection."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def _setup_linear_chain(self) -> None:
        """Seed A -> B -> C -> D chain."""
        self.create_note(
            domain="01 - Projects",
            filename="Alpha.md",
            title="Alpha",
            body="Links to [[Beta]].",
        )
        self.create_note(
            domain="01 - Projects",
            filename="Beta.md",
            title="Beta",
            body="Links to [[Gamma]].",
        )
        self.create_note(
            domain="03 - Resources",
            filename="Gamma.md",
            title="Gamma",
            body="Links to [[Delta]].",
        )
        self.create_note(
            domain="03 - Resources",
            filename="Delta.md",
            title="Delta",
            body="Leaf node.",
        )
        sync_cache(self.vault_root)

    def test_outbound_depth_1(self) -> None:
        self._setup_linear_chain()
        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            records = query_outbound_links(conn, "01 - Projects/Alpha.md", depth=1)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].target_title, "Beta")
            self.assertEqual(records[0].depth, 1)
        finally:
            conn.close()

    def test_outbound_depth_2(self) -> None:
        self._setup_linear_chain()
        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            records = query_outbound_links(conn, "01 - Projects/Alpha.md", depth=2)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].target_title, "Beta")
            self.assertEqual(records[0].depth, 1)
            self.assertEqual(records[1].target_title, "Gamma")
            self.assertEqual(records[1].depth, 2)
        finally:
            conn.close()

    def test_outbound_depth_3(self) -> None:
        self._setup_linear_chain()
        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            records = query_outbound_links(conn, "01 - Projects/Alpha.md", depth=3)
            self.assertEqual(len(records), 3)
            self.assertEqual(records[0].target_title, "Beta")
            self.assertEqual(records[0].depth, 1)
            self.assertEqual(records[1].target_title, "Gamma")
            self.assertEqual(records[1].depth, 2)
            self.assertEqual(records[2].target_title, "Delta")
            self.assertEqual(records[2].depth, 3)
        finally:
            conn.close()

    def test_outbound_cycle_detection(self) -> None:
        """Cycle: NodeA -> NodeB -> NodeA."""
        self.create_note(
            domain="01 - Projects",
            filename="NodeA.md",
            title="NodeA",
            body="Links to [[NodeB]].",
        )
        self.create_note(
            domain="01 - Projects",
            filename="NodeB.md",
            title="NodeB",
            body="Links to [[NodeA]].",
        )
        sync_cache(self.vault_root)

        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            records = query_outbound_links(conn, "01 - Projects/NodeA.md", depth=3)
            # Should have NodeA -> NodeB (depth 1) and NodeB -> NodeA (depth 2)
            # and MUST NOT loop endlessly
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].target_title, "NodeB")
            self.assertEqual(records[0].depth, 1)
            self.assertEqual(records[1].target_title, "NodeA")
            self.assertEqual(records[1].depth, 2)
        finally:
            conn.close()

    def test_backlinks_depth_2(self) -> None:
        self._setup_linear_chain()
        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            # Query backlinks for Gamma (Beta -> Gamma, and Alpha -> Beta)
            summary = query_backlinks(
                conn, "03 - Resources/Gamma.md", "Gamma", depth=2
            )
            self.assertEqual(summary.total_backlinks, 2)
            self.assertEqual(summary.backlinks[0].source_path, "01 - Projects/Beta.md")
            self.assertEqual(summary.backlinks[0].depth, 1)
            self.assertEqual(summary.backlinks[1].source_path, "01 - Projects/Alpha.md")
            self.assertEqual(summary.backlinks[1].depth, 2)
        finally:
            conn.close()

    def test_backlinks_cycle_detection(self) -> None:
        """Cycle: NodeX -> NodeY -> NodeX."""
        self.create_note(
            domain="01 - Projects",
            filename="NodeX.md",
            title="NodeX",
            body="Links to [[NodeY]].",
        )
        self.create_note(
            domain="01 - Projects",
            filename="NodeY.md",
            title="NodeY",
            body="Links to [[NodeX]].",
        )
        sync_cache(self.vault_root)

        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            summary = query_backlinks(
                conn, "01 - Projects/NodeX.md", "NodeX", depth=3
            )
            self.assertEqual(len(summary.backlinks), 2)
            self.assertEqual(summary.backlinks[0].depth, 1)
            self.assertEqual(summary.backlinks[1].depth, 2)
        finally:
            conn.close()

    def test_isolated_note_depth_2(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Island.md",
            title="Island",
            body="No links whatsoever.",
        )
        sync_cache(self.vault_root)

        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            records = query_outbound_links(conn, "03 - Resources/Island.md", depth=2)
            self.assertEqual(records, [])
            summary = query_backlinks(
                conn, "03 - Resources/Island.md", "Island", depth=2
            )
            self.assertEqual(summary.backlinks, [])
        finally:
            conn.close()

    def test_formatting_with_depth_sections(self) -> None:
        records = [
            NoteLinkRecord(
                source_path="01 - Projects/Alpha.md",
                target_title="Beta",
                resolved_path="01 - Projects/Beta.md",
                depth=1,
            ),
            NoteLinkRecord(
                source_path="01 - Projects/Beta.md",
                target_title="Gamma",
                resolved_path="03 - Resources/Gamma.md",
                depth=2,
            ),
        ]
        text = format_outbound_links_text(records)
        self.assertIn("## Depth 1 (Direct)", text)
        self.assertIn("01 - Projects/Beta.md", text)
        self.assertIn("## Depth 2 (Transitive)", text)
        self.assertIn("03 - Resources/Gamma.md", text)

    def test_formatting_single_depth_without_sections(self) -> None:
        records = [
            NoteLinkRecord(
                source_path="01 - Projects/Alpha.md",
                target_title="Beta",
                resolved_path="01 - Projects/Beta.md",
                depth=1,
            ),
        ]
        text = format_outbound_links_text(records)
        self.assertNotIn("## Depth", text)
        self.assertEqual(text, "01 - Projects/Beta.md")

    def test_backlink_formatting_with_depth_sections(self) -> None:
        summary = BacklinkSummary(
            target_note="03 - Resources/Gamma.md",
            target_title="Gamma",
            backlinks=[
                BacklinkOccurrence(source_path="01 - Projects/Beta.md", line_number=1, depth=1),
                BacklinkOccurrence(source_path="01 - Projects/Alpha.md", line_number=1, depth=2),
            ],
        )
        text = format_backlinks_text(summary)
        self.assertIn("## Depth 1 (Direct)", text)
        self.assertIn("01 - Projects/Beta.md", text)
        self.assertIn("## Depth 2 (Transitive)", text)
        self.assertIn("01 - Projects/Alpha.md", text)

