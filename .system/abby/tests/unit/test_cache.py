"""Unit and sandbox tests for SQLite FTS5 cache engine."""

import os
import sqlite3
import sys
import time
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

from abby.constants import DEFAULT_CACHE_DB, DEFAULT_INBOX_DIR, DEFAULT_PROJECTS_DIR
from abby.core.cache import (
    get_cache_db_path,
    get_db_connection,
    init_schema,
    rebuild_cache,
    scan_vault_files,
    sync_cache,
)


class TestCacheEngine(IsolatedVaultTestCase):
    """Tier 2 tests for SQLite cache creation, indexing, and incremental sync."""

    def test_schema_initialization(self) -> None:
        """Verify that schema creates notes, note_tags, and notes_fts virtual table."""
        db_path = get_cache_db_path(self.vault_root)
        conn = get_db_connection(db_path)
        try:
            init_schema(conn)

            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow');"
                ).fetchall()
            }
            self.assertIn("notes", tables)
            self.assertIn("note_tags", tables)
            self.assertIn("notes_fts", tables)

            # Check pragma foreign keys
            fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            self.assertEqual(fk, 1)

            # Check journal mode is WAL
            jm = conn.execute("PRAGMA journal_mode;").fetchone()[0].upper()
            self.assertEqual(jm, "WAL")
        finally:
            conn.close()

    def test_scan_vault_files(self) -> None:
        """Verify scan_vault_files traverses 00-04, skips .system, hidden files, and 05 - Assets."""
        self.init_vault()
        note1 = self.create_note(DEFAULT_INBOX_DIR, "Inbox Note.md")
        note2 = self.create_note(DEFAULT_PROJECTS_DIR, "Project Note.md")

        # Create note in 05 - Assets (should be ignored)
        assets_dir = self.vault_root / "05 - Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / "asset_note.md").write_text("Asset note", encoding="utf-8")

        # Create hidden file (should be ignored)
        (self.vault_root / DEFAULT_INBOX_DIR / ".hidden.md").write_text(
            "Hidden", encoding="utf-8"
        )

        files = scan_vault_files(self.vault_root)
        self.assertIn(f"{DEFAULT_INBOX_DIR}/Inbox Note.md", files)
        self.assertIn(f"{DEFAULT_PROJECTS_DIR}/Project Note.md", files)
        self.assertNotIn("05 - Assets/asset_note.md", files)
        self.assertNotIn(f"{DEFAULT_INBOX_DIR}/.hidden.md", files)

    def test_incremental_sync_lifecycle(self) -> None:
        """Verify initial indexing, untouched no-op, modification update, and deletion pruning."""
        self.init_vault()
        note1 = self.create_note(
            DEFAULT_INBOX_DIR,
            "Alpha.md",
            title="Alpha Note",
            status="unprocessed",
            type_="inbox",
            tags=["urgent", "triage"],
            body="Alpha body text.",
        )

        db_path = get_cache_db_path(self.vault_root)

        # 1. Initial sync
        stats1 = sync_cache(self.vault_root, db_path=db_path)
        self.assertEqual(stats1["indexed"], 1)
        self.assertEqual(stats1["updated"], 0)
        self.assertEqual(stats1["pruned"], 0)

        conn = get_db_connection(db_path)
        try:
            row = conn.execute(
                "SELECT title, status, type FROM notes WHERE path = ?",
                (f"{DEFAULT_INBOX_DIR}/Alpha.md",),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "Alpha Note")
            self.assertEqual(row[1], "unprocessed")

            tags = {
                r[0]
                for r in conn.execute(
                    "SELECT tag FROM note_tags WHERE path = ?",
                    (f"{DEFAULT_INBOX_DIR}/Alpha.md",),
                ).fetchall()
            }
            self.assertEqual(tags, {"urgent", "triage"})

            fts_row = conn.execute(
                "SELECT title, body, tags FROM notes_fts WHERE path = ?",
                (f"{DEFAULT_INBOX_DIR}/Alpha.md",),
            ).fetchone()
            self.assertIsNotNone(fts_row)
            self.assertEqual(fts_row[0], "Alpha Note")
            self.assertIn("Alpha body text.", fts_row[1])
        finally:
            conn.close()

        # 2. Untouched sync (no changes)
        stats2 = sync_cache(self.vault_root, db_path=db_path)
        self.assertEqual(stats2["indexed"], 0)
        self.assertEqual(stats2["updated"], 0)
        self.assertEqual(stats2["pruned"], 0)
        self.assertEqual(stats2["unmodified"], 1)

        # 3. External modification: change content and mtime
        time.sleep(0.01)  # Ensure mtime changes
        note1.write_text(
            '---\ntitle: "Alpha Updated"\ncreated: "2026-09-17T12:00:00"\ntype: inbox\nstatus: active\ntags:\n  - updated_tag\n---\nNew body content.\n',
            encoding="utf-8",
        )
        # Explicitly set mtime to be in the future to ensure mtime diff
        stat = note1.stat()
        os.utime(note1, (stat.st_atime, stat.st_mtime + 5))

        stats3 = sync_cache(self.vault_root, db_path=db_path)
        self.assertEqual(stats3["indexed"], 0)
        self.assertEqual(stats3["updated"], 1)
        self.assertEqual(stats3["pruned"], 0)

        conn = get_db_connection(db_path)
        try:
            row = conn.execute(
                "SELECT title, status FROM notes WHERE path = ?",
                (f"{DEFAULT_INBOX_DIR}/Alpha.md",),
            ).fetchone()
            self.assertEqual(row[0], "Alpha Updated")
            self.assertEqual(row[1], "active")

            tags = {
                r[0]
                for r in conn.execute(
                    "SELECT tag FROM note_tags WHERE path = ?",
                    (f"{DEFAULT_INBOX_DIR}/Alpha.md",),
                ).fetchall()
            }
            self.assertEqual(tags, {"updated_tag"})
        finally:
            conn.close()

        # 4. External deletion
        note1.unlink()
        stats4 = sync_cache(self.vault_root, db_path=db_path)
        self.assertEqual(stats4["pruned"], 1)

        conn = get_db_connection(db_path)
        try:
            count = conn.execute("SELECT count(*) FROM notes;").fetchone()[0]
            self.assertEqual(count, 0)
            tag_count = conn.execute("SELECT count(*) FROM note_tags;").fetchone()[0]
            self.assertEqual(tag_count, 0)
            fts_count = conn.execute("SELECT count(*) FROM notes_fts;").fetchone()[0]
            self.assertEqual(fts_count, 0)
        finally:
            conn.close()

    def test_corrupt_cache_recovery(self) -> None:
        """Verify that corrupted cache database is safely wiped and rebuilt."""
        self.init_vault()
        self.create_note(DEFAULT_INBOX_DIR, "Test Note.md", title="Recovered")

        db_path = get_cache_db_path(self.vault_root)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Write garbage into db_path
        db_path.write_text("CORRUPTED JUNK DATA", encoding="utf-8")

        # Sync should catch error, remove garbage and rebuild
        stats = sync_cache(self.vault_root, db_path=db_path)
        self.assertEqual(stats["indexed"], 1)

        conn = get_db_connection(db_path)
        try:
            count = conn.execute("SELECT count(*) FROM notes;").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            conn.close()

    def test_rebuild_cache(self) -> None:
        """Verify rebuild_cache purges and completely re-indexes."""
        self.init_vault()
        self.create_note(DEFAULT_INBOX_DIR, "Note1.md", title="Note 1")
        self.create_note(DEFAULT_PROJECTS_DIR, "Note2.md", title="Note 2")

        db_path = get_cache_db_path(self.vault_root)
        sync_cache(self.vault_root, db_path=db_path)

        # Force rebuild
        stats = rebuild_cache(self.vault_root, db_path=db_path)
        self.assertEqual(stats["indexed"], 2)

        conn = get_db_connection(db_path)
        try:
            count = conn.execute("SELECT count(*) FROM notes;").fetchone()[0]
            self.assertEqual(count, 2)
        finally:
            conn.close()

    def test_cache_version_mismatch_invalidation(self) -> None:
        """Verify that a schema version mismatch drops tables and stamps new version."""
        db_path = get_cache_db_path(self.vault_root)
        conn = get_db_connection(db_path)
        try:
            init_schema(conn)
            # Insert a dummy row
            conn.execute(
                "INSERT INTO notes (path, domain, status, type, title, file_mtime, file_size) "
                "VALUES ('00 - Inbox/Old.md', 'inbox', 'unprocessed', 'inbox', 'Old', 1.0, 100);"
            )
            # Tamper user_version to simulate an outdated cache
            conn.execute("PRAGMA user_version = 999;")
            conn.commit()

            # Calling init_schema should detect mismatch, drop tables, and recreate fresh
            init_schema(conn)
            ver = conn.execute("PRAGMA user_version;").fetchone()[0]
            self.assertEqual(ver, 1)

            # Old data should be purged
            count = conn.execute("SELECT count(*) FROM notes;").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            conn.close()

