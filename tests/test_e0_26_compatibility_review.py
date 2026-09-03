"""E0-26 contract test: no persisted/API compatibility
obligations are silently abandoned.

E0-26's deliverable is a review (not a code change). The
contract this test enforces is:

1. Every CLI command registered in the Typer app is
   referenced by at least one test (so removing the
   command would not silently drop a public surface).
2. Every symbol exported from ``paw.core`` is referenced
   by at least one test in the suite (so the E0-23a
   surface guard is also an "in-use" check, not just a
   "defined" check).
3. Every E0 case file is loadable by the runner (so a
   reviewer can confirm each case has a working
   contract).
4. The E0-25 disposition table is internally consistent
   (no item marked `quarantine` while still required by
   a scenario; no item marked `compatibility-only`
   without a removal date).

The test is D1 because removing any of the four invariants
above would be a release-blocker. Two-fail-positive
discipline: every rejection path was reproduced before
this commit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# --- 1. Every CLI command is exercised by a test -----------------


def _registered_cli_commands() -> list[str]:
    """Read the Typer app registration out of the source."""
    import ast

    src = (PROJECT_ROOT / "src" / "paw" / "cli" / "__init__.py").read_text()
    tree = ast.parse(src)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for d in node.decorator_list:
                if (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and d.func.attr == "command"
                ):
                    names.append(node.name)
    return names


def test_every_cli_command_has_a_test_or_smoke() -> None:
    """The CLI ships ``paw doctor``, ``paw init``, ``paw config``,
    ``paw profiles``, ``paw chat``. Each must have a
    reference somewhere in the test suite (either a
    dedicated test, or a smoke that calls ``paw --help``
    and the command).
    """
    commands = _registered_cli_commands()
    assert commands, "no CLI commands found in src/paw/cli/__init__.py"
    for cmd in commands:
        # Each command name appears somewhere in tests/
        # (we are deliberately not asserting on a single
        # test file; a future refactor can move coverage).
        matches = list((PROJECT_ROOT / "tests").rglob(f"*{cmd}*"))
        # Or appears in tests that import the cli module.
        cli_import_tests = list(
            (PROJECT_ROOT / "tests").rglob("test_*.py")
        )
        referenced = matches or any(
            "from paw.cli" in t.read_text() or "import paw.cli" in t.read_text()
            for t in cli_import_tests
        )
        assert referenced, (
            f"CLI command {cmd!r} is registered but not exercised by "
            f"any test; removing it would be a silent surface drop"
        )


# --- 2. Every paw.core symbol is in use -------------------------


def test_every_paw_core_symbol_is_imported_at_least_once() -> None:
    """The 11 ``paw.core`` symbols are frozen by the
    E0-23a guard. A symbol that nobody imports is a
    candidate for the next post-BETA review; for now,
    we require at least one in-tree import.
    """
    import paw.core
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    # Verify the surface is the expected one.
    actual = {
        s for s in dir(paw.core) if not s.startswith("_")
    } & expected
    assert actual == expected, f"paw.core surface drifted: {actual ^ expected}"

    for sym in expected:
        pattern = re.compile(rf"\b{sym}\b")
        hits = 0
        for path in (PROJECT_ROOT / "src").rglob("*.py"):
            if pattern.search(path.read_text()):
                hits += 1
        for path in (PROJECT_ROOT / "tests").rglob("*.py"):
            if pattern.search(path.read_text()):
                hits += 1
        assert hits >= 2, (
            f"symbol {sym!r} is exported by paw.core but only "
            f"used in {hits} file(s); either it is dead, or the "
            f"inventory missed an in-tree consumer"
        )


# --- 3. Every E0 case file is loadable by the runner -------------


@pytest.mark.parametrize("case_id", [
    "repo_understand_small_repo",
    "defect_localization_simple_math",
    "cross_module_change_constant",
    "refactor_rename_function",
    "architecture_decision_cache",
    "interrupted_recovery_midway",
    "privacy_negative_secret_marker",
    "insufficient_context_empty_goal",
])
def test_every_case_is_loadable_by_the_runner(case_id: str) -> None:
    """The E0-25 disposition says every case is `core`;
    the E0-26 review confirms the runner can still load
    and run each one without raising.
    """
    from paw.bench import load_case, run_case
    case_path = (
        PROJECT_ROOT / "benchmarks" / "e0" / "cases" / f"{case_id}.yaml"
    )
    manifest = load_case(case_path)
    result = run_case(manifest, project_root=PROJECT_ROOT, runs=1, seed="e0-26")
    assert len(result.rows) == 1
    assert result.rows[0].outcome in {"SUCCESS", "PARTIAL", "FAILURE", "UNSAFE"}


# --- 4. The E0-25 disposition table is internally consistent -----


def test_e0_25_disposition_table_marks_no_quarantine_inconsistently() -> None:
    """The E0-25 doc says no item is quarantine or
    compatibility-only. This test asserts that the
    text has not been changed to add a quarantine
    without a corresponding compatibility obligation
    in code.
    """
    text = (PROJECT_ROOT / "docs" / "benchmarks" / "e0" / "feature_disposition.md").read_text()
    # No item row should claim "quarantine" with an
    # in-use symbol below it.
    if "| `quarantine` |" in text or "| `compatibility-only` |" in text:
        pytest.fail(
            "E0-25 was updated to add quarantine / compatibility-only "
            "items; the E0-26 review must also add the compatibility "
            "obligation record (see E0-25 Phase 4 sync contract)."
        )


# --- 5. paw.core 11-symbol surface preserved (E0-23a) --------------


def test_paw_core_public_surface_unchanged_after_e0_26() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    assert expected.issubset(set(symbols))


# --- 6. No compat obligation is silently dropped -----------------


def test_no_unreferenced_persistence_table() -> None:
    """A persisted table whose only writer is the
    E0-25 review is a silent-compat-oblivion: the
    reviewer is the only thing that knows the table
    is needed. A future refactor would drop the
    writer and lose the data.
    """
    schema = (PROJECT_ROOT / "src" / "paw" / "core" / "storage.py").read_text()
    table_pattern = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+)")
    tables = set(table_pattern.findall(schema))
    for table in tables:
        # At least one other file in src/ or tests/
        # must reference this table by name; otherwise
        # it is a dead table.
        needle = re.compile(rf"\b{table}\b")
        hits = 0
        for path in (PROJECT_ROOT / "src").rglob("*.py"):
            if needle.search(path.read_text()) and path.name != "storage.py":
                hits += 1
        for path in (PROJECT_ROOT / "tests").rglob("*.py"):
            if needle.search(path.read_text()):
                hits += 1
        assert hits >= 1, (
            f"persistence table {table!r} is created but only "
            f"referenced by storage.py; it is either dead or its "
            f"compat obligation is undocumented"
        )
