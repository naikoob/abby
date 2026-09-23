"""Unit and domain tests for note lifecycle, frontmatter mutation, and triage functionality (Tier 1 & 2)."""

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
    from tests.support import Tier1UnitTestCase, Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import Tier1UnitTestCase, Tier2FilesystemTestCase
from abby.core.lifecycle import (
    archive_note,
    list_domain_notes,
    move_note,
    resolve_destination_dir,
    resolve_move_collision,
)
from abby.models.okf import (
    ArchiveResult,
    MoveResult,
    TriageNoteItem,
)
from abby.services.okf_parser import parse_okf_frontmatter
from abby.services.okf_serializer import mutate_okf_frontmatter


class TestLifecycleFoundations(Tier1UnitTestCase):
    def test_parse_okf_frontmatter_block_tags(self) -> None:
        content = (
            "---\n"
            'title: "Architecture Review"\n'
            'created: "2026-09-17T10:00:00"\n'
            "type: inbox\n"
            "status: unprocessed\n"
            "tags:\n"
            "  - inbox\n"
            "  - backend\n"
            "---\n"
            "# Architecture Review\n\nContent here.\n"
        )
        parsed = parse_okf_frontmatter(content, default_title="Fallback")
        self.assertEqual(parsed["title"], "Architecture Review")
        self.assertEqual(parsed["created"], "2026-09-17T10:00:00")
        self.assertEqual(parsed["type"], "inbox")
        self.assertEqual(parsed["status"], "unprocessed")
        self.assertEqual(parsed["tags"], ["inbox", "backend"])
        self.assertIsNone(parsed["updated"])

    def test_parse_okf_frontmatter_inline_tags(self) -> None:
        content = (
            "---\n"
            'title: "Quick Note"\n'
            "status: active\n"
            "tags: [inbox, goals]\n"
            "---\n"
            "Body content\n"
        )
        parsed = parse_okf_frontmatter(content, default_title="Fallback")
        self.assertEqual(parsed["title"], "Quick Note")
        self.assertEqual(parsed["status"], "active")
        self.assertEqual(parsed["tags"], ["inbox", "goals"])

    def test_parse_okf_frontmatter_missing_frontmatter(self) -> None:
        content = "# Just A Header\nNo YAML frontmatter at all.\n"
        parsed = parse_okf_frontmatter(content, default_title="Default Title")
        self.assertEqual(parsed["title"], "Default Title")
        self.assertEqual(parsed["status"], "unprocessed")
        self.assertEqual(parsed["tags"], [])

    def test_parse_okf_frontmatter_crlf_endings(self) -> None:
        # CRLF (\r\n) line endings must not leave trailing quotes on title
        content = '---\r\ntitle: "CRLF Note"\r\nstatus: active\r\n---\r\nBody\r\n'
        parsed = parse_okf_frontmatter(content, default_title="Fallback")
        self.assertEqual(parsed["title"], "CRLF Note")
        self.assertEqual(parsed["status"], "active")

    def test_parse_okf_frontmatter_unescapes_yaml_quotes_and_slashes(self) -> None:
        # In double-quoted YAML: \" is unescaped to " and \\ is unescaped to \
        content = (
            "---\n"
            'title: "Quotes \\"and\\" C:\\\\Paths"\n'
            "tags:\n"
            '  - "custom \\"tag\\""\n'
            "---\n"
        )
        parsed = parse_okf_frontmatter(content, default_title="Fallback")
        self.assertEqual(parsed["title"], 'Quotes "and" C:\\Paths')
        self.assertEqual(parsed["tags"], ['custom "tag"'])

    def test_mutate_okf_frontmatter_preserves_body_and_block_refs(self) -> None:
        original = (
            "---\n"
            'title: "Sprint Goals"\n'
            'created: "2026-09-17T09:00:00"\n'
            "type: inbox\n"
            "status: unprocessed\n"
            "tags:\n"
            "  - inbox\n"
            "---\n"
            "# Sprint Goals\n"
            "Crucial requirement item ^block-ref-123\n"
        )
        updates = {
            "status": "active",
            "type": "project-note",
            "updated": "2026-09-17T12:00:00",
        }
        updated_content, prev_status = mutate_okf_frontmatter(original, updates)
        self.assertEqual(prev_status, "unprocessed")
        self.assertIn("status: active", updated_content)
        self.assertIn("type: project-note", updated_content)
        self.assertIn("updated: 2026-09-17T12:00:00", updated_content)
        self.assertIn('title: "Sprint Goals"', updated_content)
        self.assertIn("- inbox", updated_content)
        self.assertIn("Crucial requirement item ^block-ref-123", updated_content)

    def test_mutate_okf_frontmatter_crlf_preservation(self) -> None:
        original = '---\r\ntitle: "Note"\r\nstatus: unprocessed\r\n---\r\nBody\r\n'
        updates = {"status": "active"}
        updated_content, _ = mutate_okf_frontmatter(original, updates)
        self.assertIn("\r\n", updated_content)
        self.assertNotIn("\n\n", updated_content)
        self.assertIn("status: active\r\n", updated_content)

    def test_mutate_okf_frontmatter_backslash_replacement_safe(self) -> None:
        # Regex backreference patterns like \g<1> or \1 must not raise PatternError
        original = '---\ntitle: "Math Note"\nstatus: unprocessed\n---\nBody\n'
        updates = {"status": r"foo\g<1>bar"}
        updated_content, _ = mutate_okf_frontmatter(original, updates)
        self.assertIn(r"status: foo\g<1>bar", updated_content)

    def test_mutate_okf_frontmatter_injects_if_missing(self) -> None:
        original = "# Raw Markdown Note\nSome notes here without frontmatter.\n"
        updates = {
            "status": "active",
            "type": "area-note",
            "title": "Raw Markdown Note",
        }
        updated_content, prev_status = mutate_okf_frontmatter(original, updates)
        self.assertEqual(prev_status, "unprocessed")
        self.assertIn("status: active", updated_content)
        self.assertIn("type: area-note", updated_content)
        self.assertIn("Some notes here without frontmatter.", updated_content)

    def test_dataclass_serializations(self) -> None:
        triage_item = TriageNoteItem(
            filename="Goal.md",
            path="00 - Inbox/Goal.md",
            title="Goal",
            created="2026-09-17T10:00:00",
            age_days=1,
            status="unprocessed",
            tags=["inbox"],
        )
        t_dict = triage_item.to_dict()
        self.assertEqual(t_dict["filename"], "Goal.md")
        self.assertNotIn("updated", t_dict)

        move_res = MoveResult(
            success=True,
            source_path="00 - Inbox/Goal.md",
            target_path="01 - Projects/Apollo/Goal.md",
            title="Goal",
            previous_status="unprocessed",
            new_status="active",
            timestamp="2026-09-17T11:00:00",
        )
        self.assertTrue(move_res.to_dict()["success"])

        archive_res = ArchiveResult(
            success=True,
            source_path="01 - Projects/Apollo/Goal.md",
            target_path="04 - Archives/Goal.md",
            title="Goal",
            archived_at="2026-09-17T12:00:00",
        )
        self.assertTrue(archive_res.to_dict()["success"])


class TestListDomainNotes(Tier2FilesystemTestCase):
    def test_list_empty_or_missing_domain(self) -> None:
        canonical, items = list_domain_notes(self.vault_root, "inbox")
        self.assertEqual(canonical, "00 - Inbox")
        self.assertEqual(items, [])

    def test_list_invalid_domain_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            list_domain_notes(self.vault_root, "invalid_domain")

    def test_list_inbox_fifo_order_and_metadata(self) -> None:
        inbox = self.vault_root / "00 - Inbox"
        inbox.mkdir(parents=True)

        # Create note 2 (newer)
        note2 = inbox / "Note2.md"
        note2.write_text(
            "---\n"
            'title: "Second Note"\n'
            'created: "2026-09-17T12:00:00"\n'
            "status: unprocessed\n"
            "tags: [inbox]\n"
            "---\n"
            "Second note content\n",
            encoding="utf-8",
        )

        # Create note 1 (older)
        note1 = inbox / "Note1.md"
        note1.write_text(
            "---\n"
            'title: "First Note"\n'
            'created: "2026-09-17T10:00:00"\n'
            "status: unprocessed\n"
            "tags: [inbox, urgent]\n"
            "---\n"
            "First note content\n",
            encoding="utf-8",
        )

        # Create non-markdown file and hidden file
        (inbox / "image.png").write_text("binary", encoding="utf-8")
        (inbox / ".hidden.md").write_text("hidden", encoding="utf-8")

        canonical, items = list_domain_notes(self.vault_root, "inbox")
        self.assertEqual(canonical, "00 - Inbox")
        self.assertEqual(len(items), 2)
        # Oldest first: Note1 then Note2
        self.assertEqual(items[0].filename, "Note1.md")
        self.assertEqual(items[0].title, "First Note")
        self.assertEqual(items[0].path, "00 - Inbox/Note1.md")
        self.assertEqual(items[0].tags, ["inbox", "urgent"])

        self.assertEqual(items[1].filename, "Note2.md")
        self.assertEqual(items[1].title, "Second Note")

    def test_list_timezone_aware_notes(self) -> None:
        inbox = self.vault_root / "00 - Inbox"
        inbox.mkdir(parents=True)

        # Note with explicit timezone offset (+08:00)
        note_tz = inbox / "TzNote.md"
        note_tz.write_text(
            "---\n"
            'title: "Timezone Note"\n'
            'created: "2026-09-17T08:00:00+08:00"\n'
            "status: unprocessed\n"
            "---\n",
            encoding="utf-8",
        )

        # Note with UTC 'Z'
        note_utc = inbox / "UtcNote.md"
        note_utc.write_text(
            "---\n"
            'title: "UTC Note"\n'
            'created: "2026-09-17T00:00:00Z"\n'
            "status: unprocessed\n"
            "---\n",
            encoding="utf-8",
        )

        canonical, items = list_domain_notes(self.vault_root, "inbox")
        self.assertEqual(canonical, "00 - Inbox")
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertIsInstance(item.age_days, int)
            self.assertGreaterEqual(item.age_days, 0)

    def test_list_projects_recursive(self) -> None:
        project_sub = self.vault_root / "01 - Projects" / "Apollo"
        project_sub.mkdir(parents=True)

        note = project_sub / "Specs.md"
        note.write_text(
            "---\n"
            'title: "Apollo Specs"\n'
            'created: "2026-09-17T08:00:00"\n'
            "status: active\n"
            "---\n"
            "Specs body\n",
            encoding="utf-8",
        )

        canonical, items = list_domain_notes(self.vault_root, "projects")
        self.assertEqual(canonical, "01 - Projects")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].path, "01 - Projects/Apollo/Specs.md")
        self.assertEqual(items[0].title, "Apollo Specs")


class TestMoveResolutionAndBoundaries(Tier2FilesystemTestCase):
    def test_resolve_destination_dir_aliases(self) -> None:
        dest, canonical = resolve_destination_dir(self.vault_root, "projects/Apollo")
        self.assertEqual(dest, self.vault_root / "01 - Projects" / "Apollo")
        self.assertEqual(canonical, "01 - Projects")

        dest, canonical = resolve_destination_dir(self.vault_root, "areas/Finance")
        self.assertEqual(dest, self.vault_root / "02 - Areas" / "Finance")
        self.assertEqual(canonical, "02 - Areas")

        dest, canonical = resolve_destination_dir(self.vault_root, "resources")
        self.assertEqual(dest, self.vault_root / "03 - Resources")
        self.assertEqual(canonical, "03 - Resources")

        dest, canonical = resolve_destination_dir(
            self.vault_root, "01 - Projects/Apollo"
        )
        self.assertEqual(dest, self.vault_root / "01 - Projects" / "Apollo")
        self.assertEqual(canonical, "01 - Projects")

    def test_resolve_destination_dir_invalid_or_empty(self) -> None:
        with self.assertRaises(ValueError):
            resolve_destination_dir(self.vault_root, "")

        with self.assertRaises(ValueError):
            resolve_destination_dir(self.vault_root, "unknown_domain/Sub")

    def test_resolve_destination_dir_traversal_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_destination_dir(self.vault_root, "projects/../../.system")


class TestMoveOperationAndCollision(Tier2FilesystemTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.vault_root / "00 - Inbox").mkdir(parents=True)

    def test_resolve_move_collision(self) -> None:
        dest_dir = self.vault_root / "01 - Projects" / "Apollo"
        dest_dir.mkdir(parents=True)

        # No collision
        candidate = resolve_move_collision(dest_dir, "Kickoff.md")
        self.assertEqual(candidate.name, "Kickoff.md")

        # First collision
        (dest_dir / "Kickoff.md").write_text("existing", encoding="utf-8")
        candidate = resolve_move_collision(dest_dir, "Kickoff.md")
        self.assertEqual(candidate.name, "Kickoff (1).md")

        # Second collision
        (dest_dir / "Kickoff (1).md").write_text("existing 1", encoding="utf-8")
        candidate = resolve_move_collision(dest_dir, "Kickoff.md")
        self.assertEqual(candidate.name, "Kickoff (2).md")

    def test_move_note_atomic_update(self) -> None:
        source_file = self.vault_root / "00 - Inbox" / "Retro.md"
        source_file.write_text(
            "---\n"
            'title: "Retro"\n'
            'created: "2026-09-17T10:00:00"\n'
            "type: inbox\n"
            "status: unprocessed\n"
            "tags:\n"
            "  - sprint\n"
            "---\n"
            "# Retro\n\nKey takeaways ^block-takeaways\n",
            encoding="utf-8",
        )

        res = move_note(self.vault_root, "00 - Inbox/Retro.md", "projects/Alpha")

        self.assertTrue(res.success)
        self.assertEqual(res.source_path, "00 - Inbox/Retro.md")
        self.assertEqual(res.target_path, "01 - Projects/Alpha/Retro.md")
        self.assertEqual(res.title, "Retro")
        self.assertEqual(res.previous_status, "unprocessed")
        self.assertEqual(res.new_status, "active")

        # Source must be removed
        self.assertFalse(source_file.exists())

        # Destination must exist with mutated frontmatter
        dest_file = self.vault_root / "01 - Projects" / "Alpha" / "Retro.md"
        self.assertTrue(dest_file.exists())
        content = dest_file.read_text(encoding="utf-8")
        self.assertIn("status: active", content)
        self.assertIn("type: project-note", content)
        self.assertIn("updated:", content)
        self.assertIn("Key takeaways ^block-takeaways", content)
        self.assertIn("- sprint", content)

    def test_move_note_to_resources_updates_status_evergreen(self) -> None:
        source_file = self.vault_root / "00 - Inbox" / "Cheatsheet.md"
        source_file.write_text(
            "---\n"
            'title: "Cheatsheet"\n'
            "status: unprocessed\n"
            "---\n"
            "Reference guide.\n",
            encoding="utf-8",
        )

        res = move_note(self.vault_root, "Cheatsheet.md", "resources/Python")
        self.assertTrue(res.success)
        self.assertEqual(res.new_status, "evergreen")
        dest_file = self.vault_root / "03 - Resources" / "Python" / "Cheatsheet.md"
        self.assertTrue(dest_file.exists())
        content = dest_file.read_text(encoding="utf-8")
        self.assertIn("status: evergreen", content)
        self.assertIn("type: resource-note", content)

    def test_move_source_not_found_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            move_note(self.vault_root, "NonExistent.md", "projects/Apollo")

    def test_move_from_outside_domain_rejected(self) -> None:
        system_dir = self.vault_root / ".system"
        system_dir.mkdir(parents=True)
        system_file = system_dir / "internal.md"
        system_file.write_text("internal", encoding="utf-8")

        with self.assertRaises(ValueError):
            move_note(self.vault_root, ".system/internal.md", "projects/Apollo")

    def test_move_note_dry_run(self) -> None:
        source_file = self.vault_root / "00 - Inbox" / "Proposal.md"
        source_file.write_text(
            "---\n"
            'title: "Proposal"\n'
            'created: "2026-09-17T10:00:00"\n'
            "type: inbox\n"
            "status: unprocessed\n"
            "---\n"
            "Proposal content\n",
            encoding="utf-8",
        )

        res = move_note(
            self.vault_root, "00 - Inbox/Proposal.md", "projects/Alpha", dry_run=True
        )

        self.assertTrue(res.success)
        self.assertTrue(res.is_dry_run)
        self.assertEqual(res.source_path, "00 - Inbox/Proposal.md")
        self.assertEqual(res.target_path, "01 - Projects/Alpha/Proposal.md")
        self.assertEqual(res.title, "Proposal")
        self.assertEqual(res.previous_status, "unprocessed")
        self.assertEqual(res.new_status, "active")

        # Crucial non-mutation assertions
        self.assertTrue(source_file.exists())
        self.assertFalse(
            (self.vault_root / "01 - Projects" / "Alpha" / "Proposal.md").exists()
        )
        self.assertFalse((self.vault_root / "01 - Projects" / "Alpha").exists())

    def test_move_note_dry_run_collision(self) -> None:
        source_file = self.vault_root / "00 - Inbox" / "Proposal.md"
        source_file.write_text(
            '---\ntitle: "Proposal"\nstatus: unprocessed\n---\n', encoding="utf-8"
        )
        dest_dir = self.vault_root / "01 - Projects" / "Alpha"
        dest_dir.mkdir(parents=True)
        (dest_dir / "Proposal.md").write_text("existing", encoding="utf-8")

        res = move_note(
            self.vault_root, "00 - Inbox/Proposal.md", "projects/Alpha", dry_run=True
        )

        self.assertTrue(res.success)
        self.assertTrue(res.is_dry_run)
        self.assertEqual(res.target_path, "01 - Projects/Alpha/Proposal (1).md")
        self.assertTrue(source_file.exists())
        self.assertFalse((dest_dir / "Proposal (1).md").exists())


class TestArchiveOperation(Tier2FilesystemTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.vault_root / "01 - Projects" / "Apollo").mkdir(parents=True)

    def test_archive_note_basic(self) -> None:
        proj_file = self.vault_root / "01 - Projects" / "Apollo" / "Kickoff.md"
        proj_file.write_text(
            "---\n"
            'title: "Kickoff"\n'
            'created: "2026-09-17T09:00:00"\n'
            "status: active\n"
            "type: project-note\n"
            "---\n"
            "# Kickoff Meeting\nAll notes here.\n",
            encoding="utf-8",
        )

        res = archive_note(self.vault_root, "01 - Projects/Apollo/Kickoff.md")
        self.assertTrue(res.success)
        self.assertEqual(res.source_path, "01 - Projects/Apollo/Kickoff.md")
        self.assertEqual(res.target_path, "04 - Archives/Kickoff.md")
        self.assertEqual(res.title, "Kickoff")
        self.assertTrue(res.archived_at)

        # Source is removed
        self.assertFalse(proj_file.exists())

        # Destination exists in 04 - Archives
        dest = self.vault_root / "04 - Archives" / "Kickoff.md"
        self.assertTrue(dest.exists())
        content = dest.read_text(encoding="utf-8")
        self.assertIn("status: archived", content)
        self.assertIn("type: archive-note", content)
        self.assertIn("updated:", content)
        self.assertIn("All notes here.", content)

    def test_archive_note_collision_resolution(self) -> None:
        archives_dir = self.vault_root / "04 - Archives"
        archives_dir.mkdir(parents=True)
        (archives_dir / "Milestone.md").write_text("existing archive", encoding="utf-8")

        new_note = self.vault_root / "01 - Projects" / "Apollo" / "Milestone.md"
        new_note.write_text(
            "---\n"
            'title: "Milestone"\n'
            "status: active\n"
            "---\n"
            "Milestone content\n",
            encoding="utf-8",
        )

        res = archive_note(self.vault_root, "01 - Projects/Apollo/Milestone.md")
        self.assertTrue(res.success)
        self.assertEqual(res.target_path, "04 - Archives/Milestone (1).md")
        self.assertTrue((archives_dir / "Milestone.md").exists())
        self.assertTrue((archives_dir / "Milestone (1).md").exists())

    def test_archive_missing_note_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            archive_note(self.vault_root, "NonExistent.md")

    def test_archive_note_dry_run(self) -> None:
        proj_file = self.vault_root / "01 - Projects" / "Apollo" / "Sprint.md"
        proj_file.write_text(
            '---\ntitle: "Sprint"\nstatus: active\n---\nBody\n', encoding="utf-8"
        )

        res = archive_note(
            self.vault_root, "01 - Projects/Apollo/Sprint.md", dry_run=True
        )

        self.assertTrue(res.success)
        self.assertTrue(res.is_dry_run)
        self.assertEqual(res.source_path, "01 - Projects/Apollo/Sprint.md")
        self.assertEqual(res.target_path, "04 - Archives/Sprint.md")
        self.assertTrue(proj_file.exists())
        self.assertFalse((self.vault_root / "04 - Archives" / "Sprint.md").exists())


if __name__ == "__main__":
    unittest.main()
