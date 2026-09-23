"""Vault root discovery logic using upward traversal and marker detection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from abby.constants import VALID_NOTE_DOMAINS, VAULT_MARKERS
from abby.models.exceptions import VaultError


class VaultNotFoundError(VaultError):
    """Raised when no valid knowledge vault root directory can be found."""

    pass


def find_vault_root(start_path: Optional[Path] = None) -> Path:
    """Discover the root directory of the knowledge vault.

    Resolution order:
    1. ABBY_VAULT_ROOT environment variable (if set).
    2. Upward directory traversal from start_path (or Path.cwd()).

    Raises:
        VaultNotFoundError: If no vault root can be identified or ABBY_VAULT_ROOT is invalid.
    """
    # 1. Environment variable override
    env_override = os.environ.get("ABBY_VAULT_ROOT")
    if env_override is not None:
        override_path = Path(env_override).resolve()
        if override_path.is_dir():
            return override_path
        raise VaultNotFoundError(
            f"ABBY_VAULT_ROOT environment variable is set to '{env_override}', "
            "which is not a valid directory."
        )

    # 2. Upward traversal from current working directory
    current = (start_path or Path.cwd()).resolve()
    while True:
        # Standard initialized vault: .system directory exists
        if (current / ".system").is_dir():
            return current

        # Uninitialized vault before 'abby init': at least two characteristic markers exist
        matches = sum(1 for marker in VAULT_MARKERS if (current / marker).exists())
        if matches >= 2:
            return current

        parent = current.parent
        if parent == current:
            # Reached root filesystem without finding vault
            break
        current = parent

    raise VaultNotFoundError(
        "Could not detect Abby Knowledge Vault root directory. "
        "Please run this command from within the vault workspace."
    )


def scan_vault_files(vault_root: Path) -> dict[str, tuple[float, int]]:
    """Scan knowledge domain directories for markdown notes, returning {rel_path: (mtime, size)}.

    High-speed os.scandir traversal across 00 - Inbox through 04 - Archives.
    """
    result: dict[str, tuple[float, int]] = {}
    for domain in VALID_NOTE_DOMAINS:
        domain_dir = vault_root / domain
        if not domain_dir.is_dir():
            continue
        _scan_dir_recursive(domain_dir, vault_root, result)
    return result


def _scan_dir_recursive(
    current_dir: Path,
    vault_root: Path,
    out: dict[str, tuple[float, int]],
) -> None:
    """Recursively scan directory skipping hidden files and directories."""
    try:
        with os.scandir(current_dir) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    _scan_dir_recursive(Path(entry.path), vault_root, out)
                elif entry.is_file(follow_symlinks=False) and entry.name.endswith(
                    ".md"
                ):
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        rel_path = Path(entry.path).relative_to(vault_root).as_posix()
                        out[rel_path] = (stat.st_mtime, stat.st_size)
                    except OSError:
                        continue
    except (OSError, PermissionError):
        pass

