"""Test support harness, fixtures, and base test cases for Abby.

Adheres to Constitution Principle VI (Verifiable Technical Quality & Testing Discipline).
Provides:
- Automatic 'src' path injection for zero-config test execution
- IsolatedVaultTestCase managing sandboxed temporary vault directory and environment isolation
- Tier-separated test base classes (Tier1Unit, Tier2Filesystem, Tier3Integration)
- In-process CLI test runner with stdout/stderr/stdin stream isolation
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional

# Ensure 'src' is available on sys.path before importing abby modules
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.cli import main
from abby.constants import DEFAULT_INBOX_DIR, REQUIRED_DIRECTORIES


class CliRunner:
    """Helper to run abby CLI in-process and capture exit code and standard streams."""

    @staticmethod
    def invoke(
        argv: list[str], stdin_str: Optional[str] = None
    ) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        old_stdin = sys.stdin
        if stdin_str is not None:
            fake_stdin = io.StringIO(stdin_str)
            fake_stdin.isatty = lambda: False
            sys.stdin = fake_stdin
        try:
            with redirect_stdout(out), redirect_stderr(err):
                try:
                    code = main(argv)
                except SystemExit as exc:
                    code = exc.code if isinstance(exc.code, int) else 0
        finally:
            sys.stdin = old_stdin
        return code, out.getvalue(), err.getvalue()


class Tier1UnitTestCase(unittest.TestCase):
    """Tier 1: Pure business logic and in-memory unit tests without disk I/O."""

    pass


class IsolatedVaultTestCase(unittest.TestCase):
    """Tier 2 & 3: Sandboxed filesystem test fixture.

    Guarantees that tests execute in disposable temporary directories, never mutates
    the active workspace, and isolates ABBY_VAULT_ROOT in the process environment.
    """

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_root = Path(self.temp_dir.name).resolve()
        os.environ["ABBY_VAULT_ROOT"] = str(self.vault_root)

    def tearDown(self) -> None:
        if "ABBY_VAULT_ROOT" in os.environ:
            del os.environ["ABBY_VAULT_ROOT"]
        self.temp_dir.cleanup()
        super().tearDown()

    def init_vault(self) -> None:
        """Helper to create all standard required vault directories."""
        for d in REQUIRED_DIRECTORIES:
            (self.vault_root / d).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def create_note_at(
        vault_root: Path,
        domain: str = DEFAULT_INBOX_DIR,
        filename: str = "Test Note.md",
        content: Optional[str] = None,
        title: str = "Test Note",
        description: Optional[str] = None,
        status: str = "unprocessed",
        type_: str = "inbox",
        tags: Optional[list[str]] = None,
        body: str = "Note body content.",
    ) -> Path:
        """Helper to scaffold a valid OKF note in a specific vault domain."""
        target_dir = vault_root / domain
        target_dir.mkdir(parents=True, exist_ok=True)
        note_path = target_dir / filename

        if content is not None:
            note_path.write_text(content, encoding="utf-8")
        else:
            tag_lines = "\n".join(f"  - {t}" for t in (tags or ["inbox"]))
            desc_line = f'description: "{description}"\n' if description else ""

            full_content = (
                "---\n"
                f'title: "{title}"\n'
                f"{desc_line}"
                f'created: "2026-09-17T12:00:00"\n'
                f"type: {type_}\n"
                f"status: {status}\n"
                f"tags:\n{tag_lines}\n"
                "---\n"
                f"# {title}\n\n{body}\n"
            )
            note_path.write_text(full_content, encoding="utf-8")

        return note_path

    def create_note(
        self,
        domain: str = DEFAULT_INBOX_DIR,
        filename: str = "Test Note.md",
        content: Optional[str] = None,
        title: str = "Test Note",
        description: Optional[str] = None,
        status: str = "unprocessed",
        type_: str = "inbox",
        tags: Optional[list[str]] = None,
        body: str = "Note body content.",
    ) -> Path:
        """Helper to scaffold a valid OKF note in a specific vault domain."""
        return self.create_note_at(
            self.vault_root,
            domain=domain,
            filename=filename,
            content=content,
            title=title,
            description=description,
            status=status,
            type_=type_,
            tags=tags,
            body=body,
        )

    def assert_file_exists(self, rel_path: str) -> None:
        """Assert that a file exists relative to the sandboxed vault root."""
        full_path = self.vault_root / rel_path
        self.assertTrue(
            full_path.exists(), f"Expected file '{rel_path}' to exist in vault."
        )

    def assert_file_not_exists(self, rel_path: str) -> None:
        """Assert that a file does NOT exist relative to the sandboxed vault root."""
        full_path = self.vault_root / rel_path
        self.assertFalse(
            full_path.exists(), f"Expected file '{rel_path}' NOT to exist in vault."
        )

    def invoke_cli(
        self, argv: list[str], stdin_str: Optional[str] = None
    ) -> tuple[int, str, str]:
        """Invoke CLI within the sandboxed vault environment."""
        return CliRunner.invoke(argv, stdin_str=stdin_str)


class Tier2FilesystemTestCase(IsolatedVaultTestCase):
    """Tier 2: Isolated filesystem tests for state mutations and directory scaffolding."""

    pass


class Tier3CliTestCase(IsolatedVaultTestCase):
    """Tier 3: End-to-end integration tests for command-line entrypoints and stream contracts."""

    pass
