"""Note renaming and Wikilink/Markdown link refactoring engine."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from abby.constants import FENCED_CODE_BLOCK_PATTERN, INLINE_CODE_PATTERN
from abby.core.discovery import scan_vault_files
from abby.core.graph.diagnostics import resolve_note_target
from abby.models.exceptions import (
    AmbiguousTargetError,
    DestinationCollisionError,
    RefactorError,
)
from abby.models.links import RefactorFileModification, RefactorResult
from abby.models.protocols import CacheSyncer
from abby.services.okf_serializer import mutate_okf_frontmatter
from abby.utils.io import atomic_write_text, log_warn
from abby.utils.time import now_iso
from abby.utils.transaction import atomic_transaction

__all__ = [
    "refactor_note",
    "rewrite_note_links",
]


def rewrite_note_links(
    text: str,
    old_title: str,
    new_title: str,
) -> tuple[str, list[tuple[int, str, str]]]:
    """Rewrite Wikilinks and Markdown links referencing old_title to new_title in text.

    Preserves code-fence immunity. Returns (new_text, occurrences) where each occurrence
    is (line_number, old_snippet, new_snippet).
    """
    old_stem = old_title[:-3] if old_title.lower().endswith(".md") else old_title
    new_stem = new_title[:-3] if new_title.lower().endswith(".md") else new_title
    old_escaped = re.escape(old_stem)
    old_quoted = quote(old_stem)
    new_quoted = quote(new_stem)

    # Regex for wikilinks: !?[[Target(#Heading)?(|Alias)?]]
    wiki_re = re.compile(
        r"(!?)\[\[([^\]|#\r\n]*/)?("
        + old_escaped
        + r")(\.md)?(?:#([^\]|\r\n]+))?(?:\|([^\]\r\n]+))?\]\]",
        re.IGNORECASE,
    )
    # Regex for markdown links: !?[Label](path ("title")?)
    md_re = re.compile(r"(!?)\[([^\]\r\n]*)\]\(([^)\s\r\n]+)(?:\s+\"([^\"\r\n]*)\")?\)")

    # Combined code block pattern for immunity
    code_combined = re.compile(f"{FENCED_CODE_BLOCK_PATTERN}|{INLINE_CODE_PATTERN}")

    # Split text into alternating code and prose segments
    last_idx = 0
    segments: list[tuple[bool, str]] = []
    for m in code_combined.finditer(text):
        start, end = m.span()
        if start > last_idx:
            segments.append((False, text[last_idx:start]))
        segments.append((True, text[start:end]))
        last_idx = end
    if last_idx < len(text):
        segments.append((False, text[last_idx:]))

    occurrences: list[tuple[int, str, str]] = []
    new_segments: list[str] = []
    current_char_offset = 0

    for is_code, seg in segments:
        if is_code:
            new_segments.append(seg)
            current_char_offset += len(seg)
            continue

        seg_replaced = seg

        def _sub_wiki(m: re.Match[str]) -> str:
            embed = m.group(1)
            path_prefix = m.group(2) or ""
            md_ext = m.group(4) or ""
            heading = f"#{m.group(5)}" if m.group(5) else ""
            alias = f"|{m.group(6)}" if m.group(6) else ""
            repl = f"{embed}[[{path_prefix}{new_stem}{md_ext}{heading}{alias}]]"
            char_pos = current_char_offset + m.start()
            line_num = text[:char_pos].count("\n") + 1
            occurrences.append((line_num, m.group(0), repl))
            return repl

        seg_replaced = wiki_re.sub(_sub_wiki, seg_replaced)

        def _sub_md(m: re.Match[str]) -> str:
            embed = m.group(1)
            label = m.group(2)
            url = m.group(3)
            title_hover = f' "{m.group(4)}"' if m.group(4) else ""

            new_url = re.sub(
                r"(^|/)(" + old_escaped + r")(\.md)(#|$)",
                r"\g<1>" + new_stem + r"\g<3>\g<4>",
                url,
                flags=re.IGNORECASE,
            )
            new_url = re.sub(
                r"(^|/)(" + re.escape(old_quoted) + r")(\.md)(#|$)",
                r"\g<1>" + new_quoted + r"\g<3>\g<4>",
                new_url,
                flags=re.IGNORECASE,
            )
            if new_url != url:
                repl = f"{embed}[{label}]({new_url}{title_hover})"
                char_pos = current_char_offset + m.start()
                line_num = text[:char_pos].count("\n") + 1
                occurrences.append((line_num, m.group(0), repl))
                return repl
            return m.group(0)

        seg_replaced = md_re.sub(_sub_md, seg_replaced)
        new_segments.append(seg_replaced)
        current_char_offset += len(seg)

    new_text = "".join(new_segments)
    occurrences.sort(key=lambda x: x[0])
    return new_text, occurrences


def _resolve_refactor_targets(
    vault_root: Path,
    conn: Any,
    old_title: str,
    new_title: str,
    *,
    force: bool,
    links_only: bool,
) -> tuple[str, str, str, str, Optional[str], Optional[str]]:
    """Resolve target note path and stem, validating ambiguities and destination collisions."""
    old_title_clean = old_title.strip()
    new_title_clean = new_title.strip()
    if not old_title_clean or not new_title_clean:
        raise RefactorError("Both old-title and new-title must be non-empty strings.")

    resolved_path, resolved_title, candidate_paths = resolve_note_target(
        conn, old_title_clean
    )

    if candidate_paths and not force:
        msg = (
            f"Ambiguous refactor target '{old_title_clean}'. Matching candidates: "
            + ", ".join(candidate_paths)
            + ". Qualify with domain prefix (e.g. '01 - Projects/{old_title}') or use --force."
        )
        raise AmbiguousTargetError(msg, candidate_paths)

    target_note_rel = resolved_path
    if candidate_paths and force:
        target_note_rel = candidate_paths[0]

    raw_new_stem = (
        new_title_clean[:-3]
        if new_title_clean.lower().endswith(".md")
        else new_title_clean
    )
    new_stem = Path(raw_new_stem).name

    raw_old_stem = (
        old_title_clean[:-3]
        if old_title_clean.lower().endswith(".md")
        else old_title_clean
    )
    old_stem = (
        resolved_title
        or (Path(target_note_rel).stem if target_note_rel else Path(raw_old_stem).name)
    )

    renamed_rel_path: Optional[str] = None
    if target_note_rel and not links_only:
        old_file_path = vault_root / target_note_rel
        new_filename = f"{new_stem}.md"
        new_file_path = old_file_path.parent / new_filename
        renamed_rel_path = new_file_path.relative_to(vault_root).as_posix()
        if (
            old_file_path.exists()
            and new_file_path.exists()
            and old_file_path.resolve() != new_file_path.resolve()
        ):
            msg = f"Cannot refactor note: target file '{renamed_rel_path}' already exists in destination folder."
            raise DestinationCollisionError(msg, renamed_rel_path)

    return (
        old_title_clean,
        new_title_clean,
        old_stem,
        new_stem,
        target_note_rel,
        renamed_rel_path,
    )


def _plan_link_rewrites(
    vault_root: Path,
    old_stem: str,
    new_stem: str,
) -> tuple[list[RefactorFileModification], int, list[tuple[Path, str, str]]]:
    """Scan vault files and identify all planned link rewrites."""
    vault_files = scan_vault_files(vault_root)
    files_modified: list[RefactorFileModification] = []
    total_occurrences = 0
    planned_writes: list[tuple[Path, str, str]] = []

    for rel_path in sorted(vault_files.keys()):
        file_path = vault_root / rel_path
        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            log_warn(f"Skipping unreadable file during refactor '{rel_path}': {err}")
            continue

        new_content, occurrences = rewrite_note_links(
            content, old_stem, new_stem
        )
        if occurrences:
            total_occurrences += len(occurrences)
            lines_mod = sorted(list(set(occ[0] for occ in occurrences)))
            files_modified.append(
                RefactorFileModification(
                    path=rel_path,
                    occurrences_replaced=len(occurrences),
                    lines_modified=lines_mod,
                )
            )
            planned_writes.append((file_path, content, new_content))

    return files_modified, total_occurrences, planned_writes


def _execute_rollback_envelope(
    vault_root: Path,
    planned_writes: list[tuple[Path, str, str]],
    target_note_rel: Optional[str],
    links_only: bool,
    new_stem: str,
) -> None:
    """Commit file rewrites, rename, and frontmatter mutations with ACID-style rollback."""
    with atomic_transaction(
        exc_cls=RefactorError,
        error_prefix="Refactor failed during file operations",
    ) as tx:
        # 1. Rewrite referencing note links atomically
        for file_path, old_content, new_content in planned_writes:
            atomic_write_text(file_path, new_content, encoding="utf-8")
            tx.record_undo(
                lambda p=file_path, c=old_content: atomic_write_text(
                    p, c, encoding="utf-8"
                )
            )

        # 2. Rename target note file if not links_only
        renamed_target = False
        if target_note_rel and not links_only:
            old_file_path = vault_root / target_note_rel
            new_filename = f"{new_stem}.md"
            new_file_path = old_file_path.parent / new_filename
            if (
                old_file_path.exists()
                and old_file_path.resolve() != new_file_path.resolve()
            ):
                old_file_path.rename(new_file_path)
                tx.record_undo(
                    lambda old=old_file_path, new=new_file_path: new.rename(old)
                )
                renamed_target = True

            curr_target_path = new_file_path if renamed_target else old_file_path
            if curr_target_path.exists():
                target_content = curr_target_path.read_text(encoding="utf-8")
                now_str = now_iso()
                updates = {
                    "title": f'"{new_stem}"',
                    "updated": f'"{now_str}"',
                }
                updated_content, _ = mutate_okf_frontmatter(target_content, updates)
                atomic_write_text(curr_target_path, updated_content, encoding="utf-8")
                tx.record_undo(
                    lambda p=curr_target_path, c=target_content: atomic_write_text(
                        p, c, encoding="utf-8"
                    )
                )


def refactor_note(
    vault_root: Path,
    conn: Any,
    old_title: str,
    new_title: str,
    *,
    dry_run: bool = False,
    links_only: bool = False,
    force: bool = False,
    cache_syncer: Optional[CacheSyncer] = None,
) -> RefactorResult:
    """Execute note renaming and rewrite all referencing Wikilinks and Markdown links.

    Raises:
        AmbiguousTargetError: If old_title matches multiple notes and force is False.
        DestinationCollisionError: If renaming target file already exists on disk.
        RefactorError: If arguments or file operations fail.
    """
    (
        old_title_clean,
        new_title_clean,
        old_stem,
        new_stem,
        target_note_rel,
        renamed_rel_path,
    ) = _resolve_refactor_targets(
        vault_root, conn, old_title, new_title, force=force, links_only=links_only
    )

    files_modified, total_occurrences, planned_writes = _plan_link_rewrites(
        vault_root, old_stem, new_stem
    )

    if not dry_run:
        _execute_rollback_envelope(
            vault_root, planned_writes, target_note_rel, links_only, new_stem
        )
        if cache_syncer is not None:
            try:
                cache_syncer(vault_root)
            except Exception as err:
                log_warn(f"Cache sync failed after refactor: {err}")

    return RefactorResult(
        old_title=old_title_clean,
        new_title=new_title_clean,
        file_renamed=renamed_rel_path,
        files_modified=files_modified,
        total_occurrences=total_occurrences,
        is_dry_run=dry_run,
        source_file=target_note_rel,
    )

