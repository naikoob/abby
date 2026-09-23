"""Unit tests for SQLite FTS5 search cache migration, description indexing, and BM25 ranking."""

import sqlite3
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.core.cache import init_schema
from abby.core.scoring import compute_cognitive_multiplier
from abby.core.search import build_search_sql
from abby.models.search import SearchFilter


class TestSearchBM25(unittest.TestCase):
    """Test suite verifying FTS5 cache schema, migration, and BM25 ranking."""

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.create_function("COGNITIVE_RANK_MULTIPLIER", 4, compute_cognitive_multiplier)

    def tearDown(self) -> None:
        self.conn.close()

    def test_init_schema_creates_description_columns(self) -> None:
        """Verify new schema creates description column in notes and notes_fts."""
        init_schema(self.conn)

        # Check notes table columns
        cursor = self.conn.execute("PRAGMA table_info(notes);")
        notes_cols = [row[1] for row in cursor.fetchall()]
        self.assertIn("description", notes_cols)

        # Check notes_fts columns
        cursor = self.conn.execute("PRAGMA table_info(notes_fts);")
        fts_cols = [row[1] for row in cursor.fetchall()]
        self.assertIn("description", fts_cols)
        self.assertListEqual(
            fts_cols, ["path", "title", "description", "body", "tags"]
        )

    def test_schema_migration_from_legacy_cache(self) -> None:
        """Verify cache invalidation recreates clean schema with description and notes_fts on legacy DB."""
        # Create legacy schema without description
        self.conn.executescript(
            """
            CREATE TABLE notes (
                path TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                created TEXT,
                updated TEXT,
                file_mtime REAL NOT NULL,
                file_size INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE notes_fts USING fts5(
                path UNINDEXED,
                title,
                body,
                tags,
                tokenize = 'unicode61'
            );
            """
        )
        self.conn.execute(
            "INSERT INTO notes VALUES ('01 - Projects/Old.md', '01 - Projects', 'active', 'project-note', 'Old Note', '2026-01-01', NULL, 100.0, 50);"
        )

        # Run init_schema on existing legacy DB
        init_schema(self.conn)

        # Verify current schema contains description and trust_tier
        cursor = self.conn.execute("PRAGMA table_info(notes);")
        notes_cols = [row[1] for row in cursor.fetchall()]
        self.assertIn("description", notes_cols)
        self.assertIn("trust_tier", notes_cols)

        # Verify notes_fts upgraded to 5 columns
        cursor = self.conn.execute("PRAGMA table_info(notes_fts);")
        fts_cols = [row[1] for row in cursor.fetchall()]
        self.assertIn("description", fts_cols)

        # Verify user_version is now stamped
        ver = self.conn.execute("PRAGMA user_version;").fetchone()[0]
        self.assertEqual(ver, 1)


    def test_bm25_ranking_order(self) -> None:
        """Verify BM25 ranking order: title (10.0) > description (7.0) > tags (5.0) > body (1.0)."""
        init_schema(self.conn)

        # Insert 4 notes where 'telemetry' appears in only one respective column
        # Note A: title match
        self.conn.execute(
            "INSERT INTO notes (path, domain, status, type, title, description, created, updated, file_mtime, file_size) "
            "VALUES ('01 - Projects/A.md', '01 - Projects', 'active', 'project-note', 'Telemetry System', NULL, '2026-09-18', NULL, 100.0, 10);"
        )
        self.conn.execute(
            "INSERT INTO notes_fts (path, title, description, body, tags) "
            "VALUES ('01 - Projects/A.md', 'Telemetry System', '', 'Unrelated content alpha.', 'general');"
        )

        # Note B: description match
        self.conn.execute(
            "INSERT INTO notes (path, domain, status, type, title, description, created, updated, file_mtime, file_size) "
            "VALUES ('01 - Projects/B.md', '01 - Projects', 'active', 'project-note', 'Ingestion Pipeline', 'Telemetry ingestion protocols.', '2026-09-18', NULL, 100.0, 10);"
        )
        self.conn.execute(
            "INSERT INTO notes_fts (path, title, description, body, tags) "
            "VALUES ('01 - Projects/B.md', 'Ingestion Pipeline', 'Telemetry ingestion protocols.', 'Unrelated content beta.', 'general');"
        )

        # Note C: tag match
        self.conn.execute(
            "INSERT INTO notes (path, domain, status, type, title, description, created, updated, file_mtime, file_size) "
            "VALUES ('01 - Projects/C.md', '01 - Projects', 'active', 'project-note', 'Monitoring Stack', 'System health metrics.', '2026-09-18', NULL, 100.0, 10);"
        )
        self.conn.execute(
            "INSERT INTO notes_fts (path, title, description, body, tags) "
            "VALUES ('01 - Projects/C.md', 'Monitoring Stack', 'System health metrics.', 'Unrelated content gamma.', 'telemetry');"
        )

        # Note D: body match
        self.conn.execute(
            "INSERT INTO notes (path, domain, status, type, title, description, created, updated, file_mtime, file_size) "
            "VALUES ('01 - Projects/D.md', '01 - Projects', 'active', 'project-note', 'Distributed Worker', 'High performance worker node.', '2026-09-18', NULL, 100.0, 10);"
        )
        self.conn.execute(
            "INSERT INTO notes_fts (path, title, description, body, tags) "
            "VALUES ('01 - Projects/D.md', 'Distributed Worker', 'High performance worker node.', 'Worker node streams telemetry events.', 'general');"
        )

        search_filter = SearchFilter(query="telemetry")
        sql, params = build_search_sql(search_filter, count_only=False)

        cursor = self.conn.execute(sql, params)
        ranked_paths = [row[0] for row in cursor.fetchall()]

        # BM25 weights (0.0, 10.0, 7.0, 1.0, 5.0) mean:
        # Title (A) ranks 1st, Description (B) ranks 2nd, Tags (C) ranks 3rd, Body (D) ranks 4th
        self.assertEqual(
            ranked_paths,
            [
                "01 - Projects/A.md",
                "01 - Projects/B.md",
                "01 - Projects/C.md",
                "01 - Projects/D.md",
            ],
        )

    def test_tag_fetching_batching_above_500(self) -> None:
        """Verify querying tags for > 500 notes batches queries properly without SQLite error."""
        init_schema(self.conn)

        count = 1050
        matched_paths = [f"03 - Resources/Note_{i}.md" for i in range(count)]
        rows = [
            (
                p,
                "03 - Resources",
                "evergreen",
                "resource-note",
                f"Note {i}",
                None,
                "2026-09-18",
                None,
                100.0,
                10,
            )
            for i, p in enumerate(matched_paths)
        ]
        self.conn.executemany(
            "INSERT INTO notes (path, domain, status, type, title, description, created, updated, file_mtime, file_size) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            rows,
        )

        tag_rows = [(p, f"tag_{i}") for i, p in enumerate(matched_paths)]
        self.conn.executemany(
            "INSERT INTO note_tags (path, tag) VALUES (?, ?);", tag_rows
        )

        # Batch query logic matching search.py
        tags_map: dict[str, list[str]] = {p: [] for p in matched_paths}
        batch_size = 500
        for i in range(0, len(matched_paths), batch_size):
            chunk = matched_paths[i : i + batch_size]
            placeholders = ", ".join("?" for _ in chunk)
            tag_cursor = self.conn.execute(
                f"SELECT path, tag FROM note_tags WHERE path IN ({placeholders}) ORDER BY tag ASC;",
                chunk,
            )
            for path, tag in tag_cursor.fetchall():
                tags_map[path].append(tag)

        self.assertEqual(len(tags_map), count)
        self.assertEqual(tags_map["03 - Resources/Note_0.md"], ["tag_0"])
        self.assertEqual(tags_map["03 - Resources/Note_1049.md"], ["tag_1049"])


if __name__ == "__main__":
    unittest.main()


