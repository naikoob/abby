"""Unit tests for note_read MCP tool and structured content payload extraction."""

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
    from tests.support import IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import IsolatedVaultTestCase

from abby.mcp.handlers import handle_note_read
from abby.mcp.types import NoteContentPayload


class TestNoteRead(IsolatedVaultTestCase):
    """Unit tests for handle_note_read and NoteContentPayload extraction."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_note_content_payload_dataclass(self) -> None:
        payload = NoteContentPayload(
            path="03 - Resources/Transformers.md",
            title="Transformers",
            frontmatter={"title": "Transformers", "type": "resource-note"},
            body="# Transformers\n\nAttention is all you need.",
            content="---\ntitle: Transformers\n---\n# Transformers\n\nAttention is all you need.",
        )
        d = payload.to_dict()
        self.assertEqual(d["path"], "03 - Resources/Transformers.md")
        self.assertEqual(d["title"], "Transformers")
        self.assertEqual(d["frontmatter"]["type"], "resource-note")
        self.assertEqual(d["body"], "# Transformers\n\nAttention is all you need.")
        self.assertIn("title: Transformers", d["content"])

    def test_note_read_full_frontmatter(self) -> None:
        note_content = (
            "---\n"
            'title: "Transformers Architecture"\n'
            'description: "Self-attention neural networks and sequence modeling."\n'
            'created: "2026-09-17T12:00:00"\n'
            'updated: "2026-09-17T14:30:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - ai\n"
            "  - nlp\n"
            "generated:\n"
            "  by: abby/agent:synthesizer\n"
            '  at: "2026-09-17T12:00:00Z"\n'
            "verified:\n"
            "  - by: human:bookian\n"
            '    at: "2026-09-17T14:30:00Z"\n'
            'stale_after: "2027-09-17T00:00:00Z"\n'
            "sources:\n"
            '  - resource: "https://arxiv.org/abs/1706.03762"\n'
            '    title: "Attention Is All You Need"\n'
            '    author: "Vaswani et al."\n'
            "---\n"
            "# Transformers Architecture\n\n"
            "The Transformer model relies entirely on self-attention mechanisms.\n"
        )
        self.create_note(
            domain="03 - Resources",
            filename="Transformers.md",
            content=note_content,
        )

        res = handle_note_read({"note": "Transformers"}, self.vault_root)
        self.assertFalse(res.isError)
        self.assertEqual(len(res.content), 1)

        data = json.loads(res.content[0].text)
        self.assertEqual(data["path"], "03 - Resources/Transformers.md")
        self.assertEqual(data["title"], "Transformers Architecture")
        self.assertEqual(
            data["frontmatter"]["description"],
            "Self-attention neural networks and sequence modeling.",
        )
        self.assertEqual(data["frontmatter"]["type"], "resource-note")
        self.assertEqual(data["frontmatter"]["status"], "evergreen")
        self.assertEqual(data["frontmatter"]["tags"], ["ai", "nlp"])
        self.assertEqual(data["frontmatter"]["trust_tier"], "human-reviewed")
        self.assertFalse(data["frontmatter"]["is_stale"])
        self.assertIn("Attention Is All You Need", str(data["frontmatter"]["sources"]))
        self.assertEqual(
            data["body"].strip(),
            "# Transformers Architecture\n\nThe Transformer model relies entirely on self-attention mechanisms.",
        )
        self.assertEqual(data["content"], note_content)

    def test_note_read_ambiguity_handling(self) -> None:
        # Create identical stems in two PARA domains
        self.create_note(
            domain="01 - Projects",
            filename="Architecture.md",
            title="Project Architecture",
            body="Project specific architecture.",
        )
        self.create_note(
            domain="03 - Resources",
            filename="Architecture.md",
            title="General Architecture",
            body="Evergreen software architecture concepts.",
        )

        # Querying with ambiguous stem should fail with candidate paths
        res = handle_note_read({"note": "Architecture"}, self.vault_root)
        self.assertTrue(res.isError)
        err_text = res.content[0].text
        self.assertIn("ambiguous", err_text.lower())
        self.assertIn("01 - Projects/Architecture.md", err_text)
        self.assertIn("03 - Resources/Architecture.md", err_text)
        self.assertIn("domain prefix", err_text.lower())

        # Disambiguating with domain prefix succeeds
        res_proj = handle_note_read(
            {"note": "01 - Projects/Architecture.md"}, self.vault_root
        )
        self.assertFalse(res_proj.isError)
        data_proj = json.loads(res_proj.content[0].text)
        self.assertEqual(data_proj["path"], "01 - Projects/Architecture.md")

        res_res = handle_note_read(
            {"note": "03 - Resources/Architecture.md"}, self.vault_root
        )
        self.assertFalse(res_res.isError)
        data_res = json.loads(res_res.content[0].text)
        self.assertEqual(data_res["path"], "03 - Resources/Architecture.md")

    def test_note_read_non_existent(self) -> None:
        res = handle_note_read({"note": "Ghost Note"}, self.vault_root)
        self.assertTrue(res.isError)
        self.assertIn("not found", res.content[0].text.lower())

    def test_note_read_missing_argument(self) -> None:
        res_empty = handle_note_read({}, self.vault_root)
        self.assertTrue(res_empty.isError)
        self.assertIn("required", res_empty.content[0].text.lower())

        res_blank = handle_note_read({"note": "   "}, self.vault_root)
        self.assertTrue(res_blank.isError)


if __name__ == "__main__":
    import unittest

    unittest.main()

