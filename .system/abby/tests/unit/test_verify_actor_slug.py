"""Unit tests for username slugification and linter resolution delegation (User Story 5, T023)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import IsolatedVaultTestCase, Tier1UnitTestCase
except ModuleNotFoundError:
    from support import IsolatedVaultTestCase, Tier1UnitTestCase

from abby.core.verify import derive_default_actor
from abby.services.lint.rules import find_target_note


class TestVerifyActorSlug(Tier1UnitTestCase):
    """Tier 1: Pure logic tests for username slugification in derive_default_actor."""

    def test_slugify_username_with_spaces(self) -> None:
        with patch.dict(os.environ, {"ABBY_USER": "John Doe"}):
            actor = derive_default_actor()
            self.assertEqual(actor, "human:john-doe")

    def test_slugify_username_with_special_characters(self) -> None:
        with patch.dict(os.environ, {"ABBY_USER": "Jane @ Acme !"}):
            actor = derive_default_actor()
            self.assertEqual(actor, "human:jane-acme")

    def test_slugify_username_with_dots_and_underscores(self) -> None:
        with patch.dict(os.environ, {"ABBY_USER": "Alice.Bob_42"}):
            actor = derive_default_actor()
            self.assertEqual(actor, "human:alice.bob_42")

    def test_slugify_username_only_special_characters_fallback(self) -> None:
        with patch.dict(os.environ, {"ABBY_USER": "!!!@#$%%%"}):
            actor = derive_default_actor()
            self.assertEqual(actor, "human:user")

    def test_slugify_fallback_from_getpass(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("getpass.getuser", return_value="Admin User"):
                actor = derive_default_actor()
                self.assertEqual(actor, "human:admin-user")


class TestLinterTargetDelegation(IsolatedVaultTestCase):
    """Tier 2: Test find_target_note delegation to resolve_source_note."""

    def test_find_target_note_delegates_to_resolve_source_note(self) -> None:
        self.init_vault()
        test_note = self.create_note(title="Candidate Note", filename="Candidate Note.md")

        with patch("abby.services.lint.rules.resolve_source_note") as mock_resolve:
            mock_resolve.return_value = test_note
            found = find_target_note(self.vault_root, "Candidate Note")
            self.assertEqual(found, test_note)
            mock_resolve.assert_called_once_with(self.vault_root, "Candidate Note")

    def test_find_target_note_returns_none_on_not_found(self) -> None:
        self.init_vault()
        found = find_target_note(self.vault_root, "NonExistentNote")
        self.assertIsNone(found)

