"""CLI argument parsers for note lifecycle operations (move, archive, verify)."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Mapping


def register_lifecycle_commands(
    subparsers: Any,
    sub_common: argparse.ArgumentParser,
    handlers: Mapping[str, Callable[..., int]],
) -> None:
    """Register move, archive, and verify commands."""
    # abby move <note> <target>
    move_parser = subparsers.add_parser(
        "move",
        parents=[sub_common],
        help="Promote or relocate a note into a target PARA destination",
    )
    move_parser.add_argument(
        "note",
        nargs="?",
        help="Relative path or filename of the note to move",
    )
    move_parser.add_argument(
        "target",
        nargs="?",
        help="Target PARA domain or subpath (e.g. projects/Apollo, areas/Finance)",
    )
    move_parser.add_argument(
        "--description",
        help="15-35 word executive summary to inject into frontmatter during relocation",
    )
    move_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview note relocation and frontmatter updates without altering files on disk",
    )
    if "move" in handlers:
        move_parser.set_defaults(handler=handlers["move"])

    # abby archive <note>
    archive_parser = subparsers.add_parser(
        "archive",
        parents=[sub_common],
        help="Retire an active or reference note into 04 - Archives",
    )
    archive_parser.add_argument(
        "note",
        nargs="?",
        help="Relative path or filename of the note to archive",
    )
    archive_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview note archiving without altering files on disk",
    )
    if "archive" in handlers:
        archive_parser.set_defaults(handler=handlers["archive"])

    # abby verify <note> [--by <actor>] [--dry-run]
    verify_parser = subparsers.add_parser(
        "verify",
        parents=[sub_common],
        help="Record a verification event on note frontmatter, updating its computed OKF trust tier",
    )
    verify_parser.add_argument(
        "note",
        nargs="?",
        help="Relative path or filename of the note to verify",
    )
    verify_parser.add_argument(
        "--by",
        dest="by",
        help="Actor identifier (<producer>/<version>, human:<id>, or process:<id>). Defaults to system user.",
    )
    verify_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview verification without altering files on disk",
    )
    if "verify" in handlers:
        verify_parser.set_defaults(handler=handlers["verify"])

