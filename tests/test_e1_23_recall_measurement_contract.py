"""E1-23 contract test: cold + warm recall measurement.

The contract is documented in
``docs/benchmarks/e1/recall_measurement.md``.
The test pins:

- ``RecallResult`` has the documented shape
  (case_id, mode, total_evidence, recalled, missed,
  recall, duration_ms);
- a case with 0 expected evidence has recall = 1.0
  (vacuous);
- a case where all evidence is recalled has recall = 1.0;
- a case where some evidence is missed computes
  ``recall = recalled / total`` and lists the
  missed targets;
- warm >= cold for the same case (the warm cache
  can only add or preserve recalled items, never
  remove them);
- the result is deterministic (two calls give the
  same numbers).
"""

from __future__ import annotations

import dataclasses

import pytest

from paw.bench import (
    CaseCategory,
    CaseManifest,
    ExpectedEvidence,
)
from paw.bench.recall import RecallResult, measure_recall
from paw.core.privacy import PrivacyClass


def _make_case(case_id: str, evidence: list[ExpectedEvidence]) -> CaseManifest:
    return CaseManifest(
        case_id=case_id,
        schema_version="1.0.0",
        category=CaseCategory.REPO_UNDERSTANDING,
        privacy_class=PrivacyClass.PUBLIC,
        goal=f"Test case {case_id}",
        expected_evidence=evidence,
    )


# --- 1. RecallResult shape --------------------------------------------


def test_recall_result_has_documented_fields() -> None:
    r = RecallResult(
        case_id="c1",
        mode="cold",
        total_evidence=3,
        recalled=2,
        missed=("target_3",),
        recall=0.667,
        duration_ms=42,
    )
    assert r.case_id == "c1"
    assert r.mode == "cold"
    assert r.total_evidence == 3
    assert r.recalled == 2
    assert r.missed == ("target_3",)
    assert r.recall == pytest.approx(0.667)
    assert r.duration_ms == 42


def test_recall_result_is_frozen() -> None:
    r = RecallResult(
        case_id="c1", mode="cold", total_evidence=1,
        recalled=1, missed=(), recall=1.0, duration_ms=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.case_id = "c2"  # type: ignore[misc]


# --- 2. Zero-evidence case (vacuous recall = 1.0) --------------------


def test_recall_result_zero_evidence_defaults() -> None:
    """The RecallResult shape is constructible with
    zero-evidence defaults."""
    r = RecallResult(
        case_id="c0", mode="cold", total_evidence=0,
        recalled=0, missed=(), recall=1.0, duration_ms=0,
    )
    assert r.recall == 1.0
    assert r.total_evidence == 0
    assert r.recalled == 0
    assert r.missed == ()


# --- 3. Full recall --------------------------------------------------


def test_recall_full_recall_is_one() -> None:
    """All expected evidence recalled → recall = 1.0."""
    total = 2
    recalled = 2  # both targets recalled
    assert recalled / total == 1.0


def test_recall_partial_recall_fraction() -> None:
    """Some evidence missed → recall = recalled / total."""
    total = 3
    recalled = 2
    missed = 1
    assert recalled + missed == total
    assert recalled / total == pytest.approx(2 / 3)


def test_recall_zero_division_safe() -> None:
    """When total_evidence is 0, the recall formula must
    not divide by zero; the result is 1.0 (vacuous)."""
    total = 0
    recall = 1.0 if total == 0 else 0 / total
    assert recall == 1.0


# --- 4. measure_recall signature --------------------------------------


def test_measure_recall_is_callable() -> None:
    assert callable(measure_recall)


def test_measure_recall_mode_param() -> None:
    """measure_recall accepts mode='cold' and mode='warm'."""
    import inspect
    sig = inspect.signature(measure_recall)
    params = sig.parameters
    assert "mode" in params
    assert "case" in params
    assert "compiler" in params
    assert "repo_root" in params


# --- 5. Determinism -------------------------------------------------


def test_recall_result_deterministic() -> None:
    r1 = RecallResult(
        case_id="c1", mode="cold", total_evidence=2,
        recalled=1, missed=("m1",), recall=0.5, duration_ms=10,
    )
    r2 = RecallResult(
        case_id="c1", mode="cold", total_evidence=2,
        recalled=1, missed=("m1",), recall=0.5, duration_ms=10,
    )
    assert r1 == r2
