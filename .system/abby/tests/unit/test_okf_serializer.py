"""Unit tests for decoupled OKF frontmatter serialization engine."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.models.okf import OKFFrontmatter
from abby.services.okf_serializer import (
    mutate_frontmatter_block,
    mutate_okf_frontmatter,
    serialize_okf_frontmatter,
)


class TestOKFSerializer(unittest.TestCase):
    """Tests for OKF frontmatter serialization and in-place mutation."""

    def test_serialize_basic(self) -> None:
        fm = OKFFrontmatter(
            title="Basic Note",
            description="Short summary.",
            created="2026-09-18T12:00:00",
            type="project-note",
            status="active",
            tags=["alpha", "beta"],
        )
        yaml_text = serialize_okf_frontmatter(fm)
        self.assertTrue(yaml_text.startswith("---\n"))
        self.assertTrue(yaml_text.endswith("---\n"))
        self.assertIn('title: "Basic Note"', yaml_text)
        self.assertIn('description: "Short summary."', yaml_text)
        self.assertIn("type: project-note", yaml_text)
        self.assertIn("status: active", yaml_text)
        self.assertIn("  - alpha", yaml_text)
        self.assertIn("  - beta", yaml_text)

    def test_serialize_with_trust_metadata(self) -> None:
        fm = OKFFrontmatter(
            title="Trusted Note",
            created="2026-09-18T12:00:00",
            generated={"by": "abby/agent:synthesizer", "at": "2026-09-18T12:00:00Z"},
            verified=[{"by": "human:bookian", "at": "2026-09-18T13:00:00Z"}],
            stale_after="2027-09-18T00:00:00Z",
        )
        yaml_text = serialize_okf_frontmatter(fm)
        self.assertIn("generated:", yaml_text)
        self.assertIn("by: abby/agent:synthesizer", yaml_text)
        self.assertIn("verified:", yaml_text)
        self.assertIn("- by: human:bookian", yaml_text)
        self.assertIn('stale_after: "2027-09-18T00:00:00Z"', yaml_text)

    def test_mutate_okf_frontmatter_status(self) -> None:
        raw = """---
title: "Mutating Note"
type: inbox
status: unprocessed
tags:
  - draft
---

# Content
"""
        updated, prev_status = mutate_okf_frontmatter(
            raw, {"status": "active", "type": "project-note"}
        )
        self.assertEqual(prev_status, "unprocessed")
        self.assertIn("status: active", updated)
        self.assertIn("type: project-note", updated)
        self.assertIn("# Content", updated)


    def test_serialize_stale_after_and_tags_roundtrip(self) -> None:
        from abby.services.okf_parser import parse_okf_frontmatter, tokenize_frontmatter

        fm = OKFFrontmatter(
            title="Freshness Note",
            tags=["machine-learning", "deep-learning"],
            stale_after="2027-09-18T00:00:00Z",
        )
        yaml_text = serialize_okf_frontmatter(fm)
        # Verify YAML format does not merge tag and stale_after
        self.assertIn("tags:\n  - machine-learning\n  - deep-learning\nstale_after: \"2027-09-18T00:00:00Z\"", yaml_text)

        # Tokenize and parse round-trip
        parsed = tokenize_frontmatter(yaml_text)
        self.assertEqual([t[0] for t in parsed.tags], ["machine-learning", "deep-learning"])
        self.assertEqual(parsed.stale_after, "2027-09-18T00:00:00Z")

        parsed_dict = parse_okf_frontmatter(yaml_text, "Freshness Note")
        self.assertEqual(parsed_dict["tags"], ["machine-learning", "deep-learning"])
        self.assertEqual(parsed_dict["stale_after"], "2027-09-18T00:00:00Z")

    def test_serialize_empty_tags_and_stale_after_roundtrip(self) -> None:
        from abby.services.okf_parser import parse_okf_frontmatter, tokenize_frontmatter

        fm = OKFFrontmatter(
            title="Empty Tags Note",
            tags=[],
            stale_after="2027-01-01",
        )
        yaml_text = serialize_okf_frontmatter(fm)
        self.assertIn("tags: []\nstale_after: \"2027-01-01\"", yaml_text)

        parsed = tokenize_frontmatter(yaml_text)
        self.assertEqual(parsed.tags, [])
        self.assertEqual(parsed.stale_after, "2027-01-01")

        parsed_dict = parse_okf_frontmatter(yaml_text, "Empty Tags Note")
        self.assertEqual(parsed_dict["tags"], [])
        self.assertEqual(parsed_dict["stale_after"], "2027-01-01")

    def test_serialize_all_fields_comprehensive_roundtrip(self) -> None:
        from abby.services.okf_parser import parse_okf_frontmatter

        fm = OKFFrontmatter(
            title="Comprehensive Note",
            description="Detailed description for testing.",
            created="2026-09-18T12:00:00",
            updated="2026-09-18T13:00:00",
            type="project-note",
            status="active",
            tags=["p1", "critical"],
            stale_after="2027-09-18T00:00:00Z",
            generated={"by": "abby/agent:synthesizer", "at": "2026-09-18T12:00:00Z"},
            verified=[{"by": "human:bookian", "at": "2026-09-18T13:00:00Z"}],
            sources=[{"resource": "https://example.com/spec", "title": "Upstream RFC", "usage_count": 3}],
        )
        yaml_text = serialize_okf_frontmatter(fm)
        parsed = parse_okf_frontmatter(yaml_text, "Comprehensive Note")

        self.assertEqual(parsed["title"], "Comprehensive Note")
        self.assertEqual(parsed["description"], "Detailed description for testing.")
        self.assertEqual(parsed["created"], "2026-09-18T12:00:00")
        self.assertEqual(parsed["updated"], "2026-09-18T13:00:00")
        self.assertEqual(parsed["type"], "project-note")
        self.assertEqual(parsed["status"], "active")
        self.assertEqual(parsed["tags"], ["p1", "critical"])
        self.assertEqual(parsed["stale_after"], "2027-09-18T00:00:00Z")
        self.assertEqual(parsed["generated"], {"by": "abby/agent:synthesizer", "at": "2026-09-18T12:00:00Z"})
        self.assertEqual(parsed["verified"], [{"by": "human:bookian", "at": "2026-09-18T13:00:00Z"}])
        self.assertEqual(parsed["sources"], [{"resource": "https://example.com/spec", "title": "Upstream RFC", "usage_count": 3}])
        self.assertEqual(parsed["trust_tier"], "human-reviewed")

    def test_mutate_frontmatter_block_replace_existing(self) -> None:
        raw = """---
title: "Block Note"
type: note
verified:
  - by: agent:test
    at: "2026-01-01T00:00:00Z"
status: active
---

# Content Body ^ref1
"""
        new_lines = [
            "verified:",
            "  - by: human:bookian",
            '    at: "2026-09-18T12:00:00Z"',
        ]
        result = mutate_frontmatter_block(raw, "verified", new_lines)
        self.assertIn("- by: human:bookian", result)
        self.assertNotIn("agent:test", result)
        self.assertIn("status: active", result)
        self.assertIn("# Content Body ^ref1", result)

    def test_mutate_frontmatter_block_append_new(self) -> None:
        raw = """---
title: "Block Note"
status: active
---

# Body
"""
        new_lines = [
            "tags:",
            "  - machine-learning",
            "  - ai",
        ]
        result = mutate_frontmatter_block(raw, "tags", new_lines)
        self.assertIn("tags:", result)
        self.assertIn("  - machine-learning", result)
        self.assertIn("status: active", result)
        self.assertIn("# Body", result)

    def test_mutate_frontmatter_block_crlf_preservation(self) -> None:
        raw = "---\r\ntitle: \"CRLF Note\"\r\nstatus: active\r\n---\r\n\r\n# Body\r\n"
        new_lines = ["status: archived"]
        result = mutate_frontmatter_block(raw, "status", new_lines)
        self.assertIn("\r\n", result)
        self.assertIn("status: archived", result)


if __name__ == "__main__":
    unittest.main()
