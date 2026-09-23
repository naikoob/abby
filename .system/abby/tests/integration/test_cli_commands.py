"""CLI integration and end-to-end tests for abby command runner (Tier 3)."""

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
    from tests.support import CliRunner, Tier3CliTestCase
except ModuleNotFoundError:
    from support import CliRunner, Tier3CliTestCase
from abby import __version__


class TestCliIntegration(Tier3CliTestCase):
    def test_cli_no_args_displays_help_and_exits_0(self) -> None:
        code, out, err = self.invoke_cli([])
        self.assertEqual(code, 0)
        self.assertIn("usage: abby", err)
        self.assertEqual(out, "")

    def test_cli_version_flag(self) -> None:
        code, out, _ = self.invoke_cli(["-v"])
        self.assertEqual(code, 0)
        self.assertIn(f"abby {__version__}", out)

        code, out, _ = self.invoke_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn(f"abby {__version__}", out)

    def test_cli_unknown_subcommand_exits_2(self) -> None:
        code, _, err = self.invoke_cli(["nonexistent"])
        self.assertEqual(code, 2)
        self.assertIn("invalid choice", err)

    def test_cli_check_on_unhealthy_vault(self) -> None:
        # Vault has no directories yet
        code, out, _ = self.invoke_cli(["check"])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL] 00 - Inbox", out)

        # JSON mode with flag AFTER subcommand
        code, out, _ = self.invoke_cli(["check", "--json"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertFalse(data["healthy"])
        self.assertIn("00 - Inbox", data["missing_directories"])

        # JSON mode with flag BEFORE subcommand
        code, out, _ = self.invoke_cli(["--json", "check"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertFalse(data["healthy"])

    def test_cli_init_and_subsequent_check(self) -> None:
        # Init with flag before subcommand
        code, out, _ = self.invoke_cli(["--json", "init"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertIn("00 - Inbox", data["created"])

        # Check now passes
        code, out, _ = self.invoke_cli(["--json", "check"])
        self.assertEqual(code, 0)
        check_data = json.loads(out)
        self.assertTrue(check_data["healthy"])

        # Subsequent init is idempotent (reports existed)
        code, out, _ = self.invoke_cli(["init"])
        self.assertEqual(code, 0)
        self.assertIn("[OK] 00 - Inbox: exists", out)
        self.assertIn("Initialization complete.", out)

    def test_cli_new_basic_and_stream_isolation(self) -> None:
        self.init_vault()
        code, out, err = self.invoke_cli(["new", "Architecture Thoughts"])
        self.assertEqual(code, 0)
        # In text mode, stdout must contain ONLY the relative path
        self.assertEqual(out.strip(), "00 - Inbox/Architecture Thoughts.md")
        self.assertEqual(err, "")

        # Verify file on disk
        self.assert_file_exists("00 - Inbox/Architecture Thoughts.md")
        content = (self.vault_root / "00 - Inbox/Architecture Thoughts.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('title: "Architecture Thoughts"', content)
        self.assertIn("type: inbox", content)

    def test_cli_new_with_body_flag(self) -> None:
        self.init_vault()
        code, out, _ = self.invoke_cli(
            ["new", "Meeting Summary", "--body", "Discussed roadmap."]
        )
        self.assertEqual(code, 0)
        self.assert_file_exists("00 - Inbox/Meeting Summary.md")
        content = (self.vault_root / "00 - Inbox/Meeting Summary.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Discussed roadmap.", content)

    def test_cli_new_with_piped_stdin(self) -> None:
        self.init_vault()
        code, out, _ = self.invoke_cli(
            ["new", "Piped Thought"], stdin_str="Line from stdin\nSecond line"
        )
        self.assertEqual(code, 0)
        self.assert_file_exists("00 - Inbox/Piped Thought.md")
        content = (self.vault_root / "00 - Inbox/Piped Thought.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Line from stdin\nSecond line", content)

    def test_cli_new_with_empty_piped_stdin(self) -> None:
        self.init_vault()
        code, out, _ = self.invoke_cli(["new", "Empty Pipe Note"], stdin_str="")
        self.assertEqual(code, 0)
        self.assert_file_exists("00 - Inbox/Empty Pipe Note.md")

    def test_cli_new_cjk_title(self) -> None:
        self.init_vault()
        code, out, err = self.invoke_cli(["new", "2026年 架构规划"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "00 - Inbox/2026年 架构规划.md")
        self.assert_file_exists("00 - Inbox/2026年 架构规划.md")

    def test_cli_new_json_mode(self) -> None:
        self.init_vault()
        code, out, _ = self.invoke_cli(["--json", "new", "Structured Capture"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["success"])
        self.assertEqual(data["path"], "00 - Inbox/Structured Capture.md")
        self.assertEqual(data["title"], "Structured Capture")
        self.assertEqual(data["filename"], "Structured Capture.md")
        self.assertIn("created", data)

    def test_cli_new_missing_title_exits_2(self) -> None:
        code, out, err = self.invoke_cli(["new"])
        self.assertEqual(code, 2)
        self.assertIn("Note title is required", err)

        # Whitespace-only title also exits 2
        code, out, err = self.invoke_cli(["new", "   "])
        self.assertEqual(code, 2)
        self.assertIn("Note title is required", err)

        # JSON mode error on missing title
        code, out, _ = self.invoke_cli(["--json", "new"])
        self.assertEqual(code, 2)
        data = json.loads(out)
        self.assertFalse(data["success"])
        self.assertIn("Missing note title", data["error"])

    def test_cli_info(self) -> None:
        self.init_vault()
        code, out, _ = self.invoke_cli(["info"])
        self.assertEqual(code, 0)
        self.assertIn("Abby CLI Version:", out)
        self.assertIn("Vault Root:", out)

        code, out, _ = self.invoke_cli(["--json", "info"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("cli_version", data)
        self.assertIn("vault_root", data)
        self.assertIn("python_version", data)
        self.assertIn("system_path", data)
        self.assertIn("status", data)

    def test_cli_outside_vault_exits_1(self) -> None:
        del os.environ["ABBY_VAULT_ROOT"]
        isolated_dir = Path(tempfile.mkdtemp())
        original_cwd = os.getcwd()
        try:
            os.chdir(str(isolated_dir))
            code, out, err = CliRunner.invoke(["check"])
            self.assertEqual(code, 1)
            self.assertIn("Could not detect Abby Knowledge Vault root directory", err)

            # JSON mode outside vault
            code, out, _ = CliRunner.invoke(["--json", "check"])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertFalse(data["success"])
            self.assertIn(
                "Could not detect Abby Knowledge Vault root directory", data["error"]
            )
        finally:
            os.chdir(original_cwd)
            if isolated_dir.exists():
                isolated_dir.rmdir()

    def test_cli_list_empty_domain(self) -> None:
        self.init_vault()
        code, out, err = self.invoke_cli(["list"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

        # JSON mode on empty domain
        code, out, _ = self.invoke_cli(["--json", "list", "inbox"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["domain"], "inbox")
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["notes"], [])

    def test_cli_list_text_mode_and_json_mode(self) -> None:
        self.init_vault()
        self.invoke_cli(["new", "Note A"])
        self.invoke_cli(["new", "Note B"])

        # Text mode
        code, out, err = self.invoke_cli(["list", "inbox"])
        self.assertEqual(code, 0)
        self.assertIn("00 - Inbox/Note A.md", out)
        self.assertIn("00 - Inbox/Note B.md", out)
        self.assertEqual(err, "")

        # Default domain is inbox
        code, out_default, _ = self.invoke_cli(["list"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), out_default.strip())

        # JSON mode
        code, out_json, _ = self.invoke_cli(["list", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out_json)
        self.assertEqual(data["domain"], "inbox")
        self.assertEqual(data["count"], 2)
        filenames = [n["filename"] for n in data["notes"]]
        self.assertIn("Note A.md", filenames)
        self.assertIn("Note B.md", filenames)

    def test_cli_list_invalid_domain_exits_1(self) -> None:
        self.init_vault()
        code, out, err = self.invoke_cli(["list", "unknown_domain"])
        self.assertEqual(code, 1)
        self.assertIn("Invalid domain 'unknown_domain'", err)

        # In JSON mode
        code, out_json, _ = self.invoke_cli(["--json", "list", "unknown_domain"])
        self.assertEqual(code, 1)
        data = json.loads(out_json)
        self.assertFalse(data["success"])


if __name__ == "__main__":
    unittest.main()
