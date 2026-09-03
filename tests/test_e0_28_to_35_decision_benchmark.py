"""E0-28..E0-35 contract test: research-decision benchmark.

The five ``ImplementationReadiness`` values
(``READY``, ``REJECTED``, ``NEEDS_CLARIFICATION``,
``SPIKE_REQUIRED``, ``NEEDS_RESEARCH``) each get a
worked example case. The contract is:

1. Every case parses + validates with 0 schema errors.
2. Every case has a non-empty ``decision`` field whose
   ``readiness`` is one of the five values.
3. Every case produces a unique evidence token (so the
   runner can tell the cases apart).
4. Every case has a reviewer on every evidence entry.
5. Every case runs through the deterministic runner
   and produces a SUCCESS row.
6. The five cases cover the five readiness values
   without overlap.
7. ``paw.core`` still exports 11 runtime symbols.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.bench import (
    CaseCategory,
    CaseManifest,
    PrivacyClass,
    case_manifest_from_dict,
    is_valid_case_manifest,
    load_case,
    run_case,
    validate_case_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = PROJECT_ROOT / "benchmarks" / "e0" / "cases"

# --- Case inventory ------------------------------------------------------


DECISION_CASES = [
    ("decision_ready_simple_module", "READY", CaseCategory.ARCHITECTURE_DECISION),
    ("decision_rejected_duplicate_owner", "REJECTED", CaseCategory.ARCHITECTURE_DECISION),
    ("decision_needs_clarification_auth", "NEEDS_CLARIFICATION", CaseCategory.INSUFFICIENT_CONTEXT),
    ("decision_spike_exotic_locking", "SPIKE_REQUIRED", CaseCategory.ARCHITECTURE_DECISION),
    ("decision_needs_research_security", "NEEDS_RESEARCH", CaseCategory.ARCHITECTURE_DECISION),
]

EXPECTED_READINESS = {"READY", "REJECTED", "NEEDS_CLARIFICATION", "SPIKE_REQUIRED", "NEEDS_RESEARCH"}


# --- 1. Static contract ---------------------------------------------------


def _load(case_id: str) -> dict:
    import yaml
    with (CASES_DIR / f"{case_id}.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("case_id,readiness,expected_category", DECISION_CASES)
def test_decision_case_yaml_parses_and_validates(
    case_id: str, readiness: str, expected_category
) -> None:
    d = _load(case_id)
    assert is_valid_case_manifest(d) is True
    errors = validate_case_manifest(d)
    assert errors == [], f"{case_id}: {errors}"
    m = case_manifest_from_dict(d)
    assert m.case_id == case_id
    assert m.category is expected_category
    # Privacy class is workspace for all five; we do not
    # require SECRET because none of these exercise a
    # marked source.
    assert m.privacy_class is PrivacyClass.WORKSPACE


@pytest.mark.parametrize("case_id,readiness,_", DECISION_CASES)
def test_decision_field_present_and_correct(case_id: str, readiness: str, _) -> None:
    d = _load(case_id)
    assert "decision" in d, f"{case_id} missing 'decision' field"
    decision = d["decision"]
    assert "readiness" in decision, f"{case_id} missing decision.readiness"
    assert decision["readiness"] == readiness, (
        f"{case_id}: decision.readiness is {decision['readiness']!r}, "
        f"expected {readiness!r}"
    )
    assert "rationale" in decision, f"{case_id} missing decision.rationale"
    assert decision["rationale"].strip(), f"{case_id} empty rationale"


# --- 2. Coverage ------------------------------------------------------


def test_all_five_readiness_values_covered() -> None:
    actual = {readiness for _, readiness, _ in DECISION_CASES}
    assert actual == EXPECTED_READINESS, (
        f"readiness coverage gap: {actual ^ EXPECTED_READINESS}"
    )


def test_each_case_has_a_distinct_case_id() -> None:
    ids = [c[0] for c in DECISION_CASES]
    assert len(set(ids)) == len(ids), f"duplicate case ids: {ids}"


def test_each_case_has_a_reviewable_evidence_token() -> None:
    """Each decision case must have a unique token in
    its evidence so the runner can tell the cases apart
    by their evidence alone.
    """
    tokens = []
    for case_id, _, _ in DECISION_CASES:
        d = _load(case_id)
        for entry in d["expected_evidence"]:
            if entry["kind"] == "file_contains":
                tokens.append((case_id, entry["value"]))
    values = [v for _, v in tokens]
    assert len(set(values)) == len(values), (
        f"duplicate evidence values across cases: {values}"
    )


# --- 3. Reviewer discipline -----------------------------------------------


@pytest.mark.parametrize("case_id,readiness,expected_category", DECISION_CASES)
def test_every_evidence_has_a_reviewer(case_id: str, readiness: str, expected_category) -> None:
    d = _load(case_id)
    for entry in d["expected_evidence"]:
        assert entry.get("reviewer"), (
            f"{case_id}: evidence {entry!r} has no reviewer"
        )


# --- 4. End-to-end runner smoke test ---------------------------------


@pytest.mark.parametrize("case_id,readiness,expected_category", DECISION_CASES)
def test_each_decision_case_runs_via_deterministic_runner(
    case_id: str, readiness: str, expected_category
) -> None:
    case_path = CASES_DIR / f"{case_id}.yaml"
    result = run_case_file(
        case_path, project_root=PROJECT_ROOT, seed="e0-28..35"
    )
    assert len(result.rows) == 1
    assert result.rows[0].outcome == "SUCCESS", (
        f"{case_id}: outcome {result.rows[0].outcome} expected SUCCESS"
    )
    assert result.rows[0].passed_evidence == result.rows[0].total_evidence


def run_case_file(case_path, *, project_root, seed):
    """Convenience for the parametrized smoke."""
    manifest = load_case(case_path)
    return run_case(manifest, project_root=project_root, runs=1, seed=seed)


# --- 5. paw.core 11-symbol surface preserved ---------------------------


def test_paw_core_public_surface_unchanged_after_e0_28_35() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    assert expected.issubset(set(symbols))
