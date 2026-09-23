"""Unit tests for pure cognitive scoring and SQLite function registration."""

from __future__ import annotations

import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from abby.core.cache import get_db_connection
from abby.core.scoring import (
    DOMAIN_WEIGHTS,
    GRAPH_MAX_MULTIPLIER,
    STALENESS_PENALTY,
    TRUST_MULTIPLIERS,
    compute_cognitive_multiplier,
    compute_domain_multiplier,
    compute_graph_multiplier,
    compute_staleness_multiplier,
    compute_trust_multiplier,
)


class TestCognitiveScoring(unittest.TestCase):
    """Test mathematical correctness and edge cases of scoring components."""

    def test_domain_multipliers(self) -> None:
        self.assertAlmostEqual(compute_domain_multiplier("03 - Resources"), 1.20)
        self.assertAlmostEqual(compute_domain_multiplier("01 - Projects"), 1.00)
        self.assertAlmostEqual(compute_domain_multiplier("02 - Areas"), 1.00)
        self.assertAlmostEqual(compute_domain_multiplier("00 - Inbox"), 0.80)
        self.assertAlmostEqual(compute_domain_multiplier("04 - Archives"), 0.35)
        self.assertAlmostEqual(compute_domain_multiplier(None), 1.00)
        self.assertAlmostEqual(compute_domain_multiplier("unknown-domain"), 1.00)

    def test_trust_multipliers(self) -> None:
        self.assertAlmostEqual(compute_trust_multiplier("human-reviewed"), 1.25)
        self.assertAlmostEqual(compute_trust_multiplier("machine-confirmed"), 1.00)
        self.assertAlmostEqual(compute_trust_multiplier("unverified"), 0.90)
        self.assertAlmostEqual(compute_trust_multiplier(None), 0.90)
        self.assertAlmostEqual(compute_trust_multiplier("other"), 0.90)

    def test_staleness_multipliers(self) -> None:
        self.assertAlmostEqual(compute_staleness_multiplier(None), 1.00)
        self.assertAlmostEqual(compute_staleness_multiplier(""), 1.00)
        self.assertAlmostEqual(compute_staleness_multiplier("2099-01-01T00:00:00Z"), 1.00)
        self.assertAlmostEqual(compute_staleness_multiplier("2020-01-01T00:00:00Z"), 0.60)

    def test_graph_multipliers(self) -> None:
        self.assertAlmostEqual(compute_graph_multiplier(0), 1.00)
        self.assertAlmostEqual(compute_graph_multiplier(None), 1.00)
        self.assertAlmostEqual(compute_graph_multiplier(-5), 1.00)
        self.assertAlmostEqual(compute_graph_multiplier("invalid"), 1.00)

        self.assertAlmostEqual(compute_graph_multiplier(1), 1.15)
        self.assertAlmostEqual(compute_graph_multiplier(3), 1.30)
        self.assertAlmostEqual(compute_graph_multiplier(7), 1.45)
        self.assertAlmostEqual(compute_graph_multiplier(15), 1.60)
        self.assertAlmostEqual(compute_graph_multiplier(31), 1.75)
        self.assertAlmostEqual(compute_graph_multiplier(32), 1.75)
        self.assertAlmostEqual(compute_graph_multiplier(100), 1.75)

    def test_composite_scoring_archetypes(self) -> None:
        # Archetype 1: Human Evergreen Hub (03 - Resources, human-reviewed, fresh, 8 links)
        # 1.20 * 1.25 * 1.00 * (1.0 + 0.15 * log2(9)) ≈ 2.2132
        expected_hub = 1.20 * 1.25 * 1.00 * (1.0 + 0.15 * math.log2(9))
        hub_score = compute_cognitive_multiplier("03 - Resources", "human-reviewed", None, 8)
        self.assertAlmostEqual(hub_score, expected_hub, places=4)
        self.assertAlmostEqual(hub_score, 2.2132, places=3)

        # Archetype 2: Active Project Anchor (01 - Projects, machine-confirmed, fresh, 3 links)
        # 1.00 * 1.00 * 1.00 * 1.30 = 1.30
        anchor_score = compute_cognitive_multiplier("01 - Projects", "machine-confirmed", None, 3)
        self.assertAlmostEqual(anchor_score, 1.30, places=4)

        # Archetype 3: Fresh Atomic Note (03 - Resources, machine-confirmed, fresh, 0 links)
        # 1.20 * 1.00 * 1.00 * 1.00 = 1.20
        atomic_score = compute_cognitive_multiplier("03 - Resources", "machine-confirmed", None, 0)
        self.assertAlmostEqual(atomic_score, 1.20, places=4)

        # Archetype 4: Raw Staging Dump (00 - Inbox, unverified, fresh, 0 links)
        # 0.80 * 0.90 * 1.00 * 1.00 = 0.72
        inbox_score = compute_cognitive_multiplier("00 - Inbox", "unverified", None, 0)
        self.assertAlmostEqual(inbox_score, 0.72, places=4)

        # Archetype 5: Archived Expired Note (04 - Archives, unverified, stale, 0 links)
        # 0.35 * 0.90 * 0.60 * 1.00 = 0.189
        archive_score = compute_cognitive_multiplier("04 - Archives", "unverified", "2020-01-01T00:00:00Z", 0)
        self.assertAlmostEqual(archive_score, 0.189, places=4)

        # Priority ranking assertion
        self.assertTrue(hub_score > anchor_score > atomic_score > inbox_score > archive_score)

    def test_sqlite_function_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_vault.db"
            conn = get_db_connection(db_path)
            try:
                cursor = conn.execute(
                    "SELECT COGNITIVE_RANK_MULTIPLIER(?, ?, ?, ?);",
                    ("03 - Resources", "human-reviewed", None, 8),
                )
                val = cursor.fetchone()[0]
                expected = 1.20 * 1.25 * 1.00 * (1.0 + 0.15 * math.log2(9))
                self.assertAlmostEqual(val, expected, places=4)

                # Test stale archive in SQLite
                cursor = conn.execute(
                    "SELECT COGNITIVE_RANK_MULTIPLIER(?, ?, ?, ?);",
                    ("04 - Archives", "unverified", "2020-01-01T00:00:00Z", 0),
                )
                val = cursor.fetchone()[0]
                self.assertAlmostEqual(val, 0.189, places=4)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

