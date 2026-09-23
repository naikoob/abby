"""Data models and diagnostic reporting structures for OKF schema linting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class LintViolation:
    """Represents an individual structural defect, invalid schema value, or domain alignment warning."""

    file_path: str
    field: str
    rule: str
    severity: str  # "error" or "warning"
    message: str
    line_number: Optional[int] = None
    is_fixable: bool = False
    suggested_value: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.line_number is None:
            del data["line_number"]
        if self.suggested_value is None:
            del data["suggested_value"]
        return data


@dataclass
class NoteAuditResult:
    """Audit outcome for a single note file."""

    file_path: str
    absolute_path: Path
    has_frontmatter: bool = True
    violations: list[LintViolation] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "error" for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        return any(v.severity == "warning" for v in self.violations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "has_frontmatter": self.has_frontmatter,
            "is_clean": self.is_clean,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclass
class RemediationAction:
    """Represents an individual fix planned or executed on a note."""

    file_path: str
    rule: str
    field: str
    old_value: Any
    new_value: Any
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NoteFixResult:
    """Outcome of remediating a single note file."""

    file_path: str
    success: bool
    dry_run: bool = False
    actions: list[RemediationAction] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "file_path": self.file_path,
            "success": self.success,
            "dry_run": self.dry_run,
            "actions": [a.to_dict() for a in self.actions],
        }
        if self.error is not None:
            data["error"] = self.error
        return data


@dataclass
class LintReport:
    """Vault-wide or scoped aggregation of linting results across all audited notes."""

    total_audited: int = 0
    clean_notes: int = 0
    total_violations: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    violations: list[LintViolation] = field(default_factory=list)
    fixed_notes: int = 0
    fixed_violations: int = 0
    exit_code: int = 0
    scoped_path: Optional[str] = None

    def calculate_exit_code(self, strict: bool = False) -> int:
        """Compute the process exit code based on strict mode and violation counts."""
        if strict:
            return 1 if (self.total_errors > 0 or self.total_warnings > 0) else 0
        return 0

    def to_dict(self) -> dict[str, Any]:
        data = {
            "total_audited": self.total_audited,
            "clean_notes": self.clean_notes,
            "total_violations": self.total_violations,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "violations": [v.to_dict() for v in self.violations],
            "fixed_notes": self.fixed_notes,
            "fixed_violations": self.fixed_violations,
            "exit_code": self.exit_code,
        }
        if self.scoped_path is not None:
            data["scoped_path"] = self.scoped_path
        return data
