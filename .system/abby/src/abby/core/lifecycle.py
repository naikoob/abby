"""Core lifecycle, domain listing, relocation, and archiving engine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from abby.constants import (
    DEFAULT_ARCHIVES_DIR,
    DEFAULT_INBOX_DIR,
    DOMAIN_DEFAULT_STATUS,
    DOMAIN_DEFAULT_TYPE,
)
from abby.core.domain import resolve_domain_name
from abby.core.intake import resolve_unique_filename
from abby.core.resolution import resolve_source_note as _core_resolve_source_note
from abby.models.exceptions import (
    LifecycleError,
    PathBoundaryError,
)
from abby.models.okf import (
    ArchiveResult,
    MoveResult,
    TriageNoteItem,
)
from abby.services.okf_parser import parse_okf_frontmatter
from abby.services.okf_serializer import mutate_okf_frontmatter
from abby.utils.io import atomic_write_text, log_warn
from abby.utils.time import now_iso, parse_iso_timestamp


def list_domain_notes(
    vault_root: Path,
    domain_key: str = "inbox",
) -> tuple[str, list[TriageNoteItem]]:
    """Scan and list notes in the specified PARA domain, sorted FIFO by creation date."""
    canonical_domain = resolve_domain_name(domain_key)
    target_dir = vault_root / canonical_domain

    if not target_dir.exists():
        return canonical_domain, []

    # Gather markdown files
    if canonical_domain == DEFAULT_INBOX_DIR:
        # Inbox: direct child notes only
        files = [
            f
            for f in target_dir.iterdir()
            if f.is_file() and f.name.endswith(".md") and not f.name.startswith(".")
        ]
    else:
        # Projects/Areas/Resources/Archives: recursive scan
        files = [
            f
            for f in target_dir.rglob("*.md")
            if f.is_file() and not f.name.startswith(".")
        ]

    now = datetime.now()
    items: list[TriageNoteItem] = []

    for f in files:
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            log_warn(f"Could not read {f}: {err}")
            continue

        meta = parse_okf_frontmatter(content, default_title=f.stem)
        created_str = meta.get("created") or ""
        age_days = 0

        if created_str:
            try:
                dt = parse_iso_timestamp(created_str)
                if dt:
                    if dt.tzinfo is not None:
                        # Account for timezone offsets without naive/aware collision
                        now_tz = datetime.now(dt.tzinfo)
                        age_days = max(0, (now_tz - dt).days)
                    else:
                        age_days = max(0, (now - dt).days)
            except (ValueError, TypeError):
                age_days = 0
        else:
            try:
                stat = f.stat()
                # Use st_mtime as reliable modification timestamp across POSIX systems
                dt = datetime.fromtimestamp(stat.st_mtime)
                created_str = dt.isoformat(timespec="seconds")
                age_days = max(0, (now - dt).days)
            except OSError:
                pass

        rel_path = str(f.relative_to(vault_root))
        items.append(
            TriageNoteItem(
                filename=f.name,
                path=rel_path,
                title=meta.get("title", f.stem),
                created=created_str,
                age_days=age_days,
                status=meta.get("status", "unprocessed"),
                updated=meta.get("updated"),
                tags=meta.get("tags", []),
            )
        )

    # Sort FIFO: oldest created date first, tie-breaking deterministically by filename
    items.sort(key=lambda x: (x.created or "9999", x.filename))
    return canonical_domain, items


def resolve_source_note(vault_root: Path, note_arg: str) -> Path:
    """Locate a source note in the vault, verifying domain boundaries."""
    return _core_resolve_source_note(vault_root, note_arg)


def resolve_destination_dir(vault_root: Path, target_spec: str) -> tuple[Path, str]:
    """Resolve a target domain or subpath (e.g. 'projects/Apollo') to absolute dir and canonical domain."""
    cleaned = target_spec.strip().replace("\\", "/").strip("/")
    if not cleaned:
        raise LifecycleError("Target destination cannot be empty")

    parts = cleaned.split("/", 1)
    domain_part = parts[0]
    subpath = parts[1] if len(parts) > 1 else ""

    canonical_domain = resolve_domain_name(domain_part)
    target_dir = vault_root / canonical_domain
    if subpath:
        target_dir = target_dir / subpath

    # Security boundary check: ensure destination is within canonical domain inside vault root
    resolved_vault = vault_root.resolve()
    resolved_domain = (vault_root / canonical_domain).resolve()
    resolved_target = target_dir.resolve()

    if not resolved_target.is_relative_to(resolved_domain):
        raise PathBoundaryError(
            f"Target path '{target_spec}' escapes domain '{canonical_domain}'"
        )

    if not resolved_target.is_relative_to(resolved_vault):
        raise PathBoundaryError(f"Target path '{target_spec}' escapes vault root")

    return target_dir, canonical_domain


def resolve_move_collision(destination_dir: Path, filename: str) -> Path:
    """Resolve destination filename collisions using natural incrementing suffixes (e.g. Note (1).md)."""
    return destination_dir / resolve_unique_filename(destination_dir, filename)


def _relocate_note(
    vault_root: Path,
    note_arg: str,
    target_dir: Path,
    canonical_domain: str,
    dry_run: bool = False,
    description: Optional[str] = None,
) -> tuple[Path, Path, str, str, str, str]:
    """Internal core engine for relocating a note and mutating its frontmatter.

    Returns (source_file, dest_file, title, prev_status, new_status, now_iso).
    """
    source_file = resolve_source_note(vault_root, note_arg)
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
    dest_file = resolve_move_collision(target_dir, source_file.name)

    content = source_file.read_text(encoding="utf-8")
    now_ts = now_iso()
    new_status = DOMAIN_DEFAULT_STATUS.get(canonical_domain, "active")
    new_type = DOMAIN_DEFAULT_TYPE.get(canonical_domain, "note")

    updates = {
        "status": new_status,
        "type": new_type,
        "updated": now_ts,
    }
    if description is not None and str(description).strip():
        sanitized_desc = (
            str(description).strip().replace("\r", "").replace("\n", " ").replace('"', '\\"')
        )
        updates["description"] = f'"{sanitized_desc}"'

    new_content, prev_status = mutate_okf_frontmatter(
        content,
        updates,
    )

    if not dry_run:
        atomic_write_text(dest_file, new_content, encoding="utf-8")
        if source_file.resolve() != dest_file.resolve():
            source_file.unlink()

    meta = parse_okf_frontmatter(new_content, default_title=dest_file.stem)
    title = meta.get("title", dest_file.stem)

    return source_file, dest_file, title, prev_status, new_status, now_iso


def move_note(
    vault_root: Path,
    note_arg: str,
    target_spec: str,
    dry_run: bool = False,
    description: Optional[str] = None,
) -> MoveResult:
    """Relocate a note to target PARA destination and atomically update its OKF frontmatter."""
    dest_dir, canonical_domain = resolve_destination_dir(vault_root, target_spec)
    source_file, dest_file, title, prev_status, new_status, now_iso = _relocate_note(
        vault_root=vault_root,
        note_arg=note_arg,
        target_dir=dest_dir,
        canonical_domain=canonical_domain,
        dry_run=dry_run,
        description=description,
    )
    desc_val = description.strip() if (description and description.strip()) else None
    return MoveResult(
        success=True,
        source_path=str(source_file.relative_to(vault_root)),
        target_path=str(dest_file.relative_to(vault_root)),
        title=title,
        previous_status=prev_status,
        new_status=new_status,
        timestamp=now_iso,
        is_dry_run=dry_run,
        description=desc_val,
    )


def archive_note(
    vault_root: Path,
    note_arg: str,
    dry_run: bool = False,
) -> ArchiveResult:
    """Retire an active or reference note into 04 - Archives/."""
    archives_dir = vault_root / DEFAULT_ARCHIVES_DIR
    source_file, dest_file, title, _, _, now_iso = _relocate_note(
        vault_root=vault_root,
        note_arg=note_arg,
        target_dir=archives_dir,
        canonical_domain=DEFAULT_ARCHIVES_DIR,
        dry_run=dry_run,
    )
    return ArchiveResult(
        success=True,
        source_path=str(source_file.relative_to(vault_root)),
        target_path=str(dest_file.relative_to(vault_root)),
        title=title,
        archived_at=now_iso,
        is_dry_run=dry_run,
    )


__all__ = [
    "archive_note",
    "list_domain_notes",
    "move_note",
    "resolve_destination_dir",
    "resolve_move_collision",
    "resolve_source_note",
]
