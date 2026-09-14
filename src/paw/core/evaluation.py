"""E3: Evaluation primitives for PAW.

Provides scoring rubrics, confidence calibration, and evidence quality
assessment used by the E2 benchmark harness and runtime gates.

Design:
  - EvaluationRubric: defines scoring criteria for a benchmark case category.
  - EvidenceQuality: assesses whether observed evidence meets expected criteria.
  - ConfidenceCalibrator: calibrates raw scores to calibrated confidence.

All logic is pure Python (no provider calls) for deterministic testing.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QualityLevel(Enum):
    """Evidence quality tiers."""
    STRONG = "strong"
    SUFFICIENT = "sufficient"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class EvidenceQuality:
    """Quality assessment of evidence against expected criteria."""
    level: QualityLevel
    score: float  # 0.0 - 1.0
    reasons: tuple[str, ...]

    @property
    def passes(self) -> bool:
        return self.level in (QualityLevel.STRONG, QualityLevel.SUFFICIENT)


@dataclass(frozen=True)
class EvaluationRubric:
    """Scoring criteria for a benchmark case category.

    Defines how to score evidence: the expected evidence kind, minimum
    required quality level, and weight in aggregate scoring.
    """
    name: str
    evidence_kind: str
    min_quality: QualityLevel
    weight: float = 1.0
    required_fields: tuple[str, ...] = ()

    def assess_evidence(self, evidence: dict[str, Any]) -> EvidenceQuality:
        """Score evidence quality against this rubric's criteria."""
        if evidence.get("kind") != self.evidence_kind:
            return EvidenceQuality(
                level=QualityLevel.INSUFFICIENT,
                score=0.0,
                reasons=(f"evidence kind mismatch: expected {self.evidence_kind}, "
                         f"got {evidence.get('kind')}",),
            )

        field_score = self._check_fields(evidence)
        quality = self._compute_quality(field_score)

        reasons: list[str] = []
        if field_score < 1.0:
            missing = [f for f in self.required_fields if f not in evidence or evidence[f] is None]
            if missing:
                reasons.append(f"missing or null fields: {missing}")
        if quality.level == QualityLevel.STRONG and reasons:
            reasons.insert(0, "strong match with minor issues")

        return EvidenceQuality(
            level=quality.level,
            score=field_score,
            reasons=tuple(reasons) if reasons else quality.reasons,
        )

    def _check_fields(self, evidence: dict[str, Any]) -> float:
        """Check required fields are present and non-empty."""
        if not self.required_fields:
            return 1.0
        present = sum(1 for f in self.required_fields if f in evidence and evidence[f] is not None)
        return present / len(self.required_fields)

    def _compute_quality(self, field_score: float) -> EvidenceQuality:
        """Map field score to quality level."""
        if field_score >= 0.95:
            return EvidenceQuality(QualityLevel.STRONG, field_score, ())
        elif field_score >= 0.7:
            return EvidenceQuality(QualityLevel.SUFFICIENT, field_score, ())
        elif field_score >= 0.3:
            return EvidenceQuality(QualityLevel.WEAK, field_score, ())
        else:
            return EvidenceQuality(QualityLevel.INSUFFICIENT, field_score, ())

    def score(self, evidence: dict[str, Any]) -> float:
        """Weighted score for evidence against this rubric."""
        quality = self.assess_evidence(evidence)
        return quality.score * self.weight


class ConfidenceCalibrator:
    """Calibrates raw scores to calibrated confidence using Platt scaling.

    The calibrator maps raw scores (0 - 1) to calibrated probabilities using
    a sigmoid transformation. Parameters are fit from a small set of
    (raw_score, actual_correct) observations.
    """

    def __init__(self, slope: float = 10.0, intercept: float = 0.0):
        """Initialize with default Platt parameters.

        Default maps 0.5 → 0.5 probability with steep slope.
        """
        self.slope = slope
        self.intercept = intercept

    @classmethod
    def from_observations(
        cls,
        observations: Sequence[tuple[float, bool]],
    ) -> ConfidenceCalibrator:
        """Fit calibrator parameters from (raw_score, correct) observations.

        Uses simple logistic regression (Newton's method approximation).
        Returns a calibrator; falls back to default if fitting fails.
        """
        if len(observations) < 2:
            return cls()

        sum_correct = sum(1 for _, c in observations if c)
        sum_score = sum(s for s, _ in observations)
        n = len(observations)

        if n == 0 or sum_score == 0:
            return cls()

        try:
            # Simple fit: match mean score to mean correctness
            mean_score = sum_score / n
            mean_correct = sum_correct / n
            if mean_score == 0 or mean_correct == 0 or mean_correct == 1:
                return cls()
            # slope approximation based on variance
            var_score = sum((s - mean_score) ** 2 for s, _ in observations) / n
            if var_score == 0:
                return cls()
            slope = 1.0 / (var_score ** 0.5) * 4.0
            intercept = math.log(max(mean_correct / (1 - mean_correct), 1e-6)) - slope * mean_score
            return cls(slope=max(slope, 1.0), intercept=intercept)
        except (ValueError, OverflowError):
            return cls()

    def calibrate(self, raw_score: float) -> float:
        """Convert a raw score (0 - 1) to calibrated confidence (0 - 1)."""
        raw_score = max(0.0, min(1.0, raw_score))
        # Clamp to avoid numerical issues at extremes
        z = self.slope * (raw_score - 0.5) + self.intercept
        z = max(-50.0, min(50.0, z))
        return 1.0 / (1.0 + math.exp(-z))


@dataclass
class EvaluationResult:
    """Result of evaluating a case against expected evidence."""
    case_id: str
    status: str  # PASS / FAIL / SKIP
    scores: dict[str, float]  # rubric_name -> weighted score
    qualities: dict[str, EvidenceQuality]  # evidence_kind -> quality
    calibrated_confidence: float
    raw_score: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "scores": self.scores,
            "qualities": {
                k: {"level": v.level.value, "score": v.score, "reasons": list(v.reasons)}
                for k, v in self.qualities.items()
            },
            "calibrated_confidence": self.calibrated_confidence,
            "raw_score": self.raw_score,
            "details": self.details,
        }


def evaluate_case(
    case_id: str,
    expected_evidence: list[dict[str, Any]],
    observed_evidence: list[dict[str, Any]],
    *,
    calibrator: ConfidenceCalibrator | None = None,
    rubrics: list[EvaluationRubric] | None = None,
) -> EvaluationResult:
    """Evaluate observed evidence against expected evidence for a case.

    Args:
        case_id: The benchmark case identifier.
        expected_evidence: List of expected evidence specs from the case manifest.
        observed_evidence: List of observed evidence from runtime execution.
        calibrator: Optional calibrator for confidence scoring.
        rubrics: Optional rubrics for scoring (default: inferred from expected evidence).

    Returns:
        EvaluationResult with scores, qualities, and calibrated confidence.
    """
    if rubrics is None:
        rubrics = _infer_rubrics(expected_evidence)
    if calibrator is None:
        calibrator = ConfidenceCalibrator()

    qualities: dict[str, EvidenceQuality] = {}
    scores: dict[str, float] = {}

    for rubric in rubrics:
        # Find matching observed evidence (or synthesize a missing-evidence
        # dict so assess_evidence / score receive a consistent shape).
        obs = _find_evidence(observed_evidence, rubric.evidence_kind)
        missing = {"kind": rubric.evidence_kind, "value": None}
        obs_or_missing = obs if obs is not None else missing
        quality = rubric.assess_evidence(obs_or_missing)
        qualities[rubric.evidence_kind] = quality
        scores[rubric.name] = rubric.score(obs_or_missing)

    raw_score = sum(scores.values()) / len(scores) if scores else 0.0

    # Check if any required evidence was missing or insufficient.
    # ``min_quality`` is the rubric's declared minimum acceptable level;
    # evidence below it (even if partially present) fails the rubric.
    all_pass = all(
        _meets_min_quality(q, rubric.min_quality)
        for q, rubric in _zip_qualities_rubrics(rubrics, qualities)
    ) if qualities else False

    status = "PASS" if all_pass else "FAIL"

    return EvaluationResult(
        case_id=case_id,
        status=status,
        scores=scores,
        qualities=qualities,
        calibrated_confidence=calibrator.calibrate(raw_score),
        raw_score=raw_score,
        details={"evidence_count": len(observed_evidence), "rubric_count": len(rubrics)},
    )


def _infer_rubrics(expected_evidence: list[dict[str, Any]]) -> list[EvaluationRubric]:
    """Infer rubrics from expected evidence specs."""
    rubrics: list[EvaluationRubric] = []
    for ev in expected_evidence:
        rubrics.append(EvaluationRubric(
            name=f"rubric_{ev.get('kind', 'unknown')}",
            evidence_kind=ev.get("kind", "unknown"),
            min_quality=QualityLevel.SUFFICIENT,
            weight=ev.get("weight", 1.0),
            required_fields=("target", "value"),
        ))
    return rubrics


_QUALITY_ORDER: dict[QualityLevel, int] = {
    QualityLevel.INSUFFICIENT: 0,
    QualityLevel.WEAK: 1,
    QualityLevel.SUFFICIENT: 2,
    QualityLevel.STRONG: 3,
}


def _meets_min_quality(
    quality: EvidenceQuality, min_quality: QualityLevel
) -> bool:
    """Return True if *quality* is at least *min_quality*.

    Uses the ordinal ordering INSUFFICIENT < WEAK < SUFFICIENT < STRONG so
    that a rubric declaring ``min_quality=SUFFICIENT`` rejects WEAK evidence
    even when ``EvidenceQuality.passes`` would agree (both check ≥ SUFFICIENT).
    """
    return _QUALITY_ORDER[quality.level] >= _QUALITY_ORDER[min_quality]


def _zip_qualities_rubrics(
    rubrics: list[EvaluationRubric],
    qualities: dict[str, EvidenceQuality],
) -> list[tuple[EvidenceQuality, EvaluationRubric]]:
    """Pair each quality with its rubric by evidence_kind (order-preserving)."""
    return [
        (qualities[r.evidence_kind], r)
        for r in rubrics
        if r.evidence_kind in qualities
    ]


def _find_evidence(evidence: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    """Find evidence matching the given kind."""
    for ev in evidence:
        if ev.get("kind") == kind:
            return ev
    return None


__all__ = [
    "ConfidenceCalibrator",
    "EvaluationResult",
    "EvaluationRubric",
    "EvidenceQuality",
    "QualityLevel",
    "evaluate_case",
]
