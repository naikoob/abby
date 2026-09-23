"""Tier 3: Broken link diagnostics, heading anchor validation, and strict CI mode."""

from __future__ import annotations

import json
import os
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
    from tests.support import CliRunner, IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import CliRunner, IsolatedVaultTestCase


class TestUserStory2BrokenLinks(IsolatedVaultTestCase):
    """Tier 3: Broken link diagnostics, heading anchor validation, and strict CI mode."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_broken_links_plain_text_and_json(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Apollo.md",
            title="Apollo Kickoff",
            body=(
                "Links to [[Nonexistent Note]] and "
                "[Missing Markdown](../03%20-%20Resources/missing.md).\n"
                "Also missing asset ![[nonexistent_asset.png]].\n"
            ),
        )

        # Plain text
        code, out, err = CliRunner.invoke(["links", "--broken"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Apollo.md:", out)
        self.assertIn("[[Nonexistent Note]] -> target not found", out)
        self.assertIn("../03 - Resources/missing.md) -> target not found", out)
        self.assertIn("![[nonexistent_asset.png]] -> target not found", out)

        # JSON
        code, out, err = CliRunner.invoke(["--json", "links", "--broken"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["total_broken"], 3)
        targets = [b["target"] for b in data["broken_links"]]
        self.assertIn("Nonexistent Note", targets)
        self.assertIn("../03 - Resources/missing.md", targets)
        self.assertIn("nonexistent_asset.png", targets)

    def test_broken_links_strict_exit_code(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Dirty.md",
            title="Dirty Note",
            body="Broken [[Ghost Note]].",
        )
        # With broken links, strict mode exits 1
        code, out, err = CliRunner.invoke(["links", "--broken", "--strict"])
        self.assertEqual(code, 1)

        # Without strict mode, exits 0
        code, out, err = CliRunner.invoke(["links", "--broken"])
        self.assertEqual(code, 0)

        # Now clean up vault
        (self.vault_root / "01 - Projects/Dirty.md").unlink()
        code, out, err = CliRunner.invoke(["links", "--broken", "--strict"])
        self.assertEqual(code, 0)

    def test_broken_links_headings_validation(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Guide.md",
            title="Guide",
            body=(
                "# System Overview\n\n"
                "Specs here.\n\n"
                "## Authentication\n\n"
                "Auth specs.\n"
            ),
        )
        self.create_note(
            domain="01 - Projects",
            filename="Caller.md",
            title="Caller",
            body=(
                "Valid heading [[Guide#Authentication]].\n"
                "Invalid heading [[Guide#NonexistentAnchor]].\n"
            ),
        )

        # Without --headings: missing heading anchor is NOT flagged as broken
        code, out, err = CliRunner.invoke(["links", "--broken"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

        # With --headings: missing heading anchor IS flagged
        code, out, err = CliRunner.invoke(["links", "--broken", "--headings"])
        self.assertEqual(code, 0)
        self.assertIn(
            "heading anchor '#NonexistentAnchor' not found in '03 - Resources/Guide.md'",
            out,
        )
        self.assertNotIn("#Authentication", out)

        # JSON with --headings
        code, out, err = CliRunner.invoke(["--json", "links", "--broken", "--headings"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["total_broken"], 1)
        self.assertEqual(data["broken_links"][0]["heading"], "NonexistentAnchor")

    def test_broken_links_domain_scoping(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Proj.md",
            title="Proj",
            body="Dead link [[Ghost In Projects]].",
        )
        self.create_note(
            domain="02 - Areas",
            filename="Area.md",
            title="Area",
            body="Dead link [[Ghost In Areas]].",
        )

        code, out, err = CliRunner.invoke(["links", "--broken", "--domain", "projects"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Proj.md:", out)
        self.assertNotIn("02 - Areas/Area.md:", out)


class TestFlagPositionInvariance(IsolatedVaultTestCase):
    """Tier 3: Flag position invariance tests (Constitution Principle III)."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._class_temp_dir = tempfile.TemporaryDirectory()
        cls.vault_root = Path(cls._class_temp_dir.name).resolve()
        cls._old_vault_root = os.environ.get("ABBY_VAULT_ROOT")
        cls._old_cwd = os.getcwd()
        os.environ["ABBY_VAULT_ROOT"] = str(cls.vault_root)
        os.chdir(cls.vault_root)

        for d in [
            "00 - Inbox",
            "01 - Projects",
            "02 - Areas",
            "03 - Resources",
            "04 - Archives",
            "05 - Assets",
        ]:
            (cls.vault_root / d).mkdir(parents=True, exist_ok=True)

        cls.create_note_at(
            cls.vault_root,
            domain="03 - Resources",
            filename="Architecture.md",
            title="Architecture",
            body="Architecture body.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="Apollo.md",
            title="Apollo",
            body="Links to [[Architecture]].",
        )
        from abby.core.cache import sync_cache

        sync_cache(cls.vault_root)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._old_vault_root is not None:
            os.environ["ABBY_VAULT_ROOT"] = cls._old_vault_root
        elif "ABBY_VAULT_ROOT" in os.environ:
            del os.environ["ABBY_VAULT_ROOT"]
        os.chdir(cls._old_cwd)
        cls._class_temp_dir.cleanup()
        super().tearDownClass()

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_json_flag_invariance(self) -> None:
        # Top-level --json vs subcommand --json vs trailing --json
        code1, out1, _ = CliRunner.invoke(["--json", "links", "Apollo"])
        code2, out2, _ = CliRunner.invoke(["links", "--json", "Apollo"])
        code3, out3, _ = CliRunner.invoke(["links", "Apollo", "--json"])

        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        self.assertEqual(code3, 0)

        data1 = json.loads(out1)
        data2 = json.loads(out2)
        data3 = json.loads(out3)
        self.assertEqual(data1, data2)
        self.assertEqual(data2, data3)

    def test_backlinks_and_details_flag_invariance(self) -> None:
        # -b before note vs -b after note
        code1, out1, _ = CliRunner.invoke(["links", "-b", "Architecture"])
        code2, out2, _ = CliRunner.invoke(["links", "Architecture", "-b"])
        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        self.assertEqual(out1, out2)

        # --details before note vs after note
        code3, out3, _ = CliRunner.invoke(["links", "--details", "Apollo"])
        code4, out4, _ = CliRunner.invoke(["links", "Apollo", "--details"])
        self.assertEqual(code3, 0)
        self.assertEqual(code4, 0)
        self.assertEqual(out3, out4)


if __name__ == "__main__":
    unittest.main()

