"""Report formatting and terminal display utilities for OKF linting."""

from __future__ import annotations

from abby.models.lint import LintReport, LintViolation, NoteFixResult

__all__ = [
    "format_fix_report",
    "format_lint_report",
]


def format_lint_report(report: LintReport) -> str:
    """Format a LintReport into clean, human-readable terminal output."""
    if report.total_violations == 0:
        if report.scoped_path:
            return f"✓ Note '{report.scoped_path}' OKF audit clean (0 violations)."
        return f"✓ Vault OKF audit clean ({report.total_audited} notes audited, 0 violations)."

    # Group violations by file path
    grouped: dict[str, list[LintViolation]] = {}
    for v in report.violations:
        grouped.setdefault(v.file_path, []).append(v)

    lines: list[str] = [
        f"Found {report.total_violations} violations across {len(grouped)} notes ({report.total_audited} notes audited):\n"
    ]

    for file_path, file_violations in grouped.items():
        lines.append(f"{file_path}:")
        for v in file_violations:
            line_str = f"L{v.line_number}" if v.line_number is not None else "L-"
            fix_str = " (fixable)" if v.is_fixable else ""
            lines.append(
                f"  {line_str:<4} [{v.severity.upper()}]  {v.rule}: {v.message}{fix_str}"
            )
        lines.append("")

    lines.append("Run 'abby lint --fix' to automatically resolve fixable issues.")
    return "\n".join(lines).strip()


def format_fix_report(
    fix_results: list[NoteFixResult], post_report: LintReport, dry_run: bool = False
) -> str:
    """Format remediation actions for terminal display."""
    if not fix_results:
        if post_report.scoped_path:
            return f"✓ Note '{post_report.scoped_path}' has no fixable violations."
        return f"✓ No fixable violations found ({post_report.total_audited} notes audited)."

    total_actions = sum(len(r.actions) for r in fix_results)
    header_prefix = (
        "DRY-RUN: Planned remediations for"
        if dry_run
        else f"Fixed {total_actions} violations across"
    )
    lines: list[str] = [f"{header_prefix} {len(fix_results)} notes:\n"]

    for r in fix_results:
        lines.append(f"{r.file_path}:")
        for a in r.actions:
            symbol = "~" if dry_run else "✓"
            lines.append(f"  {symbol} {a.description}")
        lines.append("")

    if dry_run:
        lines.append("No changes written to disk (dry-run mode).")
    else:
        if post_report.total_violations == 0:
            lines.append(
                f"✓ Vault OKF audit clean ({post_report.total_audited} notes audited, 0 violations)."
            )
        else:
            lines.append(
                f"Remaining: {post_report.total_violations} unfixable violations ({post_report.total_errors} errors, {post_report.total_warnings} warnings)."
            )

    return "\n".join(lines).strip()
