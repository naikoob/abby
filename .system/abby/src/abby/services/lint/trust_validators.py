"""OKF v0.2 trust, provenance, and sources validators for lint engine."""

from __future__ import annotations

from typing import Any, Optional

from abby.models.lint import LintViolation, NoteAuditResult
from abby.models.okf import ParsedFrontmatter
from abby.models.trust import parse_actor
from abby.utils.time import parse_iso_timestamp
from abby.utils.yaml import unescape_yaml_string


def validate_actor_syntax(actor: str) -> bool:
    """Validate OKF v0.2 actor string syntax (<producer>/<version>, human:<id>, process:<id>, agent:<id>, tool:<id>)."""
    if not actor or not isinstance(actor, str):
        return False
    return parse_actor(actor.strip()) is not None


def parse_iso_date(val: str) -> Optional[Any]:
    """Attempt to parse an ISO 8601 date or datetime string."""
    cleaned = unescape_yaml_string(val).strip()
    return parse_iso_timestamp(cleaned)


def _validate_stale_after(
    parsed: ParsedFrontmatter,
    fields_found: dict[str, tuple[str, int]],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    if parsed.stale_after and parse_iso_date(parsed.stale_after) is None:
        l_num = fields_found.get("stale_after", (None, 2))[1]
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="stale_after",
                rule="invalid-stale-after-date",
                severity="warning",
                message=f"Value '{parsed.stale_after}' in 'stale_after' is not a valid ISO 8601 calendar date or datetime",
                line_number=l_num,
                is_fixable=False,
            )
        )


def _validate_generated(
    parsed: ParsedFrontmatter,
    fields_found: dict[str, tuple[str, int]],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    if not parsed.generated:
        return
    gen_by = parsed.generated.get("by", "")
    l_num = fields_found.get("generated", (None, 2))[1]
    if not validate_actor_syntax(gen_by):
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="generated",
                rule="invalid-actor-format",
                severity="warning",
                message=f"Actor '{gen_by}' in 'generated' does not conform to OKF actor naming convention (<producer>/<version>, human:<id>, process:<id>, agent:<id>)",
                line_number=l_num,
                is_fixable=False,
            )
        )
    gen_at = parsed.generated.get("at")
    if gen_at and parse_iso_date(gen_at) is None:
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="generated",
                rule="invalid-generated-date",
                severity="warning",
                message=f"Timestamp '{gen_at}' in 'generated' is not a valid ISO 8601 calendar date or datetime",
                line_number=l_num,
                is_fixable=False,
            )
        )


def _validate_verified(
    parsed: ParsedFrontmatter,
    fields_found: dict[str, tuple[str, int]],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    if not parsed.verified:
        return
    l_num = fields_found.get("verified", (None, 2))[1]
    for verifier in parsed.verified:
        v_by = verifier.get("by", "")
        if not validate_actor_syntax(v_by):
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="verified",
                    rule="invalid-actor-format",
                    severity="warning",
                    message=f"Actor '{v_by}' in 'verified' does not conform to OKF actor naming convention (<producer>/<version>, human:<id>, process:<id>, agent:<id>)",
                    line_number=l_num,
                    is_fixable=False,
                )
            )
        v_at = verifier.get("at")
        if v_at and parse_iso_date(v_at) is None:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="verified",
                    rule="invalid-verified-date",
                    severity="warning",
                    message=f"Timestamp '{v_at}' in 'verified' is not a valid ISO 8601 calendar date or datetime",
                    line_number=l_num,
                    is_fixable=False,
                )
            )


def _validate_sources(
    parsed: ParsedFrontmatter,
    fields_found: dict[str, tuple[str, int]],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    if "sources" not in fields_found:
        return
    l_num = fields_found["sources"][1]
    if getattr(parsed, "sources_is_malformed", False):
        result.violations.append(
            LintViolation(
                file_path=file_path,
                field="sources",
                rule="invalid-sources-format",
                severity="warning",
                message="Field 'sources' must be a list of mapping entries (- resource: ...)",
                line_number=l_num,
                is_fixable=False,
            )
        )
        return

    for item in parsed.sources:
        if not isinstance(item, dict):
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="sources",
                    rule="invalid-sources-format",
                    severity="warning",
                    message="Field 'sources' must contain mapping entries",
                    line_number=l_num,
                    is_fixable=False,
                )
            )
            continue

        res_val = item.get("resource")
        if not res_val or not isinstance(res_val, str) or not res_val.strip():
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="sources",
                    rule="missing-source-resource",
                    severity="warning",
                    message="Source entry is missing mandatory 'resource' identifier",
                    line_number=l_num,
                    is_fixable=False,
                )
            )

        last_mod = item.get("last_modified")
        if last_mod and parse_iso_date(str(last_mod)) is None:
            result.violations.append(
                LintViolation(
                    file_path=file_path,
                    field="sources",
                    rule="invalid-source-date",
                    severity="warning",
                    message=f"Value '{last_mod}' in source 'last_modified' is not a valid ISO 8601 calendar date or datetime",
                    line_number=l_num,
                    is_fixable=False,
                )
            )


def validate_trust_and_sources(
    parsed: ParsedFrontmatter,
    fields_found: dict[str, tuple[str, int]],
    file_path: str,
    result: NoteAuditResult,
) -> None:
    """Validate OKF v0.2 trust, provenance, and sources fields."""
    _validate_stale_after(parsed, fields_found, file_path, result)
    _validate_generated(parsed, fields_found, file_path, result)
    _validate_verified(parsed, fields_found, file_path, result)
    _validate_sources(parsed, fields_found, file_path, result)

