"""Field-level validators, syntax checks, and constants for OKF Schema auditing."""

from __future__ import annotations

from typing import Optional

from abby.constants import (
    DOMAIN_DEFAULT_STATUS,
    DOMAIN_DEFAULT_TYPE,
)
from abby.models.lint import LintViolation, NoteAuditResult
from abby.models.okf import ParsedFrontmatter
from abby.utils.yaml import unescape_yaml_string
from abby.services.lint.trust_validators import (
    parse_iso_date,
    validate_actor_syntax,
    validate_trust_and_sources,
)
from abby.utils.time import now_iso

__all__ = [
    "CANONICAL_STATUSES",
    "CANONICAL_TYPES",
    "normalize_tag",
    "parse_iso_date",
    "validate_actor_syntax",
    "validate_created_field",
    "validate_description_field",
    "validate_frontmatter_structure",
    "validate_status_field",
    "validate_tag_syntax",
    "validate_tags_field",
    "validate_title_field",
    "validate_trust_and_sources",
    "validate_type_field",
]

CANONICAL_STATUSES: set[str] = {
    "unprocessed",
    "active",
    "evergreen",
    "archived",
}

CANONICAL_TYPES: set[str] = {
    "inbox",
    "project-note",
    "area-note",
    "resource-note",
    "archive-note",
}


def normalize_tag(tag: str) -> str:
    """Strip leading '#' and outer whitespace from a tag string."""
    cleaned = tag.strip()
    while cleaned.startswith("#"):
        cleaned = cleaned[1:].strip()
    return cleaned


def validate_tag_syntax(tag: str) -> tuple[bool, Optional[str]]:
    """Validate Obsidian-compatible tag syntax.

    Returns (is_valid, warning_rule).
    Disallows spaces. Flags leading '#' as fixable warning.
    """
    if not tag or not tag.strip():
        return False, "tag-empty"
    if any(c in tag for c in " \t\r\n"):
        return False, "tag-has-whitespace"
    if tag.strip().startswith("#"):
        return True, "tag-has-hash"
    return True, None


def validate_frontmatter_structure(
    parsed: ParsedFrontmatter,
    file_path: str,
    stem: str,
    result: NoteAuditResult,
) -> bool:
    """Validate presence and delimiters of YAML frontmatter.

    Returns True if valid frontmatter exists and is closed, False otherwise.
    """
    if not parsed.has_frontmatter:
        result.has_frontmatter = False
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="frontmatter",
                rule="syntax-missing-frontmatter",
                severity="error",
                message="Note is missing YAML frontmatter delimiters ('---')",
                line_number=1,
                is_fixable=True,
                suggested_value=f'---\ntitle: "{stem}"\n...',
            )
        )
        return False

    if not parsed.is_closed:
        result.has_frontmatter = False
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="frontmatter",
                rule="syntax-unclosed-frontmatter",
                severity="error",
                message="Opening frontmatter '---' present but closing delimiter missing",
                line_number=1,
                is_fixable=True,
            )
        )
        return False

    return True


def validate_title_field(
    fields_found: dict[str, tuple[str, int]],
    file_path: str,
    stem: str,
    result: NoteAuditResult,
) -> None:
    """Validate mandatory 'title' field."""
    if "title" not in fields_found:
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="title",
                rule="missing-title",
                severity="error",
                message="Missing mandatory 'title' field in frontmatter",
                line_number=2,
                is_fixable=True,
                suggested_value=stem,
            )
        )
    else:
        raw_title, l_num = fields_found["title"]
        clean_title = unescape_yaml_string(raw_title)
        if not clean_title:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="title",
                    rule="missing-title",
                    severity="error",
                    message="Mandatory 'title' field is empty",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=stem,
                )
            )


def validate_created_field(
    fields_found: dict[str, tuple[str, int]],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    """Validate mandatory 'created' ISO 8601 timestamp."""
    if "created" not in fields_found:
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="created",
                rule="missing-created",
                severity="error",
                message="Missing mandatory 'created' field in frontmatter",
                line_number=2,
                is_fixable=True,
                suggested_value=now_iso(),
            )
        )
    else:
        raw_created, l_num = fields_found["created"]
        clean_created = unescape_yaml_string(raw_created)
        if not clean_created:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="created",
                    rule="missing-created",
                    severity="error",
                    message="Mandatory 'created' field is empty",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=now_iso(),
                )
            )
        elif parse_iso_date(clean_created) is None:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="created",
                    rule="invalid-created-date",
                    severity="error",
                    message=f"Value '{clean_created}' is not a valid ISO 8601 calendar date or datetime",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=now_iso(),
                )
            )


def validate_status_field(
    fields_found: dict[str, tuple[str, int]],
    canonical_domain: Optional[str],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    """Validate mandatory 'status' field and canonical status value."""
    expected_status = (
        DOMAIN_DEFAULT_STATUS.get(canonical_domain, "active")
        if canonical_domain
        else None
    )
    if "status" not in fields_found:
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="status",
                rule="missing-status",
                severity="error",
                message="Missing mandatory 'status' field in frontmatter",
                line_number=2,
                is_fixable=True,
                suggested_value=expected_status or "unprocessed",
            )
        )
    else:
        raw_status, l_num = fields_found["status"]
        clean_status = unescape_yaml_string(raw_status).lower()
        if not clean_status:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="status",
                    rule="missing-status",
                    severity="error",
                    message="Mandatory 'status' field is empty",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=expected_status or "unprocessed",
                )
            )
        elif clean_status not in CANONICAL_STATUSES:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="status",
                    rule="invalid-status",
                    severity="error",
                    message=f"Invalid status '{clean_status}'. Must be one of: {', '.join(sorted(CANONICAL_STATUSES))}",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=expected_status or "unprocessed",
                )
            )
        elif expected_status and clean_status != expected_status:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="status",
                    rule="domain-status-mismatch",
                    severity="warning",
                    message=f"Status '{clean_status}' does not match expected domain status '{expected_status}'",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=expected_status,
                )
            )


def validate_type_field(
    fields_found: dict[str, tuple[str, int]],
    canonical_domain: Optional[str],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    """Validate mandatory 'type' field and canonical type value."""
    expected_type = (
        DOMAIN_DEFAULT_TYPE.get(canonical_domain, "project-note")
        if canonical_domain
        else None
    )
    if "type" not in fields_found:
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="type",
                rule="missing-type",
                severity="error",
                message="Missing mandatory 'type' field in frontmatter",
                line_number=2,
                is_fixable=True,
                suggested_value=expected_type or "inbox",
            )
        )
    else:
        raw_type, l_num = fields_found["type"]
        clean_type = unescape_yaml_string(raw_type).lower()
        if not clean_type:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="type",
                    rule="missing-type",
                    severity="error",
                    message="Mandatory 'type' field is empty",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=expected_type or "inbox",
                )
            )
        elif clean_type not in CANONICAL_TYPES:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="type",
                    rule="invalid-type",
                    severity="error",
                    message=f"Invalid type '{clean_type}'. Must be one of: {', '.join(sorted(CANONICAL_TYPES))}",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=expected_type or "inbox",
                )
            )
        elif expected_type and clean_type != expected_type:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="type",
                    rule="domain-type-mismatch",
                    severity="warning",
                    message=f"Type '{clean_type}' does not match expected domain type '{expected_type}'",
                    line_number=l_num,
                    is_fixable=True,
                    suggested_value=expected_type,
                )
            )


def validate_tags_field(
    fields_found: dict[str, tuple[str, int]],
    tags_list: list[tuple[str, int]],
    tags_line: int,
    tags_is_scalar: bool,
    tags_raw: str,
    file_path: str,
    result: NoteAuditResult,
) -> None:
    """Validate 'tags' field structure and Obsidian syntax constraints."""
    if "tags" not in fields_found:
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="tags",
                rule="missing-tags",
                severity="warning",
                message="Missing 'tags' field in frontmatter",
                line_number=2,
                is_fixable=True,
                suggested_value=[],
            )
        )
    elif tags_is_scalar:
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="tags",
                rule="invalid-tags-format",
                severity="error",
                message=f"Tags field must be a YAML list, found scalar: '{tags_raw}'",
                line_number=tags_line,
                is_fixable=True,
                suggested_value=[
                    normalize_tag(t) for t in tags_raw.split(",") if t.strip()
                ],
            )
        )
    else:
        for tag_val, t_line in tags_list:
            is_valid, warning_rule = validate_tag_syntax(tag_val)
            if warning_rule == "tag-empty":
                result.violations.append(
                    LintViolation(
                        file_path=file_path,
                        field="tags",
                        rule="tag-empty",
                        severity="warning",
                        message="Empty tag value detected in tags list",
                        line_number=t_line,
                        is_fixable=True,
                    )
                )
            elif warning_rule == "tag-has-whitespace":
                result.violations.append(
                    LintViolation(
                        file_path=file_path,
                        field="tags",
                        rule="tag-has-whitespace",
                        severity="warning",
                        message=f"Tag '{tag_val}' contains whitespace which is disallowed in Obsidian",
                        line_number=t_line,
                        is_fixable=False,
                    )
                )
            elif warning_rule == "tag-has-hash":
                result.violations.append(
                    LintViolation(
                        file_path=file_path,
                        field="tags",
                        rule="tag-has-hash",
                        severity="warning",
                        message=f"Tag '{tag_val}' contains leading '#' prefix",
                        line_number=t_line,
                        is_fixable=True,
                        suggested_value=normalize_tag(tag_val),
                    )
                )


def validate_description_field(
    fields_found: dict[str, tuple[str, int]],
    effective_domain: Optional[str],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    """Validate lifecycle-gated 'description' field in curated domains."""
    curated_domains = {"01 - Projects", "02 - Areas", "03 - Resources"}
    if effective_domain in curated_domains:
        if "description" in fields_found:
            raw_desc, l_num = fields_found["description"]
            clean_desc = unescape_yaml_string(raw_desc).strip()
            if not clean_desc:
                result.violations.append(
                    LintViolation(
                        file_path=file_path,
                        field="description",
                        rule="missing-description",
                        severity="warning",
                        message=f"Note in curated domain '{effective_domain}' has an empty 'description'",
                        line_number=l_num,
                        is_fixable=False,
                    )
                )
        else:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="description",
                    rule="missing-description",
                    severity="warning",
                    message=f"Note in curated domain '{effective_domain}' lacks a 'description' frontmatter field",
                    line_number=2,
                    is_fixable=False,
                )
            )
