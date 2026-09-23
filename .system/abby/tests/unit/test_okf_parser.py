"""Unit tests for decoupled OKF frontmatter parsing engine."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.models.trust import TrustTier
from abby.services.okf_parser import parse_okf_frontmatter, tokenize_frontmatter


class TestOKFParser(unittest.TestCase):
    """Tests for OKF frontmatter parsing and tokenization."""

    def test_tokenize_no_frontmatter(self) -> None:
        text = "# Title\n\nBody content without frontmatter."
        parsed = tokenize_frontmatter(text)
        self.assertFalse(parsed.has_frontmatter)
        self.assertFalse(parsed.is_closed)
        self.assertEqual(parsed.body_content, text)

    def test_tokenize_unclosed_frontmatter(self) -> None:
        text = "---\ntitle: Unclosed note\ntags:\n  - draft"
        parsed = tokenize_frontmatter(text)
        self.assertTrue(parsed.has_frontmatter)
        self.assertFalse(parsed.is_closed)

    def test_tokenize_valid_frontmatter(self) -> None:
        text = """---
title: "Project Phoenix"
description: "Mission to Mars telemetry."
type: project-note
status: active
tags:
  - space
  - mars
---

# Body
"""
        parsed = tokenize_frontmatter(text)
        self.assertTrue(parsed.has_frontmatter)
        self.assertTrue(parsed.is_closed)
        self.assertEqual(parsed.fields["title"][0], '"Project Phoenix"')
        self.assertEqual(parsed.fields["description"][0], '"Mission to Mars telemetry."')
        self.assertEqual(len(parsed.tags), 2)
        self.assertEqual(parsed.tags[0][0], "space")
        self.assertEqual(parsed.tags[1][0], "mars")

    def test_parse_okf_frontmatter_full(self) -> None:
        text = """---
title: "Complete Note"
description: "Comprehensive OKF note."
created: "2026-09-18T10:00:00"
updated: "2026-09-18T11:00:00"
type: project-note
status: active
tags:
  - testing
generated:
  by: abby/agent:synthesizer
  at: "2026-09-18T10:00:00Z"
verified:
  - by: human:bookian
    at: "2026-09-18T11:00:00Z"
stale_after: "2027-09-18T00:00:00Z"
sources:
  - resource: "https://example.com/rfc"
    title: "RFC Spec"
---

Body text.
"""
        data = parse_okf_frontmatter(text, default_title="Fallback")
        self.assertEqual(data["title"], "Complete Note")
        self.assertEqual(data["description"], "Comprehensive OKF note.")
        self.assertEqual(data["type"], "project-note")
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["tags"], ["testing"])
        self.assertEqual(data["trust_tier"], TrustTier.HUMAN_REVIEWED)
        self.assertFalse(data["is_stale"])
        self.assertEqual(data["generated"]["by"], "abby/agent:synthesizer")
        self.assertEqual(data["verified"][0]["by"], "human:bookian")


if __name__ == "__main__":
    unittest.main()
