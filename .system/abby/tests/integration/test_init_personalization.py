"""Integration tests for vault personalization and template scaffolding (abby init)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import CliRunner, Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import CliRunner, Tier2FilesystemTestCase

from abby.constants import (
    CANONICAL_TEMPLATES,
    DEFAULT_AGENTS_FILE_NAME,
    DEFAULT_STYLE_FILE_NAME,
    DEFAULT_TEMPLATES_SUBDIR,
    REQUIRED_DIRECTORIES,
)
from abby.core.init import init_vault


class TestInitPersonalization(Tier2FilesystemTestCase):
    """Integration test suite for STYLE.md, AGENTS.md, and canonical template initialization."""

    def test_init_scaffolds_style_and_templates_on_fresh_vault(self) -> None:
        result = init_vault(self.vault_root)

        self.assertTrue(result["success"])
        self.assertTrue(result.get("style_initialized"))
        self.assertTrue(result.get("agents_initialized"))
        self.assertEqual(result.get("templates_initialized"), len(CANONICAL_TEMPLATES))

        # Assert STYLE.md exists and has sane defaults
        style_file = self.vault_root / DEFAULT_STYLE_FILE_NAME
        self.assertTrue(style_file.is_file())
        style_text = style_file.read_text(encoding="utf-8")
        self.assertIn("## 1. User Profile & Context", style_text)
        self.assertIn("## 2. Voice, Tone & Cadence", style_text)
        self.assertIn("## 3. Formatting & Obsidian Markdown", style_text)
        self.assertIn("## 4. Taxonomy & Tagging", style_text)
        self.assertIn("## 5. Domain Lexicon & Shorthand", style_text)

        # Assert AGENTS.md exists and has authoritative guide
        agents_file = self.vault_root / DEFAULT_AGENTS_FILE_NAME
        self.assertTrue(agents_file.is_file())
        agents_text = agents_file.read_text(encoding="utf-8")
        self.assertIn(
            "# Abby Knowledge Vault: Agent Operating Guide & Protocol", agents_text
        )
        self.assertIn("Air-Gap Persona Model", agents_text)

        # Assert templates exist in 05 - Assets/Templates/
        templates_dir = self.vault_root / DEFAULT_TEMPLATES_SUBDIR
        self.assertTrue(templates_dir.is_dir())
        for name in CANONICAL_TEMPLATES:
            tmpl_file = templates_dir / name
            self.assertTrue(tmpl_file.is_file(), f"Missing template: {name}")
            tmpl_content = tmpl_file.read_text(encoding="utf-8")
            self.assertTrue(tmpl_content.startswith("---\n"))

        # Assert created list contains directories, style, agents, and templates
        self.assertIn(DEFAULT_STYLE_FILE_NAME, result["created"])
        self.assertIn(DEFAULT_AGENTS_FILE_NAME, result["created"])
        for name in CANONICAL_TEMPLATES:
            self.assertIn(f"{DEFAULT_TEMPLATES_SUBDIR}/{name}", result["created"])

    def test_init_is_idempotent_and_preserves_custom_style_and_templates(self) -> None:
        # First initialization
        init_vault(self.vault_root)

        # Add custom user directives
        style_file = self.vault_root / DEFAULT_STYLE_FILE_NAME
        style_file.write_text("CUSTOM_USER_DIRECTIVE_PRESERVE", encoding="utf-8")

        agents_file = self.vault_root / DEFAULT_AGENTS_FILE_NAME
        agents_file.write_text("CUSTOM_AGENT_DIRECTIVE_PRESERVE", encoding="utf-8")

        concept_file = self.vault_root / DEFAULT_TEMPLATES_SUBDIR / "Concept Note.md"
        concept_file.write_text("CUSTOM_CONCEPT_TEMPLATE_PRESERVE", encoding="utf-8")

        # Second initialization
        second_result = init_vault(self.vault_root)

        self.assertTrue(second_result["success"])
        # Custom content must remain untouched
        self.assertEqual(
            style_file.read_text(encoding="utf-8"), "CUSTOM_USER_DIRECTIVE_PRESERVE"
        )
        self.assertEqual(
            agents_file.read_text(encoding="utf-8"), "CUSTOM_AGENT_DIRECTIVE_PRESERVE"
        )
        self.assertEqual(
            concept_file.read_text(encoding="utf-8"), "CUSTOM_CONCEPT_TEMPLATE_PRESERVE"
        )

        # In existed, not created
        self.assertIn(DEFAULT_STYLE_FILE_NAME, second_result["existed"])
        self.assertIn(DEFAULT_AGENTS_FILE_NAME, second_result["existed"])
        self.assertIn(
            f"{DEFAULT_TEMPLATES_SUBDIR}/Concept Note.md", second_result["existed"]
        )
        self.assertNotIn(DEFAULT_STYLE_FILE_NAME, second_result["created"])
        self.assertNotIn(DEFAULT_AGENTS_FILE_NAME, second_result["created"])

    def test_init_partial_scaffolding_restores_only_missing_items(self) -> None:
        # First initialization
        init_vault(self.vault_root)

        # Delete only Meeting Note.md and AGENTS.md
        meeting_file = self.vault_root / DEFAULT_TEMPLATES_SUBDIR / "Meeting Note.md"
        meeting_file.unlink()
        self.assertFalse(meeting_file.exists())

        agents_file = self.vault_root / DEFAULT_AGENTS_FILE_NAME
        agents_file.unlink()
        self.assertFalse(agents_file.exists())

        # Customize Project Note.md
        project_file = self.vault_root / DEFAULT_TEMPLATES_SUBDIR / "Project Note.md"
        project_file.write_text("PRESERVE_PROJECT_TEMPLATE", encoding="utf-8")

        # Run init again
        partial_result = init_vault(self.vault_root)

        self.assertTrue(partial_result["success"])
        self.assertTrue(meeting_file.exists())
        self.assertTrue(agents_file.exists())
        self.assertEqual(
            project_file.read_text(encoding="utf-8"), "PRESERVE_PROJECT_TEMPLATE"
        )

        self.assertIn(
            f"{DEFAULT_TEMPLATES_SUBDIR}/Meeting Note.md", partial_result["created"]
        )
        self.assertIn(DEFAULT_AGENTS_FILE_NAME, partial_result["created"])
        self.assertIn(
            f"{DEFAULT_TEMPLATES_SUBDIR}/Project Note.md", partial_result["existed"]
        )

    def test_cli_init_human_output(self) -> None:
        code, out, err = CliRunner.invoke(["init"])
        self.assertEqual(code, 0)
        self.assertIn(
            f"[CREATED] {DEFAULT_STYLE_FILE_NAME}: initialized with sane defaults", out
        )
        self.assertIn(
            f"[CREATED] {DEFAULT_AGENTS_FILE_NAME}: initialized with authoritative guide",
            out,
        )
        self.assertIn("[CREATED] 05 - Assets/Templates/Project Note.md", out)
        self.assertIn("Initialization complete.", out)

        # Subsequent run reports existed
        code, out, err = CliRunner.invoke(["init"])
        self.assertEqual(code, 0)
        self.assertIn(f"[OK] {DEFAULT_STYLE_FILE_NAME}: exists", out)
        self.assertIn(f"[OK] {DEFAULT_AGENTS_FILE_NAME}: exists", out)
        self.assertIn("[OK] 05 - Assets/Templates: exists (5 templates present)", out)

    def test_cli_init_json_output(self) -> None:
        code, out, _ = CliRunner.invoke(["--json", "init"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertTrue(data["style_initialized"])
        self.assertTrue(data["agents_initialized"])
        self.assertEqual(data["templates_initialized"], len(CANONICAL_TEMPLATES))
        self.assertIn(DEFAULT_STYLE_FILE_NAME, data["created"])
        self.assertIn(DEFAULT_AGENTS_FILE_NAME, data["created"])
        self.assertIn("05 - Assets/Templates/Project Note.md", data["created"])
