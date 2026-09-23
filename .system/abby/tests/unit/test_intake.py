"""Unit tests for note intake, natural title naming, collision resolution, and OKF formatting (Tier 2)."""

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
    from tests.support import Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import Tier2FilesystemTestCase
from abby.constants import MAX_TITLE_BYTES
from abby.core.intake import capture_note, resolve_unique_filename, sanitize_title
from abby.models.okf import OKFFrontmatter
from abby.utils.yaml import format_yaml_tag, unescape_yaml_string


class TestIntake(Tier2FilesystemTestCase):
    def test_sanitize_title_basic(self) -> None:
        self.assertEqual(
            sanitize_title("Review quarterly goals"), "Review quarterly goals"
        )
        self.assertEqual(sanitize_title("Notes: 2026/09/17?"), "Notes- 2026-09-17")
        self.assertEqual(sanitize_title("   Spaces & *stars*   "), "Spaces & -stars")
        self.assertEqual(sanitize_title(""), "Untitled Note")

    def test_sanitize_title_length_limit(self) -> None:
        # Long title exceeding MAX_TITLE_BYTES (e.g. 300 characters)
        long_title = "A" * 300
        sanitized = sanitize_title(long_title)
        self.assertLessEqual(len(sanitized.encode("utf-8")), MAX_TITLE_BYTES)
        self.assertTrue(sanitized.startswith("AAAA"))

        # Long CJK title with multi-byte characters
        cjk_title = "测试笔记" * 50  # 200 chars * 3 bytes = 600 bytes
        sanitized_cjk = sanitize_title(cjk_title)
        self.assertLessEqual(len(sanitized_cjk.encode("utf-8")), MAX_TITLE_BYTES)
        # Verify it decodes valid UTF-8 without cutting characters in half
        sanitized_cjk.encode("utf-8").decode("utf-8")

    def test_capture_note_basic(self) -> None:
        note = capture_note(self.vault_root, title="Team Sync")
        self.assertEqual(note.filename, "Team Sync.md")
        self.assertEqual(note.relative_path, "00 - Inbox/Team Sync.md")
        self.assertTrue(note.absolute_path.exists())

        content = note.absolute_path.read_text(encoding="utf-8")
        self.assertIn('title: "Team Sync"', content)
        self.assertIn("type: inbox", content)
        self.assertIn("status: unprocessed", content)
        self.assertIn("- inbox", content)

    def test_capture_note_cjk_unicode(self) -> None:
        note = capture_note(self.vault_root, title="项目规划：2026战略目标")
        self.assertEqual(note.filename, "项目规划：2026战略目标.md")
        self.assertTrue(note.absolute_path.exists())
        content = note.absolute_path.read_text(encoding="utf-8")
        self.assertIn('title: "项目规划：2026战略目标"', content)

    def test_capture_note_with_body(self) -> None:
        note = capture_note(
            self.vault_root, title="Standup", body="Discussed quarterly goals."
        )
        content = note.absolute_path.read_text(encoding="utf-8")
        self.assertIn("Discussed quarterly goals.", content)

    def test_capture_note_duplicate_collision_resolution(self) -> None:
        note1 = capture_note(self.vault_root, title="Planning")
        note2 = capture_note(self.vault_root, title="Planning")
        note3 = capture_note(self.vault_root, title="Planning")

        self.assertEqual(note1.filename, "Planning.md")
        self.assertEqual(note2.filename, "Planning (1).md")
        self.assertEqual(note3.filename, "Planning (2).md")

        self.assert_file_exists("00 - Inbox/Planning.md")
        self.assert_file_exists("00 - Inbox/Planning (1).md")
        self.assert_file_exists("00 - Inbox/Planning (2).md")

    def test_capture_note_collision_with_existing_suffix(self) -> None:
        # If user explicitly creates "Planning (1)", subsequent conflict becomes "Planning (2)"
        note1 = capture_note(self.vault_root, title="Planning (1)")
        note2 = capture_note(self.vault_root, title="Planning (1)")
        self.assertEqual(note1.filename, "Planning (1).md")
        self.assertEqual(note2.filename, "Planning (2).md")

    def test_frontmatter_yaml_edge_cases(self) -> None:
        # Empty tags produces valid YAML sequence "tags: []"
        fm_empty = OKFFrontmatter(title="No Tags", tags=[])
        yaml_empty = fm_empty.to_yaml()
        self.assertIn("tags: []", yaml_empty)

        # Quotes and backslashes are escaped
        fm_escaped = OKFFrontmatter(
            title='Quotes "and" C:\\Paths', tags=["inbox", "custom tag", "lang:c#"]
        )
        yaml_escaped = fm_escaped.to_yaml()
        self.assertIn('title: "Quotes \\"and\\" C:\\\\Paths"', yaml_escaped)
        self.assertIn('  - "custom tag"', yaml_escaped)
        self.assertIn('  - "lang:c#"', yaml_escaped)
        self.assertIn("  - inbox", yaml_escaped)

    def test_yaml_unescape_and_format_tag(self) -> None:
        self.assertEqual(
            unescape_yaml_string(r"Quotes \"and\" C:\\Paths"), 'Quotes "and" C:\\Paths'
        )
        self.assertEqual(unescape_yaml_string("'Single quoted'"), "Single quoted")
        self.assertEqual(unescape_yaml_string("plain_value"), "plain_value")

        self.assertEqual(format_yaml_tag("inbox"), "  - inbox")
        self.assertEqual(format_yaml_tag("tag-with-hyphens"), "  - tag-with-hyphens")
        self.assertEqual(format_yaml_tag("custom tag"), '  - "custom tag"')
        self.assertEqual(format_yaml_tag("lang:c#"), '  - "lang:c#"')
        self.assertEqual(format_yaml_tag('with"quote'), '  - "with\\"quote"')


if __name__ == "__main__":
    unittest.main()
