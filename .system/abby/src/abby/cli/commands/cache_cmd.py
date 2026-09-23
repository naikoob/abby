"""Cache CLI command handlers for inspection, rebuilding, and maintenance."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from abby.core.cache import (
    CACHE_SCHEMA_VERSION,
    get_cache_db_path,
    rebuild_cache,
    sync_cache,
)
from abby.utils.io import output_payload


def _get_cache_stats(vault_root: Path) -> dict[str, Any]:
    """Retrieve detailed database file and table statistics."""
    db_path = get_cache_db_path(vault_root)
    if not db_path.exists():
        return {
            "status": "uninitialized",
            "db_path": str(db_path),
            "exists": False,
        }

    stat = db_path.stat()
    wal_path = Path(f"{db_path}-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0

    tables_data: dict[str, int] = {}
    user_version = 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute("PRAGMA user_version;").fetchone()
            user_version = row[0] if row else 0

            for table in ("notes", "note_links", "note_tags", "notes_fts"):
                try:
                    c = conn.execute(f"SELECT count(*) FROM {table};").fetchone()
                    tables_data[table] = c[0] if c else 0
                except sqlite3.OperationalError:
                    tables_data[table] = -1
        finally:
            conn.close()
    except Exception as exc:
        return {
            "status": "error",
            "db_path": str(db_path),
            "exists": True,
            "error": str(exc),
        }

    return {
        "status": "operational",
        "db_path": str(db_path),
        "exists": True,
        "size_bytes": stat.st_size,
        "wal_size_bytes": wal_size,
        "user_version": user_version,
        "expected_version": CACHE_SCHEMA_VERSION,
        "tables": tables_data,
    }


def execute_cache_command(
    vault_root: Path,
    action: str = "status",
    json_mode: bool = False,
) -> int:
    """Execute 'abby cache <action>' (status, rebuild, prune)."""
    if action == "status":
        stats = _get_cache_stats(vault_root)
        if json_mode:
            output_payload(stats, json_mode=True)
        else:
            if not stats.get("exists"):
                lines = [
                    f"Cache Database: {stats['db_path']}",
                    "Status: uninitialized (run 'abby cache rebuild' to initialize)",
                ]
                output_payload("\n".join(lines), json_mode=False)
            elif stats.get("status") == "error":

                output_payload(f"Cache error: {stats.get('error')}", json_mode=False)
                return 1
            else:
                size_kb = stats["size_bytes"] / 1024
                wal_kb = stats["wal_size_bytes"] / 1024
                lines = [
                    f"Cache Database: {stats['db_path']}",
                    f"Schema Version: {stats['user_version']} (expected: {stats['expected_version']})",
                    f"File Size: {size_kb:.1f} KB (WAL: {wal_kb:.1f} KB)",
                    "Indexed Tables:",
                ]
                for tbl, count in stats.get("tables", {}).items():
                    lines.append(f"  - {tbl}: {count} records")
                output_payload("\n".join(lines), json_mode=False)
        return 0

    if action == "rebuild":
        metrics = rebuild_cache(vault_root)
        if json_mode:
            output_payload(metrics, json_mode=True)
        else:
            output_payload(
                f"Cache rebuild complete: {metrics.get('indexed', 0)} indexed, "
                f"{metrics.get('updated', 0)} updated, {metrics.get('pruned', 0)} pruned.",
                json_mode=False,
            )
        return 0

    if action == "prune":
        metrics = sync_cache(vault_root)
        if json_mode:
            output_payload(metrics, json_mode=True)
        else:
            output_payload(
                f"Cache maintenance complete: {metrics.get('pruned', 0)} pruned, "
                f"{metrics.get('updated', 0)} updated, {metrics.get('indexed', 0)} newly indexed.",
                json_mode=False,
            )
        return 0

    output_payload(f"Unknown cache action: {action}. Choose from: status, rebuild, prune.", json_mode=False)
    return 1
