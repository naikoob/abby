"""Unit tests for the domain exception hierarchy (abby.models.exceptions)."""

import unittest
from abby.models.exceptions import (
    AbbyError,
    AmbiguousTargetError,
    DestinationCollisionError,
    LifecycleError,
    LinkError,
    LintError,
    NoteNotFoundError,
    PathBoundaryError,
    RefactorError,
    SearchArgumentError,
    SearchDomainError,
    SearchQueryError,
    VaultError,
)


class TestExceptions(unittest.TestCase):
    """Test suite for domain exception behavior, hierarchy, and metadata."""

    def test_base_abby_error(self):
        err = AbbyError(
            "Something failed",
            exit_code=1,
            file_path="00 - Inbox/Test.md",
            remediation_hint="Fix it",
        )
        self.assertEqual(str(err), "Something failed")
        self.assertEqual(err.message, "Something failed")
        self.assertEqual(err.exit_code, 1)
        self.assertEqual(err.file_path, "00 - Inbox/Test.md")
        self.assertEqual(err.remediation_hint, "Fix it")

    def test_vault_error_hierarchy(self):
        err = VaultError("Vault root not found")
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 1)
        self.assertEqual(str(err), "Vault root not found")

    def test_link_error_hierarchy(self):
        err = LinkError("Target note does not exist")
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 1)

    def test_refactor_error_hierarchy(self):
        err = RefactorError("Refactor failed")
        self.assertIsInstance(err, LinkError)
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 1)

    def test_ambiguous_target_error(self):
        candidates = ["01 - Projects/Alpha.md", "03 - Resources/Alpha.md"]
        err = AmbiguousTargetError(
            "Multiple notes matched 'Alpha'", candidate_paths=candidates
        )
        self.assertIsInstance(err, RefactorError)
        self.assertIsInstance(err, LinkError)
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.candidate_paths, candidates)
        self.assertEqual(err.exit_code, 1)
        self.assertIn("Qualify with domain prefix", err.remediation_hint)

    def test_destination_collision_error(self):
        dest = "01 - Projects/Beta.md"
        err = DestinationCollisionError(
            "Destination file already exists", destination_path=dest
        )
        self.assertIsInstance(err, RefactorError)
        self.assertIsInstance(err, LinkError)
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.file_path, dest)
        self.assertEqual(err.exit_code, 1)
        self.assertIn("Choose a distinct title", err.remediation_hint)

    def test_lint_error_hierarchy(self):
        err = LintError("Syntax error in frontmatter")
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 1)

    def test_search_query_error(self):
        err = SearchQueryError("Malformed regex pattern")
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 2)

    def test_search_domain_error(self):
        err = SearchDomainError("Unknown domain")
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 1)

    def test_search_argument_error(self):
        err = SearchArgumentError("Invalid limit")
        self.assertIsInstance(err, SearchQueryError)
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 2)

    def test_lifecycle_error_hierarchy(self):
        err = LifecycleError("Failed to relocate note")
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 1)

    def test_note_not_found_error(self):
        err = NoteNotFoundError("MissingNote")
        self.assertIsInstance(err, LifecycleError)
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.note_arg, "MissingNote")
        self.assertEqual(err.exit_code, 1)
        self.assertIn("MissingNote", str(err))
        self.assertIn("Check note spelling", err.remediation_hint)

    def test_path_boundary_error(self):
        err = PathBoundaryError("Escaping vault root")
        self.assertIsInstance(err, LifecycleError)
        self.assertIsInstance(err, AbbyError)
        self.assertEqual(err.exit_code, 1)
        self.assertIn("Escaping vault root", str(err))
        self.assertIn("valid knowledge domains", err.remediation_hint)


if __name__ == "__main__":
    unittest.main()

