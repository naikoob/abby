"""End-to-end integration test executing all 6 scenarios from quickstart.md (T033)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import CliRunner, IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import CliRunner, IsolatedVaultTestCase

from abby.mcp.handlers import handle_note_read, handle_note_refactor


class TestQuickstartScenarios(IsolatedVaultTestCase):
    """Execution of all 6 quickstart validation scenarios in a sandboxed temporary vault."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_scenario_1_note_read(self) -> None:
        """Scenario 1: Full Note Reading via note_read MCP Tool."""
        ai_dir = self.vault_root / "03 - Resources" / "AI"
        ai_dir.mkdir(parents=True, exist_ok=True)
        note_file = ai_dir / "Transformers.md"
        note_file.write_text(
            "---\n"
            'title: "Transformers"\n'
            'description: "Attention-based sequence models."\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n  - deep-learning\n"
            "---\n"
            "# Transformers\n\n"
            "Body content explaining self-attention.\n",
            encoding="utf-8",
        )

        res = handle_note_read(
            {"note": "03 - Resources/AI/Transformers.md"}, self.vault_root
        )
        self.assertFalse(res.isError)
        payload = json.loads(res.content[0].text)
        self.assertEqual(payload["title"], "Transformers")
        self.assertIn("description", payload["frontmatter"])
        self.assertTrue(payload["body"].startswith("# Transformers"))

    def test_scenario_2_note_refactor(self) -> None:
        """Scenario 2: Vault-Wide Link Refactoring via note_refactor MCP Tool."""
        self.create_note(
            domain="01 - Projects",
            filename="Old Name.md",
            title="Old Name",
            body="Project notes.",
        )
        referrer = self.create_note(
            domain="03 - Resources",
            filename="Overview.md",
            title="Overview",
            body="See [[Old Name]] for details.",
        )

        # 1. Preview with dry_run=True
        res_dry = handle_note_refactor(
            {
                "source": "01 - Projects/Old Name.md",
                "target": "01 - Projects/New Name.md",
                "dry_run": True,
            },
            self.vault_root,
        )
        self.assertFalse(res_dry.isError)
        self.assertIn("[DRY-RUN]", res_dry.content[0].text)
        self.assertTrue((self.vault_root / "01 - Projects" / "Old Name.md").exists())
        self.assertFalse((self.vault_root / "01 - Projects" / "New Name.md").exists())

        # 2. Execute live refactor
        res_live = handle_note_refactor(
            {
                "source": "01 - Projects/Old Name.md",
                "target": "01 - Projects/New Name.md",
                "dry_run": False,
            },
            self.vault_root,
        )
        self.assertFalse(res_live.isError)
        self.assertFalse((self.vault_root / "01 - Projects" / "Old Name.md").exists())
        self.assertTrue((self.vault_root / "01 - Projects" / "New Name.md").exists())
        self.assertIn("[[New Name]]", referrer.read_text(encoding="utf-8"))

    def test_scenario_3_sources_lint_and_search(self) -> None:
        """Scenario 3: sources Lint Validation & Search Discovery."""
        # 1. Lint detects missing resource
        malformed = self.vault_root / "03 - Resources" / "Malformed Source.md"
        malformed.write_text(
            "---\n"
            'title: "Malformed Source"\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n  - test\n"
            "sources:\n"
            '  - title: "Upstream Spec without Resource"\n'
            "---\n"
            "# Malformed Source\n\nContent.\n",
            encoding="utf-8",
        )
        code, out, _ = CliRunner.invoke(
            ["lint", "03 - Resources/Malformed Source.md", "--json"]
        )
        self.assertIn("missing-source-resource", out)

        # 2. FTS5 search finds note via cited paper author
        raft_note = self.vault_root / "03 - Resources" / "Raft Consensus.md"
        raft_note.write_text(
            "---\n"
            'title: "Raft Consensus"\n'
            'description: "Distributed consensus algorithm."\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n  - distributed-systems\n"
            "sources:\n"
            '  - resource: "https://raft.github.io"\n'
            '    title: "In Search of an Understandable Consensus Algorithm"\n'
            '    author: "Diego Ongaro and John Ousterhout"\n'
            "---\n"
            "# Raft Consensus\n\nLeader election and log replication.\n",
            encoding="utf-8",
        )
        code, out, _ = CliRunner.invoke(["find", "Ousterhout", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(len(data.get("notes", [])) >= 1)
        self.assertEqual(data["notes"][0]["title"], "Raft Consensus")

    def test_scenario_4_move_with_description_and_strict_lint(self) -> None:
        """Scenario 4: Typed Note Graduation with Description."""
        draft_note = self.vault_root / "00 - Inbox" / "Draft.md"
        draft_note.write_text(
            "---\n"
            'title: "Draft"\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: inbox\n"
            "status: unprocessed\n"
            "tags:\n  - inbox\n"
            "---\n"
            "# Draft\n\nDraft attention mechanisms.\n",
            encoding="utf-8",
        )

        # Move note with description
        code, out, err = CliRunner.invoke(
            [
                "move",
                "00 - Inbox/Draft.md",
                "03 - Resources/AI",
                "--description",
                "Core concepts of transformer attention mechanisms.",
            ]
        )
        self.assertEqual(code, 0)
        graduated_path = self.vault_root / "03 - Resources" / "AI" / "Draft.md"
        self.assertTrue(graduated_path.exists())

        # Run strict lint on the relocated note
        code, out, err = CliRunner.invoke(
            ["lint", "03 - Resources/AI/Draft.md", "--strict"]
        )
        self.assertEqual(code, 0)

    def test_scenario_5_space_safe_actor_derivation(self) -> None:
        """Scenario 5: Space-Safe Default Actor Derivation."""
        self.create_note(
            domain="03 - Resources",
            filename="Raft Consensus.md",
            title="Raft Consensus",
            body="Content.",
        )
        with patch.dict(os.environ, {"ABBY_USER": "John Doe"}):
            code, out, err = CliRunner.invoke(
                ["verify", "03 - Resources/Raft Consensus.md", "--dry-run", "--json"]
            )
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual(data["actor"], "human:john-doe")

    def test_scenario_6_multihop_link_traversal(self) -> None:
        """Scenario 6: Multi-Hop Link Traversal (--depth 2)."""
        ai_dir = self.vault_root / "03 - Resources" / "AI"
        ai_dir.mkdir(parents=True, exist_ok=True)
        (ai_dir / "Transformers.md").write_text(
            "---\n"
            'title: "Transformers"\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n  - deep-learning\n"
            "---\n"
            "# Transformers\n\nUses [[Attention]].\n",
            encoding="utf-8",
        )
        (ai_dir / "Attention.md").write_text(
            "---\n"
            'title: "Attention"\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n  - deep-learning\n"
            "---\n"
            "# Attention\n\nUses [[Softmax]].\n",
            encoding="utf-8",
        )
        (ai_dir / "Softmax.md").write_text(
            "---\n"
            'title: "Softmax"\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n  - math\n"
            "---\n"
            "# Softmax\n\nActivation function.\n",
            encoding="utf-8",
        )

        code, out, err = CliRunner.invoke(
            ["links", "03 - Resources/AI/Transformers.md", "--depth", "2"]
        )
        self.assertEqual(code, 0)
        self.assertIn("## Depth 1 (Direct)", out)
        self.assertIn("03 - Resources/AI/Attention.md", out)
        self.assertIn("## Depth 2 (Transitive)", out)
        self.assertIn("03 - Resources/AI/Softmax.md", out)
