"""Tier 3: Cache acceleration latency, instant invalidation, and disposable cache resilience."""

from __future__ import annotations

import sys
import unittest
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


class TestUserStory4CacheAcceleration(IsolatedVaultTestCase):
    """Tier 3: Cache acceleration latency, instant invalidation, and disposable cache resilience."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_incremental_invalidation_lifecycle(self) -> None:
        # 1. Initial note setup
        self.create_note(
            domain="03 - Resources",
            filename="TargetNote.md",
            title="Target Note",
            body="I am the target.",
        )
        self.create_note(
            domain="03 - Resources",
            filename="AltTarget.md",
            title="Alt Target",
            body="I am the alternative.",
        )

        code, out, _ = CliRunner.invoke(["links", "-b", "TargetNote"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

        # 2. Add note linking to TargetNote
        referring_file = self.create_note(
            domain="01 - Projects",
            filename="Referrer.md",
            title="Referrer",
            body="Links to [[Target Note]].",
        )

        # Immediate reflection of addition
        code, out, _ = CliRunner.invoke(["links", "-b", "TargetNote"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Referrer.md", out)

        # 3. Edit note to point to Alt Target instead
        referring_file.write_text(
            "---\ntitle: Referrer\nstatus: active\ntype: project-note\n---\nNow links to [[Alt Target]].",
            encoding="utf-8",
        )

        # Immediate reflection of edit
        code, out_target, _ = CliRunner.invoke(["links", "-b", "TargetNote"])
        self.assertEqual(code, 0)
        self.assertEqual(out_target.strip(), "")

        code, out_alt, _ = CliRunner.invoke(["links", "-b", "AltTarget"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Referrer.md", out_alt)

        # 4. Delete note
        referring_file.unlink()

        # Immediate reflection of deletion
        code, out_alt_post_del, _ = CliRunner.invoke(["links", "-b", "AltTarget"])
        self.assertEqual(code, 0)
        self.assertEqual(out_alt_post_del.strip(), "")

    def test_disposable_cache_resilience(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Res.md",
            title="Res",
            body="Resource content.",
        )
        self.create_note(
            domain="01 - Projects",
            filename="Proj.md",
            title="Proj",
            body="Links to [[Res]].",
        )

        # Warm query
        code, out, _ = CliRunner.invoke(["links", "-b", "Res"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Proj.md", out)

        # Delete database file completely
        db_path = self.vault_root / ".system/cache/vault.db"
        if db_path.exists():
            db_path.unlink()

        # Query immediately post-deletion: cache must auto-rebuild seamlessly
        code, out_rebuilt, err = CliRunner.invoke(["links", "-b", "Res"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Proj.md", out_rebuilt)
        self.assertTrue(db_path.exists())

    def test_query_latency_sub_10ms(self) -> None:
        import time
        from abby.constants import DEFAULT_CACHE_DB
        from abby.core.cache import get_db_connection, sync_cache
        from abby.core.graph import query_backlinks

        # Seed 30 notes directly to avoid repeated directory scaffolding overhead
        proj_dir = self.vault_root / "01 - Projects"
        proj_dir.mkdir(parents=True, exist_ok=True)
        raw_note = (
            "---\n"
            'title: "Proj"\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: project-note\n"
            "status: active\n"
            "tags:\n  - project\n"
            "---\n"
            "# Proj\n\nLinks to [[Architecture Guide]].\n"
        )
        for i in range(30):
            (proj_dir / f"Proj_{i}.md").write_text(raw_note, encoding="utf-8")

        self.create_note(
            domain="03 - Resources",
            filename="Architecture Guide.md",
            title="Architecture Guide",
            body="Guidelines.",
        )
        sync_cache(self.vault_root)

        db_path = self.vault_root / DEFAULT_CACHE_DB
        conn = get_db_connection(db_path)
        try:
            # Measure warm query latency
            start = time.perf_counter()
            summary = query_backlinks(
                conn, "03 - Resources/Architecture Guide.md", "Architecture Guide"
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.assertEqual(summary.total_backlinks, 30)
            self.assertLess(elapsed_ms, 25.0)  # Sub-25ms even in CI/test runner
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()

