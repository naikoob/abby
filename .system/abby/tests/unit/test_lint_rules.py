"""Tier 1 Unit tests for isolated OKF lint rules, tag validation, and domain mapping."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.services.lint import (
    CANONICAL_STATUSES,
    CANONICAL_TYPES,
    audit_note_content,
    normalize_tag,
    parse_iso_date,
    resolve_canonical_domain,
    resolve_domain_from_path,
    validate_actor_syntax,
    validate_tag_syntax,
)


class TestLintRules(unittest.TestCase):
    """Test suite for isolated lint rules and normalization helpers."""

    def test_canonical_sets(self) -> None:
        self.assertIn("active", CANONICAL_STATUSES)
        self.assertIn("unprocessed", CANONICAL_STATUSES)
        self.assertIn("evergreen", CANONICAL_STATUSES)
        self.assertIn("archived", CANONICAL_STATUSES)

        self.assertIn("inbox", CANONICAL_TYPES)
        self.assertIn("project-note", CANONICAL_TYPES)
        self.assertIn("area-note", CANONICAL_TYPES)
        self.assertIn("resource-note", CANONICAL_TYPES)
        self.assertIn("archive-note", CANONICAL_TYPES)

    def test_normalize_tag(self) -> None:
        self.assertEqual(normalize_tag("#alpha"), "alpha")
        self.assertEqual(normalize_tag("###deep-nested"), "deep-nested")
        self.assertEqual(normalize_tag(" clean "), "clean")

    def test_validate_tag_syntax(self) -> None:
        valid, warning = validate_tag_syntax("clean-tag")
        self.assertTrue(valid)
        self.assertIsNone(warning)

        valid, warning = validate_tag_syntax("#with-hash")
        self.assertTrue(valid)
        self.assertEqual(warning, "tag-has-hash")

        valid, warning = validate_tag_syntax("with whitespace")
        self.assertFalse(valid)
        self.assertEqual(warning, "tag-has-whitespace")

        valid, warning = validate_tag_syntax("")
        self.assertFalse(valid)
        self.assertEqual(warning, "tag-empty")

    def test_resolve_domain_from_path(self) -> None:
        self.assertEqual(
            resolve_domain_from_path("01 - Projects/Alpha.md"), "01 - Projects"
        )
        self.assertEqual(
            resolve_domain_from_path("00 - Inbox/New Note.md"), "00 - Inbox"
        )
        self.assertEqual(
            resolve_domain_from_path("projects/Subdir/Deep.md"), "01 - Projects"
        )
        self.assertIsNone(resolve_domain_from_path("random_folder/file.md"))

    def test_resolve_canonical_domain(self) -> None:
        self.assertEqual(resolve_canonical_domain("projects"), "01 - Projects")
        self.assertEqual(resolve_canonical_domain("inbox"), "00 - Inbox")
        self.assertEqual(resolve_canonical_domain("02 - Areas"), "02 - Areas")
        self.assertIsNone(resolve_canonical_domain("nonexistent"))

    def test_parse_iso_date(self) -> None:
        dt = parse_iso_date("2026-09-17T12:00:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)

        # Quoted ISO date
        dt_quoted = parse_iso_date('"2026-09-17T12:00:00"')
        self.assertIsNotNone(dt_quoted)

        # Invalid date
        self.assertIsNone(parse_iso_date("not-a-date"))

    def test_audit_note_content_clean(self) -> None:
        content = (
            "---\n"
            'title: "Clean Note"\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: inbox\n"
            "status: unprocessed\n"
            "tags:\n"
            "  - inbox\n"
            "---\n"
            "# Clean Note\n\nBody content."
        )
        result = audit_note_content(
            content, "00 - Inbox/Clean Note.md", domain="00 - Inbox"
        )
        self.assertTrue(result.is_clean)
        self.assertEqual(len(result.violations), 0)

    def test_audit_note_content_violations(self) -> None:
        content = (
            "---\n"
            "type: inbox\n"
            "status: active\n"
            "---\n"
            "# Body without title or created in frontmatter."
        )
        result = audit_note_content(
            content, "00 - Inbox/Broken.md", domain="00 - Inbox"
        )
        self.assertFalse(result.is_clean)
        rules = [v.rule for v in result.violations]
        self.assertIn("missing-title", rules)
        self.assertIn("missing-created", rules)
        self.assertIn("domain-status-mismatch", rules)

    def test_validate_actor_syntax(self) -> None:
        self.assertTrue(validate_actor_syntax("human:bookian"))
        self.assertTrue(validate_actor_syntax("human:alice"))
        self.assertTrue(validate_actor_syntax("process:nightly-sync"))
        self.assertTrue(validate_actor_syntax("agent:synthesizer"))
        self.assertTrue(validate_actor_syntax("abby/agent:synthesizer"))
        self.assertTrue(validate_actor_syntax("reference_agent/gemini-2.5-pro"))

        self.assertFalse(validate_actor_syntax(""))
        self.assertFalse(validate_actor_syntax("invalid actor with spaces"))
        self.assertFalse(validate_actor_syntax("human:"))
        self.assertFalse(validate_actor_syntax("process:"))
        self.assertFalse(validate_actor_syntax("unknown_no_prefix"))

    def test_audit_trust_fields(self) -> None:
        valid_content = (
            "---\n"
            'title: "Verified Concept"\n'
            'created: "2026-09-18T10:00:00Z"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - concept\n"
            'description: "A valid concept note with trust metadata."\n'
            'stale_after: "2027-01-01T00:00:00Z"\n'
            "generated:\n"
            "  by: abby/agent:synthesizer\n"
            '  at: "2026-09-18T10:00:00Z"\n'
            "verified:\n"
            "  - by: human:bookian\n"
            '    at: "2026-09-18T12:00:00Z"\n'
            "---\n"
            "# Verified Concept\n"
        )
        res = audit_note_content(valid_content, "03 - Resources/Verified Concept.md", domain="03 - Resources")
        self.assertTrue(res.is_clean)

        invalid_content = (
            "---\n"
            'title: "Invalid Concept"\n'
            'created: "2026-09-18T10:00:00Z"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - concept\n"
            'description: "A note with bad actor and dates."\n'
            "stale_after: not-a-date\n"
            "generated:\n"
            "  by: bad actor spaces\n"
            "  at: bad-date\n"
            "verified:\n"
            "  - by: human:\n"
            "    at: bad-date\n"
            "---\n"
            "# Invalid Concept\n"
        )
        res_invalid = audit_note_content(invalid_content, "03 - Resources/Invalid Concept.md", domain="03 - Resources")
        rules = [v.rule for v in res_invalid.violations]
        self.assertIn("invalid-stale-after-date", rules)
        self.assertIn("invalid-actor-format", rules)
        self.assertIn("invalid-generated-date", rules)
        self.assertIn("invalid-verified-date", rules)


if __name__ == "__main__":
    unittest.main()
