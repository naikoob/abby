"""Tier 1 Unit tests for OKF lint models, lexical scanner, and rule evaluation."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.models.lint import (
    LintReport,
    LintViolation,
    NoteAuditResult,
    NoteFixResult,
    RemediationAction,
)
from abby.services.lint import (
    audit_note_content,
    normalize_tag,
    resolve_domain_from_path,
    validate_tag_syntax,
)


class TestLintModels(unittest.TestCase):
    """Test suite for lint data structures and serialization."""

    def test_lint_violation_serialization(self):
        violation = LintViolation(
            file_path="01 - Projects/Apollo.md",
            field="status",
            rule="domain-status-mismatch",
            severity="warning",
            message="Status mismatch",
            line_number=5,
            is_fixable=True,
            suggested_value="active",
        )
        data = violation.to_dict()
        self.assertEqual(data["file_path"], "01 - Projects/Apollo.md")
        self.assertEqual(data["severity"], "warning")
        self.assertEqual(data["line_number"], 5)
        self.assertEqual(data["suggested_value"], "active")

    def test_note_audit_result_properties(self):
        clean_result = NoteAuditResult(
            file_path="note.md", absolute_path=Path("/tmp/note.md")
        )
        self.assertTrue(clean_result.is_clean)
        self.assertFalse(clean_result.has_errors)
        self.assertFalse(clean_result.has_warnings)

        error_violation = LintViolation(
            file_path="note.md",
            field="title",
            rule="missing-title",
            severity="error",
            message="Missing title",
        )
        error_result = NoteAuditResult(
            file_path="note.md",
            absolute_path=Path("/tmp/note.md"),
            violations=[error_violation],
        )
        self.assertFalse(error_result.is_clean)
        self.assertTrue(error_result.has_errors)
        self.assertFalse(error_result.has_warnings)

    def test_lint_report_exit_code_calculation(self):
        report = LintReport(
            total_audited=10,
            clean_notes=9,
            total_violations=1,
            total_warnings=1,
            total_errors=0,
        )
        # In non-strict mode, warnings do not trigger exit code 1
        self.assertEqual(report.calculate_exit_code(strict=False), 0)
        # In strict mode, warnings trigger exit code 1
        self.assertEqual(report.calculate_exit_code(strict=True), 1)

        report.total_errors = 1
        self.assertEqual(report.calculate_exit_code(strict=False), 0)
        self.assertEqual(report.calculate_exit_code(strict=True), 1)


class TestLintServiceRules(unittest.TestCase):
    """Test suite for lexical frontmatter analysis and rule checking."""

    def test_tag_helpers(self):
        self.assertEqual(normalize_tag("#project/apollo"), "project/apollo")
        self.assertEqual(normalize_tag("##double"), "double")
        self.assertEqual(normalize_tag("clean-tag"), "clean-tag")

        is_valid, warn = validate_tag_syntax("clean-tag")
        self.assertTrue(is_valid)
        self.assertIsNone(warn)

        is_valid, warn = validate_tag_syntax("#hashtag")
        self.assertTrue(is_valid)
        self.assertEqual(warn, "tag-has-hash")

        is_valid, warn = validate_tag_syntax("has space")
        self.assertFalse(is_valid)
        self.assertEqual(warn, "tag-has-whitespace")

    def test_domain_path_resolution(self):
        self.assertEqual(
            resolve_domain_from_path("01 - Projects/Apollo.md"), "01 - Projects"
        )
        self.assertEqual(
            resolve_domain_from_path("projects/Apollo.md"), "01 - Projects"
        )
        self.assertEqual(
            resolve_domain_from_path("00 - Inbox/New Note.md"), "00 - Inbox"
        )
        self.assertIsNone(resolve_domain_from_path("AGENTS.md"))
        self.assertIsNone(resolve_domain_from_path("custom/note.md"))

    def test_clean_note_audit(self):
        content = """---
title: "Apollo Overview"
description: "Apollo mission overview and flight objectives."
created: "2026-09-17T10:00:00"
type: project-note
status: active
tags:
  - project
  - space
---
# Apollo Mission Body
"""
        result = audit_note_content(
            content, "01 - Projects/Apollo Overview.md", domain="01 - Projects"
        )
        self.assertTrue(result.is_clean)
        self.assertEqual(len(result.violations), 0)

    def test_missing_frontmatter(self):
        content = "# Raw Note\nThis note has no YAML header."
        result = audit_note_content(
            content, "00 - Inbox/Raw Note.md", domain="00 - Inbox"
        )
        self.assertFalse(result.has_frontmatter)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].rule, "syntax-missing-frontmatter")

    def test_unclosed_frontmatter(self):
        content = "---\ntitle: Unclosed\ncreated: 2026-09-17\nBody starts here"
        result = audit_note_content(
            content, "00 - Inbox/Unclosed.md", domain="00 - Inbox"
        )
        self.assertFalse(result.has_frontmatter)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].rule, "syntax-unclosed-frontmatter")

    def test_missing_and_invalid_fields(self):
        content = """---
title: ""
created: "not-a-date"
type: invalid-type
status: not-a-status
tags: "scalar-tag, another-tag"
---
Body text
"""
        result = audit_note_content(
            content, "01 - Projects/Bad.md", domain="01 - Projects"
        )
        rules = {v.rule for v in result.violations}
        self.assertIn("missing-title", rules)
        self.assertIn("invalid-created-date", rules)
        self.assertIn("invalid-type", rules)
        self.assertIn("invalid-status", rules)
        self.assertIn("invalid-tags-format", rules)

    def test_domain_alignment_mismatch(self):
        content = """---
title: "Project in Archive"
created: "2026-09-17"
type: project-note
status: active
tags: []
---
Body
"""
        result = audit_note_content(
            content, "04 - Archives/Project in Archive.md", domain="04 - Archives"
        )
        rules = {v.rule for v in result.violations}
        self.assertIn("domain-status-mismatch", rules)
        self.assertIn("domain-type-mismatch", rules)


if __name__ == "__main__":
    unittest.main()
