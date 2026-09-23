"""Unit tests for FileSystemTransaction and atomic_transaction context manager."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.utils.transaction import (
    FileSystemTransaction,
    TransactionError,
    atomic_transaction,
)


class CustomTestError(Exception):
    """Custom domain exception for testing transaction error wrapping."""


class TestFileSystemTransaction(unittest.TestCase):
    """Unit tests for FileSystemTransaction class."""

    def test_record_undo_and_count(self) -> None:
        tx = FileSystemTransaction()
        self.assertEqual(tx.undo_count, 0)
        tx.record_undo(lambda: None)
        self.assertEqual(tx.undo_count, 1)
        tx.record_undo(lambda: None)
        self.assertEqual(tx.undo_count, 2)
        tx.clear()
        self.assertEqual(tx.undo_count, 0)

    def test_rollback_reverse_order(self) -> None:
        tx = FileSystemTransaction()
        execution_order: list[int] = []

        tx.record_undo(lambda: execution_order.append(1))
        tx.record_undo(lambda: execution_order.append(2))
        tx.record_undo(lambda: execution_order.append(3))

        warnings = tx.rollback()
        self.assertEqual(warnings, [])
        # Must execute in LIFO reverse order: 3, 2, 1
        self.assertEqual(execution_order, [3, 2, 1])

    def test_rollback_warning_aggregation_on_error(self) -> None:
        tx = FileSystemTransaction()
        execution_order: list[int] = []

        def _failing_undo() -> None:
            raise OSError("Simulated disk error during rollback")

        tx.record_undo(lambda: execution_order.append(1))
        tx.record_undo(_failing_undo)
        tx.record_undo(lambda: execution_order.append(3))

        warnings = tx.rollback()
        # Should execute 3, attempt failing undo (record warning), and continue to 1
        self.assertEqual(execution_order, [3, 1])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Simulated disk error during rollback", warnings[0])


class TestAtomicTransactionContextManager(unittest.TestCase):
    """Unit tests for atomic_transaction context manager."""

    def test_clean_execution_does_not_trigger_rollback(self) -> None:
        undone = False

        with atomic_transaction() as tx:
            tx.record_undo(lambda: setattr(sys.modules[__name__], "_should_not_run", True))
            # Normal completion
            pass

        self.assertFalse(undone)

    def test_exception_triggers_rollback_and_reraises_with_cause(self) -> None:
        undone_actions: list[str] = []

        with self.assertRaises(TransactionError) as ctx:
            with atomic_transaction(error_prefix="Step failed") as tx:
                tx.record_undo(lambda: undone_actions.append("undo_1"))
                tx.record_undo(lambda: undone_actions.append("undo_2"))
                raise ValueError("Something went wrong mid-process")

        # Rollback executed in LIFO order
        self.assertEqual(undone_actions, ["undo_2", "undo_1"])
        err_msg = str(ctx.exception)
        self.assertIn("Step failed: Something went wrong mid-process. All changes rolled back.", err_msg)
        self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_custom_exception_class_and_warnings(self) -> None:
        with self.assertRaises(CustomTestError) as ctx:
            with atomic_transaction(
                exc_cls=CustomTestError,
                error_prefix="Custom refactor failed",
            ) as tx:
                def _faulty_undo() -> None:
                    raise RuntimeError("Failed to restore backup")

                tx.record_undo(_faulty_undo)
                raise RuntimeError("Initial trigger error")

        err_msg = str(ctx.exception)
        self.assertIn("Custom refactor failed: Initial trigger error. All changes rolled back.", err_msg)
        self.assertIn("Rollback warnings: Failed to restore backup", err_msg)


if __name__ == "__main__":
    unittest.main()

