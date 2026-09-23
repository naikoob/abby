"""Lint and remediation CLI command handler: execute_lint."""

from __future__ import annotations

import argparse
from pathlib import Path

from abby.constants import DOMAIN_ALIAS_MAP
from abby.core.domain import canonicalize_domain
from abby.models.lint import LintReport, NoteFixResult
from abby.services.lint import (
    audit_single_note,
    audit_vault,
    find_target_note,
    format_fix_report,
    format_lint_report,
    remediate_note_file,
    remediate_vault,
)
from abby.utils.io import log_error, output_payload


def _execute_lint_fix(
    vault_root: Path,
    domain: Optional[str],
    note_arg: Optional[str],
    json_mode: bool,
    strict: bool,
    dry_run: bool,
) -> int:
    """Execute lint remediation for a single note or whole vault/domain."""
    fix_results: list[NoteFixResult] = []
    post_report: LintReport

    if note_arg:
        target_path = find_target_note(vault_root, note_arg)
        if not target_path or not target_path.is_file():
            log_error(f"Note '{note_arg}' not found in vault.")
            if json_mode:
                output_payload(
                    {"success": False, "error": f"Note '{note_arg}' not found"},
                    json_mode=True,
                )
            return 1

        fix_res = remediate_note_file(target_path, vault_root, dry_run=dry_run)
        if not fix_res.success and fix_res.error:
            log_error(f"Failed to remediate note: {fix_res.error}")

        if fix_res.actions:
            fix_results.append(fix_res)

        audit_res = audit_single_note(vault_root, note_arg)
        if audit_res is not None:
            post_report = LintReport(
                total_audited=1,
                clean_notes=1 if audit_res.is_clean else 0,
                total_violations=len(audit_res.violations),
                total_errors=sum(
                    1 for v in audit_res.violations if v.severity == "error"
                ),
                total_warnings=sum(
                    1 for v in audit_res.violations if v.severity == "warning"
                ),
                violations=audit_res.violations,
                fixed_notes=1 if fix_res.actions else 0,
                fixed_violations=len(fix_res.actions),
                scoped_path=audit_res.file_path,
            )
        else:
            post_report = LintReport(total_audited=1)
    else:
        post_report, fix_results = remediate_vault(
            vault_root, domain=domain, dry_run=dry_run
        )

    post_report.exit_code = post_report.calculate_exit_code(strict=strict)

    if json_mode:
        payload = post_report.to_dict()
        payload["dry_run"] = dry_run
        payload["remediations"] = [r.to_dict() for r in fix_results]
        output_payload(payload, json_mode=True)
    else:
        output_payload(
            format_fix_report(fix_results, post_report, dry_run=dry_run),
            json_mode=False,
        )

    return post_report.exit_code


def _execute_lint_audit(
    vault_root: Path,
    domain: Optional[str],
    note_arg: Optional[str],
    json_mode: bool,
    strict: bool,
) -> int:
    """Execute read-only lint audit for a single note or whole vault/domain."""
    report: LintReport

    if note_arg:
        note_res = audit_single_note(vault_root, note_arg)
        if note_res is None:
            log_error(f"Note '{note_arg}' not found in vault.")
            if json_mode:
                output_payload(
                    {"success": False, "error": f"Note '{note_arg}' not found"},
                    json_mode=True,
                )
            return 1

        report = LintReport(
            total_audited=1,
            clean_notes=1 if note_res.is_clean else 0,
            total_violations=len(note_res.violations),
            total_errors=sum(1 for v in note_res.violations if v.severity == "error"),
            total_warnings=sum(
                1 for v in note_res.violations if v.severity == "warning"
            ),
            violations=note_res.violations,
            scoped_path=note_res.file_path,
        )
    else:
        report = audit_vault(vault_root, domain=domain)

    report.exit_code = report.calculate_exit_code(strict=strict)

    if json_mode:
        output_payload(report.to_dict(), json_mode=True)
    else:
        output_payload(format_lint_report(report), json_mode=False)

    return report.exit_code


def execute_lint(vault_root: Path, args: argparse.Namespace) -> int:
    """Execute vault-wide or scoped OKF schema linting and remediation."""
    json_mode = getattr(args, "json", False)
    strict = getattr(args, "strict", False)
    fix = getattr(args, "fix", False)
    dry_run = getattr(args, "dry_run", False)
    domain = getattr(args, "domain", None)
    note_arg = getattr(args, "note", None)

    # Validate domain if supplied
    if domain:
        canonical_domain = canonicalize_domain(domain)
        if not canonical_domain:
            err_msg = f"Invalid domain '{domain}'. Must be one of: {', '.join(sorted(DOMAIN_ALIAS_MAP.keys()))}"
            log_error(err_msg)
            if json_mode:
                output_payload({"success": False, "error": err_msg}, json_mode=True)
            return 2
        domain = canonical_domain

    # If --dry-run is passed without --fix, enable fix logic in dry-run mode
    if fix or dry_run:
        return _execute_lint_fix(
            vault_root, domain, note_arg, json_mode, strict, dry_run
        )
    return _execute_lint_audit(vault_root, domain, note_arg, json_mode, strict)

