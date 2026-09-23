"""Unified note target resolution, candidate discovery, and path boundary validation for Abby Knowledge Vault."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from abby.constants import DEFAULT_INBOX_DIR, VALID_NOTE_DOMAINS
from abby.core.domain import resolve_domain_name
from abby.models.exceptions import NoteNotFoundError, PathBoundaryError


def validate_note_boundary(vault_root: Path, note_path: Path, note_arg: str = "") -> Path:
    """Ensure note_path is strictly within vault_root and belongs to a valid note domain.

    Raises:
        PathBoundaryError: If the note is outside vault_root or resides in a non-knowledge directory.
    """
    resolved_vault = vault_root.resolve()
    resolved_note = note_path.resolve()

    if not resolved_note.is_relative_to(resolved_vault):
        identifier = note_arg or str(note_path)
        raise PathBoundaryError(f"Source note '{identifier}' is outside vault root")

    rel_to_vault = resolved_note.relative_to(resolved_vault)
    if len(rel_to_vault.parts) == 0:
        raise PathBoundaryError("Invalid note path")

    top_dir = rel_to_vault.parts[0]
    if top_dir not in VALID_NOTE_DOMAINS:
        raise PathBoundaryError(
            f"Source note cannot be located outside valid knowledge domains (found in '{top_dir}')"
        )

    return note_path


def resolve_source_note(
    vault_root: Path,
    note_arg: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Path:
    """Locate a source note in the vault, verifying domain boundaries.

    Supports:
    - Exact path relative to vault root
    - Path without extension
    - Path inside 00 - Inbox
    - Filename search across all valid PARA note domains
    - Fast SQLite cache lookup if connection is provided

    Raises:
        ValueError: If note_arg is empty.
        NoteNotFoundError: If no matching file exists.
        PathBoundaryError: If the note violates vault containment boundaries.
    """
    cleaned = note_arg.strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("Note path cannot be empty")

    candidates = [
        vault_root / cleaned,
        vault_root / (cleaned + ".md"),
        vault_root / DEFAULT_INBOX_DIR / cleaned,
        vault_root / DEFAULT_INBOX_DIR / (cleaned + ".md"),
    ]

    matched: Optional[Path] = None
    for cand in candidates:
        if cand.is_file():
            matched = cand
            break

    # If connection provided and no exact candidate match, check SQLite cache
    if not matched and conn is not None:
        try:
            rel_path, _, _ = resolve_note_target(conn, cleaned)
            if rel_path:
                cand_db = vault_root / rel_path
                if cand_db.is_file():
                    matched = cand_db
        except (sqlite3.DatabaseError, OSError):
            pass

    if not matched:
        # Fallback: search across all valid note domains for filename match
        filename = Path(cleaned).name
        target_names = (
            filename,
            filename + ".md" if not filename.endswith(".md") else filename,
        )
        for domain in VALID_NOTE_DOMAINS:
            domain_path = vault_root / domain
            if domain_path.exists():
                for cand_file in domain_path.rglob("*.md"):
                    if cand_file.name in target_names and cand_file.is_file():
                        matched = cand_file
                        break
            if matched:
                break

    if not matched or not matched.is_file():
        raise NoteNotFoundError(note_arg)

    return validate_note_boundary(vault_root, matched, note_arg=note_arg)


def _disambiguate_candidates(
    matches: list[tuple[str, Optional[str], str]],
    canonical_domain: Optional[str],
) -> Optional[tuple[Optional[str], Optional[str], list[str]]]:
    """Filter and disambiguate matching note tuples, returning (path, title, candidates) or None."""
    if not matches:
        return None
    if len(matches) == 1:
        p, t, _ = matches[0]
        return p, t or Path(p).stem, []
    if canonical_domain:
        filtered = [m for m in matches if m[2] == canonical_domain]
        if len(filtered) == 1:
            return filtered[0][0], filtered[0][1] or Path(filtered[0][0]).stem, []
    return None, None, sorted([p for p, _, _ in matches])


def resolve_note_target(
    conn: sqlite3.Connection, note_arg: str, domain_filter: Optional[str] = None
) -> tuple[Optional[str], Optional[str], list[str]]:
    """Resolve a user-supplied note argument to (resolved_path, resolved_title, candidate_paths).

    Returns:
        (resolved_path, resolved_title, candidate_paths)
        - Unique match: (path, title, [])
        - Ambiguous match: (None, None, [cand1, cand2, ...])
        - No match: (None, None, [])
    """
    cleaned = note_arg.strip().replace("\\", "/")
    if not cleaned:
        return None, None, []

    canonical_domain = None
    if domain_filter:
        canonical_domain = resolve_domain_name(domain_filter)

    cursor = conn.execute("SELECT path, title, domain FROM notes;")
    all_notes = cursor.fetchall()

    cleaned_lower = cleaned.lower()
    cleaned_md = (
        cleaned_lower if cleaned_lower.endswith(".md") else f"{cleaned_lower}.md"
    )

    # 1. Exact path match across all notes
    for p, t, _ in all_notes:
        p_lower = p.lower()
        if p_lower == cleaned_lower or p_lower == cleaned_md:
            return p, t or Path(p).stem, []

    # 2. Match with path suffix (e.g. Projects/Kickoff or Apollo/Kickoff)
    suffix_matches = [
        (p, t, d)
        for p, t, d in all_notes
        if p.lower().endswith("/" + cleaned_lower)
        or p.lower().endswith("/" + cleaned_md)
    ]
    res = _disambiguate_candidates(suffix_matches, canonical_domain)
    if res is not None:
        return res

    # 3. Match by filename stem or title
    target_stem = Path(cleaned).stem.lower()
    stem_matches = [
        (p, t, d) for p, t, d in all_notes if Path(p).stem.lower() == target_stem
    ]
    res = _disambiguate_candidates(stem_matches, canonical_domain)
    if res is not None:
        return res

    title_matches = [
        (p, t, d) for p, t, d in all_notes if t and t.lower() == target_stem
    ]
    res = _disambiguate_candidates(title_matches, canonical_domain)
    if res is not None:
        return res

    return None, None, []

