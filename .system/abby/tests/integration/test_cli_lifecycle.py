"""CLI integration tests for abby move, archive, dry-run, and stream piping (Tier 3)."""

from __future__ import annotations

import json
import os
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
    from tests.support import Tier3CliTestCase
except ModuleNotFoundError:
    from support import Tier3CliTestCase


class TestCliLifecycle(Tier3CliTestCase):
    """Tier 3 integration tests for move, archive, and lifecycle piping."""

    def test_cli_move_basic_text_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Roadmap"])
        code, out, err = self.invoke_cli(
            ["move", "00 - Inbox/Roadmap.md", "projects/Roadmap"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Roadmap/Roadmap.md")
        self.assertEqual(err, "")

        # Verify on disk
        self.assert_file_exists("01 - Projects/Roadmap/Roadmap.md")
        self.assert_file_not_exists("00 - Inbox/Roadmap.md")

    def test_cli_move_json_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Architecture"])
        code, out, _ = self.invoke_cli(
            ["--json", "move", "Architecture", "projects/Core"]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertEqual(data["source_path"], "00 - Inbox/Architecture.md")
        self.assertEqual(data["target_path"], "01 - Projects/Core/Architecture.md")
        self.assertEqual(data["title"], "Architecture")
        self.assertEqual(data["previous_status"], "unprocessed")
        self.assertEqual(data["new_status"], "active")
        self.assertIn("timestamp", data)

    def test_cli_move_collision(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Duplicate"])
        code1, out1, _ = self.invoke_cli(["move", "Duplicate", "projects/Shared"])
        self.assertEqual(code1, 0)
        self.assertEqual(out1.strip(), "01 - Projects/Shared/Duplicate.md")

        self.invoke_cli(["new", "Duplicate"])
        code2, out2, _ = self.invoke_cli(["move", "Duplicate", "projects/Shared"])
        self.assertEqual(code2, 0)
        self.assertEqual(out2.strip(), "01 - Projects/Shared/Duplicate (1).md")

        self.assert_file_exists("01 - Projects/Shared/Duplicate.md")
        self.assert_file_exists("01 - Projects/Shared/Duplicate (1).md")

    def test_cli_move_missing_args_exits_2(self) -> None:
        code, _, err = self.invoke_cli(["move"])
        self.assertEqual(code, 2)

        code, _, err = self.invoke_cli(["move", "NoteOnly"])
        self.assertEqual(code, 2)

        code, out, _ = self.invoke_cli(["--json", "move"])
        self.assertEqual(code, 2)
        data = json.loads(out)
        self.assertFalse(data["success"])

    def test_cli_move_not_found_exits_1(self) -> None:
        self.init_vault()
        code, out, err = self.invoke_cli(["move", "NonExistentNote", "projects/Apollo"])
        self.assertEqual(code, 1)
        self.assertIn("not found in vault", err)

        code, out, _ = self.invoke_cli(
            ["--json", "move", "NonExistentNote", "projects/Apollo"]
        )
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertFalse(data["success"])
        self.assertIn("not found in vault", data["error"])

    def test_cli_move_invalid_target_domain_exits_1(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "ValidNote"])
        code, out, err = self.invoke_cli(["move", "ValidNote", "bad_domain"])
        self.assertEqual(code, 1)
        self.assertIn("Invalid domain 'bad_domain'", err)

    def test_cli_archive_basic_text_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Old Spec"])
        self.invoke_cli(["move", "Old Spec", "projects/Legacy"])
        code, out, err = self.invoke_cli(
            ["archive", "01 - Projects/Legacy/Old Spec.md"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "04 - Archives/Old Spec.md")
        self.assertEqual(err, "")

        self.assert_file_exists("04 - Archives/Old Spec.md")
        self.assert_file_not_exists("01 - Projects/Legacy/Old Spec.md")

    def test_cli_archive_json_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Old Research"])
        code, out, _ = self.invoke_cli(["--json", "archive", "Old Research"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertEqual(data["source_path"], "00 - Inbox/Old Research.md")
        self.assertEqual(data["target_path"], "04 - Archives/Old Research.md")
        self.assertEqual(data["title"], "Old Research")
        self.assertIn("archived_at", data)

    def test_cli_archive_missing_args_exits_2(self) -> None:
        code, _, err = self.invoke_cli(["archive"])
        self.assertEqual(code, 2)

        code, out, _ = self.invoke_cli(["--json", "archive"])
        self.assertEqual(code, 2)
        data = json.loads(out)
        self.assertFalse(data["success"])

    def test_cli_archive_not_found_exits_1(self) -> None:
        self.init_vault()
        code, out, err = self.invoke_cli(["archive", "NonExistent"])
        self.assertEqual(code, 1)
        self.assertIn("not found in vault", err)

        code, out, _ = self.invoke_cli(["--json", "archive", "NonExistent"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertFalse(data["success"])

    def test_cli_move_dry_run_text_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Dry Move Note"])
        code, out, err = self.invoke_cli(
            ["move", "00 - Inbox/Dry Move Note.md", "projects/Preview", "--dry-run"]
        )
        self.assertEqual(code, 0)
        self.assertIn("[DRY-RUN] Planned move:", out)
        self.assertIn("00 - Inbox/Dry Move Note.md", out)
        self.assertIn("01 - Projects/Preview/Dry Move Note.md", out)
        self.assertIn("(status: active, type: project-note)", out)
        self.assertEqual(err, "")

        # Assert non-mutation on disk
        self.assert_file_exists("00 - Inbox/Dry Move Note.md")
        self.assert_file_not_exists("01 - Projects/Preview/Dry Move Note.md")

    def test_cli_move_dry_run_json_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Dry Move JSON Note"])
        code, out, _ = self.invoke_cli(
            ["--json", "move", "Dry Move JSON Note", "areas/Finance", "--dry-run"]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertTrue(data["is_dry_run"])
        self.assertEqual(data["source_path"], "00 - Inbox/Dry Move JSON Note.md")
        self.assertEqual(
            data["target_path"], "02 - Areas/Finance/Dry Move JSON Note.md"
        )
        self.assertEqual(data["new_status"], "active")

        # Assert non-mutation on disk
        self.assert_file_exists("00 - Inbox/Dry Move JSON Note.md")
        self.assert_file_not_exists("02 - Areas/Finance/Dry Move JSON Note.md")

    def test_cli_archive_dry_run_text_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Dry Archive Note"])
        code, out, err = self.invoke_cli(
            ["archive", "00 - Inbox/Dry Archive Note.md", "--dry-run"]
        )
        self.assertEqual(code, 0)
        self.assertIn("[DRY-RUN] Planned archive:", out)
        self.assertIn("00 - Inbox/Dry Archive Note.md", out)
        self.assertIn("04 - Archives/Dry Archive Note.md", out)
        self.assertEqual(err, "")

        # Assert non-mutation on disk
        self.assert_file_exists("00 - Inbox/Dry Archive Note.md")
        self.assert_file_not_exists("04 - Archives/Dry Archive Note.md")

    def test_cli_archive_dry_run_json_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Dry Archive JSON Note"])
        code, out, _ = self.invoke_cli(
            ["--json", "archive", "Dry Archive JSON Note", "--dry-run"]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertTrue(data["is_dry_run"])
        self.assertEqual(data["source_path"], "00 - Inbox/Dry Archive JSON Note.md")
        self.assertEqual(data["target_path"], "04 - Archives/Dry Archive JSON Note.md")

        # Assert non-mutation on disk
        self.assert_file_exists("00 - Inbox/Dry Archive JSON Note.md")
        self.assert_file_not_exists("04 - Archives/Dry Archive JSON Note.md")

    def test_cli_stream_isolation_and_piping(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Stream Note 1"])
        self.invoke_cli(["new", "Stream Note 2"])
        self.invoke_cli(["new", "Stream Note 3"])

        # 1. Verify stdout contains strictly relative paths without decoration
        code, out, err = self.invoke_cli(["list", "inbox"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertTrue(line.startswith("00 - Inbox/"))
            self.assertTrue(line.endswith(".md"))
            # File referenced by stdout line must exist on disk
            self.assert_file_exists(line)

        # 2. Simulate pipeline: head -n 1 -> abby move -> abby archive
        first_path = lines[0]
        move_code, move_out, move_err = self.invoke_cli(
            ["move", first_path, "projects/Pipeline"]
        )
        self.assertEqual(move_code, 0)
        self.assertEqual(move_err, "")
        moved_path = move_out.strip()
        self.assertEqual(moved_path, "01 - Projects/Pipeline/Stream Note 1.md")
        self.assert_file_exists(moved_path)

        archive_code, archive_out, archive_err = self.invoke_cli(
            ["archive", moved_path]
        )
        self.assertEqual(archive_code, 0)
        self.assertEqual(archive_err, "")
        archived_path = archive_out.strip()
        self.assertEqual(archived_path, "04 - Archives/Stream Note 1.md")


if __name__ == "__main__":
    unittest.main()

