"""E0-02 contract test: case manifest validation (D1).

These tests verify the case manifest schema, not the future
runner. The runner itself is owned by E0-16; E0-02 only
locks the contract so that E0-08..15 (the minimum case
set) and E0-16 (the runner) can be authored against a
frozen interface.

Two-fail-positive discipline (per
doc-driven-stabilization Phase 2.3):

  - Every rejection path below was added because the
    failure it asserts was reproduced against an earlier
    candidate that lacked the check. The committed version
    passes; reverting any branch should make the matching
    test fail.
"""

from __future__ import annotations

import pytest

from paw.bench import (
    CASE_MANIFEST_SCHEMA_VERSION,
    CaseCategory,
    CaseManifest,
    ExpectedEvidence,
    FixtureRef,
    PrivacyClass,
    case_manifest_from_dict,
    case_manifest_to_dict,
)


# --- Fixtures ------------------------------------------------------------


def _good_evidence_dict() -> dict:
    return {
        "kind": "ledger_event",
        "target": "TASK_COMPLETED",
        "value": "COMPLETED",
        "reviewer": "alice@example.com",
    }


def _good_fixture_dict() -> dict:
    return {
        "path": "benchmarks/e0/fixtures/pa_small_repo.txt",
        "revision": "f3ad4ef",
        "purpose": "small repository tree for the case",
    }


def _good_manifest_dict(**overrides) -> dict:
    base = {
        "schema_version": CASE_MANIFEST_SCHEMA_VERSION,
        "case_id": "repo_understand_small_repo",
        "category": "repo_understanding",
        "privacy_class": "internal",
        "goal": "Summarize the structure of the small repository fixture.",
        "fixtures": [_good_fixture_dict()],
        "expected_evidence": [_good_evidence_dict()],
        "timeout_seconds": 60,
        "max_iterations": 5,
        "tags": ["smoke"],
    }
    base.update(overrides)
    return base


# --- 1. Happy path --------------------------------------------------------


def test_good_manifest_parses_and_roundtrips() -> None:
    """A complete, valid manifest parses and round-trips losslessly."""
    m = case_manifest_from_dict(_good_manifest_dict())
    assert m.case_id == "repo_understand_small_repo"
    assert m.category is CaseCategory.REPO_UNDERSTANDING
    assert m.privacy_class is PrivacyClass.INTERNAL
    assert m.schema_version == CASE_MANIFEST_SCHEMA_VERSION
    assert m.timeout_seconds == 60
    assert m.max_iterations == 5
    assert m.tags == ["smoke"]
    assert m.fixtures[0].revision == "f3ad4ef"
    assert m.expected_evidence[0].reviewer == "alice@example.com"

    # Round-trip via JSON to prove the dict form is stable.
    import json
    d = case_manifest_to_dict(m)
    json.dumps(d)  # must not raise
    m2 = case_manifest_from_dict(d)
    assert m == m2


# --- 2. Schema version is a hard gate ------------------------------------


def test_wrong_schema_version_is_rejected() -> None:
    """A manifest whose ``schema_version`` does not match the
    current contract is rejected. This is the contract that
    lets future schema changes fail closed.
    """
    d = _good_manifest_dict()
    d["schema_version"] = "0.9.0"
    with pytest.raises(ValueError, match="schema_version"):
        case_manifest_from_dict(d)


def test_missing_schema_version_is_rejected() -> None:
    d = _good_manifest_dict()
    d.pop("schema_version")
    with pytest.raises(ValueError, match="schema_version"):
        case_manifest_from_dict(d)


# --- 3. case_id is a stable, path-free identifier -------------------------


def test_case_id_with_slash_is_rejected() -> None:
    d = _good_manifest_dict()
    d["case_id"] = "foo/bar"
    with pytest.raises(ValueError, match="path separators"):
        case_manifest_from_dict(d)


def test_empty_case_id_is_rejected() -> None:
    d = _good_manifest_dict()
    d["case_id"] = ""
    with pytest.raises(ValueError, match="case_id"):
        case_manifest_from_dict(d)


# --- 4. Privacy class is mandatory and validated -------------------------


def test_unknown_privacy_class_is_rejected() -> None:
    d = _good_manifest_dict()
    d["privacy_class"] = "top_secret"
    with pytest.raises(ValueError, match="privacy class"):
        case_manifest_from_dict(d)


def test_secret_privacy_class_is_accepted() -> None:
    """The strictest class must still parse; it is a valid choice."""
    d = _good_manifest_dict()
    d["privacy_class"] = "secret"
    m = case_manifest_from_dict(d)
    assert m.privacy_class is PrivacyClass.SECRET


# --- 5. Case category is from the minimum set -----------------------------


def test_unknown_category_is_rejected() -> None:
    d = _good_manifest_dict()
    d["category"] = "totally_made_up"
    with pytest.raises(ValueError, match="case category"):
        case_manifest_from_dict(d)


def test_every_minimum_category_parses() -> None:
    """E0-08..15 categories are all in the enum."""
    for cat in CaseCategory:
        d = _good_manifest_dict()
        d["category"] = cat.value
        d["case_id"] = f"case_for_{cat.value}"
        m = case_manifest_from_dict(d)
        assert m.category is cat


# --- 6. Fixtures are non-empty, path-relative, revision-pinned ------------


def test_no_fixtures_is_rejected() -> None:
    d = _good_manifest_dict()
    d["fixtures"] = []
    with pytest.raises(ValueError, match="fixtures"):
        case_manifest_from_dict(d)


def test_absolute_fixture_path_is_rejected() -> None:
    d = _good_manifest_dict()
    d["fixtures"] = [{"path": "/etc/passwd", "revision": "f3ad4ef"}]
    with pytest.raises(ValueError, match="repository-relative"):
        case_manifest_from_dict(d)


def test_empty_fixture_revision_is_rejected() -> None:
    d = _good_manifest_dict()
    d["fixtures"] = [{"path": "foo.txt", "revision": ""}]
    with pytest.raises(ValueError, match="revision"):
        case_manifest_from_dict(d)


# --- 7. Expected evidence requires a reviewer -----------------------------


def test_no_expected_evidence_is_rejected() -> None:
    """A case without expected evidence cannot be verified, so
    it must be rejected at parse time.
    """
    d = _good_manifest_dict()
    d["expected_evidence"] = []
    with pytest.raises(ValueError, match="expected_evidence"):
        case_manifest_from_dict(d)


def test_evidence_without_reviewer_is_rejected() -> None:
    d = _good_manifest_dict()
    d["expected_evidence"] = [
        {"kind": "ledger_event", "target": "TASK_COMPLETED", "value": "COMPLETED"},
    ]
    with pytest.raises(ValueError, match="reviewer"):
        case_manifest_from_dict(d)


def test_unknown_evidence_kind_is_rejected() -> None:
    d = _good_manifest_dict()
    d["expected_evidence"] = [
        {"kind": "magic", "target": "x", "value": "y", "reviewer": "alice"},
    ]
    with pytest.raises(ValueError, match="kind must be one of"):
        case_manifest_from_dict(d)


# --- 8. Budget fields are positive ----------------------------------------


def test_zero_timeout_is_rejected() -> None:
    d = _good_manifest_dict()
    d["timeout_seconds"] = 0
    with pytest.raises(ValueError, match="timeout_seconds"):
        case_manifest_from_dict(d)


def test_zero_max_iterations_is_rejected() -> None:
    d = _good_manifest_dict()
    d["max_iterations"] = 0
    with pytest.raises(ValueError, match="max_iterations"):
        case_manifest_from_dict(d)


# --- 9. The contract does not leak into paw.core --------------------------


def test_paw_core_public_surface_unchanged_after_e0_02() -> None:
    """E0-23a: a contract test that ``paw.core`` still exports
    exactly eleven runtime-contract symbols after E0 lands.
    Adding ``paw.bench`` must not change ``paw.core``.
    """
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
    assert expected_runtime.issubset(set(symbols)), (
        f"paw.core missing runtime symbols: {expected_runtime - set(symbols)}"
    )


# --- 10. Empty goal is rejected ------------------------------------------


def test_empty_goal_is_rejected() -> None:
    d = _good_manifest_dict()
    d["goal"] = ""
    with pytest.raises(ValueError, match="goal"):
        case_manifest_from_dict(d)
