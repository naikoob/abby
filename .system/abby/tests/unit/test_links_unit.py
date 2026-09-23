"""Tier 1: Serialization, validation, and parsing unit tests for link models and extraction."""

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
    from tests.support import Tier1UnitTestCase
except ModuleNotFoundError:
    from support import Tier1UnitTestCase

from abby.core.graph import extract_links_from_text
from abby.models.links import (
    BacklinkOccurrence,
    BacklinkSummary,
    BrokenLinkItem,
    NoteLinkRecord,
    OrphanReport,
    RefactorFileModification,
    RefactorResult,
)


class TestLinkModels(Tier1UnitTestCase):
    """Tier 1: Serialization and validation tests for link data models."""

    def test_note_link_record_to_dict(self) -> None:
        rec = NoteLinkRecord(
            source_path="01 - Projects/Apollo.md",
            target_title="Architecture",
            target_heading="Auth",
            target_alias="Auth Guide",
            link_syntax="wikilink",
            is_embed=False,
            line_number=12,
            resolved_path="03 - Resources/Architecture.md",
            is_ambiguous=False,
        )
        d = rec.to_dict()
        self.assertEqual(d["source_path"], "01 - Projects/Apollo.md")
        self.assertEqual(d["target_title"], "Architecture")
        self.assertEqual(d["target_heading"], "Auth")
        self.assertEqual(d["target_alias"], "Auth Guide")
        self.assertEqual(d["link_syntax"], "wikilink")
        self.assertFalse(d["is_embed"])
        self.assertEqual(d["line_number"], 12)
        self.assertEqual(d["resolved_path"], "03 - Resources/Architecture.md")
        self.assertFalse(d["is_ambiguous"])
        self.assertEqual(d["candidate_paths"], [])

    def test_backlink_summary_to_dict(self) -> None:
        summary = BacklinkSummary(
            target_note="03 - Resources/Architecture.md",
            target_title="Architecture",
            backlinks=[
                BacklinkOccurrence(
                    source_path="01 - Projects/Apollo.md",
                    line_number=14,
                    alias="Our Arch",
                    heading="Auth",
                )
            ],
        )
        self.assertEqual(summary.total_backlinks, 1)
        d = summary.to_dict()
        self.assertEqual(d["total_backlinks"], 1)
        self.assertEqual(len(d["backlinks"]), 1)
        self.assertEqual(d["backlinks"][0]["source_path"], "01 - Projects/Apollo.md")

    def test_broken_link_item_to_dict(self) -> None:
        broken = BrokenLinkItem(
            source_path="01 - Projects/Apollo.md",
            line_number=35,
            target="Missing Plan",
            heading=None,
            link_syntax="wikilink",
            raw_text="[[Missing Plan]]",
        )
        d = broken.to_dict()
        self.assertEqual(d["target"], "Missing Plan")
        self.assertEqual(d["line_number"], 35)

    def test_refactor_result_to_dict(self) -> None:
        res = RefactorResult(
            old_title="Old Plan",
            new_title="New Plan",
            file_renamed="01 - Projects/New Plan.md",
            files_modified=[
                RefactorFileModification(
                    path="02 - Areas/Strategy.md",
                    occurrences_replaced=2,
                    lines_modified=[10, 20],
                )
            ],
            total_occurrences=2,
            is_dry_run=True,
        )
        d = res.to_dict()
        self.assertEqual(d["old_title"], "Old Plan")
        self.assertEqual(d["new_title"], "New Plan")
        self.assertEqual(d["file_renamed"], "01 - Projects/New Plan.md")
        self.assertTrue(d["is_dry_run"])
        self.assertEqual(d["total_occurrences"], 2)
        self.assertEqual(len(d["files_modified"]), 1)

    def test_orphan_report_to_dict(self) -> None:
        report = OrphanReport(
            orphans=["02 - Areas/Island.md"],
            unreferenced=["03 - Resources/Leaf.md"],
            domain_filter="areas",
            included_inbox=False,
        )
        d = report.to_dict()
        self.assertEqual(d["total_orphans"], 1)
        self.assertEqual(d["total_unreferenced"], 1)
        self.assertEqual(d["domain_filter"], "areas")
        self.assertFalse(d["included_inbox"])


class TestLinkExtraction(Tier1UnitTestCase):
    """Tier 1: Syntax parsing, code-fence masking, and line-number accuracy."""

    def test_extract_plain_and_aliased_wikilinks(self) -> None:
        text = "Hello world!\nCheck [[Architecture Guide]] and [[Database Migration|DB Migration]]."
        links = extract_links_from_text(text, source_path="01 - Projects/Kickoff.md")
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].target_title, "Architecture Guide")
        self.assertIsNone(links[0].target_alias)
        self.assertEqual(links[0].line_number, 2)
        self.assertEqual(links[0].link_syntax, "wikilink")

        self.assertEqual(links[1].target_title, "Database Migration")
        self.assertEqual(links[1].target_alias, "DB Migration")
        self.assertEqual(links[1].line_number, 2)

    def test_extract_heading_and_embeds(self) -> None:
        text = (
            "# Title\n\n"
            "Reference [[Architecture#Authentication]] in detail.\n"
            "Transclusion: ![[Diagram.png]] and ![[Component#Summary|Overview]]."
        )
        links = extract_links_from_text(text, source_path="01 - Projects/Apollo.md")
        self.assertEqual(len(links), 3)

        self.assertEqual(links[0].target_title, "Architecture")
        self.assertEqual(links[0].target_heading, "Authentication")
        self.assertFalse(links[0].is_embed)
        self.assertEqual(links[0].line_number, 3)

        self.assertEqual(links[1].target_title, "Diagram.png")
        self.assertTrue(links[1].is_embed)
        self.assertEqual(links[1].line_number, 4)

        self.assertEqual(links[2].target_title, "Component")
        self.assertEqual(links[2].target_heading, "Summary")
        self.assertEqual(links[2].target_alias, "Overview")
        self.assertTrue(links[2].is_embed)
        self.assertEqual(links[2].line_number, 4)

    def test_extract_local_markdown_links(self) -> None:
        text = (
            "See [Architecture](../03%20-%20Resources/Architecture.md) and "
            "[Online Docs](https://example.com/docs).\n"
            'Also check image ![Schematic](./assets/schema.svg "hover title").'
        )
        links = extract_links_from_text(text, source_path="01 - Projects/Kickoff.md")
        self.assertEqual(len(links), 2)

        self.assertEqual(links[0].target_title, "../03 - Resources/Architecture.md")
        self.assertEqual(links[0].target_alias, "Architecture")
        self.assertEqual(links[0].link_syntax, "markdown")
        self.assertFalse(links[0].is_embed)
        self.assertEqual(links[0].line_number, 1)

        self.assertEqual(links[1].target_title, "./assets/schema.svg")
        self.assertEqual(links[1].target_alias, "Schematic")
        self.assertEqual(links[1].link_syntax, "markdown")
        self.assertTrue(links[1].is_embed)
        self.assertEqual(links[1].line_number, 2)

    def test_code_block_immunity_preserves_line_numbers(self) -> None:
        content = """# Document

Here is some code:
```python
# This is a sample [[Fenced Code Link 1]]
def foo():
    return "[Not a link](https://test.com)"
```

And regular prose with [[Real Outbound Note]].
Inline code `[[Inline Code Link 2]]` must be skipped.
Finally, check [Real Markdown Link](../Resources/Guide.md) on line 12.
"""
        links = extract_links_from_text(content, source_path="01 - Projects/Test.md")
        self.assertEqual(len(links), 2)

        self.assertEqual(links[0].target_title, "Real Outbound Note")
        self.assertEqual(links[0].line_number, 10)

        self.assertEqual(links[1].target_title, "../Resources/Guide.md")
        self.assertEqual(links[1].line_number, 12)


if __name__ == "__main__":
    unittest.main()

