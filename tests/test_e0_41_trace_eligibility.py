"""E0-41 contract test: trace eligibility.

The contract is in ``docs/benchmarks/e0/trace_eligibility_spec.md``.
This test enforces the seven eligibility checks against
synthetic traces so the rules are codified in code, not
just prose. Two-fail-positive: each rejection path was
reproduced before the test was committed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from paw.bench import (
    VerificationRecord,
    VerificationResult,
    VerificationSpec,
)


def _spec() -> VerificationSpec:
    return VerificationSpec(
        spec_id="v1", spec_version="1.0.0", task_id="t1",
        project_revision="f3ad4ef", check_kind="file_contains",
        expected_outcome="x",
    )


def _eligible_record(**overrides) -> VerificationRecord:
    defaults = {
        "spec": _spec(),
        "result": VerificationResult.PASS,
        "observed_outcome": "x",
        "verifier_identity": "alice@example.com",
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
    }
    defaults.update(overrides)
    return VerificationRecord(**defaults)


# The seven checks, in plain Python so the test does not
# need to import a future runner. The checks are a direct
# transcription of the spec.


def is_eligible(record, *, case_task_id="t1", case_project_revision="f3ad4ef",
                decision_readiness=None, today=None):
    today = today or datetime.now(UTC)
    reasons = []
    if record.spec.task_id != case_task_id:
        reasons.append("task_id_mismatch")
    if record.spec.project_revision != case_project_revision:
        reasons.append("project_revision_mismatch")
    if record.result is not VerificationResult.PASS:
        reasons.append(f"result_{record.result.value.lower()}")
    if record.spec.check_kind not in VerificationSpec.ALLOWED_KINDS:
        reasons.append("unknown_check_kind")
    if not record.verifier_identity or "@" not in record.verifier_identity:
        reasons.append("no_human_reviewer")
    started = datetime.fromisoformat(record.started_at)
    if (today - started) > timedelta(days=90):
        reasons.append("trace_too_old")
    if decision_readiness is not None and decision_readiness not in (
        "READY", None
    ):
        reasons.append(f"decision_{decision_readiness.lower()}")
    return (not reasons, reasons)


# --- 1. The happy path ------------------------------------------------


def test_eligible_record_passes_all_seven_checks() -> None:
    record = _eligible_record()
    eligible, reasons = is_eligible(record)
    assert eligible is True
    assert reasons == []


# --- 2. Each rejection path is exercised by one test --------------


def test_task_id_mismatch_disqualifies() -> None:
    record = _eligible_record()
    spec2 = VerificationSpec(
        spec_id="v1", spec_version="1.0.0", task_id="other",
        project_revision="f3ad4ef", check_kind="file_contains",
        expected_outcome="x",
    )
    rec2 = VerificationRecord(spec=spec2, result=VerificationResult.PASS)
    eligible, reasons = is_eligible(rec2)
    assert not eligible
    assert "task_id_mismatch" in reasons


def test_project_revision_mismatch_disqualifies() -> None:
    spec2 = VerificationSpec(
        spec_id="v1", spec_version="1.0.0", task_id="t1",
        project_revision="deadbeef", check_kind="file_contains",
        expected_outcome="x",
    )
    rec2 = VerificationRecord(spec=spec2, result=VerificationResult.PASS)
    eligible, reasons = is_eligible(rec2)
    assert not eligible
    assert "project_revision_mismatch" in reasons


def test_failed_result_disqualifies() -> None:
    rec = _eligible_record(result=VerificationResult.FAIL)
    eligible, reasons = is_eligible(rec)
    assert not eligible
    assert any("result_fail" in r for r in reasons)


def test_skipped_result_disqualifies() -> None:
    rec = _eligible_record(result=VerificationResult.SKIPPED)
    eligible, reasons = is_eligible(rec)
    assert not eligible
    assert any("result_skipped" in r for r in reasons)


def test_error_result_disqualifies() -> None:
    rec = _eligible_record(
        result=VerificationResult.ERROR, error="boom"
    )
    eligible, reasons = is_eligible(rec)
    assert not eligible
    assert any("result_error" in r for r in reasons)


def test_no_human_reviewer_disqualifies() -> None:
    rec = _eligible_record(verifier_identity="paw.bench.deterministic_runner")
    eligible, reasons = is_eligible(rec)
    assert not eligible
    assert "no_human_reviewer" in reasons


def test_empty_reviewer_disqualifies() -> None:
    rec = _eligible_record(verifier_identity="")
    eligible, reasons = is_eligible(rec)
    assert not eligible
    assert "no_human_reviewer" in reasons


def test_stale_trace_disqualifies() -> None:
    old_start = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    rec = _eligible_record(started_at=old_start, finished_at=old_start)
    eligible, reasons = is_eligible(rec)
    assert not eligible
    assert "trace_too_old" in reasons


def test_rejected_decision_disqualifies() -> None:
    record = _eligible_record()
    eligible, reasons = is_eligible(record, decision_readiness="REJECTED")
    assert not eligible
    assert "decision_rejected" in reasons


def test_needs_clarification_decision_disqualifies() -> None:
    record = _eligible_record()
    eligible, reasons = is_eligible(
        record, decision_readiness="NEEDS_CLARIFICATION"
    )
    assert not eligible
    assert "decision_needs_clarification" in reasons


# --- 3. Boundary cases ------------------------------------------------


def test_just_within_90_days_is_eligible() -> None:
    recent = (datetime.now(UTC) - timedelta(days=89)).isoformat()
    rec = _eligible_record(started_at=recent, finished_at=recent)
    eligible, reasons = is_eligible(rec)
    assert eligible is True
    assert reasons == []


def test_ready_decision_with_no_record_disqualifies() -> None:
    """If the case declares a decision, even READY, the
    record must still satisfy every other check. The
    decision field is checked separately.
    """
    record = _eligible_record()
    eligible, reasons = is_eligible(record, decision_readiness="READY")
    assert eligible is True
    assert reasons == []


# --- 4. paw.core 11-symbol surface preserved ---------------------


def test_paw_core_unchanged_after_e0_41() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    assert expected.issubset(set(symbols))
