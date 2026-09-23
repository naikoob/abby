"""Holistic vault diagnostics and health doctor for Abby Knowledge Vault."""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from abby.constants import (
    DEFAULT_AGENTS_FILE_NAME,
    DEFAULT_STYLE_FILE_NAME,
    DEFAULT_TEMPLATES_SUBDIR,
    REQUIRED_DIRECTORIES,
)
from abby.core.cache import CACHE_SCHEMA_VERSION, get_cache_db_path


@dataclass
class DoctorCheck:
    """Individual diagnostic check result."""

    name: str
    passed: bool
    status: str  # "PASS", "FAIL", "WARN"
    detail: str


@dataclass
class DoctorReport:
    """Consolidated doctor diagnostic report."""

    vault_root: str
    healthy: bool
    checks: list[DoctorCheck]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return {
            "vault_root": self.vault_root,
            "healthy": self.healthy,
            "summary": self.summary,
            "checks": [asdict(c) for c in self.checks],
        }


def _check_python_version() -> DoctorCheck:
    """Verify Python runtime version >= 3.10."""
    ver = sys.version_info
    passed = ver >= (3, 10)
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"
    return DoctorCheck(
        name="Python Runtime",
        passed=passed,
        status="PASS" if passed else "FAIL",
        detail=f"Python {ver_str} ({sys.executable})",
    )


def _check_vault_directories(vault_root: Path) -> DoctorCheck:
    """Verify required PARA+ directories exist and are directories."""
    missing: list[str] = []
    for d in REQUIRED_DIRECTORIES:
        p = vault_root / d
        if not p.exists() or not p.is_dir():
            missing.append(d)

    passed = len(missing) == 0
    detail = (
        f"All {len(REQUIRED_DIRECTORIES)} required directories present"
        if passed
        else f"Missing {len(missing)} directories: {', '.join(missing)}"
    )
    return DoctorCheck(
        name="PARA+ Directory Taxonomy",
        passed=passed,
        status="PASS" if passed else "FAIL",
        detail=detail,
    )


def _check_cache_integrity(vault_root: Path) -> DoctorCheck:
    """Verify SQLite cache integrity and schema version."""
    db_path = get_cache_db_path(vault_root)
    if not db_path.exists():
        return DoctorCheck(
            name="SQLite Cache Integrity",
            passed=True,
            status="PASS",
            detail=f"Cache database not created yet ({db_path.name})",
        )

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            integrity = row[0] if row else "unknown"
            if integrity.lower() != "ok":
                return DoctorCheck(
                    name="SQLite Cache Integrity",
                    passed=False,
                    status="FAIL",
                    detail=f"Corruption detected: {integrity}",
                )

            ver_row = conn.execute("PRAGMA user_version;").fetchone()
            ver = ver_row[0] if ver_row else 0
            detail = f"Integrity OK (schema version {ver}, expected {CACHE_SCHEMA_VERSION})"
            return DoctorCheck(
                name="SQLite Cache Integrity",
                passed=True,
                status="PASS",
                detail=detail,
            )
        finally:
            conn.close()
    except Exception as exc:
        return DoctorCheck(
            name="SQLite Cache Integrity",
            passed=False,
            status="FAIL",
            detail=f"Failed to inspect cache: {exc}",
        )


def _check_mcp_launcher(vault_root: Path) -> DoctorCheck:
    """Verify abby-mcp executable launcher is present and executable."""
    mcp_bin = vault_root / ".system" / "abby" / "bin" / "abby-mcp"
    if not mcp_bin.exists():
        fallback_bin = Path(__file__).resolve().parent.parent.parent.parent / "bin" / "abby-mcp"
        if fallback_bin.exists():
            mcp_bin = fallback_bin

    if not mcp_bin.exists():
        return DoctorCheck(
            name="MCP Server Launcher",
            passed=False,
            status="FAIL",
            detail=f"Binary missing at {mcp_bin}",
        )
    is_exec = os.access(mcp_bin, os.X_OK)
    return DoctorCheck(
        name="MCP Server Launcher",
        passed=is_exec,
        status="PASS" if is_exec else "FAIL",
        detail="Executable launcher verified" if is_exec else "File exists but lacks execute permissions",
    )


def _check_authoritative_guides(vault_root: Path) -> DoctorCheck:
    """Verify AGENTS.md and STYLE.md guides exist at vault root."""
    missing = []
    for f in (DEFAULT_AGENTS_FILE_NAME, DEFAULT_STYLE_FILE_NAME):
        if not (vault_root / f).exists():
            missing.append(f)

    passed = len(missing) == 0
    detail = (
        "Authoritative AGENTS.md and STYLE.md present"
        if passed
        else f"Missing guides: {', '.join(missing)}"
    )
    return DoctorCheck(
        name="Vault Guides",
        passed=True,
        status="PASS" if passed else "WARN",
        detail=detail,
    )


def _check_starter_templates(vault_root: Path) -> DoctorCheck:
    """Verify starter templates exist in 05 - Assets/Templates."""
    tmpl_dir = vault_root / DEFAULT_TEMPLATES_SUBDIR
    if not tmpl_dir.exists() or not tmpl_dir.is_dir():
        return DoctorCheck(
            name="Starter Templates",
            passed=True,
            status="WARN",
            detail=f"Templates directory missing ({DEFAULT_TEMPLATES_SUBDIR})",
        )
    count = sum(1 for p in tmpl_dir.glob("*.md"))
    passed = count > 0
    return DoctorCheck(
        name="Starter Templates",
        passed=True,
        status="PASS" if passed else "WARN",
        detail=f"{count} markdown templates detected" if passed else "No markdown templates found",
    )


def diagnose_vault(vault_root: Path) -> DoctorReport:
    """Execute all diagnostic checks against the target vault."""
    checks = [
        _check_python_version(),
        _check_vault_directories(vault_root),
        _check_cache_integrity(vault_root),
        _check_mcp_launcher(vault_root),
        _check_authoritative_guides(vault_root),
        _check_starter_templates(vault_root),
    ]

    healthy = not any(c.status == "FAIL" for c in checks)
    passed_count = sum(1 for c in checks if c.status == "PASS")
    failed_count = sum(1 for c in checks if c.status == "FAIL")
    warn_count = sum(1 for c in checks if c.status == "WARN")

    summary = (
        f"All {len(checks)} checks passed. Vault is fully operational."
        if healthy and failed_count == 0 and warn_count == 0
        else f"{passed_count} passed, {failed_count} failed, {warn_count} warning(s)."
    )

    return DoctorReport(
        vault_root=str(vault_root),
        healthy=healthy,
        checks=checks,
        summary=summary,
    )

