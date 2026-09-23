"""Integration test suite for architectural boundaries, line count limits, and import cycles."""

import ast
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class TestArchitectureBoundaries(unittest.TestCase):
    """Verifies modularity bounds, file length caps, and import cycle freedom."""

    def setUp(self) -> None:
        self.src_abby = SRC_DIR / "abby"
        self.assertTrue(
            self.src_abby.exists(), f"Source dir {self.src_abby} does not exist"
        )

    def test_module_loc_under_750(self) -> None:
        """Every Python file in src/abby/ must remain strictly under 750 lines of code."""
        max_allowed_lines = 750
        violators = []

        for py_path in sorted(self.src_abby.rglob("*.py")):
            lines = len(py_path.read_text(encoding="utf-8").splitlines())
            if lines >= max_allowed_lines:
                rel_path = py_path.relative_to(SRC_DIR)
                violators.append((str(rel_path), lines))

        self.assertEqual(
            violators,
            [],
            f"The following modules violate the 750 LOC bound: {violators}",
        )

    def test_isolated_imports_zero_circular_dependencies(self) -> None:
        """Every module in src/abby/ must successfully import in an isolated interpreter.

        Circular imports between partially initialized modules cause ImportError during
        isolated module imports.
        """
        modules_to_test = []

        for py_path in sorted(self.src_abby.rglob("*.py")):
            rel = py_path.relative_to(SRC_DIR)
            mod_name = str(rel.with_suffix("")).replace(os.sep, "/")
            if mod_name.endswith("/__main__"):
                continue
            if mod_name.endswith("/__init__"):
                mod_name = mod_name[:-9]
            mod_dotted = mod_name.replace("/", ".")
            modules_to_test.append(mod_dotted)

        def _import_probe(mod: str) -> tuple[str, int, str]:
            proc = subprocess.run(
                [sys.executable, "-c", f"import {mod}"],
                env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
                capture_output=True,
                text=True,
            )
            return mod, proc.returncode, proc.stderr.strip()

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(_import_probe, modules_to_test))

        failed_modules = [
            (mod, stderr) for mod, retcode, stderr in results if retcode != 0
        ]

        self.assertEqual(
            failed_modules,
            [],
            f"The following modules failed isolated import (likely circular dependency): {failed_modules}",
        )

    def test_layering_boundaries(self) -> None:
        """Enforce strict directional dependencies across architectural layers.

        Hierarchy:
          - models and utils: foundational, must never import core, services, or mcp.
          - services and core: domain logic, must never import presentation layer (mcp, cli).
          - mcp and cli: presentation layer, can consume core, services, models, and utils.
        """
        for py_path in sorted(self.src_abby.rglob("*.py")):
            rel_path = py_path.relative_to(self.src_abby)
            parts = rel_path.parts

            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))

            top_level_imports: list[str] = []
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level_imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_level_imports.append(node.module)

            # Rule 1: models/ and utils/ cannot depend on core, services, or mcp
            if parts[0] in ("models", "utils"):
                for imp in top_level_imports:
                    for forbidden in (
                        "abby.core",
                        "abby.services",
                        "abby.mcp",
                        "abby.cli",
                    ):
                        self.assertFalse(
                            imp == forbidden or imp.startswith(f"{forbidden}."),
                            f"Layer violation: {rel_path} must not import {imp}",
                        )

            # Rule 2: core/ and services/ cannot depend on mcp
            if parts[0] in ("core", "services"):
                for imp in top_level_imports:
                    self.assertFalse(
                        imp == "abby.mcp" or imp.startswith("abby.mcp."),
                        f"Layer violation: {rel_path} must not import presentation module {imp}",
                    )

    def test_no_mid_file_imports_per_pep8(self) -> None:
        """Every module in src/abby/ must place all top-level imports before class/function definitions."""
        mid_file_violations = []

        for py_path in sorted(self.src_abby.rglob("*.py")):
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            seen_def = False
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    seen_def = True
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if seen_def:
                        rel_path = py_path.relative_to(SRC_DIR)
                        mid_file_violations.append((str(rel_path), node.lineno, ast.unparse(node)))

        self.assertEqual(
            mid_file_violations,
            [],
            f"The following modules have mid-file imports violating PEP 8: {mid_file_violations}",
        )

    def test_no_function_level_deferred_imports(self) -> None:
        """Ensure all functions/methods avoid deferred imports, preventing hidden circular dependencies."""
        deferred_violations = []

        for py_path in sorted(self.src_abby.rglob("*.py")):
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Import, ast.ImportFrom)):
                            rel_path = py_path.relative_to(SRC_DIR)
                            deferred_violations.append(
                                (
                                    str(rel_path),
                                    node.name,
                                    child.lineno,
                                    ast.unparse(child),
                                )
                            )

        self.assertEqual(
            deferred_violations,
            [],
            f"Found deferred/inline function imports that should be resolved at module top-level: {deferred_violations}",
        )

    def test_zero_getattr_shims_in_codebase(self) -> None:
        """Ensure no module in src/abby/ defines dynamic PEP 562 __getattr__ shims."""
        getattr_violations = []

        for py_path in sorted(self.src_abby.rglob("*.py")):
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__":
                    rel_path = py_path.relative_to(SRC_DIR)
                    getattr_violations.append((str(rel_path), node.lineno))

        self.assertEqual(
            getattr_violations,
            [],
            f"Found legacy __getattr__ shims that must be removed: {getattr_violations}",
        )

    def test_refactored_modules_loc_under_500(self) -> None:
        """Key refactored modules must remain strictly under 500 lines of code."""
        targets = [
            "abby/cli/handlers.py",
            "abby/cli/parser.py",
            "abby/cli/args/__init__.py",
            "abby/cli/args/vault.py",
            "abby/cli/args/lifecycle.py",
            "abby/cli/args/search_graph.py",
            "abby/cli/args/lint_mcp.py",
            "abby/cli/commands/__init__.py",
            "abby/cli/commands/vault.py",
            "abby/cli/commands/notes.py",
            "abby/cli/commands/search.py",
            "abby/cli/commands/links.py",
            "abby/cli/commands/lint.py",
            "abby/mcp/tools.py",
            "abby/mcp/handlers/__init__.py",
            "abby/mcp/handlers/vault.py",
            "abby/mcp/handlers/notes.py",
            "abby/mcp/handlers/search.py",
            "abby/mcp/handlers/graph.py",
            "abby/mcp/handlers/lint.py",
            "abby/mcp/registry.py",
            "abby/mcp/schemas.py",
            "abby/models/okf.py",
            "abby/models/trust.py",
            "abby/services/okf_parser.py",
            "abby/services/okf_serializer.py",
            "abby/core/cache.py",
            "abby/core/graph/__init__.py",
            "abby/core/graph/parser.py",
            "abby/core/graph/cache.py",
            "abby/core/graph/diagnostics.py",
            "abby/core/graph/traversal.py",
            "abby/core/graph/refactor.py",
            "abby/core/scoring.py",
            "abby/core/domain.py",
            "abby/core/resolution.py",
            "abby/core/search.py",
            "abby/core/search_builder.py",
            "abby/services/lint/rules.py",
            "abby/services/lint/validators.py",
            "abby/services/lint/trust_validators.py",
            "abby/utils/time.py",
            "abby/utils/yaml.py",
        ]
        violators = []
        for target in targets:
            py_path = SRC_DIR / target
            self.assertTrue(py_path.exists(), f"Target module {target} does not exist")
            lines = len(py_path.read_text(encoding="utf-8").splitlines())
            if lines >= 500:
                violators.append((target, lines))

        self.assertEqual(
            violators,
            [],
            f"The following refactored modules violate the 500 LOC target: {violators}",
        )

    def test_function_cyclomatic_complexity_under_20(self) -> None:
        """Enforce that no function in src/abby/ exceeds cyclomatic complexity of 20."""
        violators = []
        for py_path in sorted(self.src_abby.rglob("*.py")):
            try:
                tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            except Exception as e:
                self.fail(f"Failed to parse AST for {py_path}: {e}")
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cc = calculate_cyclomatic_complexity(node)
                    if cc > 20:
                        rel = py_path.relative_to(SRC_DIR)
                        violators.append((f"{rel}:{node.lineno}", node.name, cc))

        self.assertEqual(
            violators,
            [],
            f"The following functions exceed cyclomatic complexity threshold of 20: {violators}",
        )


def calculate_cyclomatic_complexity(node: ast.AST) -> int:
    """Calculate standard McCabe cyclomatic complexity for an AST function node."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.If,
                ast.While,
                ast.For,
                ast.AsyncFor,
                ast.ExceptHandler,
                ast.With,
                ast.AsyncWith,
                ast.IfExp,
            ),
        ):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


