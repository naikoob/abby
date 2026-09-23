"""Vault health inspection and environment diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from abby import __version__
from abby.constants import REQUIRED_DIRECTORIES, SYSTEM_SUBPATH
from abby.models.okf import DirectoryStatus, VaultHealthReport


def inspect_vault(vault_root: Path) -> VaultHealthReport:
    """Perform a read-only audit of the vault directory structure."""
    dir_statuses: dict[str, DirectoryStatus] = {}
    missing: list[str] = []

    for name in REQUIRED_DIRECTORIES:
        target_path = vault_root / name
        exists = target_path.exists()
        is_dir = target_path.is_dir() if exists else False
        item_count = 0
        if is_dir:
            try:
                # Count non-hidden items
                item_count = sum(
                    1 for item in target_path.iterdir() if not item.name.startswith(".")
                )
            except (PermissionError, OSError):
                item_count = -1

        status = DirectoryStatus(
            name=name,
            expected_relative_path=name,
            exists=exists,
            is_dir=is_dir,
            item_count=item_count,
        )
        dir_statuses[name] = status
        if not (exists and is_dir):
            missing.append(name)

    healthy = len(missing) == 0

    # System status details
    system_root = vault_root / SYSTEM_SUBPATH
    system_status = {
        "cli_version": __version__,
        "python_version": sys.version.split()[0],
        "system_path": str(system_root),
        "status": "Operational" if system_root.exists() else "Missing System Root",
    }

    return VaultHealthReport(
        vault_root=str(vault_root),
        healthy=healthy,
        directories=dir_statuses,
        missing_directories=missing,
        system_status=system_status,
    )


__all__ = [
    "inspect_vault",
]
