"""Pure Python YAML string sanitization, escaping, comment stripping, and mapping parsers."""

from __future__ import annotations

from typing import Any, Optional


def unescape_yaml_string(val: str) -> str:
    """Strip optional outer quotes and unescape backslash-escaped characters in YAML scalar strings."""
    cleaned = val.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        quote = cleaned[0]
        inner = cleaned[1:-1]
        if quote == '"':
            # Double-quoted YAML escapes
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        elif quote == "'":
            inner = inner.replace("\\'", "'")
        return inner
    # Even if unquoted, decode any escaped quotes/slashes
    return cleaned.replace('\\"', '"').replace("\\\\", "\\")


# Backward compatibility aliases
_unescape_yaml_string = unescape_yaml_string
_unescape_scalar = unescape_yaml_string


def format_yaml_tag(tag: str) -> str:
    """Format a tag into YAML list item representation, safely escaping special characters."""
    clean = tag.strip()
    if any(c in clean for c in " :#\"'[]{}%@`,"):
        escaped = clean.replace("\\", "\\\\").replace('"', '\\"')
        return f'  - "{escaped}"'
    return f"  - {clean}"


def strip_yaml_comment(val: str) -> str:
    """Remove trailing YAML comment (# ...) outside of quotes."""
    if "#" not in val:
        return val
    in_double = False
    in_single = False
    for i, c in enumerate(val):
        if c == '"' and not in_single:
            num_slashes = len(val[:i]) - len(val[:i].rstrip("\\"))
            if num_slashes % 2 == 0:
                in_double = not in_double
        elif c == "'" and not in_double:
            num_slashes = len(val[:i]) - len(val[:i].rstrip("\\"))
            if num_slashes % 2 == 0:
                in_single = not in_single
        elif c == "#" and not in_double and not in_single:
            return val[:i].strip()
    return val


# Backward compatibility aliases
_strip_yaml_comment = strip_yaml_comment
_strip_comment = strip_yaml_comment


def parse_yaml_inline_mapping(text: str) -> dict[str, str]:
    """Parse inline YAML mapping like '{ by: "human:alice", at: "2026-06-25" }'."""
    raw = text.strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1].strip()
    if not raw:
        return {}
    result: dict[str, str] = {}
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    quote_char = ""
    for c in raw:
        if c in ('"', "'"):
            if not in_quote:
                in_quote = True
                quote_char = c
            elif quote_char == c:
                in_quote = False
                quote_char = ""
            current.append(c)
        elif c == "," and not in_quote:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(c)
    if current:
        parts.append("".join(current).strip())
    for part in parts:
        if ":" in part:
            k, _, v = part.partition(":")
            clean_k = k.strip()
            clean_v = unescape_yaml_string(strip_yaml_comment(v.strip()))
            result[clean_k] = clean_v
    return result


def parse_yaml_inline_list_of_mappings(text: str) -> list[dict[str, Any]]:
    """Parse inline YAML list of mappings like '[ { by: "human:alice", at: "..." } ]'."""
    raw = text.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1].strip()
    if not raw:
        return []
    items: list[dict[str, Any]] = []

    start_idx = -1
    in_quote = False
    quote_char = ""
    bracket_depth = 0

    for i, c in enumerate(raw):
        if c in ('"', "'"):
            if not in_quote:
                in_quote = True
                quote_char = c
            elif quote_char == c and (i == 0 or raw[i - 1] != "\\"):
                in_quote = False
                quote_char = ""
        elif not in_quote:
            if c == "{":
                if bracket_depth == 0:
                    start_idx = i
                bracket_depth += 1
            elif c == "}":
                bracket_depth -= 1
                if bracket_depth == 0 and start_idx != -1:
                    chunk = raw[start_idx : i + 1]
                    mapping = parse_yaml_inline_mapping(chunk)
                    if mapping:
                        items.append(mapping)
                    start_idx = -1

    return items


def parse_yaml_block_mapping(lines: list[str]) -> dict[str, str]:
    """Parse indented lines into a dict of key-value pairs."""
    mapping: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            k, _, v = stripped.partition(":")
            clean_k = k.strip()
            clean_v = unescape_yaml_string(strip_yaml_comment(v.strip()))
            mapping[clean_k] = clean_v
    return mapping


def parse_yaml_list_of_mappings(lines: list[str]) -> list[dict[str, Any]]:
    """Parse indented YAML lines representing a list of mappings (- k: v)."""
    items: list[dict[str, Any]] = []
    current_item: Optional[dict[str, Any]] = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            if current_item is not None:
                items.append(current_item)
            current_item = {}
            rest = stripped[1:].strip()
            if rest and ":" in rest and not rest.startswith("{"):
                k, _, v = rest.partition(":")
                clean_k = k.strip()
                clean_v = unescape_yaml_string(strip_yaml_comment(v.strip()))
                val: Any = int(clean_v) if clean_v.isdigit() else clean_v
                current_item[clean_k] = val
            elif rest.startswith("{") and rest.endswith("}"):
                current_item.update(parse_yaml_inline_mapping(rest))
        elif ":" in stripped and current_item is not None:
            k, _, v = stripped.partition(":")
            clean_k = k.strip()
            clean_v = unescape_yaml_string(strip_yaml_comment(v.strip()))
            val = int(clean_v) if clean_v.isdigit() else clean_v
            current_item[clean_k] = val
    if current_item is not None:
        items.append(current_item)
    return items


__all__ = [
    "_strip_comment",
    "_strip_yaml_comment",
    "_unescape_scalar",
    "_unescape_yaml_string",
    "format_yaml_tag",
    "parse_yaml_block_mapping",
    "parse_yaml_inline_list_of_mappings",
    "parse_yaml_inline_mapping",
    "parse_yaml_list_of_mappings",
    "strip_yaml_comment",
    "unescape_yaml_string",
]
