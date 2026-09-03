"""E0-42 contract test: validated edge case (challenging input).

The E0-42 acceptance criterion is: the runner can
score a case whose fixture is the smallest valid
input. The contract is:

1. The edge case file exists at the named path.
2. The case parses + validates with 0 schema errors.
3. The runner produces a deterministic outcome for
   the edge case (PASS, FAIL, or UNSAFE; never a crash).
4. The edge case exercises a "missing evidence" path:
   the fixture does not contain every expected
   substring, so the runner must report FAILURE
   rather than silently producing SUCCESS.
5. The case has a reviewer on every evidence entry.
6. The runner's output is reproducible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.bench import load_case, run_case, validate_case_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EDGE_CASE_PATH = PROJECT_ROOT / "benchmarks" / "e0" / "cases" / "repo_understand_empty_repo.yaml"
EDGE_FIXTURE_PATH = PROJECT_ROOT / "benchmarks" / "e0" / "fixtures" / "edge_case_empty_repo.txt"


# --- 1. Static contract -----------------------------------------------


def test_edge_case_file_exists() -> None:
    assert EDGE_CASE_PATH.is_file(), (
        f"missing edge case: {EDGE_CASE_PATH}"
    )


def test_edge_fixture_file_exists() -> None:
    assert EDGE_FIXTURE_PATH.is_file(), (
        f"missing edge fixture: {EDGE_FIXTURE_PATH}"
    )


def test_edge_case_yaml_parses_and_validates() -> None:
    import yaml
    with EDGE_CASE_PATH.open() as f:
        data = yaml.safe_load(f)
    errors = validate_case_manifest(data)
    assert errors == [], f"schema errors: {errors}"
    m = load_case(EDGE_CASE_PATH)
    assert m.case_id == "repo_understand_empty_repo"
    assert m.category.value == "repo_understanding"
    assert m.privacy_class.value == "workspace"


def test_every_evidence_has_a_reviewer() -> None:
    import yaml
    with EDGE_CASE_PATH.open() as f:
        data = yaml.safe_load(f)
    for entry in data["expected_evidence"]:
        assert entry.get("reviewer"), (
            f"evidence {entry!r} has no reviewer"
        )


# --- 2. Edge-case behavior: the runner must NOT silently PASS ---


def test_edge_case_produces_failure_not_silent_success() -> None:
    """The edge fixture is intentionally missing one of
    the expected substrings. The runner must report
    ``FAILURE`` (not ``SUCCESS``); a silent ``SUCCESS``
    would be a runner bug.
    """
    manifest = load_case(EDGE_CASE_PATH)
    result = run_case(manifest, project_root=PROJECT_ROOT, seed="e0-42")
    assert len(result.rows) == 1
    assert result.rows[0].outcome == "FAILURE", (
        f"edge case produced {result.rows[0].outcome}; "
        f"the runner must report FAILURE for a missing "
        f"evidence entry"
    )
    assert result.rows[0].passed_evidence < result.rows[0].total_evidence, (
        "edge case scored all evidence as PASS; the "
        "fixture was supposed to be missing one substring"
    )


# --- 3. Edge case is reproducible -------------------------------


def test_edge_case_is_reproducible() -> None:
    manifest = load_case(EDGE_CASE_PATH)
    r1 = run_case(
        manifest, project_root=PROJECT_ROOT, runs=1, seed="edge",
        deterministic_timestamps=True,
    )
    r2 = run_case(
        manifest, project_root=PROJECT_ROOT, runs=1, seed="edge",
        deterministic_timestamps=True,
    )
    assert r1.rows[0].to_jsonl() == r2.rows[0].to_jsonl()


# --- 4. The runner does not crash on a tiny fixture ---------------


def test_runner_does_not_crash_on_tiny_fixture() -> None:
    """The edge-case fixture is the smallest valid input
    the runner accepts; if the runner crashes here,
    it is a regression.
    """
    manifest = load_case(EDGE_CASE_PATH)
    # The runner must return a CaseRunResult, not raise.
    result = run_case(manifest, project_root=PROJECT_ROOT, seed="e0-42")
    assert result is not None
    assert hasattr(result, "rows")
    assert len(result.rows) == 1


# --- 5. paw.core 11-symbol surface preserved ---------------------


def test_paw_core_unchanged_after_e0_42() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    assert expected.issubset(set(symbols))
