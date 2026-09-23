"""Core note verification service and frontmatter attestation engine.

Adheres to OKF v0.2 Trust Model specifications (FR-005, FR-006).
"""

from __future__ import annotations

import getpass
import os
import re
from pathlib import Path
from typing import Any, Optional

from abby.core.lifecycle import resolve_source_note
from abby.services.okf_parser import tokenize_frontmatter
from abby.models.trust import VerifyResult, resolve_trust_tier
from abby.services.lint.rules import validate_actor_syntax
from abby.services.okf_serializer import mutate_frontmatter_block
from abby.utils.io import atomic_write_text
from abby.utils.time import now_utc_iso


def derive_default_actor() -> str:
    """Derive default human actor identifier from environment or current system login."""
    user = os.environ.get("ABBY_USER")
    if not user or not user.strip():
        try:
            user = getpass.getuser()
        except Exception:
            user = os.environ.get("USER") or os.environ.get("USERNAME") or "user"
    clean_user = re.sub(r"[^a-zA-Z0-9._-]+", "-", user.strip()).strip("-").lower()
    return f"human:{clean_user or 'user'}"


def mutate_frontmatter_verification(
    raw_content: str, actor: str, timestamp: str
) -> tuple[str, str, str]:
    """Append or update verification metadata in note frontmatter non-destructively.

    Returns:
        (updated_content, old_trust_tier, new_trust_tier)
    """
    is_crlf = "\r\n" in raw_content
    normalized = raw_content.replace("\r\n", "\n").replace("\r", "\n")

    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
    match = pattern.match(normalized)
    if not match:
        raise ValueError("Note does not contain valid YAML frontmatter")

    fm_text = match.group(1)
    body = match.group(2)

    parsed = tokenize_frontmatter(normalized)
    if not parsed.has_frontmatter:
        raise ValueError("Note does not contain valid YAML frontmatter")

    old_trust_tier = resolve_trust_tier(parsed.verified)

    # Build updated verified list
    new_verified = [dict(v) for v in parsed.verified]
    found = False
    for v in new_verified:
        if v.get("by") == actor:
            v["at"] = timestamp
            found = True
            break
    if not found:
        new_verified.append({"by": actor, "at": timestamp})

    new_trust_tier = resolve_trust_tier(new_verified)

    # Format new verified YAML block
    v_lines = ["verified:"]
    for v in new_verified:
        v_by = v.get("by", "")
        v_at = v.get("at")
        if v_at:
            v_lines.append(f"  - by: {v_by}\n    at: \"{v_at}\"")
        else:
            v_lines.append(f"  - by: {v_by}")

    updated_content = mutate_frontmatter_block(raw_content, "verified", v_lines)
    return updated_content, old_trust_tier, new_trust_tier


def verify_note(
    vault_root: Path,
    note_arg: str,
    actor: Optional[str] = None,
    dry_run: bool = False,
) -> VerifyResult:
    """Verify a note by recording a verification event in its frontmatter."""
    resolved_actor = actor.strip() if actor else derive_default_actor()
    if not validate_actor_syntax(resolved_actor):
        raise ValueError(
            f"Invalid actor identifier '{resolved_actor}'. Must conform to OKF v0.2 actor syntax."
        )

    note_path = resolve_source_note(vault_root, note_arg)
    content = note_path.read_text(encoding="utf-8")
    now_iso = now_utc_iso()

    updated_content, old_tier, new_tier = mutate_frontmatter_verification(
        content, resolved_actor, now_iso
    )

    resolved_vault = vault_root.resolve()
    rel_path = str(note_path.resolve().relative_to(resolved_vault))

    if not dry_run:
        atomic_write_text(note_path, updated_content, encoding="utf-8")

    return VerifyResult(
        path=rel_path,
        actor=resolved_actor,
        timestamp=now_iso,
        trust_tier=new_tier,
        old_trust_tier=old_tier,
        dry_run=dry_run,
        success=True,
    )


__all__ = [
    "derive_default_actor",
    "mutate_frontmatter_verification",
    "validate_actor_syntax",
    "verify_note",
]

