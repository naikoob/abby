"""Link resolution and active backlink materialization for Abby cache."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

__all__ = [
    "resolve_cached_links",
    "update_active_backlinks",
]


def _build_notes_indexes(
    notes_rows: list[tuple[str, Optional[str]]],
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[str]]]:
    exact_path_map: dict[str, str] = {}
    stem_map: dict[str, list[str]] = {}
    title_map: dict[str, list[str]] = {}

    for path_str, title in notes_rows:
        stem = Path(path_str).stem.lower()
        t_lower = (title or "").lower()
        p_lower = path_str.lower()

        exact_path_map[p_lower] = path_str
        stem_map.setdefault(stem, []).append(path_str)
        if t_lower:
            title_map.setdefault(t_lower, []).append(path_str)

    return exact_path_map, stem_map, title_map


def _build_assets_index(vault_root: Path) -> dict[str, str]:
    asset_files: dict[str, str] = {}
    assets_dir = vault_root / "05 - Assets"
    if assets_dir.is_dir():
        for p in assets_dir.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                rel = p.relative_to(vault_root).as_posix()
                asset_files[p.name.lower()] = rel
                asset_files[rel.lower()] = rel
    return asset_files


def _resolve_markdown_link(
    vault_root: Path, source_path: str, target_title: str
) -> Optional[str]:
    source_dir = (vault_root / source_path).parent
    cand = (source_dir / target_title).resolve()
    try:
        rel = cand.relative_to(vault_root).as_posix()
        if (vault_root / rel).exists():
            return rel
    except (ValueError, OSError):
        pass
    return None


def _resolve_wikilink(
    target_title: str,
    exact_path_map: dict[str, str],
    stem_map: dict[str, list[str]],
    title_map: dict[str, list[str]],
    asset_files: dict[str, str],
) -> Optional[str]:
    if "/" in target_title or "\\" in target_title:
        norm_target = target_title.replace("\\", "/").lower()
        norm_md = norm_target if norm_target.endswith(".md") else f"{norm_target}.md"
        if norm_md in exact_path_map:
            return exact_path_map[norm_md]
        matches = [
            p
            for p_lower, p in exact_path_map.items()
            if p_lower.endswith("/" + norm_md) or p_lower == norm_md
        ]
        return matches[0] if len(matches) == 1 else None

    target_lower = target_title.lower()
    stems = stem_map.get(target_lower, [])
    if len(stems) == 1:
        return stems[0]
    if len(stems) > 1:
        return None

    titles = title_map.get(target_lower, [])
    if len(titles) == 1:
        return titles[0]
    if len(titles) > 1:
        return None

    return asset_files.get(target_lower)


def resolve_cached_links(conn: sqlite3.Connection, vault_root: Path) -> None:
    """Resolve and populate target_path for all rows in note_links.

    Supports case-insensitive note stem matching, frontmatter title matching,
    asset resolution in 05 - Assets, and local relative Markdown link resolution.
    Leaves target_path as NULL if target is missing or ambiguous.
    """
    cursor = conn.execute("SELECT path, title FROM notes;")
    notes_rows = cursor.fetchall()
    exact_path_map, stem_map, title_map = _build_notes_indexes(notes_rows)
    asset_files = _build_assets_index(vault_root)

    cursor = conn.execute(
        "SELECT id, source_path, target_title, link_syntax, is_embed FROM note_links;"
    )
    links_rows = cursor.fetchall()

    updates: list[tuple[Optional[str], int]] = []
    for link_id, source_path, target_title, link_syntax, is_embed in links_rows:
        if link_syntax == "markdown":
            resolved = _resolve_markdown_link(vault_root, source_path, target_title)
        else:
            resolved = _resolve_wikilink(
                target_title, exact_path_map, stem_map, title_map, asset_files
            )
        updates.append((resolved, link_id))

    if updates:
        conn.executemany("UPDATE note_links SET target_path = ? WHERE id = ?;", updates)


def update_active_backlinks(conn: sqlite3.Connection) -> None:
    """Materialize active inbound link counts on notes excluding links from 04 - Archives.

    Calculates distinct referring non-archive note count for each note in the vault.
    """
    conn.execute(
        """
        UPDATE notes SET active_backlinks = (
            SELECT COUNT(DISTINCT nl.source_path)
            FROM note_links nl
            JOIN notes src ON nl.source_path = src.path
            WHERE nl.target_path = notes.path
              AND src.domain != '04 - Archives'
        );
        """
    )

