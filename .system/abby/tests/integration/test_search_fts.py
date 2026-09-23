"""Tier 2 tests for FTS5 full-text matching, BM25 ranking, snippets, and REGEXP support."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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

from abby.constants import DEFAULT_INBOX_DIR, DEFAULT_PROJECTS_DIR
from abby.cli.commands.search import execute_find
from abby.models.search import SearchFilter


class TestSearchFtsBase(IsolatedVaultTestCase):
    """Base class for search FTS integration tests."""

    def _run_find(self, f: SearchFilter) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = execute_find(self.vault_root, f)
        return code, out.getvalue(), err.getvalue()


class TestFtsSharedQueries(TestSearchFtsBase):
    """Tier 2 tests for FTS5 queries and ranking sharing a single indexed vault."""

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
            DEFAULT_PROJECTS_DIR,
            "Arch.md",
            title="System Architecture",
            body="Notes on components.",
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_INBOX_DIR,
            "Retro.md",
            title="Sprint Retro",
            body="We discussed system architecture decisions in detail. We discussed PostgreSQL performance.",
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_PROJECTS_DIR,
            "Postgres.md",
            content=(
                "---\n"
                'title: "PostgreSQL Setup"\n'
                'created: "2026-09-17T12:00:00"\n'
                "type: project-note\n"
                "status: active\n"
                "tags: []\n"
                "---\n"
                "Installation steps without repeating the title keyword.\n"
            ),
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_PROJECTS_DIR,
            "Phrase1.md",
            title="Migration Guide",
            body="Step-by-step database migration checklist.",
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_PROJECTS_DIR,
            "Phrase2.md",
            title="Other",
            body="Migration of the database was completed.",
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_PROJECTS_DIR,
            "Auth2026.md",
            title="Auth 2026",
            body="Content",
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_PROJECTS_DIR,
            "OtherAuth.md",
            title="NonAuth 123",
            body="Content",
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_PROJECTS_DIR,
            "Agile.md",
            title="Fast-Paced Delivery",
            body="Working in a fast-paced environment.",
        )
        cls.create_note_at(
            cls.vault_root,
            DEFAULT_PROJECTS_DIR,
            "CppNote.md",
            title="Learning C++",
            body="This is NOT a drill.",
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

    def test_fts5_ranking_title_above_body(self) -> None:
        """Verify title match ranks higher than body match using BM25 weights."""
        f = SearchFilter(query="Architecture")
        code, out, _ = self._run_find(f)
        self.assertEqual(code, 0)
        lines = [line for line in out.strip().split("\n") if line]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], f"{DEFAULT_PROJECTS_DIR}/Arch.md")
        self.assertEqual(lines[1], f"{DEFAULT_INBOX_DIR}/Retro.md")

    def test_fts5_title_only_and_content_only_scoping(self) -> None:
        """Verify --title-only and --content-only scopes."""
        f_title = SearchFilter(query="PostgreSQL", scope="title")
        code, out_title, _ = self._run_find(f_title)
        self.assertEqual(code, 0)
        self.assertEqual(out_title.strip(), f"{DEFAULT_PROJECTS_DIR}/Postgres.md")

        f_content = SearchFilter(query="PostgreSQL", scope="content")
        code, out_content, _ = self._run_find(f_content)
        self.assertEqual(code, 0)
        self.assertEqual(out_content.strip(), f"{DEFAULT_INBOX_DIR}/Retro.md")

    def test_fts5_phrase_query(self) -> None:
        """Verify exact phrase matching."""
        f = SearchFilter(query='"database migration"')
        code, out, _ = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f"{DEFAULT_PROJECTS_DIR}/Phrase1.md")

    def test_regex_query_execution(self) -> None:
        """Verify regex query execution via SQLite REGEXP function."""
        f = SearchFilter(query=r"^Auth \d{4}$")
        code, out, _ = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f"{DEFAULT_PROJECTS_DIR}/Auth2026.md")

    def test_fts5_hyphenated_search(self) -> None:
        """Verify searching for hyphenated terms like fast-paced succeeds without FTS syntax error."""
        f = SearchFilter(query="fast-paced")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out.strip(), f"{DEFAULT_PROJECTS_DIR}/Agile.md")

    def test_fts5_operator_and_special_chars(self) -> None:
        """Verify searching for standalone boolean operator words or C++ executes safely."""
        f_not = SearchFilter(query="NOT")
        code_not, out_not, err_not = self._run_find(f_not)
        self.assertEqual(code_not, 0)
        self.assertEqual(err_not, "")
        self.assertEqual(out_not.strip(), f"{DEFAULT_PROJECTS_DIR}/CppNote.md")

        f_cpp = SearchFilter(query="C++")
        code_cpp, out_cpp, err_cpp = self._run_find(f_cpp)
        self.assertEqual(code_cpp, 0)
        self.assertEqual(err_cpp, "")
        self.assertEqual(out_cpp.strip(), f"{DEFAULT_PROJECTS_DIR}/CppNote.md")


class TestFtsAndRegexSearch(TestSearchFtsBase):
    """Tier 2 tests for FTS5 snippets and error handling."""

    def test_malformed_regex_returns_code_2(self) -> None:
        """Verify malformed regex raises SearchArgumentError and returns code 2."""
        f = SearchFilter(query=r"^[unterminated")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 2)
        self.assertIn("Malformed regular expression", err)

    def test_fts5_snippets_text_output(self) -> None:
        """Verify FTS5 snippet extraction in text mode with bold markers."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "PostgresGuide.md",
            title="Database Guide",
            body="We decided to adopt PostgreSQL with connection pooling in Q4.",
        )
        f = SearchFilter(query="PostgreSQL", snippets=True)
        code, out, _ = self._run_find(f)
        self.assertEqual(code, 0)
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            f"{DEFAULT_PROJECTS_DIR}/PostgresGuide.md [{DEFAULT_PROJECTS_DIR} | unprocessed | unverified | 0 links]",
        )
        self.assertTrue(lines[1].startswith("  "))
        self.assertIn("**PostgreSQL**", lines[1])

    def test_regex_snippets_output(self) -> None:
        """Verify regex query snippet extraction with match window and markers."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "ServiceConfig.md",
            title="Service Config",
            body="Production cluster listening on port 8080 for incoming traffic.",
        )
        f = SearchFilter(query=r"port \d+", snippets=True)
        code, out, _ = self._run_find(f)
        self.assertEqual(code, 0)
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            f"{DEFAULT_PROJECTS_DIR}/ServiceConfig.md [{DEFAULT_PROJECTS_DIR} | unprocessed | unverified | 0 links]",
        )
        self.assertTrue(lines[1].startswith("  "))
        self.assertIn("**port 8080**", lines[1])

    def test_metadata_only_snippets_output(self) -> None:
        """Verify leading body excerpt is displayed when search has no text query but snippets=True."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "Overview.md",
            title="Project Overview",
            body="This project builds high-velocity indexing for knowledge vaults.",
        )
        f = SearchFilter(domain="projects", snippets=True)
        code, out, _ = self._run_find(f)
        self.assertEqual(code, 0)
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            f"{DEFAULT_PROJECTS_DIR}/Overview.md [{DEFAULT_PROJECTS_DIR} | unprocessed | unverified | 0 links]",
        )
        self.assertTrue(lines[1].startswith("  "))
        self.assertIn("This project builds high-velocity", lines[1])

    def test_snippet_fallback_for_title_only_match(self) -> None:
        """Verify fallback to leading body when query matches title but not body."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "Architecture.md",
            title="Architecture Standards",
            body="Clean separation between knowledge domain and system automation.",
        )
        f = SearchFilter(query="Architecture", scope="title", snippets=True)
        code, out, _ = self._run_find(f)
        self.assertEqual(code, 0)
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            f"{DEFAULT_PROJECTS_DIR}/Architecture.md [{DEFAULT_PROJECTS_DIR} | unprocessed | unverified | 0 links]",
        )
        self.assertTrue(lines[1].startswith("  "))


if __name__ == "__main__":
    unittest.main()

