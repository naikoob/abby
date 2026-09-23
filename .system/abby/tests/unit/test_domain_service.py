"""Unit tests for centralized domain authority and path resolution."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.core.domain import (
    canonicalize_domain,
    get_domain_defaults,
    is_valid_domain,
    resolve_domain_from_path,
)


class TestDomainService(unittest.TestCase):
    """Tests for DomainService domain resolution and canonicalization."""

    def test_canonicalize_domain_exact_matches(self) -> None:
        self.assertEqual(canonicalize_domain("00 - Inbox"), "00 - Inbox")
        self.assertEqual(canonicalize_domain("01 - Projects"), "01 - Projects")
        self.assertEqual(canonicalize_domain("02 - Areas"), "02 - Areas")
        self.assertEqual(canonicalize_domain("03 - Resources"), "03 - Resources")
        self.assertEqual(canonicalize_domain("04 - Archives"), "04 - Archives")
        self.assertEqual(canonicalize_domain("05 - Assets"), "05 - Assets")

    def test_canonicalize_domain_aliases(self) -> None:
        self.assertEqual(canonicalize_domain("inbox"), "00 - Inbox")
        self.assertEqual(canonicalize_domain("projects"), "01 - Projects")
        self.assertEqual(canonicalize_domain("project"), "01 - Projects")
        self.assertEqual(canonicalize_domain("areas"), "02 - Areas")
        self.assertEqual(canonicalize_domain("resources"), "03 - Resources")
        self.assertEqual(canonicalize_domain("archive"), "04 - Archives")
        self.assertEqual(canonicalize_domain("archives"), "04 - Archives")
        self.assertEqual(canonicalize_domain("assets"), "05 - Assets")

    def test_canonicalize_domain_unknown(self) -> None:
        self.assertIsNone(canonicalize_domain(None))
        self.assertIsNone(canonicalize_domain(""))
        self.assertIsNone(canonicalize_domain("nonexistent"))

    def test_is_valid_domain(self) -> None:
        self.assertTrue(is_valid_domain("00 - Inbox"))
        self.assertTrue(is_valid_domain("01 - Projects"))
        self.assertTrue(is_valid_domain("projects"))
        self.assertFalse(is_valid_domain("unknown_domain"))

    def test_resolve_domain_from_path_posix(self) -> None:
        self.assertEqual(resolve_domain_from_path("01 - Projects/Alpha.md"), "01 - Projects")
        self.assertEqual(resolve_domain_from_path("03 - Resources/Tech/Python.md"), "03 - Resources")
        self.assertEqual(resolve_domain_from_path(Path("02 - Areas/Health.md")), "02 - Areas")
        self.assertIsNone(resolve_domain_from_path("README.md"))

    def test_resolve_domain_from_path_windows(self) -> None:
        self.assertEqual(resolve_domain_from_path(r"01 - Projects\Alpha.md"), "01 - Projects")
        self.assertEqual(resolve_domain_from_path(r"00 - Inbox\QuickNote.md"), "00 - Inbox")

    def test_get_domain_defaults(self) -> None:
        status, type_ = get_domain_defaults("01 - Projects")
        self.assertEqual(status, "active")
        self.assertEqual(type_, "project-note")

        status, type_ = get_domain_defaults("03 - Resources")
        self.assertEqual(status, "evergreen")
        self.assertEqual(type_, "resource-note")


if __name__ == "__main__":
    unittest.main()
