"""Dedicated parsing engine for Open Knowledge Format (OKF) frontmatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from abby.models.okf import OKFFrontmatter, ParsedFrontmatter
from abby.models.trust import (
    TrustTier,
    evaluate_staleness,
    resolve_trust_tier,
)
from abby.utils.yaml import (
    parse_yaml_block_mapping,
    parse_yaml_inline_list_of_mappings,
    parse_yaml_inline_mapping,
    parse_yaml_list_of_mappings,
    strip_yaml_comment,
    unescape_yaml_string,
)


def _extract_frontmatter_envelope(
    text: str,
) -> tuple[bool, bool, str, str, int, list[str]]:
    """Extract frontmatter delimiters, raw frontmatter text, and body slice.

    Returns:
        (has_frontmatter, is_closed, raw_frontmatter, body_content, closing_line_number, fm_lines)
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---"):
        return False, False, "", normalized, -1, []

    lines = normalized.split("\n")
    closing_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            closing_idx = i
            break

    if closing_idx == -1:
        return True, False, "\n".join(lines[1:]), "", -1, lines[1:]

    return (
        True,
        True,
        "\n".join(lines[1:closing_idx]),
        "\n".join(lines[closing_idx + 1 :]),
        closing_idx + 1,
        lines[1:closing_idx],
    )


def _commit_block_lines(
    in_block_key: str, block_lines: list[str]
) -> tuple[Optional[dict[str, str]], Optional[list[dict[str, str]]], Optional[list[dict[str, Any]]], bool]:
    """Parse block lines into generated mapping, verified list, or sources list."""
    generated = None
    verified = None
    sources = None
    sources_is_malformed = False

    if in_block_key == "generated":
        generated = parse_yaml_block_mapping(block_lines)
    elif in_block_key == "verified":
        has_dash = any(l.strip().startswith("-") for l in block_lines if l.strip())
        if has_dash:
            verified = parse_yaml_list_of_mappings(block_lines)
        else:
            bare = parse_yaml_block_mapping(block_lines)
            if bare:
                verified = [bare]
    elif in_block_key == "sources":
        non_empty = [l for l in block_lines if l.strip() and not l.strip().startswith("#")]
        has_dash = any(l.strip().startswith("-") for l in non_empty)
        if non_empty and not has_dash:
            sources_is_malformed = True
        else:
            sources = parse_yaml_list_of_mappings(block_lines)

    return generated, verified, sources, sources_is_malformed


def _parse_inline_provenance(
    clean_key: str, val_no_comment: str
) -> tuple[Optional[dict[str, str]], Optional[list[dict[str, str]]], Optional[list[dict[str, Any]]], bool, bool]:
    """Parse inline YAML mapping or list syntax for generated, verified, or sources.

    Returns:
        (generated, verified, sources, sources_is_malformed, is_block)
    """
    if val_no_comment.startswith("{") and val_no_comment.endswith("}"):
        mapping = parse_yaml_inline_mapping(val_no_comment)
        if clean_key == "generated":
            return mapping, None, None, False, False
        elif clean_key == "verified":
            return None, [mapping] if mapping else [], None, False, False
        elif clean_key == "sources":
            return None, None, None, True, False

    if val_no_comment.startswith("[") and val_no_comment.endswith("]"):
        items = parse_yaml_inline_list_of_mappings(val_no_comment)
        if clean_key == "verified":
            return None, items, None, False, False
        elif clean_key == "sources":
            return None, None, items, False, False

    malformed = clean_key == "sources" and bool(val_no_comment)
    return None, None, None, malformed, True


def _parse_tags_line(
    after: str, line_num: int
) -> tuple[list[tuple[str, int]], bool, bool]:
    """Parse tags definition line returning (tags, is_scalar, in_tags)."""
    tags: list[tuple[str, int]] = []
    if after.startswith("[") and after.endswith("]"):
        inner = after[1:-1].strip()
        if inner:
            for t in inner.split(","):
                cleaned_t = t.strip()
                if cleaned_t:
                    tags.append((unescape_yaml_string(cleaned_t), line_num))
        return tags, False, False
    elif after:
        for t in after.split(","):
            cleaned_t = t.strip()
            if cleaned_t:
                tags.append((unescape_yaml_string(cleaned_t), line_num))
        return tags, True, False
    return tags, False, True


@dataclass
class _ParserState:
    fields: dict[str, tuple[str, int]] = field(default_factory=dict)
    tags: list[tuple[str, int]] = field(default_factory=list)
    tags_line: int = -1
    tags_is_scalar: bool = False
    in_tags: bool = False
    in_multiline: Optional[str] = None
    multiline_buf: list[str] = field(default_factory=list)
    multiline_start_line: int = -1
    generated: Optional[dict[str, str]] = None
    verified: list[dict[str, str]] = field(default_factory=list)
    stale_after: Optional[str] = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    sources_is_malformed: bool = False
    in_block_key: Optional[str] = None
    block_lines: list[str] = field(default_factory=list)


def _commit_block(state: _ParserState) -> None:
    if not state.in_block_key:
        return
    g, v, s, mal = _commit_block_lines(state.in_block_key, state.block_lines)
    if g is not None:
        state.generated = g
    if v is not None:
        state.verified = v
    if s is not None:
        state.sources = s
    if mal:
        state.sources_is_malformed = True
    state.in_block_key = None
    state.block_lines = []


def _handle_in_tags(state: _ParserState, stripped: str, line_num: int) -> bool:
    if stripped.startswith("-"):
        tag_raw = strip_yaml_comment(stripped[1:].strip())
        state.tags.append((unescape_yaml_string(tag_raw), line_num))
        return True
    if ":" in stripped or (stripped and not stripped.startswith("-")):
        state.in_tags = False
        return False
    return not stripped


def _handle_in_multiline(state: _ParserState, line: str, stripped: str) -> bool:
    if (line.startswith(" ") or line.startswith("\t")) and not (
        ":" in stripped and not stripped.startswith("-")
    ):
        state.multiline_buf.append(stripped)
        return True
    if state.in_multiline:
        state.fields[state.in_multiline] = (" ".join(state.multiline_buf), state.multiline_start_line)
        state.in_multiline = None
        state.multiline_buf = []
    return False


def _handle_in_block(state: _ParserState, line: str, stripped: str) -> bool:
    if line.startswith(" ") or line.startswith("\t") or not stripped:
        state.block_lines.append(line)
        return True
    _commit_block(state)
    return False


def _parse_kv_entry(state: _ParserState, stripped: str, line_num: int) -> None:
    _commit_block(state)
    key, _, val = stripped.partition(":")
    clean_key = key.strip().lower()
    val_clean = val.strip()
    val_no_comment = strip_yaml_comment(val_clean)

    if clean_key == "stale_after":
        state.stale_after = unescape_yaml_string(val_no_comment)
        state.fields[clean_key] = (val_no_comment, line_num)
        return

    if clean_key in ("generated", "verified", "sources"):
        state.fields[clean_key] = (val_no_comment or "block", line_num)
        g, v, s, mal, is_block = _parse_inline_provenance(clean_key, val_no_comment)
        if g is not None:
            state.generated = g
        if v is not None:
            state.verified = v
        if s is not None:
            state.sources = s
        if mal:
            state.sources_is_malformed = True
        if is_block:
            state.in_block_key = clean_key
            state.block_lines = []
        return

    if val_no_comment in (">", "|", ">-", "|-", ">+", "|+"):
        state.in_multiline = clean_key
        state.multiline_buf = []
        state.multiline_start_line = line_num
    else:
        state.fields[clean_key] = (val_no_comment, line_num)


def tokenize_frontmatter(text: str) -> ParsedFrontmatter:
    """Parse frontmatter delimiters, key-value mappings, and tags non-destructively.

    Args:
        text: Full raw text of a Markdown note.

    Returns:
        ParsedFrontmatter object with extracted fields, 1-indexed line numbers,
        and unparsed body content.
    """
    (
        has_frontmatter,
        is_closed,
        raw_frontmatter,
        body_content,
        closing_line_number,
        fm_lines,
    ) = _extract_frontmatter_envelope(text)

    if not has_frontmatter:
        return ParsedFrontmatter(
            has_frontmatter=False,
            is_closed=False,
            raw_frontmatter="",
            body_content=body_content,
            fields={},
            tags=[],
            tags_line=-1,
            tags_is_scalar=False,
            closing_line_number=-1,
            generated=None,
            verified=[],
            stale_after=None,
            sources=[],
        )

    state = _ParserState()

    for idx, line in enumerate(fm_lines):
        line_num = idx + 2  # 1-indexed; line 1 was opening '---'
        stripped = line.strip()

        if stripped.startswith("#"):
            continue

        if state.in_tags and _handle_in_tags(state, stripped, line_num):
            continue

        if state.in_multiline and _handle_in_multiline(state, line, stripped):
            continue

        if state.in_block_key and _handle_in_block(state, line, stripped):
            continue

        if stripped.startswith("tags:"):
            _commit_block(state)
            state.tags_line = line_num
            after = strip_yaml_comment(stripped[5:].strip())
            new_tags, tags_is_scalar, in_tags = _parse_tags_line(after, line_num)
            state.tags.extend(new_tags)
            state.tags_is_scalar = tags_is_scalar
            state.in_tags = in_tags
            state.fields["tags"] = (after, line_num)
            continue

        if ":" in stripped:
            _parse_kv_entry(state, stripped, line_num)

    if state.in_multiline:
        state.fields[state.in_multiline] = (" ".join(state.multiline_buf), state.multiline_start_line)
    if state.in_block_key:
        _commit_block(state)

    return ParsedFrontmatter(
        has_frontmatter=has_frontmatter,
        is_closed=is_closed,
        raw_frontmatter=raw_frontmatter,
        body_content=body_content,
        fields=state.fields,
        tags=state.tags,
        tags_line=state.tags_line,
        tags_is_scalar=state.tags_is_scalar,
        closing_line_number=closing_line_number,
        generated=state.generated,
        verified=state.verified,
        stale_after=state.stale_after,
        sources=state.sources,
        sources_is_malformed=state.sources_is_malformed,
    )


def parse_okf_frontmatter(content: str, default_title: str = "Untitled Note") -> dict[str, Any]:
    """Extract OKF metadata dictionary from markdown content using tokenize_frontmatter.

    Handles Windows CRLF endings, escaped quotes/backslashes, and varied tag syntax.
    """
    parsed = tokenize_frontmatter(content)
    if not parsed.has_frontmatter:
        return {
            "title": default_title,
            "description": None,
            "created": "",
            "status": "unprocessed",
            "type": "inbox",
            "tags": [],
            "updated": None,
            "stale_after": None,
            "generated": None,
            "verified": [],
            "sources": [],
            "trust_tier": TrustTier.UNVERIFIED,
            "is_stale": False,
        }

    title_raw = parsed.fields.get("title", (default_title, 0))[0]
    desc_raw = parsed.fields.get("description", (None, 0))[0]
    created_raw = parsed.fields.get("created", ("", 0))[0]
    status_raw = parsed.fields.get("status", ("unprocessed", 0))[0]
    type_raw = parsed.fields.get("type", ("inbox", 0))[0]
    updated_raw = parsed.fields.get("updated", (None, 0))[0]

    return {
        "title": unescape_yaml_string(title_raw) if title_raw else default_title,
        "description": unescape_yaml_string(desc_raw) if desc_raw else None,
        "created": unescape_yaml_string(created_raw) if created_raw else "",
        "status": unescape_yaml_string(status_raw) if status_raw else "unprocessed",
        "type": unescape_yaml_string(type_raw) if type_raw else "inbox",
        "tags": [t[0] for t in parsed.tags],
        "updated": unescape_yaml_string(updated_raw) if updated_raw else None,
        "stale_after": parsed.stale_after,
        "generated": parsed.generated,
        "verified": parsed.verified,
        "sources": parsed.sources,
        "trust_tier": resolve_trust_tier(parsed.verified),
        "is_stale": evaluate_staleness(parsed.stale_after),
    }


def parse_okf_frontmatter_model(
    content: str, default_title: str = "Untitled Note"
) -> OKFFrontmatter:
    """Parse markdown content directly into an OKFFrontmatter instance."""
    d = parse_okf_frontmatter(content, default_title=default_title)
    return OKFFrontmatter(
        title=d["title"],
        description=d["description"],
        created=d["created"],
        updated=d["updated"],
        type=d["type"],
        status=d["status"],
        tags=d["tags"],
        generated=d["generated"],
        verified=d["verified"],
        stale_after=d["stale_after"],
        sources=d["sources"],
    )


OKFFrontmatter.from_markdown = staticmethod(parse_okf_frontmatter_model)

