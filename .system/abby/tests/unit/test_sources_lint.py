"""Unit tests for OKF v0.2 sources schema lint validation rules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.services.lint.rules import audit_note_content


class TestSourcesLint(unittest.TestCase):
    """Unit tests for sources validation in audit_note_content."""

    def test_valid_sources(self) -> None:
        content = (
            "---\n"
            'title: "Raft Consensus Algorithm"\n'
            'description: "Distributed state machine replication."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - consensus\n"
            "sources:\n"
            '  - resource: "https://raft.github.io/raft.pdf"\n'
            '    id: "ongaro2014"\n'
            '    title: "In Search of an Understandable Consensus Algorithm"\n'
            '    author: "Diego Ongaro and John Ousterhout"\n'
            "    usage_count: 3\n"
            '    last_modified: "2014-05-20T00:00:00Z"\n'
            "---\n"
            "# Raft Consensus Algorithm\n\nRaft is designed for understandability.\n"
        )
        res = audit_note_content(content, "03 - Resources/Raft.md", domain="03 - Resources")
        sources_violations = [v for v in res.violations if v.field == "sources"]
        self.assertEqual(len(sources_violations), 0)

    def test_invalid_sources_format_scalar(self) -> None:
        content = (
            "---\n"
            'title: "Scalar Sources Note"\n'
            'description: "Test note with scalar sources."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - test\n"
            'sources: "https://example.com/spec"\n'
            "---\n"
            "# Content\n"
        )
        res = audit_note_content(content, "03 - Resources/Test.md", domain="03 - Resources")
        rules = [v.rule for v in res.violations if v.field == "sources"]
        self.assertIn("invalid-sources-format", rules)

    def test_invalid_sources_format_non_list_mapping(self) -> None:
        content = (
            "---\n"
            'title: "Mapping Sources Note"\n'
            'description: "Test note with mapping sources."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - test\n"
            "sources:\n"
            '  resource: "https://example.com/spec"\n'
            "---\n"
            "# Content\n"
        )
        res = audit_note_content(content, "03 - Resources/Test.md", domain="03 - Resources")
        rules = [v.rule for v in res.violations if v.field == "sources"]
        self.assertIn("invalid-sources-format", rules)

    def test_missing_source_resource(self) -> None:
        content = (
            "---\n"
            'title: "Missing Resource Note"\n'
            'description: "Test note missing resource."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - test\n"
            "sources:\n"
            '  - title: "Paper Without Resource"\n'
            '    author: "Jane Doe"\n'
            "---\n"
            "# Content\n"
        )
        res = audit_note_content(content, "03 - Resources/Test.md", domain="03 - Resources")
        rules = [v.rule for v in res.violations if v.field == "sources"]
        self.assertIn("missing-source-resource", rules)

    def test_empty_source_resource_string(self) -> None:
        content = (
            "---\n"
            'title: "Empty Resource Note"\n'
            'description: "Test note with empty resource string."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - test\n"
            "sources:\n"
            '  - resource: ""\n'
            '    title: "Empty Resource"\n'
            "---\n"
            "# Content\n"
        )
        res = audit_note_content(content, "03 - Resources/Test.md", domain="03 - Resources")
        rules = [v.rule for v in res.violations if v.field == "sources"]
        self.assertIn("missing-source-resource", rules)

    def test_invalid_source_date(self) -> None:
        content = (
            "---\n"
            'title: "Invalid Source Date Note"\n'
            'description: "Test note with malformed source last_modified."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - test\n"
            "sources:\n"
            '  - resource: "https://example.com/paper.pdf"\n'
            '    last_modified: "May 20, 2014"\n'
            "---\n"
            "# Content\n"
        )
        res = audit_note_content(content, "03 - Resources/Test.md", domain="03 - Resources")
        rules = [v.rule for v in res.violations if v.field == "sources"]
        self.assertIn("invalid-source-date", rules)

    def test_empty_sources_list_is_valid(self) -> None:
        content = (
            "---\n"
            'title: "Empty Sources Note"\n'
            'description: "Test note with empty sources list."\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - test\n"
            "sources: []\n"
            "---\n"
            "# Content\n"
        )
        res = audit_note_content(content, "03 - Resources/Test.md", domain="03 - Resources")
        sources_violations = [v for v in res.violations if v.field == "sources"]
        self.assertEqual(len(sources_violations), 0)


if __name__ == "__main__":
    unittest.main()

