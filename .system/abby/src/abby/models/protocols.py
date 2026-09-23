"""Structural subtyping protocols for Abby Knowledge Vault.

Defines compile-time and runtime verifiable protocols for dependency injection
without circular dependencies or concrete layer coupling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

__all__ = [
    "CacheSyncer",
    "FileSystemUndo",
    "NoteTargetResolver",
]


@runtime_checkable
class CacheSyncer(Protocol):
    """Protocol for cache synchronization callbacks."""

    def __call__(
        self,
        vault_root: Path,
        *,
        db_path: Optional[Path] = None,
        force: bool = False,
    ) -> dict[str, int]:
        """Perform cache synchronization and return operation statistics."""
        ...


@runtime_checkable
class NoteTargetResolver(Protocol):
    """Protocol for note target ambiguity and candidate resolution."""

    def __call__(
        self,
        conn: Any,
        target_query: str,
    ) -> tuple[Optional[str], Optional[str], list[str]]:
        """Resolve a note title to (path, title, candidate_paths)."""
        ...


@runtime_checkable
class FileSystemUndo(Protocol):
    """Protocol for reversible filesystem undo actions."""

    def __call__(self) -> None:
        """Execute the inverse operation to restore filesystem state."""
        ...

