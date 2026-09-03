"""E0-39 contract test: VerificationSpec + VerificationRecord.

The two types are the E0 architecture Layer 2. They
must:

1. Carry every field named in the E0-38 spec.
2. Reject malformed values at construction time.
3. ``SKIPPED`` is never reported as ``is_pass()``.
4. ``error`` is set iff ``result=ERROR``.
5. ``make_spec_from_evidence`` converts an
   ``ExpectedEvidence`` entry into a spec the future
   runner can consume.
6. The JSONL row carries every field; reviewer can
   cross-check the record against the spec without
   consulting the source.
7. ``paw.core`` still exports 11 runtime symbols (no
   second result model leaked into the runtime
   surface).
"""

from __future__ import annotations

import json

import pytest

from paw.bench import (
    CASE_MANIFEST_SCHEMA_VERSION,
    CaseCategory,
    ExpectedEvidence,
    FixtureRef,
    PrivacyClass,
    VerificationRecord,
    VerificationResult,
    VerificationSpec,
    make_spec_from_evidence,
)


# --- 1. Happy path -----------------------------------------------------


def test_spec_accepts_minimal_fields() -> None:
    spec = VerificationSpec(
        spec_id="v1",
        spec_version="1.0.0",
        task_id="t1",
        project_revision="f3ad4ef",
        check_kind="file_contains",
        expected_outcome="src/<package_name>/core.py",
    )
    assert spec.spec_id == "v1"
    assert spec.timeout_seconds == 60
    assert spec.privacy_requirements == "workspace"


def test_record_is_pass_only_for_pass() -> None:
    spec = VerificationSpec(
        spec_id="v1", spec_version="1.0.0", task_id="t1",
        project_revision="f3ad4ef", check_kind="file_contains",
        expected_outcome="x",
    )
    for r, expected in [
        (VerificationResult.PASS, True),
        (VerificationResult.FAIL, False),
        (VerificationResult.ERROR, False),
        (VerificationResult.SKIPPED, False),
    ]:
        rec = VerificationRecord(spec=spec, result=r)
        assert rec.is_pass() is expected, (
            f"result={r.value} is_pass() should be {expected}"
        )


def test_error_set_iff_result_error() -> None:
    spec = VerificationSpec(
        spec_id="v1", spec_version="1.0.0", task_id="t1",
        project_revision="f3ad4ef", check_kind="file_contains",
        expected_outcome="x",
    )
    # error with non-ERROR result is rejected.
    with pytest.raises(ValueError, match="error"):
        VerificationRecord(spec=spec, result=VerificationResult.PASS, error="boom")
    # error with ERROR result is allowed.
    rec = VerificationRecord(spec=spec, result=VerificationResult.ERROR, error="boom")
    assert rec.error == "boom"


# --- 2. Spec validation ----------------------------------------------


def test_spec_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="check_kind"):
        VerificationSpec(
            spec_id="v1", spec_version="1.0.0", task_id="t1",
            project_revision="f3ad4ef", check_kind="magic",
            expected_outcome="x",
        )


def test_spec_rejects_empty_spec_id() -> None:
    with pytest.raises(ValueError, match="spec_id"):
        VerificationSpec(
            spec_id="", spec_version="1.0.0", task_id="t1",
            project_revision="f3ad4ef", check_kind="file_contains",
            expected_outcome="x",
        )


def test_spec_rejects_empty_project_revision() -> None:
    with pytest.raises(ValueError, match="project_revision"):
        VerificationSpec(
            spec_id="v1", spec_version="1.0.0", task_id="t1",
            project_revision="", check_kind="file_contains",
            expected_outcome="x",
        )


def test_spec_rejects_non_semver_version() -> None:
    with pytest.raises(ValueError, match="semantic version"):
        VerificationSpec(
            spec_id="v1", spec_version="not-a-version", task_id="t1",
            project_revision="f3ad4ef", check_kind="file_contains",
            expected_outcome="x",
        )


def test_spec_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="timeout"):
        VerificationSpec(
            spec_id="v1", spec_version="1.0.0", task_id="t1",
            project_revision="f3ad4ef", check_kind="file_contains",
            expected_outcome="x", timeout_seconds=0,
        )


# --- 3. Result parsing ------------------------------------------------


def test_result_parse_strict() -> None:
    assert VerificationResult.parse("PASS") is VerificationResult.PASS
    assert VerificationResult.parse("SKIPPED") is VerificationResult.SKIPPED
    with pytest.raises(ValueError, match="unknown verification result"):
        VerificationResult.parse("MAYBE")


# --- 4. make_spec_from_evidence -------------------------------------


def test_make_spec_from_evidence_for_file_contains() -> None:
    ev = ExpectedEvidence(
        kind="file_contains",
        target="benchmarks/e0/fixtures/small_repo_tree.txt",
        value="src/<package_name>/core.py",
        reviewer="alice@example.com",
    )
    spec = make_spec_from_evidence(
        spec_id="v1",
        case_id="case_a",
        project_revision="f3ad4ef",
        kind=ev.kind,
        target=ev.target,
        expected_value=ev.value,
    )
    assert spec.check_kind == "file_contains"
    assert spec.expected_outcome == "src/<package_name>/core.py"
    assert spec.evidence_paths == ["benchmarks/e0/fixtures/small_repo_tree.txt"]
    assert "FILESYSTEM_READ" in spec.capability_requirements


def test_make_spec_from_evidence_for_command_exit() -> None:
    spec = make_spec_from_evidence(
        spec_id="v1",
        case_id="case_a",
        project_revision="f3ad4ef",
        kind="command_exit",
        target='["true"]',
        expected_value="0",
    )
    assert spec.check_kind == "command_exit"
    assert spec.evidence_paths == ['["true"]']
    # Command-exit does not need FILESYSTEM_READ.
    assert "FILESYSTEM_READ" not in spec.capability_requirements


# --- 5. JSONL round-trip --------------------------------------------


def test_record_to_jsonl_roundtrip() -> None:
    spec = VerificationSpec(
        spec_id="v1", spec_version="1.0.0", task_id="t1",
        project_revision="f3ad4ef", check_kind="file_contains",
        expected_outcome="x",
    )
    rec = VerificationRecord(
        spec=spec, result=VerificationResult.PASS,
        observed_outcome="x", observed_output="matched at line 5",
    )
    line = rec.to_jsonl()
    parsed = json.loads(line)
    assert parsed["spec"]["spec_id"] == "v1"
    assert parsed["result"] == "PASS"
    assert parsed["observed_outcome"] == "x"
    assert parsed["observed_output"] == "matched at line 5"


# --- 6. No second result model in paw.core -----------------------


def test_paw_core_unchanged_after_e0_39() -> None:
    """E0-39 must not introduce a second result model in
    the runtime surface.
    """
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    assert expected.issubset(set(symbols))
    # The new types live in paw.bench, not paw.core.
    assert "VerificationRecord" not in symbols
    assert "VerificationSpec" not in symbols
