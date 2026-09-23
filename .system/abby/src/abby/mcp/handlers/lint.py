"""MCP handler for vault_lint tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abby.mcp.types import MCPToolCallResult
from abby.models.lint import LintReport
from abby.services.lint import (
    audit_single_note,
    audit_vault,
    find_target_note,
    format_fix_report,
    format_lint_report,
    remediate_note_file,
    remediate_vault,
)


def handle_vault_lint(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for vault_lint tool."""
    note, domain = args.get("note"), args.get("domain")
    fix, dry_run = bool(args.get("fix", False)), bool(args.get("dry_run", False))
    strict = bool(args.get("strict", False))

    if note:
        note_path = find_target_note(vault_root, note)
        if not note_path or not note_path.is_file():
            return MCPToolCallResult.error(f"Note '{note}' not found in vault.")

        audit_res = audit_single_note(vault_root, note)
        if not audit_res:
            return MCPToolCallResult.error(f"Note '{note}' not found in vault.")

        v_list = audit_res.violations
        n_err = sum(1 for v in v_list if v.severity == "error")
        n_warn = sum(1 for v in v_list if v.severity == "warning")

        if fix:
            fix_res = remediate_note_file(note_path, vault_root, dry_run=dry_run)
            post_report = LintReport(
                total_audited=1,
                clean_notes=1 if audit_res.is_clean else 0,
                total_violations=len(v_list),
                total_errors=n_err,
                total_warnings=n_warn,
                violations=v_list,
                fixed_notes=1 if fix_res.actions else 0,
                fixed_violations=len(fix_res.actions),
                scoped_path=str(note_path.relative_to(vault_root)),
            )
            post_report.exit_code = post_report.calculate_exit_code(strict=strict)
            text = format_fix_report([fix_res], post_report, dry_run=dry_run)
            if strict and post_report.exit_code != 0:
                text += "\n[STRICT] Audit failed: warnings promoted to errors under strict mode."
            return MCPToolCallResult.success(text)
        else:
            report = LintReport(
                total_audited=1,
                clean_notes=1 if audit_res.is_clean else 0,
                total_violations=len(v_list),
                total_errors=n_err,
                total_warnings=n_warn,
                violations=v_list,
                scoped_path=audit_res.file_path,
            )
            report.exit_code = report.calculate_exit_code(strict=strict)
            text = format_lint_report(report)
            if strict and report.exit_code != 0:
                text += "\n[STRICT] Audit failed: warnings promoted to errors under strict mode."
            return MCPToolCallResult.success(text)
    else:
        if fix:
            post_report, fix_results = remediate_vault(
                vault_root, domain=domain, dry_run=dry_run
            )
            post_report.exit_code = post_report.calculate_exit_code(strict=strict)
            text = format_fix_report(fix_results, post_report, dry_run=dry_run)
            if strict and post_report.exit_code != 0:
                text += "\n[STRICT] Audit failed: warnings promoted to errors under strict mode."
            return MCPToolCallResult.success(text)
        else:
            report = audit_vault(vault_root, domain=domain)
            report.exit_code = report.calculate_exit_code(strict=strict)
            text = format_lint_report(report)
            if strict and report.exit_code != 0:
                text += "\n[STRICT] Audit failed: warnings promoted to errors under strict mode."
            return MCPToolCallResult.success(text)

