"""OKF Frontmatter remediation and non-destructive auto-repair engine."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from abby.constants import (
    DOMAIN_DEFAULT_STATUS,
    DOMAIN_DEFAULT_TYPE,
    VALID_NOTE_DOMAINS,
)
from abby.core.domain import canonicalize_domain
from abby.models.lint import (
    LintReport,
    NoteFixResult,
    RemediationAction,
)
from abby.utils.io import atomic_write_text
from abby.utils.time import now_iso
from abby.utils.yaml import format_yaml_tag, unescape_yaml_string
from abby.services.lint.rules import (
    CANONICAL_STATUSES,
    CANONICAL_TYPES,
    audit_vault,
    normalize_tag,
    parse_iso_date,
    resolve_canonical_domain,
    resolve_domain_from_path,
)
from abby.services.lint.scanner import scan_frontmatter

__all__ = [
    "remediate_note_content",
    "remediate_note_file",
    "remediate_vault",
]


def _repair_missing_frontmatter(
    normalized: str,
    rel_path: str,
    canonical_domain: Optional[str],
    file_stem: str,
    is_crlf: bool,
) -> tuple[str, list[RemediationAction], bool]:
    """Auto-inject complete canonical OKF frontmatter header if note has none."""
    now = now_iso()
    expected_type = (
        DOMAIN_DEFAULT_TYPE.get(canonical_domain, "inbox")
        if canonical_domain
        else "inbox"
    )
    expected_status = (
        DOMAIN_DEFAULT_STATUS.get(canonical_domain, "unprocessed")
        if canonical_domain
        else "unprocessed"
    )
    default_tags = ["inbox"] if canonical_domain in ("00 - Inbox", "inbox") else []
    tag_str = (
        "\ntags: []"
        if not default_tags
        else ("\ntags:\n" + "\n".join(f"  - {t}" for t in default_tags))
    )
    sanitized_title = file_stem.replace('"', '\\"')
    header = f'---\ntitle: "{sanitized_title}"\ncreated: "{now}"\ntype: {expected_type}\nstatus: {expected_status}{tag_str}\n---\n'
    new_content = header + normalized.lstrip("\n")
    if is_crlf:
        new_content = new_content.replace("\n", "\r\n")
    actions = [
        RemediationAction(
            file_path=rel_path,
            rule="syntax-missing-frontmatter",
            field="frontmatter",
            old_value=None,
            new_value="OKF Header",
            description=f"Injected canonical OKF frontmatter header with title '{file_stem}'",
        )
    ]
    return new_content, actions, True


def _ensure_closing_delimiter(
    lines: list[str], rel_path: str, closing_line_number: int, is_closed: bool
) -> tuple[int, list[RemediationAction]]:
    """Ensure frontmatter has a closing delimiter, inserting one before body if missing."""
    closing_idx = closing_line_number - 1 if is_closed else -1
    actions: list[RemediationAction] = []
    if closing_idx == -1:
        body_start = len(lines)
        for i in range(1, len(lines)):
            l_str = lines[i].strip()
            if l_str and not l_str.startswith("-") and ":" not in l_str:
                body_start = i
                break
        lines.insert(body_start, "---")
        closing_idx = body_start
        actions.append(
            RemediationAction(
                file_path=rel_path,
                rule="syntax-unclosed-frontmatter",
                field="frontmatter",
                old_value=None,
                new_value="---",
                description="Inserted missing closing frontmatter delimiter '---'",
            )
        )
    return closing_idx, actions


def _repair_lifecycle_field(
    field_name: str,
    clean_val: str,
    expected_val: str,
    canonical_domain: Optional[str],
    canonical_set: set[str],
    rel_path: str,
) -> tuple[str, Optional[RemediationAction]]:
    """Validate and repair type or status fields against canonical sets and domain defaults."""
    unescaped_val = unescape_yaml_string(clean_val)
    is_valid = unescaped_val.lower() in canonical_set
    is_domain_match = not canonical_domain or unescaped_val.lower() == expected_val
    if not is_valid or not is_domain_match:
        rule_name = f"invalid-{field_name}" if not is_valid else f"domain-{field_name}-mismatch"
        return f"{field_name}: {expected_val}", RemediationAction(
            file_path=rel_path,
            rule=rule_name,
            field=field_name,
            old_value=clean_val,
            new_value=expected_val,
            description=f"Updated {field_name} to canonical domain default '{expected_val}'",
        )
    return f"{field_name}: {clean_val}", None


def _repair_scalar_field(
    clean_key: str,
    clean_val: str,
    line: str,
    rel_path: str,
    file_stem: str,
    canonical_domain: Optional[str],
    expected_type: str,
    expected_status: str,
) -> tuple[str, Optional[RemediationAction]]:
    """Repair a single frontmatter key-value pair, returning the formatted line and optional action."""
    unescaped_val = unescape_yaml_string(clean_val)
    if clean_key == "title":
        if not unescaped_val:
            sanitized = file_stem.replace('"', '\\"')
            return f'title: "{sanitized}"', RemediationAction(
                file_path=rel_path,
                rule="missing-title",
                field="title",
                old_value=clean_val,
                new_value=file_stem,
                description=f"Populated missing title '{file_stem}'",
            )
        return line, None

    if clean_key == "created":
        if not unescaped_val or parse_iso_date(unescaped_val) is None:
            now = now_iso()
            return f'created: "{now}"', RemediationAction(
                file_path=rel_path,
                rule="invalid-created-date",
                field="created",
                old_value=clean_val,
                new_value=now,
                description=f"Updated invalid created timestamp to '{now}'",
            )
        return line, None

    if clean_key == "type":
        return _repair_lifecycle_field(
            "type", clean_val, expected_type, canonical_domain, CANONICAL_TYPES, rel_path
        )

    if clean_key == "status":
        return _repair_lifecycle_field(
            "status", clean_val, expected_status, canonical_domain, CANONICAL_STATUSES, rel_path
        )

    return line, None


def _parse_tags_header(
    after: str, current_tags: list[str]
) -> tuple[Optional[str], bool]:
    """Parse tags header line returning (tags_scalar_raw, in_tags)."""
    if after.startswith("[") and after.endswith("]"):
        inner = after[1:-1].strip()
        if inner:
            for t in inner.split(","):
                if t.strip():
                    current_tags.append(unescape_yaml_string(t.strip()))
        return None, False
    if after:
        return after, False
    return None, True


def _process_fm_lines(
    fm_lines: list[str],
    rel_path: str,
    file_stem: str,
    canonical_domain: Optional[str],
    expected_type: str,
    expected_status: str,
) -> tuple[list[str], set[str], list[str], Optional[str], Optional[int], list[RemediationAction]]:
    """Parse and repair existing frontmatter lines, collecting tags and seen keys."""
    new_fm_lines: list[str] = []
    seen_keys: set[str] = set()
    actions: list[RemediationAction] = []
    in_tags = False
    current_tags: list[str] = []
    tags_scalar_raw: Optional[str] = None
    tags_idx_in_new: Optional[int] = None

    for line in fm_lines:
        stripped = line.strip()
        if in_tags:
            if stripped.startswith("-"):
                val = unescape_yaml_string(stripped.lstrip("-").strip())
                current_tags.append(val)
                continue
            elif ":" in stripped or (stripped and not stripped.startswith("-")):
                in_tags = False
            elif not stripped:
                continue

        if stripped.startswith("tags:"):
            seen_keys.add("tags")
            tags_scalar_raw, in_tags = _parse_tags_header(stripped[5:].strip(), current_tags)
            tags_idx_in_new = len(new_fm_lines)
            new_fm_lines.append("__TAGS_PLACEHOLDER__")
            continue

        if ":" in stripped:
            key, _, val = stripped.partition(":")
            clean_key = key.strip()
            clean_val = val.strip()
            seen_keys.add(clean_key)
            repaired_line, scalar_action = _repair_scalar_field(
                clean_key,
                clean_val,
                line,
                rel_path,
                file_stem,
                canonical_domain,
                expected_type,
                expected_status,
            )
            new_fm_lines.append(repaired_line)
            if scalar_action is not None:
                actions.append(scalar_action)
        else:
            new_fm_lines.append(line)

    return new_fm_lines, seen_keys, current_tags, tags_scalar_raw, tags_idx_in_new, actions


def _inject_missing_mandatory_keys(
    new_fm_lines: list[str],
    seen_keys: set[str],
    rel_path: str,
    file_stem: str,
    expected_type: str,
    expected_status: str,
) -> list[RemediationAction]:
    """Inject required frontmatter fields (title, created, type, status) if absent."""
    actions: list[RemediationAction] = []
    if "title" not in seen_keys:
        sanitized = file_stem.replace('"', '\\"')
        new_fm_lines.insert(0, f'title: "{sanitized}"')
        actions.append(
            RemediationAction(
                file_path=rel_path,
                rule="missing-title",
                field="title",
                old_value=None,
                new_value=file_stem,
                description=f"Injected missing title '{file_stem}'",
            )
        )
    if "created" not in seen_keys:
        now = now_iso()
        title_idx = next(
            (i for i, l in enumerate(new_fm_lines) if l.startswith("title:")), -1
        )
        new_fm_lines.insert(title_idx + 1 if title_idx >= 0 else 0, f'created: "{now}"')
        actions.append(
            RemediationAction(
                file_path=rel_path,
                rule="missing-created",
                field="created",
                old_value=None,
                new_value=now,
                description=f"Injected missing created timestamp '{now}'",
            )
        )
    if "type" not in seen_keys:
        new_fm_lines.append(f"type: {expected_type}")
        actions.append(
            RemediationAction(
                file_path=rel_path,
                rule="missing-type",
                field="type",
                old_value=None,
                new_value=expected_type,
                description=f"Injected missing type '{expected_type}'",
            )
        )
    if "status" not in seen_keys:
        new_fm_lines.append(f"status: {expected_status}")
        actions.append(
            RemediationAction(
                file_path=rel_path,
                rule="missing-status",
                field="status",
                old_value=None,
                new_value=expected_status,
                description=f"Injected missing status '{expected_status}'",
            )
        )
    return actions


def _repair_and_render_tags(
    tags_scalar_raw: Optional[str],
    seen_keys: set[str],
    current_tags: list[str],
    rel_path: str,
) -> tuple[list[str], list[RemediationAction]]:
    """Normalize tags into clean YAML array, stripping '#' and dropping empty items."""
    final_tags: list[str] = []
    actions: list[RemediationAction] = []

    if tags_scalar_raw is not None:
        raw_split = [t.strip() for t in tags_scalar_raw.split(",") if t.strip()]
        for t in raw_split:
            final_tags.append(normalize_tag(unescape_yaml_string(t)))
        actions.append(
            RemediationAction(
                file_path=rel_path,
                rule="invalid-tags-format",
                field="tags",
                old_value=tags_scalar_raw,
                new_value=final_tags,
                description=f"Coerced scalar tags to list: {final_tags}",
            )
        )
    elif "tags" in seen_keys:
        had_hash = False
        had_empty = False
        for t in current_tags:
            norm = normalize_tag(t)
            if not norm:
                had_empty = True
                continue
            if norm != t:
                had_hash = True
            final_tags.append(norm)
        if had_empty:
            actions.append(
                RemediationAction(
                    file_path=rel_path,
                    rule="tag-empty",
                    field="tags",
                    old_value=current_tags,
                    new_value=final_tags,
                    description=f"Removed empty tags: {final_tags}",
                )
            )
        if had_hash:
            actions.append(
                RemediationAction(
                    file_path=rel_path,
                    rule="tag-has-hash",
                    field="tags",
                    old_value=current_tags,
                    new_value=final_tags,
                    description=f"Normalized tags by stripping '#' prefixes: {final_tags}",
                )
            )
    else:
        actions.append(
            RemediationAction(
                file_path=rel_path,
                rule="missing-tags",
                field="tags",
                old_value=None,
                new_value=[],
                description="Injected missing empty tags list",
            )
        )

    if final_tags:
        tags_rendered = ["tags:"] + [format_yaml_tag(t) for t in final_tags]
    else:
        tags_rendered = ["tags: []"]
    return tags_rendered, actions


def remediate_note_content(
    raw_content: str,
    rel_path: str,
    domain: Optional[str] = None,
    file_stem: str = "Untitled Note",
) -> tuple[str, list[RemediationAction], bool]:
    """Calculate non-destructive auto-repairs on frontmatter while preserving note body and block references."""
    is_crlf = "\r\n" in raw_content
    normalized = raw_content.replace("\r\n", "\n").replace("\r", "\n")
    actions: list[RemediationAction] = []
    canonical_domain = canonicalize_domain(domain)

    parsed = scan_frontmatter(raw_content)

    # 1. Note completely lacking frontmatter: auto-inject complete header
    if not parsed.has_frontmatter:
        return _repair_missing_frontmatter(
            normalized, rel_path, canonical_domain, file_stem, is_crlf
        )

    # 2. Ensure closing frontmatter delimiter
    lines = normalized.split("\n")
    closing_idx, delim_actions = _ensure_closing_delimiter(
        lines, rel_path, parsed.closing_line_number, parsed.is_closed
    )
    actions.extend(delim_actions)

    fm_lines = lines[1:closing_idx]
    body_lines = lines[closing_idx + 1 :]

    expected_type = (
        DOMAIN_DEFAULT_TYPE.get(canonical_domain, "inbox")
        if canonical_domain
        else "inbox"
    )
    expected_status = (
        DOMAIN_DEFAULT_STATUS.get(canonical_domain, "unprocessed")
        if canonical_domain
        else "unprocessed"
    )

    new_fm_lines, seen_keys, current_tags, tags_scalar_raw, tags_idx_in_new, line_actions = (
        _process_fm_lines(
            fm_lines,
            rel_path,
            file_stem,
            canonical_domain,
            expected_type,
            expected_status,
        )
    )
    actions.extend(line_actions)

    # 3. Insert missing mandatory fields
    missing_actions = _inject_missing_mandatory_keys(
        new_fm_lines,
        seen_keys,
        rel_path,
        file_stem,
        expected_type,
        expected_status,
    )
    actions.extend(missing_actions)

    # 4. Handle tags formatting and normalization
    tags_rendered, tag_actions = _repair_and_render_tags(
        tags_scalar_raw, seen_keys, current_tags, rel_path
    )
    actions.extend(tag_actions)

    if tags_idx_in_new is not None and "__TAGS_PLACEHOLDER__" in new_fm_lines:
        placeholder_idx = new_fm_lines.index("__TAGS_PLACEHOLDER__")
        new_fm_lines[placeholder_idx : placeholder_idx + 1] = tags_rendered
    elif "tags" not in seen_keys:
        new_fm_lines.extend(tags_rendered)

    fm_block = "---\n" + "\n".join(new_fm_lines) + "\n---\n"
    if body_lines:
        new_content = fm_block + "\n".join(body_lines)
    else:
        new_content = fm_block

    if is_crlf:
        new_content = new_content.replace("\n", "\r\n")

    is_modified = len(actions) > 0
    return new_content, actions, is_modified


def remediate_note_file(
    file_path: Path, vault_root: Path, dry_run: bool = False
) -> NoteFixResult:
    """Remediate a single note file in-place on disk without creating .bak sidecars."""
    try:
        rel_path = str(file_path.relative_to(vault_root)).replace("\\", "/")
    except ValueError:
        rel_path = file_path.name

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return NoteFixResult(file_path=rel_path, success=False, error=str(exc))

    domain = resolve_domain_from_path(rel_path)
    stem = file_path.stem if file_path.stem else "Untitled Note"

    try:
        updated_content, actions, is_modified = remediate_note_content(
            content, rel_path, domain=domain, file_stem=stem
        )
    except Exception as exc:
        return NoteFixResult(file_path=rel_path, success=False, error=str(exc))

    if is_modified and not dry_run:
        try:
            atomic_write_text(file_path, updated_content, encoding="utf-8")
        except Exception as exc:
            return NoteFixResult(file_path=rel_path, success=False, error=str(exc))

    return NoteFixResult(
        file_path=rel_path, success=True, dry_run=dry_run, actions=actions
    )


def remediate_vault(
    vault_root: Path, domain: Optional[str] = None, dry_run: bool = False
) -> tuple[LintReport, list[NoteFixResult]]:
    """Scan and remediate notes across vault or within a specific domain."""
    fix_results: list[NoteFixResult] = []

    # Target directories
    target_dirs: list[str] = []
    if domain:
        canonical_domain = resolve_canonical_domain(domain)
        if canonical_domain and canonical_domain in VALID_NOTE_DOMAINS:
            target_dirs = [canonical_domain]
    else:
        target_dirs = list(VALID_NOTE_DOMAINS)

    notes_to_fix: list[Path] = []
    for d_name in target_dirs:
        dir_path = vault_root / d_name
        if not dir_path.is_dir():
            continue
        for file_path in dir_path.rglob("*.md"):
            if file_path.is_file():
                if any(
                    part.startswith(".")
                    for part in file_path.relative_to(dir_path).parts
                ):
                    continue
                notes_to_fix.append(file_path)

    notes_to_fix.sort()

    for p in notes_to_fix:
        res = remediate_note_file(p, vault_root, dry_run=dry_run)
        if res.actions:
            fix_results.append(res)

    # Post-remediation report
    post_report = audit_vault(vault_root, domain=domain)
    post_report.fixed_notes = len(fix_results)
    post_report.fixed_violations = sum(len(r.actions) for r in fix_results)

    return post_report, fix_results
