"""E3-02: Rubric-based grading for E2 benchmark cases.

Verifies that evaluation primitives (E3-01) produce calibrated scores
for benchmark cases and that grading is deterministic.
"""
import pytest

from paw.core.evaluation import (
    EvidenceQuality,
    QualityLevel,
    EvaluationRubric,
    ConfidenceCalibrator,
    EvaluationResult,
    evaluate_case,
)


class TestRubricGrading:
    """E3-02: Grade benchmark cases using evaluation rubrics."""

    def test_grading_strong_evidence(self):
        """A case with complete evidence gets strong quality."""
        rubric = EvaluationRubric(
            name="gate_pass",
            evidence_kind="ledger_event",
            min_quality=QualityLevel.STRONG,
            weight=1.0,
            required_fields=("event_type", "task_id"),
        )
        evidence = {
            "kind": "ledger_event",
            "event_type": "task_completed",
            "task_id": "task_001",
            "details": {"duration_ms": 150},
        }
        quality = rubric.assess_evidence(evidence)
        assert quality.level == QualityLevel.STRONG
        assert quality.score == 1.0

    def test_grading_insufficient_evidence(self):
        """Missing evidence yields insufficient quality."""
        rubric = EvaluationRubric(
            name="gate_pass",
            evidence_kind="ledger_event",
            min_quality=QualityLevel.SUFFICIENT,
            required_fields=("event_type", "task_id"),
        )
        quality = rubric.assess_evidence({"kind": "ledger_event"})  # no fields
        assert quality.level == QualityLevel.INSUFFICIENT
        assert quality.score < 0.3

    def test_grading_uses_min_quality_threshold(self):
        """Evidence below rubric's min_quality fails the gate."""
        rubric = EvaluationRubric(
            name="strict",
            evidence_kind="policy_decision",
            min_quality=QualityLevel.STRONG,
            required_fields=("target", "value"),
        )
        # Weak evidence (50% fields) -> WEAK level, below rubric min_quality of STRONG
        evidence = {"kind": "policy_decision", "target": "blocked"}
        quality = rubric.assess_evidence(evidence)
        assert quality.level == QualityLevel.WEAK
        # Order: INSUFFICIENT < WEAK < SUFFICIENT < STRONG
        assert quality.level is not QualityLevel.STRONG

    def test_grading_deterministic(self):
        """Same input produces same grade every time."""
        rubric = EvaluationRubric(
            name="test", evidence_kind="outcome",
            min_quality=QualityLevel.SUFFICIENT,
            required_fields=("status",),
        )
        evidence = {"kind": "outcome", "status": "success", "value": 1}
        q1 = rubric.assess_evidence(evidence)
        q2 = rubric.assess_evidence(evidence)
        assert q1 == q2
        assert q1.level == q2.level
        assert q1.score == q2.score

    def test_grade_pass_aggregates_multiple_rubrics(self):
        """evaluate_case aggregates multiple rubrics for a case."""
        expected = [
            {"kind": "ledger_event", "target": "task_completed"},
            {"kind": "policy_decision", "target": "blocked"},
        ]
        observed = [
            {"kind": "ledger_event", "target": "task_completed", "value": "success"},
            {"kind": "policy_decision", "target": "blocked", "value": "DENY"},
        ]
        result = evaluate_case("bench_case_01", expected, observed)
        assert result.status == "PASS"
        assert len(result.scores) == 2
        assert len(result.qualities) == 2
        # Both strong evidence → high confidence
        assert result.calibrated_confidence > 0.5

    def test_grade_fail_when_any_rubric_insufficient(self):
        """One missing evidence type → FAIL."""
        expected = [
            {"kind": "ledger_event", "target": "task_completed"},
            {"kind": "policy_decision", "target": "blocked"},
        ]
        observed = [
            {"kind": "ledger_event", "target": "task_completed", "value": "success"},
            # policy_decision missing
        ]
        result = evaluate_case("bench_case_02", expected, observed)
        assert result.status == "FAIL"
        assert result.raw_score < 0.6

    def test_grade_calibrated_confidence_range(self):
        """Calibrated confidence is always in [0, 1]."""
        expected = [{"kind": "policy_decision", "target": "blocked"}]
        observed = [{"kind": "policy_decision", "target": "blocked", "value": "DENY"}]

        for slope in [1.0, 5.0, 10.0, 20.0]:
            cal = ConfidenceCalibrator(slope=slope, intercept=0.0)
            result = evaluate_case("case", expected, observed, calibrator=cal)
            assert 0.0 <= result.calibrated_confidence <= 1.0

    def test_grade_result_serializable(self):
        """EvaluationResult can be serialized to dict for storage."""
        expected = [{"kind": "ledger_event", "target": "done"}]
        observed = [{"kind": "ledger_event", "target": "done", "value": "ok"}]
        result = evaluate_case("case_serializable", expected, observed)
        d = result.to_dict()
        assert d["case_id"] == "case_serializable"
        assert d["status"] == "PASS"
        assert isinstance(d["scores"], dict)
        assert isinstance(d["qualities"], dict)
        assert isinstance(d["calibrated_confidence"], float)
