"""Tier 2 Filesystem tests for OKF linting service and vault-wide scanner."""

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
from abby.services.lint import audit_single_note, audit_vault


class TestLintServiceFilesystem(Tier2FilesystemTestCase):
    """Tier 2: Auditing notes on filesystem and domain isolation."""

    def test_audit_clean_vault(self):
        self.init_vault()
        self.create_note(
            domain="01 - Projects",
            filename="Apollo.md",
            title="Apollo",
            description="Apollo project overview.",
            type_="project-note",
            status="active",
            tags=["space"],
        )
        self.create_note(
            domain="00 - Inbox",
            filename="Idea.md",
            title="Idea",
            type_="inbox",
            status="unprocessed",
            tags=["inbox"],
        )

        report = audit_vault(self.vault_root)
        self.assertEqual(report.total_audited, 2)
        self.assertEqual(report.clean_notes, 2)
        self.assertEqual(report.total_violations, 0)
        self.assertEqual(report.total_errors, 0)
        self.assertEqual(report.total_warnings, 0)

    def test_audit_excludes_root_and_system_files(self):
        self.init_vault()
        # Create root markdown files that do NOT have frontmatter
        (self.vault_root / "AGENTS.md").write_text(
            "# Agent Instructions\nRoot instructions.", encoding="utf-8"
        )
        (self.vault_root / "README.md").write_text(
            "# Vault Readme\nRoot documentation.", encoding="utf-8"
        )
        # Create a valid note in projects
        self.create_note(
            domain="01 - Projects",
            filename="Project.md",
            title="Project",
            description="Project description.",
            type_="project-note",
            status="active",
        )

        report = audit_vault(self.vault_root)
        # Only the note in 01 - Projects should be audited
        self.assertEqual(report.total_audited, 1)
        self.assertEqual(report.clean_notes, 1)
        self.assertEqual(report.total_violations, 0)

    def test_audit_with_defects(self):
        self.init_vault()
        # Defective note in 00 - Inbox: missing title, scalar tags
        bad_inbox = """---
created: "2026-09-17"
type: inbox
status: unprocessed
tags: "scalar-tag"
---
Body
"""
        (self.vault_root / "00 - Inbox" / "Bad.md").write_text(
            bad_inbox, encoding="utf-8"
        )

        # Defective note in 01 - Projects: domain status mismatch
        mismatch_proj = """---
title: "Project Apollo"
created: "2026-09-17"
type: project-note
status: unprocessed
tags: []
---
Body
"""
        (self.vault_root / "01 - Projects" / "Apollo.md").write_text(
            mismatch_proj, encoding="utf-8"
        )

        report = audit_vault(self.vault_root)
        self.assertEqual(report.total_audited, 2)
        self.assertEqual(report.clean_notes, 0)
        self.assertTrue(report.total_errors >= 2)  # missing title, scalar tags
        self.assertTrue(report.total_warnings >= 1)  # domain-status-mismatch

    def test_audit_single_note_and_domain_filter(self):
        self.init_vault()
        self.create_note(
            domain="01 - Projects",
            filename="Proj1.md",
            title="Proj1",
            description="Proj1 description.",
            type_="project-note",
            status="active",
        )
        self.create_note(
            domain="02 - Areas",
            filename="Area1.md",
            title="Area1",
            description="Area1 description.",
            type_="area-note",
            status="active",
        )

        # Scoped to single note
        single_res = audit_single_note(self.vault_root, "01 - Projects/Proj1.md")
        self.assertIsNotNone(single_res)
        self.assertEqual(single_res.file_path, "01 - Projects/Proj1.md")
        self.assertTrue(single_res.is_clean)

        # Scoped to domain
        domain_report = audit_vault(self.vault_root, domain="projects")
        self.assertEqual(domain_report.total_audited, 1)

    def test_remediate_note_in_place_and_preserves_block_refs(self):
        self.init_vault()
        raw = """---
description: "Apollo lunar mission exploration program."
created: "2026-09-17T12:00:00"
type: project-note
status: unprocessed
tags: ["#apollo", "#space"]
custom_field: preserve_this
aliases:
  - MoonShot
---
# Apollo Mission

Key goal: Land on the moon ^block-landing-99
"""
        note_file = self.vault_root / "01 - Projects" / "Apollo Mission.md"
        note_file.write_text(raw, encoding="utf-8")

        from abby.services.lint import remediate_note_file, remediate_vault

        # 1. Dry run: verify planned actions without writing to disk
        dry_res = remediate_note_file(note_file, self.vault_root, dry_run=True)
        self.assertTrue(dry_res.success)
        self.assertTrue(dry_res.dry_run)
        self.assertEqual(
            len(dry_res.actions), 3
        )  # missing title, status mismatch, tag hashes
        self.assertEqual(note_file.read_text(encoding="utf-8"), raw)
        # Ensure no .bak file was created
        self.assertFalse(
            (self.vault_root / "01 - Projects" / "Apollo Mission.md.bak").exists()
        )

        # 2. Live fix: verify disk write and preservation
        fix_res = remediate_note_file(note_file, self.vault_root, dry_run=False)
        self.assertTrue(fix_res.success)
        self.assertFalse(fix_res.dry_run)

        # Verify no .bak files
        self.assertFalse(
            (self.vault_root / "01 - Projects" / "Apollo Mission.md.bak").exists()
        )

        updated = note_file.read_text(encoding="utf-8")
        self.assertIn('title: "Apollo Mission"', updated)
        self.assertIn("status: active", updated)
        self.assertIn("- apollo", updated)
        self.assertIn("- space", updated)
        self.assertNotIn("#apollo", updated)
        self.assertIn("custom_field: preserve_this", updated)
        self.assertIn("MoonShot", updated)
        self.assertIn("Key goal: Land on the moon ^block-landing-99", updated)

        # Audit should now be completely clean
        audit_res = audit_single_note(
            self.vault_root, "01 - Projects/Apollo Mission.md"
        )
        self.assertTrue(audit_res.is_clean)

    def test_remediate_raw_note_injection(self):
        self.init_vault()
        raw = "# Raw Meeting Note\n\nDiscussion notes with ^block-123"
        note_file = self.vault_root / "00 - Inbox" / "Meeting Note.md"
        note_file.write_text(raw, encoding="utf-8")

        from abby.services.lint import remediate_note_file

        fix_res = remediate_note_file(note_file, self.vault_root, dry_run=False)
        self.assertTrue(fix_res.success)
        updated = note_file.read_text(encoding="utf-8")
        self.assertTrue(updated.startswith("---\n"))
        self.assertIn('title: "Meeting Note"', updated)
        self.assertIn("type: inbox", updated)
        self.assertIn("status: unprocessed", updated)
        self.assertIn("Discussion notes with ^block-123", updated)

        # Audit should now be completely clean
        audit_res = audit_single_note(self.vault_root, "00 - Inbox/Meeting Note.md")
        self.assertTrue(audit_res.is_clean)

    def test_domain_status_and_type_mismatch_detection(self):
        """Verify domain-lifecycle misalignment detection across all PARA domains."""
        self.init_vault()
        # 1. 00 - Inbox with project-note and active
        self.create_note(
            domain="00 - Inbox",
            filename="Task.md",
            title="Task",
            type_="project-note",
            status="active",
        )
        # 2. 01 - Projects with inbox and unprocessed
        self.create_note(
            domain="01 - Projects",
            filename="Alpha.md",
            title="Alpha",
            description="Alpha description.",
            type_="inbox",
            status="unprocessed",
        )
        # 3. 02 - Areas with resource-note and evergreen
        self.create_note(
            domain="02 - Areas",
            filename="Health.md",
            title="Health",
            description="Health description.",
            type_="resource-note",
            status="evergreen",
        )
        # 4. 03 - Resources with area-note and active
        self.create_note(
            domain="03 - Resources",
            filename="Rust.md",
            title="Rust",
            description="Rust description.",
            type_="area-note",
            status="active",
        )
        # 5. 04 - Archives with project-note and active
        self.create_note(
            domain="04 - Archives",
            filename="Old.md",
            title="Old",
            type_="project-note",
            status="active",
        )

        report = audit_vault(self.vault_root)
        self.assertEqual(report.total_audited, 5)
        self.assertEqual(report.clean_notes, 0)
        self.assertEqual(report.total_errors, 0)
        self.assertEqual(report.total_warnings, 10)  # 2 per note (type + status)

        rules = {v.rule for v in report.violations}
        self.assertIn("domain-status-mismatch", rules)
        self.assertIn("domain-type-mismatch", rules)
        self.assertTrue(all(v.is_fixable for v in report.violations))

    def test_domain_alignment_remediation(self):
        """Verify automated repair of domain-status and domain-type mismatches to canonical defaults."""
        self.init_vault()
        self.create_note(
            domain="00 - Inbox",
            filename="Task.md",
            title="Task",
            type_="project-note",
            status="active",
        )
        self.create_note(
            domain="01 - Projects",
            filename="Alpha.md",
            title="Alpha",
            description="Alpha description.",
            type_="inbox",
            status="unprocessed",
        )
        self.create_note(
            domain="02 - Areas",
            filename="Health.md",
            title="Health",
            description="Health description.",
            type_="resource-note",
            status="evergreen",
        )
        self.create_note(
            domain="03 - Resources",
            filename="Rust.md",
            title="Rust",
            description="Rust description.",
            type_="area-note",
            status="active",
        )
        self.create_note(
            domain="04 - Archives",
            filename="Old.md",
            title="Old",
            type_="project-note",
            status="active",
        )

        from abby.services.lint import remediate_vault

        post_report, fix_results = remediate_vault(self.vault_root, dry_run=False)
        self.assertEqual(len(fix_results), 5)
        self.assertEqual(post_report.fixed_notes, 5)
        self.assertEqual(post_report.fixed_violations, 10)

        # Verify on-disk file contents are aligned to canonical defaults
        inbox_content = (self.vault_root / "00 - Inbox" / "Task.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("type: inbox", inbox_content)
        self.assertIn("status: unprocessed", inbox_content)

        proj_content = (self.vault_root / "01 - Projects" / "Alpha.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("type: project-note", proj_content)
        self.assertIn("status: active", proj_content)

        area_content = (self.vault_root / "02 - Areas" / "Health.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("type: area-note", area_content)
        self.assertIn("status: active", area_content)

        res_content = (self.vault_root / "03 - Resources" / "Rust.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("type: resource-note", res_content)
        self.assertIn("status: evergreen", res_content)

        arch_content = (self.vault_root / "04 - Archives" / "Old.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("type: archive-note", arch_content)
        self.assertIn("status: archived", arch_content)

        # Vault audit should now be completely clean
        clean_report = audit_vault(self.vault_root)
        self.assertEqual(clean_report.total_violations, 0)
        self.assertEqual(clean_report.clean_notes, 5)

    def test_domain_scoped_remediation(self):
        """Verify --domain scoping restricts remediation to that domain only."""
        self.init_vault()
        self.create_note(
            domain="01 - Projects",
            filename="Proj.md",
            title="Proj",
            type_="inbox",
            status="unprocessed",
        )
        self.create_note(
            domain="04 - Archives",
            filename="Old.md",
            title="Old",
            type_="project-note",
            status="active",
        )

        from abby.services.lint import remediate_vault

        # Remediate only archives
        post_report, fix_results = remediate_vault(
            self.vault_root, domain="archives", dry_run=False
        )
        self.assertEqual(len(fix_results), 1)
        self.assertEqual(fix_results[0].file_path, "04 - Archives/Old.md")

        # Verify archives was repaired
        arch_content = (self.vault_root / "04 - Archives" / "Old.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("type: archive-note", arch_content)
        self.assertIn("status: archived", arch_content)

        # Verify projects was untouched
        proj_content = (self.vault_root / "01 - Projects" / "Proj.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("type: inbox", proj_content)
        self.assertIn("status: unprocessed", proj_content)


if __name__ == "__main__":
    unittest.main()
