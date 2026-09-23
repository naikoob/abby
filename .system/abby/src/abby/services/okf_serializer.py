"""Dedicated serialization and in-place mutation engine for Open Knowledge Format (OKF) frontmatter."""

from __future__ import annotations

import re
from typing import Any

from abby.utils.time import now_iso
from abby.utils.yaml import format_yaml_tag, unescape_yaml_string


def _sanitize_yaml_value(val: str) -> str:
    """Sanitize string for YAML double-quoted value."""
    return (
        val.replace("\r", "")
        .replace("\n", " ")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def _format_generated_block(generated: dict[str, str]) -> list[str]:
    lines = ["generated:"]
    gen_by = generated.get("by", "")
    lines.append(f"  by: {gen_by}")
    gen_at = generated.get("at")
    if gen_at:
        lines.append(f'  at: "{gen_at}"')
    return lines


def _format_verified_block(verified: list[dict[str, str]]) -> list[str]:
    lines = ["verified:"]
    for v in verified:
        v_by = v.get("by", "")
        v_at = v.get("at")
        if v_at:
            lines.append(f'  - by: {v_by}\n    at: "{v_at}"')
        else:
            lines.append(f"  - by: {v_by}")
    return lines


def _format_sources_block(sources: list[dict[str, Any]]) -> list[str]:
    lines = ["sources:"]
    for s in sources:
        res = s.get("resource", "")
        lines.append(f'  - resource: "{res}"')
        if "id" in s and s["id"]:
            lines.append(f"    id: {s['id']}")
        if "title" in s and s["title"]:
            lines.append(f'    title: "{s["title"]}"')
        if "author" in s and s["author"]:
            lines.append(f'    author: "{s["author"]}"')
        if "usage_count" in s and s["usage_count"] is not None:
            lines.append(f"    usage_count: {s['usage_count']}")
        if "last_modified" in s and s["last_modified"]:
            lines.append(f'    last_modified: "{s["last_modified"]}"')
    return lines


def serialize_okf_frontmatter(metadata: Any) -> str:
    """Serialize frontmatter into standard YAML block fenced by triple dashes.

    Accepts an OKFFrontmatter instance or object with equivalent attributes.
    """
    raw_title = getattr(metadata, "title", "Untitled Note")
    lines = ["---", f'title: "{_sanitize_yaml_value(raw_title)}"']

    description = getattr(metadata, "description", None)
    if description:
        lines.append(f'description: "{_sanitize_yaml_value(description)}"')

    created = getattr(metadata, "created", "")
    lines.append(f'created: "{created}"')

    updated = getattr(metadata, "updated", None)
    if updated:
        lines.append(f'updated: "{_sanitize_yaml_value(updated)}"')

    note_type = getattr(metadata, "type", "inbox")
    lines.append(f"type: {note_type}")

    status = getattr(metadata, "status", "unprocessed")
    lines.append(f"status: {status}")

    tags = getattr(metadata, "tags", [])
    if tags:
        lines.append("tags:")
        for tag in tags:
            lines.append(format_yaml_tag(tag))
    else:
        lines.append("tags: []")

    stale_after = getattr(metadata, "stale_after", None)
    if stale_after:
        lines.append(f'stale_after: "{_sanitize_yaml_value(stale_after)}"')

    generated = getattr(metadata, "generated", None)
    if generated:
        lines.extend(_format_generated_block(generated))

    verified = getattr(metadata, "verified", [])
    if verified:
        lines.extend(_format_verified_block(verified))

    sources = getattr(metadata, "sources", [])
    if sources:
        lines.extend(_format_sources_block(sources))

    lines.append("---")
    return "\n".join(lines) + "\n"


def mutate_okf_frontmatter(
    raw_content: str, updates: dict[str, str]
) -> tuple[str, str]:
    """Update or inject frontmatter values while preserving body text and block references.

    Preserves original line endings (CRLF or LF) and prevents backslash group reference issues.
    """
    is_crlf = "\r\n" in raw_content
    normalized_content = raw_content.replace("\r\n", "\n").replace("\r", "\n")

    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
    match = pattern.match(normalized_content)

    if match:
        fm_text = match.group(1)
        body = match.group(2)

        status_match = re.search(r"^status:\s*(.*?)\s*$", fm_text, re.MULTILINE)
        prev_status = (
            unescape_yaml_string(status_match.group(1))
            if status_match
            else "unprocessed"
        )

        for key, val in updates.items():
            key_pattern = re.compile(r"^" + re.escape(key) + r":\s*.*$", re.MULTILINE)
            if key_pattern.search(fm_text):
                fm_text = key_pattern.sub(lambda _: f"{key}: {val}", fm_text)
            else:
                fm_text = fm_text.rstrip("\n") + f"\n{key}: {val}"

        updated_content = f"---\n{fm_text.strip()}\n---\n"
        if body:
            updated_content += body
        if is_crlf:
            updated_content = updated_content.replace("\n", "\r\n")
        return updated_content, prev_status
    else:
        prev_status = "unprocessed"
        now = now_iso()
        status = updates.get("status", "active")
        type_ = updates.get("type", "note")
        title = updates.get("title", "Untitled Note")
        header = f'---\ntitle: "{title}"\ncreated: "{now}"\ntype: {type_}\nstatus: {status}\ntags: []\n---\n'
        result = header + normalized_content
        if is_crlf:
            result = result.replace("\n", "\r\n")
        return result, prev_status


def mutate_frontmatter_block(
    raw_content: str, key: str, block_lines: list[str]
) -> str:
    """Update or append a multi-line YAML block under a root-level key in frontmatter.

    Preserves existing body content and original CRLF / LF line endings.
    """
    is_crlf = "\r\n" in raw_content
    normalized_content = raw_content.replace("\r\n", "\n").replace("\r", "\n")

    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
    match = pattern.match(normalized_content)

    if not match:
        raise ValueError("Note does not contain valid YAML frontmatter")

    fm_text = match.group(1)
    body = match.group(2)

    fm_lines = fm_text.splitlines()
    key_pattern = re.compile(r"^" + re.escape(key) + r":\s*(.*)$")
    block_start = -1
    block_end = -1

    for i, line in enumerate(fm_lines):
        if key_pattern.match(line):
            block_start = i
            block_end = i + 1
            for j in range(i + 1, len(fm_lines)):
                next_line = fm_lines[j]
                if not next_line.strip():
                    continue
                # Next root-level key ends this block
                if re.match(r"^[a-zA-Z0-9_-]+:", next_line):
                    block_end = j
                    break
                block_end = j + 1
            break

    if block_start >= 0:
        new_fm_lines = (
            fm_lines[:block_start]
            + block_lines
            + fm_lines[block_end:]
        )
    else:
        new_fm_lines = fm_lines + block_lines

    new_fm_text = "\n".join(new_fm_lines).strip()
    updated_content = f"---\n{new_fm_text}\n---\n"
    if body:
        updated_content += body
    if is_crlf:
        updated_content = updated_content.replace("\n", "\r\n")
    return updated_content

