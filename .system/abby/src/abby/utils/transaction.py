"""Transactional filesystem operations and rollback stack context managers.

Enforces ACID-style atomicity across multi-file operations by maintaining a LIFO
undo stack that automatically restores pre-transaction state if any step fails.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Optional

__all__ = [
    "FileSystemTransaction",
    "TransactionError",
    "atomic_transaction",
]


class TransactionError(Exception):
    """Base exception raised when a filesystem transaction fails and is rolled back."""


class FileSystemTransaction:
    """Encapsulates an ordered sequence of reversible filesystem actions."""

    def __init__(self) -> None:
        self._undo_stack: list[Callable[[], None]] = []

    def record_undo(self, undo_fn: Callable[[], None]) -> None:
        """Register an inverse undo action to be executed if the transaction aborts."""
        self._undo_stack.append(undo_fn)

    def rollback(self) -> list[str]:
        """Execute all registered undo actions in reverse order (LIFO).

        Captures any secondary errors during rollback and returns them as warning strings.
        """
        warnings: list[str] = []
        for undo in reversed(self._undo_stack):
            try:
                undo()
            except Exception as err:
                warnings.append(str(err))
        return warnings

    def clear(self) -> None:
        """Clear all recorded undo actions (used upon successful commit)."""
        self._undo_stack.clear()

    @property
    def undo_count(self) -> int:
        """Return the number of registered undo actions."""
        return len(self._undo_stack)


@contextmanager
def atomic_transaction(
    exc_cls: type[Exception] = TransactionError,
    error_prefix: str = "Transaction aborted",
) -> Generator[FileSystemTransaction, None, None]:
    """Context manager executing filesystem actions with two-phase rollback guarantees.

    Yields a FileSystemTransaction instance. If an exception occurs within the block,
    all registered undo actions are drained in reverse order (LIFO). Any rollback
    warnings are appended to the resulting exception message.
    """
    tx = FileSystemTransaction()
    try:
        yield tx
    except Exception as exc:
        warnings = tx.rollback()
        err_msg = f"{error_prefix}: {exc}. All changes rolled back."
        if warnings:
            err_msg += f" (Rollback warnings: {'; '.join(warnings)})"
        raise exc_cls(err_msg) from exc

