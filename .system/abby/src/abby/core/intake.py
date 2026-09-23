"""Rapid note capture and ingestion logic for 00 - Inbox."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from abby.constants import DEFAULT_INBOX_DIR, MAX_COLLISION_ATTEMPTS, MAX_TITLE_BYTES
from abby.models.okf import InboxNote, OKFFrontmatter
from abby.utils.io import atomic_write_text
from abby.utils.templates import get_default_inbox_body

# Forbidden characters across POSIX / Windows filesystems
ILLEGAL_CHARS_PATTERN = re.compile(r'[/\\:*?"<>|]')


def sanitize_title(raw_title: str) -> str:
    """Sanitize raw title for use as a clean, natural file name, bounded by filesystem byte limits."""
    cleaned = raw_title.strip()
    # Replace slashes and forbidden characters with dashes
    cleaned = ILLEGAL_CHARS_PATTERN.sub("-", cleaned)
    # Collapse multiple consecutive dashes or spaces
    cleaned = re.sub(r"-+", "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(". -")
    if not cleaned:
        cleaned = "Untitled Note"

    # Enforce UTF-8 byte boundary limit to ensure filenames fit within OS 255-byte limits
    encoded = cleaned.encode("utf-8")
    if len(encoded) > MAX_TITLE_BYTES:
        cleaned = (
            encoded[:MAX_TITLE_BYTES].decode("utf-8", errors="ignore").rstrip(". -")
        )
        if not cleaned:
            cleaned = "Untitled Note"
    return cleaned


def resolve_unique_filename(target_dir: Path, base_title: str) -> str:
    """Resolve an available filename in target_dir using natural title format.

    If <base_title>.md exists, tests <base_stem> (1).md, <base_stem> (2).md, etc.,
    handling existing suffix patterns appropriately.
    """
    filename = f"{base_title}.md" if not base_title.endswith(".md") else base_title
    if not (target_dir / filename).exists():
        return filename

    raw_name = filename[:-3] if filename.endswith(".md") else filename
    m = re.match(r"^(.*?)(?: \((\d+)\))?$", raw_name)
    base_stem = m.group(1) if m else raw_name

    for counter in range(1, MAX_COLLISION_ATTEMPTS):
        candidate = f"{base_stem} ({counter}).md"
        if not (target_dir / candidate).exists():
            return candidate

    raise RuntimeError(
        f"Exceeded maximum collision resolution attempts ({MAX_COLLISION_ATTEMPTS - 1}) for '{base_title}'"
    )


def capture_note(
    vault_root: Path,
    title: str,
    body: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    generated: Optional[dict[str, str]] = None,
    verified: Optional[list[dict[str, str]]] = None,
    sources: Optional[list[dict[str, Any]]] = None,
) -> InboxNote:
    """Create a new note in 00 - Inbox conforming to OKF conventions."""
    inbox_dir = vault_root / DEFAULT_INBOX_DIR
    inbox_dir.mkdir(parents=True, exist_ok=True)

    clean_title = sanitize_title(title)
    filename = resolve_unique_filename(inbox_dir, clean_title)
    target_path = inbox_dir / filename
    relative_path = f"{DEFAULT_INBOX_DIR}/{filename}"

    note_tags = ["inbox"]
    if tags:
        for t in tags:
            cleaned = t.lstrip("#").strip()
            if cleaned and cleaned not in note_tags:
                note_tags.append(cleaned)

    clean_desc = description.strip() if description and description.strip() else None

    frontmatter = OKFFrontmatter(
        title=clean_title,
        description=clean_desc,
        type="inbox",
        status="unprocessed",
        tags=note_tags,
        generated=generated,
        verified=verified or [],
        sources=sources or [],
    )

    if body is not None and body.strip():
        final_body = body.strip()
    else:
        final_body = get_default_inbox_body(clean_title)

    note = InboxNote(
        title=clean_title,
        filename=filename,
        relative_path=relative_path,
        absolute_path=target_path,
        frontmatter=frontmatter,
        body=final_body,
    )

    # Write note to disk in UTF-8 atomically
    atomic_write_text(target_path, note.to_markdown(), encoding="utf-8")
    return note


__all__ = [
    "capture_note",
    "resolve_unique_filename",
    "sanitize_title",
]
