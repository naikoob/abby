"""CLI integration tests for abby find filters, metadata, dates, cache rebuild, and limits (Tier 3)."""

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


class TestCliFindFilters(Tier3CliTestCase):
    """Tier 3 integration tests for abby find filtering, dates, cache sync, and limits."""

    def test_find_no_args_returns_all_notes(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Inbox Note 1"])
        self.invoke_cli(["new", "Inbox Note 2"])
        code, out, err = self.invoke_cli(["find"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = [line for line in out.strip().split("\n") if line]
        self.assertEqual(len(lines), 2)
        self.assertIn("00 - Inbox/Inbox Note 1.md", lines)
        self.assertIn("00 - Inbox/Inbox Note 2.md", lines)

    def test_find_metadata_filters(self) -> None:
        self.init_vault()
        self.create_note(
            "01 - Projects",
            "Kickoff.md",
            title="Kickoff Meeting",
            status="active",
            type_="project-note",
            tags=["backend", "urgent"],
        )
        self.create_note(
            "00 - Inbox",
            "InboxNote.md",
            title="Raw Idea",
            status="unprocessed",
            type_="inbox",
            tags=["idea"],
        )

        # Filter by status
        code, out, _ = self.invoke_cli(["find", "--status", "active"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Kickoff.md")

        # Filter by domain alias
        code, out, _ = self.invoke_cli(["find", "--domain", "inbox"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "00 - Inbox/InboxNote.md")

        # Filter by tag
        code, out, _ = self.invoke_cli(["find", "--tag", "backend"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Kickoff.md")

        # Filter by type
        code, out, _ = self.invoke_cli(["find", "--type", "project-note"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Kickoff.md")

    def test_find_json_mode(self) -> None:
        self.init_vault()
        self.create_note(
            "01 - Projects",
            "Apollo.md",
            title="Project Apollo",
            status="active",
            type_="project-note",
            tags=["space", "backend"],
        )

        code, out, err = self.invoke_cli(["--json", "find", "--domain", "projects"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        data = json.loads(out)
        self.assertEqual(data["domain"], "projects")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total_matches"], 1)
        self.assertEqual(len(data["notes"]), 1)
        note = data["notes"][0]
        self.assertEqual(note["filename"], "Apollo.md")
        self.assertEqual(note["path"], "01 - Projects/Apollo.md")
        self.assertEqual(note["title"], "Project Apollo")
        self.assertEqual(note["status"], "active")
        self.assertIn("space", note["tags"])
        self.assertIn("backend", note["tags"])

    def test_find_date_filters_cli(self) -> None:
        self.init_vault()
        self.create_note(
            "00 - Inbox",
            "Aug.md",
            content=(
                "---\n"
                'title: "August Note"\n'
                'created: "2026-08-15T10:00:00"\n'
                "type: inbox\n"
                "status: unprocessed\n"
                "tags: []\n"
                "---\n"
                "Body\n"
            ),
        )
        self.create_note(
            "00 - Inbox",
            "Sep.md",
            content=(
                "---\n"
                'title: "September Note"\n'
                'created: "2026-09-10T10:00:00"\n'
                "type: inbox\n"
                "status: unprocessed\n"
                "tags: []\n"
                "---\n"
                "Body\n"
            ),
        )

        code, out, _ = self.invoke_cli(["find", "--created-after", "2026-09-01"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "00 - Inbox/Sep.md")

        code, out, _ = self.invoke_cli(["find", "--created-before", "2026-09-01"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "00 - Inbox/Aug.md")

        # Invalid date exits with 2
        code, out, err = self.invoke_cli(["find", "--created-after", "bad-date"])
        self.assertEqual(code, 2)
        self.assertIn("Invalid date format", err)

    def test_find_cache_rebuild_and_missing_recovery(self) -> None:
        self.init_vault()
        self.create_note("00 - Inbox", "Note1.md", title="Note 1")

        # 1. First find run indexes note
        code1, out1, _ = self.invoke_cli(["find"])
        self.assertEqual(code1, 0)
        self.assertEqual(out1.strip(), "00 - Inbox/Note1.md")

        # 2. Delete cache database file manually
        cache_db = self.vault_root / ".system/cache/vault.db"
        self.assertTrue(cache_db.exists())
        cache_db.unlink()
        self.assertFalse(cache_db.exists())

        # 3. Next find run automatically recreates and reindexes
        code2, out2, _ = self.invoke_cli(["find"])
        self.assertEqual(code2, 0)
        self.assertEqual(out2.strip(), "00 - Inbox/Note1.md")
        self.assertTrue(cache_db.exists())

        # 4. Explicit rebuild flag -r / --rebuild-cache
        code3, out3, _ = self.invoke_cli(["find", "-r"])
        self.assertEqual(code3, 0)
        self.assertEqual(out3.strip(), "00 - Inbox/Note1.md")

    def test_find_auto_sync_on_external_mutation(self) -> None:
        self.init_vault()
        note_path = self.create_note(
            "00 - Inbox",
            "ObsidianNote.md",
            title="Initial Title",
            body="Initial body",
        )

        code1, out1, _ = self.invoke_cli(["find", "Initial"])
        self.assertEqual(code1, 0)
        self.assertEqual(out1.strip(), "00 - Inbox/ObsidianNote.md")

        # External edit simulating Obsidian writing to disk
        note_path.write_text(
            '---\ntitle: "Edited Outside"\ncreated: "2026-09-17T12:00:00"\ntype: inbox\nstatus: unprocessed\ntags: []\n---\nEdited body content.\n',
            encoding="utf-8",
        )
        stat = note_path.stat()
        os.utime(note_path, (stat.st_atime, stat.st_mtime + 5))

        # find immediately discovers the updated title and body
        code2, out2, _ = self.invoke_cli(["find", "Edited"])
        self.assertEqual(code2, 0)
        self.assertEqual(out2.strip(), "00 - Inbox/ObsidianNote.md")

        # External file deletion
        note_path.unlink()
        code3, out3, _ = self.invoke_cli(["find", "Edited"])
        self.assertEqual(code3, 0)
        self.assertEqual(out3, "")

    def test_find_limit_and_stream_isolation(self) -> None:
        self.init_vault()
        for i in range(5):
            self.create_note("00 - Inbox", f"Item_{i}.md", title=f"Item {i}")

        # Text mode with -n 2
        code, out, err = self.invoke_cli(["find", "-n", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = [l for l in out.strip().split("\n") if l]
        self.assertEqual(len(lines), 2)

        # JSON mode with -n 2: bounded count, total_matches is 5
        code, out_json, err = self.invoke_cli(["--json", "find", "-n", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        data = json.loads(out_json)
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["total_matches"], 5)
        self.assertEqual(len(data["notes"]), 2)

        # Negative limit exits with 2
        code, out, err = self.invoke_cli(["find", "-n", "-1"])
        self.assertEqual(code, 2)
        self.assertIn("Limit must be a positive integer", err)


if __name__ == "__main__":
    unittest.main()

