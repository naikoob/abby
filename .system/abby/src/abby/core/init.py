"""Idempotent directory initialization for Abby Knowledge Vault."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abby.constants import (
    DEFAULT_AGENTS_FILE_NAME,
    DEFAULT_STYLE_FILE_NAME,
    DEFAULT_TEMPLATES_SUBDIR,
    REQUIRED_DIRECTORIES,
)
from abby.utils.templates import (
    get_canonical_templates,
    get_default_agents_content,
    get_default_style_content,
)


def scaffold_style_file(vault_root: Path) -> tuple[bool, str]:
    """Idempotently scaffold STYLE.md at the vault root if missing.

    Returns:
        (created, relative_path)
    """
    style_path = vault_root / DEFAULT_STYLE_FILE_NAME
    if style_path.exists():
        return False, DEFAULT_STYLE_FILE_NAME

    style_path.write_text(get_default_style_content(), encoding="utf-8")
    return True, DEFAULT_STYLE_FILE_NAME


def scaffold_agents_file(vault_root: Path) -> tuple[bool, str]:
    """Idempotently scaffold AGENTS.md at the vault root if missing.

    Returns:
        (created, relative_path)
    """
    agents_path = vault_root / DEFAULT_AGENTS_FILE_NAME
    if agents_path.exists():
        return False, DEFAULT_AGENTS_FILE_NAME

    agents_path.write_text(get_default_agents_content(), encoding="utf-8")
    return True, DEFAULT_AGENTS_FILE_NAME


def scaffold_templates_directory(vault_root: Path) -> tuple[list[str], list[str]]:
    """Idempotently scaffold 05 - Assets/Templates and canonical templates if missing.

    Returns:
        (created_templates, existed_templates)
    """
    templates_dir = vault_root / DEFAULT_TEMPLATES_SUBDIR
    templates_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    existed: list[str] = []
    canonical = get_canonical_templates()

    for filename, content in canonical.items():
        template_file = templates_dir / filename
        rel_path = f"{DEFAULT_TEMPLATES_SUBDIR}/{filename}"
        if template_file.exists():
            existed.append(rel_path)
        else:
            template_file.write_text(content, encoding="utf-8")
            created.append(rel_path)

    return created, existed


def init_vault(vault_root: Path) -> dict[str, Any]:
    """Idempotently scaffold missing required directories, STYLE.md, AGENTS.md, and templates.

    Returns a dictionary matching the VaultInitResult schema:
    {
        "success": bool,
        "vault_root": str,
        "created": list[str],
        "existed": list[str],
        "style_initialized": bool,
        "agents_initialized": bool,
        "templates_initialized": int
    }
    """
    created: list[str] = []
    existed: list[str] = []

    for name in REQUIRED_DIRECTORIES:
        target_dir = vault_root / name
        if target_dir.is_dir():
            existed.append(name)
        elif target_dir.exists() and not target_dir.is_dir():
            raise FileExistsError(
                f"Path '{name}' already exists as a non-directory file."
            )
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            created.append(name)

    # Idempotently scaffold STYLE.md at vault root
    style_created, style_name = scaffold_style_file(vault_root)
    if style_created:
        created.append(style_name)
    else:
        existed.append(style_name)

    # Idempotently scaffold AGENTS.md at vault root
    agents_created, agents_name = scaffold_agents_file(vault_root)
    if agents_created:
        created.append(agents_name)
    else:
        existed.append(agents_name)

    # Idempotently scaffold 05 - Assets/Templates and canonical templates
    tmpl_created, tmpl_existed = scaffold_templates_directory(vault_root)
    created.extend(tmpl_created)
    existed.extend(tmpl_existed)

    return {
        "success": True,
        "vault_root": str(vault_root),
        "created": created,
        "existed": existed,
        "style_initialized": True,
        "agents_initialized": True,
        "templates_initialized": len(tmpl_created) + len(tmpl_existed),
    }


__all__ = [
    "init_vault",
    "scaffold_agents_file",
    "scaffold_directories",
    "scaffold_style_file",
    "scaffold_templates",
]
