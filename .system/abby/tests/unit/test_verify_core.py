"""Unit tests for note verification core service, frontmatter mutation, and actor deduplication.

Covers User Story 2 (T013) of OKF 0.2 Trust Model.
"""

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

from abby.core.verify import (
    derive_default_actor,
    mutate_frontmatter_verification,
    verify_note,
)
from abby.services.okf_parser import tokenize_frontmatter
from abby.models.trust import TrustTier, VerifyResult


class TestVerifyPureLogic(Tier1UnitTestCase):
    """Tier 1: Pure logic tests for actor derivation and in-memory frontmatter mutation."""

    def test_derive_default_actor_with_env(self) -> None:
        with patch.dict(os.environ, {"ABBY_USER": "testuser"}):
            actor = derive_default_actor()
            self.assertEqual(actor, "human:testuser")

    def test_mutate_frontmatter_verification_appends_to_unverified(self) -> None:
        raw = (
            "---\n"
            'title: "Simple Note"\n'
            'created: "2026-09-18T10:00:00Z"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - testing\n"
            "---\n"
            "\n"
            "# Simple Note\n"
            "\n"
            "Some content.\n"
        )
        updated, old_tier, new_tier = mutate_frontmatter_verification(
            raw, actor="human:alice", timestamp="2026-09-18T12:00:00Z"
        )
        self.assertEqual(old_tier, TrustTier.UNVERIFIED)
        self.assertEqual(new_tier, TrustTier.HUMAN_REVIEWED)
        self.assertIn("verified:\n  - by: human:alice\n    at: \"2026-09-18T12:00:00Z\"", updated)
        self.assertTrue(updated.endswith("# Simple Note\n\nSome content.\n"))

    def test_mutate_frontmatter_verification_updates_existing_actor(self) -> None:
        raw = (
            "---\n"
            'title: "Already Verified Note"\n'
            'created: "2026-09-18T10:00:00Z"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "verified:\n"
            "  - by: human:alice\n"
            '    at: "2026-09-18T10:30:00Z"\n'
            "---\n"
            "\n"
            "Body content.\n"
        )
        updated, old_tier, new_tier = mutate_frontmatter_verification(
            raw, actor="human:alice", timestamp="2026-09-18T15:00:00Z"
        )
        self.assertEqual(old_tier, TrustTier.HUMAN_REVIEWED)
        self.assertEqual(new_tier, TrustTier.HUMAN_REVIEWED)
        # Check that timestamp is updated and only one entry exists for human:alice
        self.assertIn('at: "2026-09-18T15:00:00Z"', updated)
        self.assertNotIn('at: "2026-09-18T10:30:00Z"', updated)
        parsed = tokenize_frontmatter(updated)
        self.assertEqual(len(parsed.verified), 1)
        self.assertEqual(parsed.verified[0]["by"], "human:alice")
        self.assertEqual(parsed.verified[0]["at"], "2026-09-18T15:00:00Z")

    def test_mutate_frontmatter_preserves_custom_keys_and_block_refs(self) -> None:
        raw = (
            "---\n"
            'title: "Complex Note"\n'
            "custom_prop: keep_me\n"
            "tags:\n"
            "  - arch\n"
            "---\n"
            "\n"
            "Paragraph with block ref ^p-1234\n"
        )
        updated, old_tier, new_tier = mutate_frontmatter_verification(
            raw, actor="process:ci", timestamp="2026-09-18T14:00:00Z"
        )
        self.assertEqual(old_tier, TrustTier.UNVERIFIED)
        self.assertEqual(new_tier, TrustTier.MACHINE_CONFIRMED)
        self.assertIn("custom_prop: keep_me", updated)
        self.assertIn("^p-1234", updated)

    def test_mutate_frontmatter_preserves_crlf(self) -> None:
        raw = "---\r\ntitle: \"CRLF Note\"\r\ntype: inbox\r\n---\r\n\r\nBody\r\n"
        updated, _, _ = mutate_frontmatter_verification(
            raw, actor="human:bob", timestamp="2026-09-18T12:00:00Z"
        )
        self.assertIn("\r\n", updated)
        self.assertNotIn("\n\n", updated.replace("\r\n", "\n"))


class TestVerifyFilesystem(IsolatedVaultTestCase):
    """Tier 2: Filesystem integration tests for verify_note service."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_verify_note_success(self) -> None:
        note_path = self.create_note(
            domain="03 - Resources",
            filename="Distributed Systems.md",
            title="Distributed Systems",
            body="Content with [[Wikilink]].\n^block-id",
        )
        res = verify_note(
            vault_root=self.vault_root,
            note_arg="03 - Resources/Distributed Systems.md",
            actor="human:bookian",
        )
        self.assertIsInstance(res, VerifyResult)
        self.assertEqual(res.path, "03 - Resources/Distributed Systems.md")
        self.assertEqual(res.actor, "human:bookian")
        self.assertEqual(res.trust_tier, TrustTier.HUMAN_REVIEWED)
        self.assertEqual(res.old_trust_tier, TrustTier.UNVERIFIED)
        self.assertFalse(res.dry_run)

        # Assert disk file updated
        disk_content = note_path.read_text(encoding="utf-8")
        self.assertIn("human:bookian", disk_content)
        self.assertIn("^block-id", disk_content)

    def test_verify_note_dry_run_does_not_modify_disk(self) -> None:
        note_path = self.create_note(
            domain="03 - Resources",
            filename="DryRun Note.md",
            title="DryRun Note",
            body="Original content.",
        )
        original_content = note_path.read_text(encoding="utf-8")
        original_mtime = note_path.stat().st_mtime_ns

        res = verify_note(
            vault_root=self.vault_root,
            note_arg="DryRun Note.md",
            actor="human:tester",
            dry_run=True,
        )
        self.assertTrue(res.dry_run)
        self.assertEqual(res.trust_tier, TrustTier.HUMAN_REVIEWED)

        # Confirm 0 modifications to file
        self.assertEqual(note_path.read_text(encoding="utf-8"), original_content)
        self.assertEqual(note_path.stat().st_mtime_ns, original_mtime)

    def test_verify_note_invalid_actor_raises_value_error(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Invalid Actor.md",
            title="Invalid Actor",
        )
        with self.assertRaises(ValueError):
            verify_note(
                vault_root=self.vault_root,
                note_arg="Invalid Actor.md",
                actor="invalid actor with spaces",
            )

    def test_verify_note_missing_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            verify_note(
                vault_root=self.vault_root,
                note_arg="NonExistent.md",
                actor="human:alice",
            )
