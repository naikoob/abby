"""SQLite FTS5 acceleration cache engine for Abby Knowledge Vault."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from abby.constants import DEFAULT_CACHE_DB, VALID_NOTE_DOMAINS
from abby.core.discovery import scan_vault_files
from abby.core.domain import resolve_domain_from_path
from abby.core.graph.cache import resolve_cached_links, update_active_backlinks
from abby.core.graph.parser import extract_links_from_text
from abby.core.scoring import compute_cognitive_multiplier
from abby.models.links import NoteLinkRecord
from abby.models.trust import evaluate_staleness
from abby.services.okf_parser import parse_okf_frontmatter
from abby.utils.io import log_warn


def get_cache_db_path(vault_root: Path) -> Path:
    """Return the absolute path to the SQLite cache database."""
    return vault_root / DEFAULT_CACHE_DB


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Create and configure a SQLite connection with WAL pragmas and custom functions."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        # WAL mode for high concurrency and write speed
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")

        # User-defined regex function for case-insensitive regular expression matching
        def _sqlite_regexp(expr: str, item: Optional[str]) -> bool:
            if not expr:
                return True
            try:
                return bool(re.search(expr, item or "", re.IGNORECASE))
            except re.error:
                return False

        def _sqlite_is_stale(stale_after: Optional[str]) -> int:
            return 1 if evaluate_staleness(stale_after) else 0

        conn.create_function("REGEXP", 2, _sqlite_regexp)
        conn.create_function("IS_STALE", 1, _sqlite_is_stale)
        conn.create_function("COGNITIVE_RANK_MULTIPLIER", 4, compute_cognitive_multiplier)
        return conn
    except Exception:
        conn.close()
        raise


CACHE_SCHEMA_VERSION = 1


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize relational, link graph, and FTS5 virtual tables with version-checked cache busting."""
    with conn:
        user_version_row = conn.execute("PRAGMA user_version;").fetchone()
        current_version = user_version_row[0] if user_version_row else 0

        # If schema version mismatch occurs (including unversioned legacy caches), invalidate and recreate
        if current_version != CACHE_SCHEMA_VERSION:
            conn.executescript("""
                DROP TABLE IF EXISTS notes_fts;
                DROP TABLE IF EXISTS note_links;
                DROP TABLE IF EXISTS note_tags;
                DROP TABLE IF EXISTS notes;
            """)


        conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS notes (
                path TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                trust_tier TEXT DEFAULT 'unverified',
                stale_after TEXT,
                active_backlinks INTEGER DEFAULT 0,
                created TEXT,
                updated TEXT,
                file_mtime REAL NOT NULL,
                file_size INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notes_domain ON notes(domain);
            CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(status);
            CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(type);
            CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated);
            CREATE INDEX IF NOT EXISTS idx_notes_trust_tier ON notes(trust_tier);
            CREATE INDEX IF NOT EXISTS idx_notes_active_backlinks ON notes(active_backlinks);

            CREATE TABLE IF NOT EXISTS note_tags (
                path TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (path, tag),
                FOREIGN KEY(path) REFERENCES notes(path) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag);

            CREATE TABLE IF NOT EXISTS note_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                target_title TEXT NOT NULL,
                target_heading TEXT,
                target_alias TEXT,
                target_path TEXT,
                link_syntax TEXT NOT NULL CHECK (link_syntax IN ('wikilink', 'markdown')),
                is_embed INTEGER NOT NULL DEFAULT 0,
                line_number INTEGER NOT NULL,
                FOREIGN KEY(source_path) REFERENCES notes(path) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_note_links_source ON note_links(source_path);
            CREATE INDEX IF NOT EXISTS idx_note_links_source_line ON note_links(source_path, line_number);
            CREATE INDEX IF NOT EXISTS idx_note_links_target_title ON note_links(target_title COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_note_links_target_path ON note_links(target_path);
            CREATE INDEX IF NOT EXISTS idx_note_links_target_source ON note_links(target_path, source_path);

            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                path UNINDEXED,
                title,
                description,
                body,
                tags,
                tokenize = 'unicode61'
            );

            PRAGMA user_version = {CACHE_SCHEMA_VERSION};
        """)





def _format_source_summary(s: dict[str, Any]) -> Optional[str]:
    """Format a single source entry into a searchable summary line."""
    if not isinstance(s, dict):
        return None
    title, author = s.get("title"), s.get("author")
    resource, src_id = s.get("resource"), s.get("id")
    if title and author:
        desc = f"{title} by {author}"
    elif title:
        desc = str(title)
    elif author:
        desc = f"by {author}"
    else:
        desc = ""

    parts = [p for p in [desc, f"({resource})" if resource else "", f"[{src_id}]" if src_id else ""] if p]
    return " ".join(parts) if parts else None


def _append_sources_to_body(body: str, raw_sources: Any) -> str:
    """Append formatted source entries to note body for FTS indexing."""
    if not isinstance(raw_sources, list) or not raw_sources:
        return body
    source_lines = []
    for s in raw_sources:
        summary = _format_source_summary(s)
        if summary:
            source_lines.append(summary)
    if source_lines:
        return body + "\n\nSources:\n" + "\n".join(f"- {line}" for line in source_lines)
    return body


def _extract_note_record(
    vault_root: Path,
    rel_path: str,
    mtime: float,
    size: int,
) -> tuple[dict[str, Any], list[str], str, list[NoteLinkRecord]]:
    """Parse frontmatter, body, and links for a single note file."""
    full_path = vault_root / rel_path
    try:
        raw = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raw = ""

    norm = raw.replace("\r\n", "\n").replace("\r", "\n")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", norm, re.DOTALL)
    body = m.group(2) if m else norm

    fm = parse_okf_frontmatter(raw, default_title=full_path.stem)
    domain = resolve_domain_from_path(rel_path) or rel_path.split("/")[0]

    raw_tags = fm.get("tags") or []
    tags = [t.strip().lower() for t in raw_tags if isinstance(t, str) and t.strip()]

    body = _append_sources_to_body(body, fm.get("sources"))

    links = extract_links_from_text(raw, source_path=rel_path)

    record = {
        "path": rel_path,
        "domain": domain,
        "status": fm.get("status") or "unprocessed",
        "type": fm.get("type") or "inbox",
        "title": fm.get("title") or full_path.stem,
        "description": fm.get("description"),
        "trust_tier": fm.get("trust_tier") or "unverified",
        "stale_after": fm.get("stale_after"),
        "created": fm.get("created"),
        "updated": fm.get("updated"),
        "file_mtime": mtime,
        "file_size": size,
    }
    return record, tags, body, links



def sync_cache(
    vault_root: Path,
    db_path: Optional[Path] = None,
    force: bool = False,
) -> dict[str, int]:
    """Perform incremental stat-based cache synchronization.

    Returns summary counts: {"indexed": X, "updated": Y, "pruned": Z, "unmodified": W}.
    Handles automatic schema creation and recovery from corrupt cache files.
    """
    if db_path is None:
        db_path = get_cache_db_path(vault_root)

    try:
        return _execute_sync(vault_root, db_path, force=force)
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as err:
        log_warn(f"Abby cache error detected ({err}). Rebuilding search cache...")
        # Remove corrupted DB files and rebuild
        _purge_db_files(db_path)
        return _execute_sync(vault_root, db_path, force=True)


def _purge_db_files(db_path: Path) -> None:
    """Safely remove database, WAL, and SHM files."""
    for p in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


def _execute_sync(
    vault_root: Path,
    db_path: Path,
    force: bool = False,
) -> dict[str, int]:
    """Internal implementation of cache sync."""
    conn = get_db_connection(db_path)
    try:
        init_schema(conn)

        if force:
            with conn:
                conn.execute("DELETE FROM notes;")
                conn.execute("DELETE FROM note_tags;")
                conn.execute("DELETE FROM notes_fts;")
                conn.execute("DELETE FROM note_links;")
            db_records: dict[str, tuple[float, int]] = {}
        else:
            cursor = conn.execute("SELECT path, file_mtime, file_size FROM notes;")
            db_records = {
                row[0]: (float(row[1]), int(row[2])) for row in cursor.fetchall()
            }

        disk_files = scan_vault_files(vault_root)

        db_keys = set(db_records.keys())
        disk_keys = set(disk_files.keys())

        deleted_paths = db_keys - disk_keys
        new_paths = disk_keys - db_keys
        modified_paths = {
            p for p in (disk_keys & db_keys)
            if db_records[p][0] != disk_files[p][0] or db_records[p][1] != disk_files[p][1]
        }
        unmodified_count = len(disk_keys) - len(new_paths) - len(modified_paths)

        if not deleted_paths and not new_paths and not modified_paths and not force:
            return {"indexed": 0, "updated": 0, "pruned": 0, "unmodified": unmodified_count}

        with conn:
            # Prune deleted notes
            if deleted_paths:
                del_tuples = [(p,) for p in deleted_paths]
                conn.executemany("DELETE FROM notes WHERE path = ?", del_tuples)
                conn.executemany("DELETE FROM note_tags WHERE path = ?", del_tuples)
                conn.executemany("DELETE FROM notes_fts WHERE path = ?", del_tuples)
                conn.executemany("DELETE FROM note_links WHERE source_path = ?", del_tuples)

            # Upsert new and modified notes
            for p in new_paths | modified_paths:
                mtime, size = disk_files[p]
                rec, tags, body, links = _extract_note_record(
                    vault_root, p, mtime, size
                )

                conn.execute(
                    """
                    INSERT INTO notes (path, domain, status, type, title, description, trust_tier, stale_after, created, updated, file_mtime, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        domain=excluded.domain,
                        status=excluded.status,
                        type=excluded.type,
                        title=excluded.title,
                        description=excluded.description,
                        trust_tier=excluded.trust_tier,
                        stale_after=excluded.stale_after,
                        created=excluded.created,
                        updated=excluded.updated,
                        file_mtime=excluded.file_mtime,
                        file_size=excluded.file_size;
                    """,
                    (
                        rec["path"], rec["domain"], rec["status"], rec["type"],
                        rec["title"], rec["description"], rec["trust_tier"], rec["stale_after"],
                        rec["created"], rec["updated"], rec["file_mtime"], rec["file_size"],
                    ),
                )

                # Update tags
                conn.execute("DELETE FROM note_tags WHERE path = ?", (p,))
                for tag in set(tags):
                    conn.execute(
                        "INSERT OR IGNORE INTO note_tags (path, tag) VALUES (?, ?)",
                        (p, tag),
                    )

                # Update FTS
                conn.execute("DELETE FROM notes_fts WHERE path = ?", (p,))
                tags_fts = " ".join(tags)
                conn.execute(
                    "INSERT INTO notes_fts (path, title, description, body, tags) VALUES (?, ?, ?, ?, ?)",
                    (p, rec["title"], rec["description"] or "", body, tags_fts),
                )

                # Update Links
                conn.execute("DELETE FROM note_links WHERE source_path = ?", (p,))
                for link in links:
                    conn.execute(
                        """
                        INSERT INTO note_links (source_path, target_title, target_heading, target_alias, target_path, link_syntax, is_embed, line_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            link.source_path,
                            link.target_title,
                            link.target_heading,
                            link.target_alias,
                            link.resolved_path,
                            link.link_syntax,
                            1 if link.is_embed else 0,
                            link.line_number,
                        ),
                    )

        # Resolve links across notes and assets
        with conn:
            resolve_cached_links(conn, vault_root)
            update_active_backlinks(conn)

        return {
            "indexed": len(new_paths),
            "updated": len(modified_paths),
            "pruned": len(deleted_paths),
            "unmodified": unmodified_count,
        }
    finally:
        conn.close()


def rebuild_cache(vault_root: Path, db_path: Optional[Path] = None) -> dict[str, int]:
    """Force complete purge and re-indexing of the SQLite search cache."""
    if db_path is None:
        db_path = get_cache_db_path(vault_root)
    _purge_db_files(db_path)
    return sync_cache(vault_root, db_path=db_path, force=True)
