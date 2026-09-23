"""Unit tests for search query construction, domain resolution, and metadata filtering."""

import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import IsolatedVaultTestCase, Tier1UnitTestCase
except ModuleNotFoundError:
    from support import IsolatedVaultTestCase, Tier1UnitTestCase

from abby.constants import (
    DEFAULT_INBOX_DIR,
    DEFAULT_PROJECTS_DIR,
    DEFAULT_RESOURCES_DIR,
)
from abby.cli.commands.search import execute_find
from abby.core.search import (
    SearchArgumentError,
    SearchDomainError,
    build_search_sql,
    is_regex_query,
    resolve_search_domain,
    sanitize_fts_query,
    validate_iso_date,
)
from abby.models.search import SearchFilter


class TestSearchUnit(Tier1UnitTestCase):
    """Tier 1 unit tests for search helpers and query builder."""

    def test_resolve_search_domain(self) -> None:
        """Verify PARA domain alias resolution and invalid domain detection."""
        self.assertEqual(resolve_search_domain("inbox"), "00 - Inbox")
        self.assertEqual(resolve_search_domain("projects"), "01 - Projects")
        self.assertEqual(resolve_search_domain("areas"), "02 - Areas")
        self.assertEqual(resolve_search_domain("resources"), "03 - Resources")
        self.assertEqual(resolve_search_domain("archives"), "04 - Archives")
        self.assertEqual(resolve_search_domain("01 - Projects"), "01 - Projects")
        self.assertIsNone(resolve_search_domain(None))
        self.assertIsNone(resolve_search_domain(""))

        with self.assertRaises(SearchDomainError):
            resolve_search_domain("invalid-domain")

    def test_validate_iso_date(self) -> None:
        """Verify ISO calendar date validation."""
        self.assertEqual(
            validate_iso_date("2026-09-17", "--created-after"), "2026-09-17"
        )
        self.assertIsNone(validate_iso_date(None, "--created-after"))

        with self.assertRaises(SearchArgumentError):
            validate_iso_date("17-09-2026", "--created-after")

        with self.assertRaises(SearchArgumentError):
            validate_iso_date("2026-02-30", "--created-after")

    def test_regex_detection(self) -> None:
        """Verify regex query detection versus FTS5 terms."""
        self.assertTrue(is_regex_query("/architecture/"))
        self.assertTrue(is_regex_query("^Auth.*"))
        self.assertTrue(is_regex_query(r"\d+"))
        self.assertTrue(is_regex_query("Auth[0-9]+"))
        self.assertFalse(is_regex_query("architecture"))
        self.assertFalse(is_regex_query("Sprint Retro"))
        self.assertFalse(is_regex_query('"database migration"'))

    def test_build_metadata_sql_no_args(self) -> None:
        """Verify default SQL when no filters or query provided."""
        f = SearchFilter()
        sql, params = build_search_sql(f)
        self.assertIn("FROM notes", sql)
        self.assertNotIn("WHERE", sql)
        self.assertIn("ORDER BY COALESCE(notes.updated, notes.created) DESC", sql)
        self.assertEqual(len(params), 0)

    def test_build_metadata_sql_filters(self) -> None:
        """Verify SQL generation for status, domain, type, and tags."""
        f = SearchFilter(
            domain="projects",
            status="active",
            type="project-note",
            tags=["urgent", "backend"],
            tag_conjunction="AND",
        )
        sql, params = build_search_sql(f)
        self.assertIn("notes.domain = ?", sql)
        self.assertIn("LOWER(notes.status) = LOWER(?)", sql)
        self.assertIn("LOWER(notes.type) = LOWER(?)", sql)
        self.assertIn("GROUP BY path HAVING COUNT(DISTINCT LOWER(tag)) = 2", sql)
        self.assertIn("01 - Projects", params)
        self.assertIn("active", params)
        self.assertIn("project-note", params)
        self.assertIn("urgent", params)
        self.assertIn("backend", params)

    def test_build_metadata_sql_or_tags(self) -> None:
        """Verify SQL generation for OR tag conjunction."""
        f = SearchFilter(
            tags=["urgent", "backend"],
            tag_conjunction="OR",
        )
        sql, params = build_search_sql(f)
        self.assertIn(
            "WHERE notes.path IN (SELECT path FROM note_tags WHERE LOWER(tag) IN (?, ?))",
            sql,
        )
        self.assertEqual(params, ["urgent", "backend"])

    def test_sanitize_fts_query(self) -> None:
        """Verify FTS5 query sanitization handles hyphens, operators, and special tokens."""
        self.assertEqual(sanitize_fts_query(""), "")
        self.assertEqual(sanitize_fts_query("architecture"), "architecture")
        self.assertEqual(sanitize_fts_query("arch*"), "arch*")
        self.assertEqual(sanitize_fts_query("fast-paced"), '"fast-paced"')
        self.assertEqual(sanitize_fts_query("NOT"), '"NOT"')
        self.assertEqual(sanitize_fts_query("AND"), '"AND"')
        self.assertEqual(sanitize_fts_query("OR"), '"OR"')
        self.assertEqual(sanitize_fts_query("NEAR"), '"NEAR"')
        self.assertEqual(sanitize_fts_query("C++"), '"C++"')
        self.assertEqual(sanitize_fts_query("*"), '"*"')
        self.assertEqual(
            sanitize_fts_query('"database migration"'), '"database migration"'
        )
        self.assertEqual(
            sanitize_fts_query('foo "bar baz" fast-paced'),
            'foo "bar baz" "fast-paced"',
        )

    def test_build_metadata_sql_duplicate_tags(self) -> None:
        """Verify duplicate tags are deduplicated so AND conjunction count is accurate."""
        f = SearchFilter(
            tags=["backend", "backend"],
            tag_conjunction="AND",
        )
        sql, params = build_search_sql(f)
        self.assertIn("GROUP BY path HAVING COUNT(DISTINCT LOWER(tag)) = 1", sql)
        self.assertEqual(params, ["backend"])

    def test_build_search_sql_regex_title_skips_fts_join(self) -> None:
        """Verify regex search scoped to title does not join notes_fts."""
        f_title = SearchFilter(query="/^Auth/", scope="title")
        sql_title, _ = build_search_sql(f_title)
        self.assertNotIn("notes_fts", sql_title)

        f_content = SearchFilter(query="/^Auth/", scope="content")
        sql_content, _ = build_search_sql(f_content)
        self.assertIn("notes_fts", sql_content)


class TestSearchBase(IsolatedVaultTestCase):
    """Base class for search integration test cases providing isolated runner helper."""

    def _run_find(self, f: SearchFilter) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = execute_find(self.vault_root, f)
        return code, out.getvalue(), err.getvalue()


class TestSearchMetadataExecution(TestSearchBase):
    """Tier 2 tests for execute_find with metadata and tag filters."""

    def test_find_no_args_returns_all_notes(self) -> None:
        """Verify abby find with no arguments lists all notes across knowledge domains."""
        self.init_vault()
        self.create_note(DEFAULT_INBOX_DIR, "Inbox1.md", title="Inbox 1")
        self.create_note(DEFAULT_PROJECTS_DIR, "Project1.md", title="Project 1")

        f = SearchFilter()
        code, out, err = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertIn("00 - Inbox/Inbox1.md", out)
        self.assertIn("01 - Projects/Project1.md", out)

    def test_find_status_filter(self) -> None:
        """Verify filtering by status."""
        self.init_vault()
        self.create_note(
            DEFAULT_INBOX_DIR,
            "Active.md",
            title="Active Note",
            status="active",
        )
        self.create_note(
            DEFAULT_INBOX_DIR,
            "Unprocessed.md",
            title="Unprocessed Note",
            status="unprocessed",
        )

        f = SearchFilter(status="unprocessed")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "00 - Inbox/Unprocessed.md")

    def test_find_domain_alias_resolution(self) -> None:
        """Verify domain filtering with alias resolution."""
        self.init_vault()
        self.create_note(DEFAULT_INBOX_DIR, "Note1.md", title="Note 1")
        self.create_note(DEFAULT_PROJECTS_DIR, "Note2.md", title="Note 2")

        f = SearchFilter(domain="projects")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Note2.md")

    def test_find_invalid_domain_returns_code_1(self) -> None:
        """Verify invalid domain alias returns code 1."""
        f = SearchFilter(domain="unknown_zone")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 1)
        self.assertIn("Unrecognized domain", err)

    def test_find_tag_and_conjunction(self) -> None:
        """Verify AND tag conjunction requires all tags."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "Both.md",
            tags=["backend", "urgent"],
        )
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "One.md",
            tags=["backend"],
        )

        f = SearchFilter(tags=["backend", "urgent"], tag_conjunction="AND")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Both.md")

    def test_find_duplicate_tags_conjunction(self) -> None:
        """Verify passing duplicate tags does not break AND conjunction matching."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "TaggedNote.md",
            tags=["backend"],
        )
        f = SearchFilter(tags=["backend", "backend"], tag_conjunction="AND")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f"{DEFAULT_PROJECTS_DIR}/TaggedNote.md")

class TestDateFilters(TestSearchBase):
    """Tier 2 tests for ISO calendar date range filters."""

    def test_created_date_bounds(self) -> None:
        """Verify --created-after and --created-before filtering."""
        self.init_vault()
        # August note
        self.create_note(
            DEFAULT_INBOX_DIR,
            "Aug.md",
            content=(
                "---\n"
                'title: "August Note"\n'
                'created: "2026-08-15T10:00:00"\n'
                "type: inbox\n"
                "status: unprocessed\n"
                "tags: []\n"
                "---\n"
                "August body.\n"
            ),
        )
        # September note
        self.create_note(
            DEFAULT_INBOX_DIR,
            "Sep.md",
            content=(
                "---\n"
                'title: "September Note"\n'
                'created: "2026-09-10T10:00:00"\n'
                "type: inbox\n"
                "status: unprocessed\n"
                "tags: []\n"
                "---\n"
                "September body.\n"
            ),
        )

        # --created-after 2026-09-01 -> Sep.md only
        f_after = SearchFilter(created_after="2026-09-01")
        code, out_after, _ = self._run_find(f_after)
        self.assertEqual(code, 0)
        self.assertEqual(out_after.strip(), f"{DEFAULT_INBOX_DIR}/Sep.md")

        # --created-before 2026-09-01 -> Aug.md only
        f_before = SearchFilter(created_before="2026-09-01")
        code, out_before, _ = self._run_find(f_before)
        self.assertEqual(code, 0)
        self.assertEqual(out_before.strip(), f"{DEFAULT_INBOX_DIR}/Aug.md")

    def test_updated_date_bounds(self) -> None:
        """Verify --updated-after and --updated-before filtering."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "UpdatedNote.md",
            content=(
                "---\n"
                'title: "Updated Note"\n'
                'created: "2026-08-01T10:00:00"\n'
                'updated: "2026-09-15T14:30:00"\n'
                "type: project-note\n"
                "status: active\n"
                "tags: []\n"
                "---\n"
                "Updated body.\n"
            ),
        )

        f_up = SearchFilter(updated_after="2026-09-01")
        code, out, _ = self._run_find(f_up)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f"{DEFAULT_PROJECTS_DIR}/UpdatedNote.md")

        f_old = SearchFilter(updated_before="2026-09-01")
        code, out_old, _ = self._run_find(f_old)
        self.assertEqual(code, 0)
        self.assertEqual(out_old.strip(), "")

    def test_invalid_date_format_returns_code_2(self) -> None:
        """Verify invalid date string exits with code 2."""
        f = SearchFilter(created_after="invalid-date-format")
        code, out, err = self._run_find(f)
        self.assertEqual(code, 2)
        self.assertIn("Invalid date format", err)


class TestLimitsAndConjunction(TestSearchBase):
    """Tier 2 tests for result limiting and multi-tag conjunction logic."""

    def test_limit_bounding_and_json_counts(self) -> None:
        """Verify limit restricts output and reports total_matches in JSON."""
        self.init_vault()
        for i in range(5):
            self.create_note(DEFAULT_INBOX_DIR, f"Note_{i}.md", title=f"Note {i}")

        # Text mode limit
        f_text = SearchFilter(limit=2)
        code, out_text, _ = self._run_find(f_text)
        self.assertEqual(code, 0)
        lines = [line for line in out_text.strip().split("\n") if line]
        self.assertEqual(len(lines), 2)

        # JSON mode limit
        import json

        f_json = SearchFilter(limit=2, json_mode=True)
        code, out_json, _ = self._run_find(f_json)
        self.assertEqual(code, 0)
        data = json.loads(out_json)
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["total_matches"], 5)
        self.assertEqual(len(data["notes"]), 2)

    def test_negative_or_zero_limit_returns_code_2(self) -> None:
        """Verify limit <= 0 returns code 2."""
        f = SearchFilter(limit=0)
        code, out, err = self._run_find(f)
        self.assertEqual(code, 2)
        self.assertIn("Limit must be a positive integer", err)

        f_neg = SearchFilter(limit=-5)
        code, out, err = self._run_find(f_neg)
        self.assertEqual(code, 2)
        self.assertIn("Limit must be a positive integer", err)

    def test_any_tag_or_conjunction(self) -> None:
        """Verify --any-tag matches notes with ANY specified tag (OR logic)."""
        self.init_vault()
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "BackendNote.md",
            tags=["backend"],
        )
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "FrontendNote.md",
            tags=["frontend"],
        )
        self.create_note(
            DEFAULT_PROJECTS_DIR,
            "DesignNote.md",
            tags=["design"],
        )

        # Default AND: should match 0 notes because none have BOTH backend and frontend
        f_and = SearchFilter(tags=["backend", "frontend"], tag_conjunction="AND")
        code, out_and, _ = self._run_find(f_and)
        self.assertEqual(code, 0)
        self.assertEqual(out_and.strip(), "")

        # OR conjunction: should match BackendNote and FrontendNote
        f_or = SearchFilter(tags=["backend", "frontend"], tag_conjunction="OR")
        code, out_or, _ = self._run_find(f_or)
        self.assertEqual(code, 0)
        lines = [line for line in out_or.strip().split("\n") if line]
        self.assertEqual(len(lines), 2)
        self.assertIn(f"{DEFAULT_PROJECTS_DIR}/BackendNote.md", lines)
        self.assertIn(f"{DEFAULT_PROJECTS_DIR}/FrontendNote.md", lines)
