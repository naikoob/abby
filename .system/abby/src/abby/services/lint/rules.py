"""OKF Schema validation rules, domain alignment, and audit engine."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from abby.constants import VALID_NOTE_DOMAINS
from abby.core.domain import canonicalize_domain, resolve_domain_from_path as _core_resolve_domain_from_path
from abby.core.resolution import resolve_source_note
from abby.models.lint import LintReport, LintViolation, NoteAuditResult
from abby.services.lint.scanner import scan_frontmatter
from abby.services.lint.validators import (
    CANONICAL_STATUSES,
    CANONICAL_TYPES,
    normalize_tag,
    parse_iso_date,
    validate_actor_syntax,
    validate_created_field,
    validate_description_field,
    validate_frontmatter_structure,
    validate_status_field,
    validate_tag_syntax,
    validate_tags_field,
    validate_title_field,
    validate_trust_and_sources,
    validate_type_field,
)

__all__ = [
    "CANONICAL_STATUSES",
    "CANONICAL_TYPES",
    "audit_note_content",
    "audit_single_note",
    "audit_vault",
    "find_target_note",
    "normalize_tag",
    "parse_iso_date",
    "resolve_canonical_domain",
    "resolve_domain_from_path",
    "validate_actor_syntax",
    "validate_tag_syntax",
]


def resolve_domain_from_path(rel_path: str | Path) -> Optional[str]:
    """Identify which PARA domain directory a relative path belongs to."""
    return _core_resolve_domain_from_path(rel_path)


def resolve_canonical_domain(domain: Optional[str]) -> Optional[str]:
    """Resolve a domain directory name, alias, or shorthand to its canonical PARA name."""
    return canonicalize_domain(domain)


def audit_note_content(
    content: str,
    file_path: str,
    domain: Optional[str] = None,
    file_stem: Optional[str] = None,
    absolute_path: Optional[Path] = None,
) -> NoteAuditResult:
    """Perform line-accurate lexical and structural OKF schema audit on note content."""
    abs_path = absolute_path if absolute_path is not None else Path(file_path)
    result = NoteAuditResult(file_path=file_path, absolute_path=abs_path)
    canonical_domain = resolve_canonical_domain(domain)
    stem = file_stem or (abs_path.stem if abs_path.stem else "Untitled Note")

    parsed = scan_frontmatter(content)
    if not validate_frontmatter_structure(parsed, file_path, stem, result):
        return result

    fields_found = parsed.fields
    tags_raw = fields_found["tags"][0] if "tags" in fields_found else ""

    # 1. Validate mandatory fields: title, created, status, type
    validate_title_field(fields_found, file_path, stem, result)
    validate_created_field(fields_found, file_path, result)
    validate_status_field(fields_found, canonical_domain, file_path, result)
    validate_type_field(fields_found, canonical_domain, file_path, result)

    # 2. Validate tags
    validate_tags_field(
        fields_found=fields_found,
        tags_list=parsed.tags,
        tags_line=parsed.tags_line,
        tags_is_scalar=parsed.tags_is_scalar,
        tags_raw=tags_raw,
        file_path=file_path,
        result=result,
    )

    # 3. Validate lifecycle-gated field: description
    effective_domain = canonical_domain or resolve_domain_from_path(file_path)
    validate_description_field(fields_found, effective_domain, file_path, result)

    # 4. Validate OKF v0.2 trust, provenance, and sources
    validate_trust_and_sources(parsed, fields_found, file_path, result)

    return result


def find_target_note(vault_root: Path, note_arg: str) -> Optional[Path]:
    """Resolve a note path argument to an existing file strictly within the vault."""
    try:
        return resolve_source_note(vault_root, note_arg)
    except Exception:
        return None


def audit_single_note(vault_root: Path, note_arg: str) -> Optional[NoteAuditResult]:
    """Audit a single note by path or filename."""
    note_path = find_target_note(vault_root, note_arg)
    if not note_path or not note_path.is_file():
        return None
    try:
        content = note_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None

    try:
        rel_path = str(note_path.relative_to(vault_root)).replace("\\", "/")
    except ValueError:
        rel_path = note_path.name

    domain = resolve_domain_from_path(rel_path)
    return audit_note_content(content, rel_path, domain=domain, absolute_path=note_path)


def audit_vault(vault_root: Path, domain: Optional[str] = None) -> LintReport:
    """Scan vault notes for OKF schema compliance across PARA domains."""
    report = LintReport()

    target_dirs: list[str] = []
    if domain:
        canonical_domain = resolve_canonical_domain(domain)
        if canonical_domain and canonical_domain in VALID_NOTE_DOMAINS:
            target_dirs = [canonical_domain]
    else:
        target_dirs = list(VALID_NOTE_DOMAINS)

    notes_to_audit: list[tuple[Path, str, Optional[str]]] = []
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
                try:
                    rel_path = str(file_path.relative_to(vault_root)).replace("\\", "/")
                except ValueError:
                    rel_path = file_path.name
                notes_to_audit.append((file_path, rel_path, d_name))

    notes_to_audit.sort(key=lambda item: item[1])

    report.total_audited = len(notes_to_audit)
    for abs_path, rel_path, d_name in notes_to_audit:
        try:
            content = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            v = LintViolation(
                file_path=rel_path,
                field="content",
                rule="file-read-error",
                severity="error",
                message=f"Failed to read note file: {exc}",
                is_fixable=False,
            )
            report.violations.append(v)
            report.total_violations += 1
            report.total_errors += 1
            continue
        audit_res = audit_note_content(
            content, rel_path, domain=d_name, absolute_path=abs_path
        )
        if audit_res.is_clean:
            report.clean_notes += 1
        else:
            for v in audit_res.violations:
                report.violations.append(v)
                report.total_violations += 1
                if v.severity == "error":
                    report.total_errors += 1
                elif v.severity == "warning":
                    report.total_warnings += 1

    return report
