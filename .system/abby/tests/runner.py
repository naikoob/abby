"""High-velocity test runner for Abby Knowledge Vault.

Provides multi-core parallel execution across test modules using standard library
ProcessPoolExecutor, tiered test suite selection (unit, integration, all), and
strict warning enforcement (-W error::ResourceWarning, -W error::UserWarning).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PACKAGE_ROOT / "src"
TESTS_DIR = PACKAGE_ROOT / "tests"


KNOWN_HEAVY_TESTS = [
    # Wave 1: Dispatched at t=0 to all 8 workers (> 3.5s)
    "test_mcp_tools.py",
    "test_links_refactor.py",
    "test_architecture.py",
    "test_search_trust.py",
    "test_multihop_links.py",
    "test_lint_cli.py",
    "test_links_graph.py",
    "test_links_diagnostics.py",
    # Wave 2: Dispatched to first free workers (1.8s - 3.4s)
    "test_search_engine.py",
    "test_search_fts.py",
    "test_cli_find.py",
    "test_cli_find_filters.py",
    "test_cli_commands.py",
    "test_cli_lifecycle.py",
    "test_mcp_links_lint.py",
    "test_links_cache.py",
    "test_cache.py",
    "test_note_read.py",
    "test_mcp_gap_tools.py",
    "test_quickstart_scenarios.py",
    "test_refactor_rollback.py",
    "test_lint_service.py",
    "test_search_snippets_backlinks.py",
    "test_lifecycle_ops.py",
    "test_init_personalization.py",
    "test_refactor.py",
    "test_cli_description.py",
    "test_resolution.py",
    "test_search_cognitive.py",
    "test_links_orphans.py",
    "test_verify_core.py",
    "test_mcp_verify.py",
    # Wave 3: Short integration / heavy unit (1.0s - 1.9s)
    "test_cli_verify.py",
    "test_mcp_description.py",
    "test_intake.py",
    "test_intake_provenance.py",
    "test_mcp_cli.py",
    "test_cache_backlinks.py",
    "test_cli_move_desc.py",
    "test_sources_search.py",
    "test_init.py",
    "test_verify_actor_slug.py",
    "test_discovery.py",
    "test_health.py",
    "test_atomic_io.py",
    "test_cli_doctor_cache.py",
]



def prioritize_test_files(files: list[Path]) -> list[Path]:
    """Sort test files so slowest and heaviest tests are dispatched first to parallel workers.

    Applies Longest Processing Time First (LPT) greedy scheduling to maximize worker
    saturation and eliminate the long-tail straggler effect.
    """
    heavy_rank = {name: idx for idx, name in enumerate(KNOWN_HEAVY_TESTS)}

    def sort_key(p: Path) -> tuple[int, int, str]:
        name = p.name
        if name in heavy_rank:
            return (0, heavy_rank[name], name)
        tier_weight = 1 if "integration" in p.parts else 2
        try:
            size_weight = -p.stat().st_size
        except OSError:
            size_weight = 0
        return (tier_weight, size_weight, name)

    return sorted(files, key=sort_key)


def discover_test_files(target: str = "all", pattern_filter: Optional[str] = None) -> list[Path]:
    """Discover test files based on tier, specific path, or filter pattern."""
    target_path = Path(target)
    # Check if target is an exact existing file or path
    if target_path.is_file():
        files = [target_path.resolve()]
    elif (PACKAGE_ROOT / target).is_file():
        files = [(PACKAGE_ROOT / target).resolve()]
    elif (TESTS_DIR / "unit" / target).is_file():
        files = [(TESTS_DIR / "unit" / target).resolve()]
    elif (TESTS_DIR / "integration" / target).is_file():
        files = [(TESTS_DIR / "integration" / target).resolve()]
    elif (TESTS_DIR / "unit" / f"{target}.py").is_file():
        files = [(TESTS_DIR / "unit" / f"{target}.py").resolve()]
    elif (TESTS_DIR / "integration" / f"{target}.py").is_file():
        files = [(TESTS_DIR / "integration" / f"{target}.py").resolve()]
    elif target == "arch":
        files = [(TESTS_DIR / "integration" / "test_architecture.py").resolve()]
    elif target == "unit":
        files = sorted((TESTS_DIR / "unit").glob("test_*.py"))
    elif target == "integration":
        files = sorted((TESTS_DIR / "integration").glob("test_*.py"))
    else:  # "all" or general pattern
        files = sorted((TESTS_DIR / "unit").glob("test_*.py")) + sorted(
            (TESTS_DIR / "integration").glob("test_*.py")
        )
        if target != "all":
            matched = [f for f in files if target.lower() in f.name.lower()]
            if matched:
                files = matched

    if pattern_filter:
        files = [f for f in files if pattern_filter.lower() in f.name.lower()]

    return prioritize_test_files(files)



def run_single_test_file(
    test_file: Path, verbose: bool = False
) -> tuple[Path, int, float, str, str]:
    """Execute a single test file in an isolated Python subprocess."""
    t0 = time.perf_counter()
    env = {
        **os.environ,
        "PYTHONPATH": f"{SRC_DIR}:{PACKAGE_ROOT}:{os.environ.get('PYTHONPATH', '')}",
    }
    cmd = [
        sys.executable,
        "-W",
        "error::ResourceWarning",
        "-W",
        "error::UserWarning",
        "-m",
        "unittest",
        str(test_file),
    ]
    if verbose:
        cmd.append("-v")

    proc = subprocess.run(
        cmd,
        cwd=str(PACKAGE_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - t0
    return test_file, proc.returncode, elapsed, proc.stdout, proc.stderr


def run_sequential(tier: str, verbose: bool) -> int:
    """Run tests sequentially using standard unittest discovery."""
    env = {
        **os.environ,
        "PYTHONPATH": f"{SRC_DIR}:{PACKAGE_ROOT}:{os.environ.get('PYTHONPATH', '')}",
    }
    cmd = [
        sys.executable,
        "-W",
        "error::ResourceWarning",
        "-W",
        "error::UserWarning",
        "-m",
        "unittest",
        "discover",
        "-s",
        f"tests/{tier}" if tier in ("unit", "integration") else "tests",
    ]
    if verbose:
        cmd.append("-v")

    proc = subprocess.run(cmd, cwd=str(PACKAGE_ROOT), env=env)
    return proc.returncode


def run_typecheck(verbose: bool = False, strict: bool = False) -> int:
    """Run static type checking against src/abby/ using mypy or pyright if available."""
    print("=" * 60)
    print(" Abby Static Type Checker Gate")
    print("=" * 60)

    checker_bin = shutil.which("mypy") or shutil.which("pyright")
    if not checker_bin:
        print("No external static type checker detected (mypy or pyright not found).")
        print("Abby Knowledge Vault engine adheres strictly to the Python standard library.")
        print("To run static type checking in your environment:")
        print("    pip install mypy")
        print("    mypy src/abby")
        if strict:
            print("\nError: Static type checker required in strict mode (--strict).")
            return 1
        print("\nStatic type checking skipped (clean exit 0).")
        return 0

    checker_name = Path(checker_bin).name
    print(f"Detected static type checker: {checker_bin}")

    if "mypy" in checker_name:
        cmd = [checker_bin, str(SRC_DIR / "abby")]
        if strict:
            cmd.append("--strict")
        if verbose:
            cmd.append("-v")
    else:  # pyright
        cmd = [checker_bin, str(SRC_DIR / "abby")]
        if verbose:
            cmd.append("--verbose")

    print(f"Executing: {' '.join(cmd)}\n")
    proc = subprocess.run(cmd, cwd=str(PACKAGE_ROOT))
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Abby High-Velocity Test Runner")
    parser.add_argument(
        "tier",
        nargs="?",
        default="all",
        help="Tier (all, unit, integration, typecheck, arch) or specific test file/path (default: all)",
    )
    parser.add_argument(
        "-k",
        "--filter",
        help="Filter test files by substring or pattern (case-insensitive)",
    )
    parser.add_argument(
        "-x",
        "--failfast",
        action="store_true",
        help="Stop parallel test execution immediately upon first failure",
    )
    parser.add_argument(
        "-s",
        "--sequential",
        action="store_true",
        help="Run sequentially via standard unittest discovery",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=min(8, os.cpu_count() or 4),
        help="Number of parallel worker processes (default: up to 8)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose test output",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode for static type checking gate",
    )

    args = parser.parse_args()

    if args.tier == "typecheck":
        return run_typecheck(verbose=args.verbose, strict=args.strict)

    print("=" * 60)
    print(f" Abby Test Runner | Target: {args.tier} | Python {sys.version.split()[0]}")
    print("=" * 60)

    if args.sequential:
        t0 = time.perf_counter()
        code = run_sequential(args.tier, args.verbose)
        elapsed = time.perf_counter() - t0
        print(f"\nSequential run finished in {elapsed:.2f}s (exit code {code})")
        return code

    test_files = discover_test_files(args.tier, pattern_filter=args.filter)
    if not test_files:
        filter_msg = f" matching filter '{args.filter}'" if args.filter else ""
        print(f"No test files found for target '{args.tier}'{filter_msg}.")
        return 1

    print(f"Running {len(test_files)} test files across {args.workers} workers in parallel...\n")

    t_start = time.perf_counter()
    results: list[tuple[Path, int, float, str, str]] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(run_single_test_file, f, args.verbose): f
            for f in test_files
        }
        for future in concurrent.futures.as_completed(future_map):
            res = future.result()
            results.append(res)
            file_path, retcode, duration, stdout, stderr = res
            rel_name = file_path.relative_to(PACKAGE_ROOT)
            status_tag = "[PASS]" if retcode == 0 else "[FAIL]"
            print(f" {status_tag} {duration:5.2f}s : {rel_name}")
            if args.failfast and retcode != 0:
                print("\n[FAILFAST] Aborting remaining tests on first failure.")
                for pending in future_map:
                    pending.cancel()
                break


    t_total = time.perf_counter() - t_start

    failures = [r for r in results if r[1] != 0]

    print("\n" + "=" * 60)
    print(f" RESULTS: {len(results) - len(failures)} passed, {len(failures)} failed")
    print(f" Wall-clock time: {t_total:.2f}s (workers: {args.workers})")
    print("=" * 60)

    if failures:
        print("\nFAILURES:")
        for file_path, retcode, _, stdout, stderr in failures:
            print(f"\n--- {file_path.relative_to(PACKAGE_ROOT)} (exit code {retcode}) ---")
            if stdout.strip():
                print(stdout)
            if stderr.strip():
                print(stderr)
        return 1

    # Show top 5 slowest test files for optimization insights
    results.sort(key=lambda x: x[2], reverse=True)
    print("\nSlowest test files:")
    for file_path, _, dur, _, _ in results[:5]:
        print(f"  {dur:5.2f}s : {file_path.relative_to(PACKAGE_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

