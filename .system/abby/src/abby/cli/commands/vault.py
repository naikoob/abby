"""Vault health and initialization CLI command handlers."""

from __future__ import annotations

import sys
from pathlib import Path

from abby.constants import (
    DEFAULT_AGENTS_FILE_NAME,
    DEFAULT_STYLE_FILE_NAME,
    DEFAULT_TEMPLATES_SUBDIR,
    REQUIRED_DIRECTORIES,
)
from abby.core.doctor import diagnose_vault
from abby.core.health import inspect_vault
from abby.core.init import init_vault
from abby.utils.io import output_payload



def execute_check(vault_root: Path, json_mode: bool = False) -> int:
    """Execute 'abby check' command and output result according to contracts."""
    report = inspect_vault(vault_root)

    if json_mode:
        output_payload(report, json_mode=True)
    else:
        lines: list[str] = [f"Vault Root: {report.vault_root}"]
        for name, d_status in report.directories.items():
            if d_status.exists and d_status.is_dir:
                lines.append(f"[PASS] {name} ({d_status.item_count} items)")
            elif d_status.exists and not d_status.is_dir:
                lines.append(f"[FAIL] {name} (exists but is not a directory)")
            else:
                lines.append(f"[FAIL] {name} (missing)")

        if report.healthy:
            lines.append("Result: All required directories are present.")
            output_payload("\n".join(lines), json_mode=False)
        else:
            lines.append(
                f"Result: {len(report.missing_directories)} required directory(ies) missing."
            )
            output_payload("\n".join(lines), json_mode=False)
            return 1

    return 0 if report.healthy else 1


def execute_init(vault_root: Path, json_mode: bool = False) -> int:
    """Execute 'abby init' command and output result according to contracts."""
    result = init_vault(vault_root)

    if json_mode:
        output_payload(result, json_mode=True)
    else:
        lines: list[str] = []
        for name in REQUIRED_DIRECTORIES:
            if name in result["created"]:
                lines.append(f"[CREATED] {name}: created")
            else:
                lines.append(f"[OK] {name}: exists")

        # Style guide status
        if DEFAULT_STYLE_FILE_NAME in result["created"]:
            lines.append(
                f"[CREATED] {DEFAULT_STYLE_FILE_NAME}: initialized with sane defaults"
            )
        else:
            lines.append(f"[OK] {DEFAULT_STYLE_FILE_NAME}: exists")

        # Agent guide status
        if DEFAULT_AGENTS_FILE_NAME in result["created"]:
            lines.append(
                f"[CREATED] {DEFAULT_AGENTS_FILE_NAME}: initialized with authoritative guide"
            )
        else:
            lines.append(f"[OK] {DEFAULT_AGENTS_FILE_NAME}: exists")

        # Templates status
        tmpl_created_count = sum(
            1
            for item in result["created"]
            if item.startswith(f"{DEFAULT_TEMPLATES_SUBDIR}/")
        )
        tmpl_existed_count = sum(
            1
            for item in result["existed"]
            if item.startswith(f"{DEFAULT_TEMPLATES_SUBDIR}/")
        )

        if tmpl_created_count > 0:
            lines.append(f"[CREATED] {DEFAULT_TEMPLATES_SUBDIR}: directory created")
            for item in result["created"]:
                if item.startswith(f"{DEFAULT_TEMPLATES_SUBDIR}/"):
                    lines.append(f"[CREATED] {item}: template created")
        else:
            lines.append(
                f"[OK] {DEFAULT_TEMPLATES_SUBDIR}: exists ({tmpl_existed_count} templates present)"
            )

        lines.append("Initialization complete.")
        output_payload("\n".join(lines), json_mode=False)

    return 0


def execute_info(vault_root: Path, json_mode: bool = False) -> int:
    """Execute 'abby info' command and output runtime diagnostics."""
    report = inspect_vault(vault_root)
    sys_info = {
        "cli_version": report.system_status["cli_version"],
        "vault_root": report.vault_root,
        "python_version": report.system_status["python_version"],
        "system_path": report.system_status["system_path"],
        "status": report.system_status["status"],
    }

    if json_mode:
        output_payload(sys_info, json_mode=True)
    else:
        lines = [
            f"Abby CLI Version: {sys_info['cli_version']}",
            f"Vault Root: {sys_info['vault_root']}",
            f"Python Runtime: {sys_info['python_version']} ({sys.executable})",
            f"System Root: {sys_info['system_path']}",
            f"Status: {sys_info['status']}",
        ]
        output_payload("\n".join(lines), json_mode=False)

    return 0


def execute_doctor(vault_root: Path, json_mode: bool = False) -> int:
    """Execute 'abby doctor' command and output diagnostic report."""
    report = diagnose_vault(vault_root)

    if json_mode:
        output_payload(report.to_dict(), json_mode=True)
    else:
        lines: list[str] = [
            "=" * 60,
            " Abby Vault Doctor Diagnostics",
            "=" * 60,
            f"Vault Root: {report.vault_root}",
            "",
        ]
        for c in report.checks:
            lines.append(f"[{c.status}] {c.name}: {c.detail}")

        lines.append("")
        lines.append(f"Result: {report.summary}")
        lines.append("=" * 60)
        output_payload("\n".join(lines), json_mode=False)

    return 0 if report.healthy else 1


