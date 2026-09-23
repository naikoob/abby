"""Domain exception hierarchy for Abby Knowledge Vault."""

from __future__ import annotations

from typing import Optional


class AbbyError(Exception):
    """Base exception for all Abby domain and system errors."""

    def __init__(
        self,
        message: str,
        exit_code: int = 1,
        file_path: Optional[str] = None,
        remediation_hint: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.file_path = file_path
        self.remediation_hint = remediation_hint

    def __str__(self) -> str:
        return self.message


class VaultError(AbbyError):
    """Raised when vault root cannot be found or standard directories are invalid."""

    pass


class LinkError(AbbyError):
    """Raised when link resolution or graph querying fails."""

    pass


class RefactorError(LinkError):
    """Base error for link refactoring operations."""

    pass


class AmbiguousTargetError(RefactorError):
    """Raised when refactor target matches multiple note paths without domain qualification."""

    def __init__(self, message: str, candidate_paths: list[str]) -> None:
        super().__init__(
            message=message,
            exit_code=1,
            remediation_hint=(
                "Qualify with domain prefix (e.g. '01 - Projects/{title}') or use --force."
            ),
        )
        self.candidate_paths = candidate_paths


class DestinationCollisionError(RefactorError):
    """Raised when refactoring a note into an already-existing destination file."""

    def __init__(self, message: str, destination_path: str) -> None:
        super().__init__(
            message=message,
            exit_code=1,
            file_path=destination_path,
            remediation_hint="Choose a distinct title or archive the existing note first.",
        )


class LintError(AbbyError):
    """Raised during OKF schema linting or remediation failures."""

    pass


class SearchQueryError(AbbyError):
    """Raised when search query arguments or regular expressions are malformed."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        remediation_hint: Optional[str] = None,
    ) -> None:
        super().__init__(
            message=message,
            exit_code=2,
            file_path=file_path,
            remediation_hint=remediation_hint,
        )


class SearchDomainError(AbbyError):
    """Raised when an unrecognized or invalid domain is specified."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=1)


class SearchArgumentError(SearchQueryError):
    """Raised when search arguments (dates, limits, regex) are malformed."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message)


class LifecycleError(AbbyError, ValueError):
    """Base error for note lifecycle operations (move, archive, triage)."""

    def __init__(
        self,
        message: str,
        exit_code: int = 1,
        file_path: Optional[str] = None,
        remediation_hint: Optional[str] = None,
    ) -> None:
        AbbyError.__init__(
            self,
            message=message,
            exit_code=exit_code,
            file_path=file_path,
            remediation_hint=remediation_hint,
        )


class NoteNotFoundError(LifecycleError, FileNotFoundError):
    """Raised when a specified note cannot be found in the vault."""

    def __init__(self, note_arg: str) -> None:
        LifecycleError.__init__(
            self,
            message=f"Note '{note_arg}' not found in vault",
            exit_code=1,
            remediation_hint="Check note spelling or run 'abby find' to search the vault.",
        )
        self.note_arg = note_arg


class PathBoundaryError(LifecycleError, ValueError):
    """Raised when a note path or target destination attempts to escape the vault or domain."""

    def __init__(self, message: str) -> None:
        LifecycleError.__init__(
            self,
            message=message,
            exit_code=1,
            remediation_hint="Ensure paths are relative and stay within valid knowledge domains.",
        )
