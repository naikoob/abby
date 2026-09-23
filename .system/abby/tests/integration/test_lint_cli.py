"""Tier 3 CLI integration tests for abby lint entrypoint."""

import json
import sys
import tempfile
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


class TestLintCli(Tier3CliTestCase):
    """Tier 3: Testing abby lint CLI contract, streams, and flag position invariance."""

    def test_lint_clean_vault_human(self):
        self.init_vault()
        self.create_note(
            domain="01 - Projects",
            filename="Alpha.md",
            title="Alpha",
            description="Alpha project plan.",
            type_="project-note",
            status="active",
        )
        code, stdout, stderr = self.invoke_cli(["lint"])
        self.assertEqual(code, 0)
        self.assertIn("Vault OKF audit clean", stdout)
        self.assertIn("1 notes audited, 0 violations", stdout)
        self.assertEqual(stderr, "")

    def test_lint_with_violations_human(self):
        self.init_vault()
        # Missing title in 00 - Inbox
        (self.vault_root / "00 - Inbox" / "Untracked.md").write_text(
            "---\ncreated: 2026-09-17\ntype: inbox\nstatus: unprocessed\ntags: []\n---\nBody\n",
            encoding="utf-8",
        )
        code, stdout, stderr = self.invoke_cli(["lint"])
        self.assertEqual(code, 0)  # Non-strict mode exits 0 on audit
        self.assertIn("Untracked.md", stdout)
        self.assertIn("missing-title", stdout)

    def test_lint_json_mode_and_flag_position_invariance(self):
        self.init_vault()
        self.create_note(
            domain="01 - Projects",
            filename="Alpha.md",
            title="Alpha",
            description="Alpha project plan.",
            type_="project-note",
            status="active",
        )

        # 1. Postfix flag: abby lint --json
        code1, stdout1, stderr1 = self.invoke_cli(["lint", "--json"])
        self.assertEqual(code1, 0)
        self.assertEqual(stderr1, "")
        data1 = json.loads(stdout1)
        self.assertEqual(data1["total_audited"], 1)
        self.assertEqual(data1["total_violations"], 0)

        # 2. Prefix flag: abby --json lint
        code2, stdout2, stderr2 = self.invoke_cli(["--json", "lint"])
        self.assertEqual(code2, 0)
        self.assertEqual(stderr2, "")
        data2 = json.loads(stdout2)
        self.assertEqual(data2["total_audited"], 1)
        self.assertEqual(data2["total_violations"], 0)

    def test_lint_scoped_single_note(self):
        self.init_vault()
        note_path = self.create_note(
            domain="01 - Projects",
            filename="Target.md",
            title="Target",
            type_="project-note",
            status="active",
        )
        self.create_note(
            domain="00 - Inbox",
            filename="Other.md",
            title="Other",
            type_="inbox",
            status="unprocessed",
        )

        code, stdout, stderr = self.invoke_cli(["lint", "01 - Projects/Target.md"])
        self.assertEqual(code, 0)
        self.assertIn("Target.md", stdout)
        self.assertNotIn("Other.md", stdout)

    def test_lint_scoped_domain(self):
        self.init_vault()
        self.create_note(
            domain="01 - Projects",
            filename="Proj.md",
            title="Proj",
            type_="project-note",
            status="active",
        )
        self.create_note(
            domain="00 - Inbox",
            filename="In.md",
            title="In",
            type_="inbox",
            status="unprocessed",
        )

        code, stdout, stderr = self.invoke_cli(
            ["lint", "--domain", "projects", "--json"]
        )
        self.assertEqual(code, 0)
        data = json.loads(stdout)
        self.assertEqual(data["total_audited"], 1)

    def test_lint_fix_dry_run_cli(self):
        self.init_vault()
        note_path = self.vault_root / "00 - Inbox" / "Raw.md"
        raw_content = "# Raw Idea\nSome thoughts."
        note_path.write_text(raw_content, encoding="utf-8")

        # Execute abby lint --fix --dry-run
        code, stdout, stderr = self.invoke_cli(["lint", "--fix", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("DRY-RUN", stdout)
        self.assertIn("Raw.md", stdout)
        self.assertEqual(note_path.read_text(encoding="utf-8"), raw_content)

    def test_lint_fix_live_cli(self):
        self.init_vault()
        note_path = self.vault_root / "00 - Inbox" / "Raw.md"
        raw_content = "# Raw Idea\nSome thoughts with ^block-99."
        note_path.write_text(raw_content, encoding="utf-8")

        # Execute abby lint --fix
        code, stdout, stderr = self.invoke_cli(["lint", "--fix"])
        self.assertEqual(code, 0)
        self.assertIn("Fixed", stdout)

        # File is updated on disk
        updated = note_path.read_text(encoding="utf-8")
        self.assertTrue(updated.startswith("---\n"))
        self.assertIn('title: "Raw"', updated)
        self.assertIn("Some thoughts with ^block-99.", updated)

        # Re-linting should report 0 violations
        code2, stdout2, stderr2 = self.invoke_cli(["lint"])
        self.assertEqual(code2, 0)
        self.assertIn("0 violations", stdout2)

    def test_lint_strict_mode_exit_codes(self):
        self.init_vault()
        # Clean vault -> exit code 0 under --strict
        self.create_note(
            domain="01 - Projects",
            filename="Clean.md",
            title="Clean",
            description="Clean project note.",
            type_="project-note",
            status="active",
        )
        code_clean, stdout_clean, _ = self.invoke_cli(["lint", "--strict"])
        self.assertEqual(code_clean, 0)

        # Introduce a warning: tag with '#' prefix
        bad_note = self.vault_root / "00 - Inbox" / "HasWarning.md"
        bad_note.write_text(
            '---\ntitle: "Has Warning"\ncreated: "2026-09-17"\ntype: inbox\nstatus: unprocessed\ntags: ["#warn"]\n---\nBody\n',
            encoding="utf-8",
        )

        # Non-strict mode exits 0
        code_warn_norm, _, _ = self.invoke_cli(["lint"])
        self.assertEqual(code_warn_norm, 0)

        # Strict mode exits 1 on warning
        code_warn_strict, _, _ = self.invoke_cli(["lint", "--strict"])
        self.assertEqual(code_warn_strict, 1)

        # Run --fix followed by --strict -> exits 0
        code_fix, _, _ = self.invoke_cli(["lint", "--fix"])
        self.assertEqual(code_fix, 0)
        code_post_strict, _, _ = self.invoke_cli(["lint", "--strict"])
        self.assertEqual(code_post_strict, 0)

    def test_lint_domain_alignment_lifecycle_cli(self):
        """Verify CLI auditing and remediation of domain lifecycle misalignments."""
        self.init_vault()
        # Create an archived note with active status and project-note type
        bad_archive = self.vault_root / "04 - Archives" / "OldProject.md"
        bad_archive.write_text(
            '---\ntitle: "Old Project"\ncreated: "2026-09-17"\ntype: project-note\nstatus: active\ntags: []\n---\nOld content\n',
            encoding="utf-8",
        )

        # 1. Audit reports warnings
        code, stdout, _ = self.invoke_cli(["lint"])
        self.assertEqual(code, 0)
        self.assertIn("domain-status-mismatch", stdout)
        self.assertIn("domain-type-mismatch", stdout)

        # 2. Strict mode exits 1
        code_strict, _, _ = self.invoke_cli(["lint", "--strict"])
        self.assertEqual(code_strict, 1)

        # 3. Fix aligns to domain defaults
        code_fix, stdout_fix, _ = self.invoke_cli(["lint", "--fix"])
        self.assertEqual(code_fix, 0)
        self.assertIn("Fixed", stdout_fix)

        # Check content on disk
        repaired = bad_archive.read_text(encoding="utf-8")
        self.assertIn("type: archive-note", repaired)
        self.assertIn("status: archived", repaired)

        # 4. Strict mode now passes with exit code 0
        code_clean, stdout_clean, _ = self.invoke_cli(["lint", "--strict"])
        self.assertEqual(code_clean, 0)
        self.assertIn("0 violations", stdout_clean)

    def test_lint_invalid_domain_exit_code_2(self):
        """Verify invalid domain arguments trigger exit code 2."""
        self.init_vault()
        # Human mode
        code, stdout, stderr = self.invoke_cli(
            ["lint", "--domain", "nonexistent_domain"]
        )
        self.assertEqual(code, 2)
        self.assertIn("Invalid domain", stderr)

        # JSON mode
        code_json, stdout_json, _ = self.invoke_cli(
            ["lint", "--domain", "nonexistent_domain", "--json"]
        )
        self.assertEqual(code_json, 2)
        data = json.loads(stdout_json)
        self.assertFalse(data["success"])
        self.assertIn("Invalid domain", data["error"])

    def test_lint_path_traversal_rejected(self):
        """Verify that attempting to lint or fix files outside vault root is rejected with code 1."""
        self.init_vault()

        with tempfile.TemporaryDirectory() as outside_dir:
            outside_file = Path(outside_dir) / "outside_secret.md"
            outside_content = (
                "---\ntitle: Secret\ncreated: 2026-09-17\n---\nTop secret content\n"
            )
            outside_file.write_text(outside_content, encoding="utf-8")

            # 1. Traversal via relative path
            code, stdout, stderr = self.invoke_cli(["lint", "../../outside_secret.md"])
            self.assertEqual(code, 1)
            self.assertIn("not found in vault", stderr)

            # 2. Traversal via absolute path
            code_abs, _, stderr_abs = self.invoke_cli(
                ["lint", str(outside_file.resolve())]
            )
            self.assertEqual(code_abs, 1)
            self.assertIn("not found in vault", stderr_abs)

            # 3. Traversal via --fix
            code_fix, _, stderr_fix = self.invoke_cli(
                ["lint", str(outside_file.resolve()), "--fix"]
            )
            self.assertEqual(code_fix, 1)
            self.assertIn("not found in vault", stderr_fix)
            # Verify external file was not modified
            self.assertEqual(outside_file.read_text(encoding="utf-8"), outside_content)

            # 4. JSON mode returns structured error
            code_json, stdout_json, _ = self.invoke_cli(
                ["lint", str(outside_file.resolve()), "--json"]
            )
            self.assertEqual(code_json, 1)
            data = json.loads(stdout_json)
            self.assertFalse(data["success"])
            self.assertIn("not found", data["error"])

    def test_lint_ignores_root_style_and_assets_templates(self):
        """Verify that STYLE.md at vault root and templates in 05 - Assets/ are ignored by abby lint."""
        # Initialize vault to scaffold STYLE.md and 05 - Assets/Templates/
        code_init, _, _ = self.invoke_cli(["init"])
        self.assertEqual(code_init, 0)
        self.assertTrue((self.vault_root / "STYLE.md").exists())
        self.assertTrue(
            (self.vault_root / "05 - Assets/Templates/Project Note.md").exists()
        )

        # Run strict linting on empty note domains
        code, stdout, stderr = self.invoke_cli(["lint", "--strict"])
        self.assertEqual(code, 0)
        self.assertIn("0 notes audited, 0 violations", stdout)
        self.assertEqual(stderr, "")

        # Add a valid note and ensure templates and STYLE.md remain excluded
        self.create_note(
            domain="01 - Projects",
            filename="Alpha.md",
            title="Alpha",
            description="Alpha project plan.",
            type_="project-note",
            status="active",
        )
        code_note, stdout_note, stderr_note = self.invoke_cli(["lint", "--strict"])
        self.assertEqual(code_note, 0)
        self.assertIn("1 notes audited, 0 violations", stdout_note)
        self.assertEqual(stderr_note, "")


if __name__ == "__main__":
    unittest.main()
