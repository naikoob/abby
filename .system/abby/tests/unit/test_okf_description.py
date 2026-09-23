import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.models.okf import OKFFrontmatter
from abby.services.okf_parser import parse_okf_frontmatter, tokenize_frontmatter


class TestOKFDescription(unittest.TestCase):
    """Test suite verifying OKF frontmatter description parsing, serialization, and safety."""

    def test_okf_frontmatter_default_none(self):
        fm = OKFFrontmatter(title="Test Note")
        self.assertIsNone(fm.description)

    def test_okf_frontmatter_with_description(self):
        fm = OKFFrontmatter(
            title="Project Apollo",
            description="Core telemetry and ingestion pipeline.",
        )
        self.assertEqual(fm.description, "Core telemetry and ingestion pipeline.")

    def test_to_yaml_omits_description_when_none_or_empty(self):
        fm1 = OKFFrontmatter(title="Simple Note", description=None)
        yaml1 = fm1.to_yaml()
        self.assertNotIn("description:", yaml1)

        fm2 = OKFFrontmatter(title="Simple Note 2", description="")
        yaml2 = fm2.to_yaml()
        self.assertNotIn("description:", yaml2)

    def test_to_yaml_serializes_description_properly(self):
        fm = OKFFrontmatter(
            title="Project Apollo",
            description="Core telemetry and ingestion pipeline.",
            created="2026-09-18T10:00:00",
            type="project-note",
            status="active",
            tags=["telemetry"],
        )
        yaml_out = fm.to_yaml()
        expected = (
            "---\n"
            'title: "Project Apollo"\n'
            'description: "Core telemetry and ingestion pipeline."\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: project-note\n"
            "status: active\n"
            "tags:\n"
            "  - telemetry\n"
            "---\n"
        )
        self.assertEqual(yaml_out, expected)

    def test_to_yaml_escapes_quotes_and_backslashes(self):
        fm = OKFFrontmatter(
            title="Escaped Note",
            description='Uses "Raft" consensus and C:\\data path.',
        )
        yaml_out = fm.to_yaml()
        self.assertIn(
            'description: "Uses \\"Raft\\" consensus and C:\\\\data path."',
            yaml_out,
        )

    def test_from_markdown_parses_description(self):
        md = (
            "---\n"
            'title: "Consensus Note"\n'
            'description: "Raft algorithm overview."\n'
            'created: "2026-09-18T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - consensus\n"
            "---\n"
            "\n"
            "# Consensus Note\n"
            "\n"
            "Body content...\n"
        )
        fm = OKFFrontmatter.from_markdown(md)
        self.assertEqual(fm.title, "Consensus Note")
        self.assertEqual(fm.description, "Raft algorithm overview.")
        self.assertEqual(fm.type, "resource-note")
        self.assertEqual(fm.status, "evergreen")

    def test_from_markdown_without_description_defaults_none(self):
        md = (
            "---\n"
            'title: "Legacy Note"\n'
            'created: "2026-09-18T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - legacy\n"
            "---\n"
        )
        fm = OKFFrontmatter.from_markdown(md)
        self.assertEqual(fm.title, "Legacy Note")
        self.assertIsNone(fm.description)

    def test_parse_okf_frontmatter_helper_extracts_description(self):
        md = (
            "---\n"
            'title: "Helper Test"\n'
            'description: "Helper description."\n'
            "status: active\n"
            "---\n"
        )
        d = parse_okf_frontmatter(md, default_title="Helper Test")
        self.assertEqual(d.get("title"), "Helper Test")
        self.assertEqual(d.get("description"), "Helper description.")
        self.assertEqual(d.get("status"), "active")


if __name__ == "__main__":
    unittest.main()
