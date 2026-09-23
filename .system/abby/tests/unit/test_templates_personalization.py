"""Unit tests for template utilities and personalization constants."""

import unittest
from pathlib import Path

from abby.constants import (
    CANONICAL_TEMPLATES,
    DEFAULT_AGENTS_CONTENT,
    DEFAULT_AGENTS_FILE_NAME,
    DEFAULT_STYLE_CONTENT,
    DEFAULT_STYLE_FILE_NAME,
    DEFAULT_TEMPLATES_SUBDIR,
)
from abby.utils.templates import (
    get_assets_dir,
    get_canonical_templates,
    get_default_agents_content,
    get_default_style_content,
)


class TestTemplatesPersonalization(unittest.TestCase):
    """Test suite for personalization constants and template content getters."""

    def test_constants_defined(self):
        self.assertEqual(DEFAULT_STYLE_FILE_NAME, "STYLE.md")
        self.assertEqual(DEFAULT_AGENTS_FILE_NAME, "AGENTS.md")
        self.assertEqual(DEFAULT_TEMPLATES_SUBDIR, "05 - Assets/Templates")
        self.assertIsInstance(DEFAULT_STYLE_CONTENT, str)
        self.assertIsInstance(DEFAULT_AGENTS_CONTENT, str)
        self.assertIsInstance(CANONICAL_TEMPLATES, dict)

    def test_vault_first_resolution(self):
        assets_dir = get_assets_dir()
        self.assertTrue(assets_dir.is_dir(), f"Assets dir does not exist: {assets_dir}")
        self.assertTrue((assets_dir / "Templates").is_dir())
        templates = get_canonical_templates()
        self.assertEqual(len(templates), 5)
        self.assertIn("Project Note.md", templates)

    def test_fallback_templates_when_vault_detached(self):
        dummy_root = Path("/tmp/nonexistent_vault_root_12345")
        templates = get_canonical_templates(vault_root=dummy_root)
        self.assertEqual(len(templates), 5)
        self.assertIn("Project Note.md", templates)
        style = get_default_style_content(vault_root=dummy_root)
        self.assertIn("## 1. User Profile & Context", style)
        agents = get_default_agents_content(vault_root=dummy_root)
        self.assertIn("Air-Gap Persona Model", agents)

    def test_default_style_content(self):
        content = get_default_style_content()
        self.assertTrue(len(content) > 100)
        self.assertIn("## 1. User Profile & Context", content)
        self.assertIn("## 2. Voice, Tone & Cadence", content)
        self.assertIn("## 3. Formatting & Obsidian Markdown", content)
        self.assertIn("## 4. Taxonomy & Tagging", content)
        self.assertIn("## 5. Domain Lexicon & Shorthand", content)
        self.assertIn("05 - Assets/Templates/", content)

    def test_default_agents_content(self):
        content = get_default_agents_content()
        self.assertTrue(len(content) > 100)
        self.assertIn(
            "# Abby Knowledge Vault: Agent Operating Guide & Protocol", content
        )
        self.assertIn("Air-Gap Persona Model", content)
        self.assertIn("Knowledge Domain", content)
        self.assertIn("System Domain", content)

    def test_canonical_templates_presence(self):
        templates = get_canonical_templates()
        expected_names = [
            "Project Note.md",
            "Area Note.md",
            "Concept Note.md",
            "Meeting Note.md",
            "Decision Record.md",
        ]
        for name in expected_names:
            self.assertIn(name, templates, f"Expected template '{name}' not found")
            tmpl_content = templates[name]
            self.assertTrue(
                tmpl_content.startswith("---\n"),
                f"Template '{name}' missing frontmatter delimiter",
            )
            self.assertIn(
                "type:", tmpl_content, f"Template '{name}' missing type frontmatter key"
            )
            self.assertIn(
                "status:",
                tmpl_content,
                f"Template '{name}' missing status frontmatter key",
            )
            has_title_header = (
                "# {{title}}" in tmpl_content or "# ADR: {{title}}" in tmpl_content
            )
            self.assertTrue(
                has_title_header, f"Template '{name}' missing primary title header"
            )


if __name__ == "__main__":
    unittest.main()
