"""E0-09..E0-15 contract tests: minimum case set.

The seven cases here complete the E0 minimum case set
defined in EXECUTION_CHECKLIST.md (categories
defect_localization, cross_module_change, refactoring,
architecture_decision, interrupted_recovery,
privacy_negative, insufficient_context). For each case
the contract is:

1. The YAML parses + validates with 0 schema errors.
2. Every `file_contains` evidence entry passes when the
   verify command is run by hand.
3. The fixture exists and is committed at the named
   revision.
4. Every evidence entry has a reviewer tag.

The E0-16 runner will repeat step 2 inside a sandbox.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from paw.bench import (
    CaseCategory,
    case_manifest_from_dict,
    is_valid_case_manifest,
    validate_case_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = PROJECT_ROOT / "benchmarks" / "e0" / "cases"


# --- Case inventory: (case_id, expected_category) ---------------------


CASES = [
    ("defect_localization_simple_math", CaseCategory.DEFECT_LOCALIZATION),
    ("cross_module_change_constant", CaseCategory.CROSS_MODULE_CHANGE),
    ("refactor_rename_function", CaseCategory.REFACTORING),
    ("architecture_decision_cache", CaseCategory.ARCHITECTURE_DECISION),
    ("interrupted_recovery_midway", CaseCategory.INTERRUPTED_RECOVERY),
    ("privacy_negative_secret_marker", CaseCategory.PRIVACY_NEGATIVE),
    ("insufficient_context_empty_goal", CaseCategory.INSUFFICIENT_CONTEXT),
]


# --- Helpers ----------------------------------------------------------


def _case_path(case_id: str) -> Path:
    return BENCH_DIR / f"{case_id}.yaml"


def _fixture_path(case_id: str) -> Path:
    """Fixture path is the basename of the case file
    minus the category prefix; we look it up via the
    manifest's first fixture."""
    import yaml
    with _case_path(case_id).open() as f:
        data = yaml.safe_load(f)
    return PROJECT_ROOT / data["fixtures"][0]["path"]


def _load(case_id: str) -> dict:
    import yaml
    with _case_path(case_id).open() as f:
        return yaml.safe_load(f)


def _run_file_contains(fixture: Path, value: str) -> bool:
    return (
        fixture.is_file()
        and subprocess.run(
            ["grep", "-F", "-q", "--", value, str(fixture)],
            check=False,
        ).returncode
        == 0
    )


# --- 1. Static contract for every case --------------------------------


@pytest.mark.parametrize("case_id,expected_category", CASES)
def test_case_yaml_exists(case_id: str, expected_category) -> None:
    assert _case_path(case_id).is_file(), f"missing case: {case_id}"


@pytest.mark.parametrize("case_id,expected_category", CASES)
def test_case_parses_and_validates_with_zero_errors(
    case_id: str, expected_category
) -> None:
    data = _load(case_id)
    assert is_valid_case_manifest(data) is True
    errors = validate_case_manifest(data)
    assert errors == [], f"schema errors in {case_id}: {errors}"
    m = case_manifest_from_dict(data)
    assert m.case_id == case_id
    assert m.category is expected_category
    assert len(m.fixtures) >= 1
    assert len(m.expected_evidence) >= 1


@pytest.mark.parametrize("case_id,_", CASES)
def test_every_evidence_entry_has_a_reviewer(case_id: str, _) -> None:
    data = _load(case_id)
    for entry in data["expected_evidence"]:
        assert entry.get("reviewer"), (
            f"{case_id}: evidence {entry!r} has no reviewer"
        )


# --- 2. Verify commands pass for every case ---------------------------


@pytest.mark.parametrize("case_id,_", CASES)
def test_all_evidence_passes_with_committed_fixture(case_id: str, _) -> None:
    data = _load(case_id)
    fixture = _fixture_path(case_id)
    for entry in data["expected_evidence"]:
        if entry["kind"] == "file_contains":
            assert _run_file_contains(fixture, entry["value"]) is True, (
                f"{case_id}: file_contains for {entry['value']!r} failed"
            )


# --- 3. Cross-checks ---------------------------------------------------


def test_every_case_targets_a_real_fixture() -> None:
    """Each case's first fixture must exist on disk at the
    current revision.
    """
    for case_id, _ in CASES:
        data = _load(case_id)
        fixture_rel = data["fixtures"][0]["path"]
        fixture_abs = PROJECT_ROOT / fixture_rel
        assert fixture_abs.is_file(), (
            f"{case_id}: fixture {fixture_rel} does not exist"
        )


def test_every_case_has_a_distinct_case_id() -> None:
    """Two cases with the same id would silently merge."""
    ids = [c[0] for c in CASES]
    assert len(set(ids)) == len(ids), f"duplicate case ids: {ids}"


def test_every_case_picks_a_different_category() -> None:
    """E0-08..E0-15 must cover the seven minimum categories."""
    cats = [c[1] for c in CASES]
    assert len(set(cats)) == len(cats), f"duplicate categories: {cats}"


# --- 4. paw.core 11-symbol surface preserved ---------------------------


def test_paw_core_public_surface_unchanged_after_e0_09_15() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected_runtime = {
        "AutonomyDecision",
        "Capability",
        "ExecutionObservation",
        "PawRuntime",
        "PolicyDecision",
        "ProposedAction",
        "ResourceUsage",
        "RuntimeOutcome",
        "StopReason",
        "TaskResult",
        "TaskStatus",
    }
    assert expected_runtime.issubset(set(symbols))
