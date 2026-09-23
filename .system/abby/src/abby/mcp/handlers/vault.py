"""MCP handlers for vault health and initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abby.core.health import inspect_vault
from abby.core.init import init_vault
from abby.mcp.types import MCPToolCallResult


def handle_vault_check(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for vault_check tool."""
    report = inspect_vault(vault_root)
    status_str = "Healthy" if report.healthy else "Issues Detected"
    lines = [
        f"Vault Health Audit: {status_str}",
        f"Root: {report.vault_root}",
        "Required Domains:",
    ]
    for d in report.directories.values():
        mark = "✓" if d.exists else "✗"
        lines.append(f"  {mark} {d.name} ({d.item_count} files)")

    if report.missing_directories:
        lines.append("\nMissing Directories:")
        for m in report.missing_directories:
            lines.append(f"  - {m}")

    return MCPToolCallResult.success("\n".join(lines))


def handle_vault_init(args: dict[str, Any], vault_root: Path) -> MCPToolCallResult:
    """Handler for vault_init tool."""
    res = init_vault(vault_root)
    created = res.get("created", [])
    existed = res.get("existed", [])
    lines = [
        "Vault Initialization: Complete",
        f"Vault Root: {vault_root}",
    ]
    if created:
        lines.append("Created Directories:")
        for d in created:
            lines.append(f"  + {d}")
    if existed:
        lines.append(f"Verified {len(existed)} existing required directories.")

    return MCPToolCallResult.success("\n".join(lines))

