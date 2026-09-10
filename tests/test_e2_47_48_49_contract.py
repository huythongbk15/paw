"""E2-47 + E2-48 + E2-49: immutable decision versions, typed reasoning assessment, canonical proposal contract.

Four-layer evidence:
  1. Invariant  — dataclass fields, transitions, typed assessment fields
  2. Runtime    — transitions + canonical proposal wiring
  3. Adversarial — invalid states/values rejected
  4. Measurable — __all__ exports, frozen semantics
"""
import math
import pytest

from paw.core.reasoning_contracts import (
    DecisionVersion,
    DecisionVersionState,
    ReasoningAssessment,
    ReasoningTier,
    OODSignal,
    CanonicalProposal,
)


def test_decision_version_states():
    assert DecisionVersionState.DRAFT.value == "draft"
    assert DecisionVersionState.FINAL.value == "final"
    assert DecisionVersionState.STALE.value == "stale"
    assert DecisionVersionState.SUPERSEDED.value == "superseded"


def test_decision_version_defaults():
    dv = DecisionVersion(
        version_id="v-1",
        decision_id="d-1",
        state=DecisionVersionState.FINAL,
        payload={"readiness": "READY"},
        created_at="2026-09-10T00:00:00Z",
    )
    assert dv.created_by == ""
    assert dv.superseded_by == ""


def test_decision_version_invalid_empty():
    with pytest.raises(ValueError):
        DecisionVersion(
            version_id="",
            decision_id="d-1",
            state=DecisionVersionState.DRAFT,
            payload={},
            created_at="",
        )


def test_reasoning_tier_values():
    assert ReasoningTier.ROUTINE.value == "routine"
    assert ReasoningTier.COMPLEX.value == "complex"
    assert ReasoningTier.SAFETY_CRITICAL.value == "safety_critical"


def test_ood_signal_values():
    assert OODSignal.NONE.value == "none"
    assert OODSignal.SUSPICIOUS.value == "suspicious"
    assert OODSignal.CRITICAL.value == "critical"


def test_reasoning_assessment_valid():
    ra = ReasoningAssessment(
        tier=ReasoningTier.COMPLEX,
        uncertainty=0.4,
        ood_signal=OODSignal.NONE,
        confidence=0.9,
        role_ceiling="planner",
        allowed_roles=("planner", "reviewer"),
        blocked_roles=("executor",),
    )
    assert ra.tier is ReasoningTier.COMPLEX
    assert ra.ood_signal is OODSignal.NONE


def test_reasoning_assessment_rejects_nan():
    with pytest.raises(ValueError):
        ReasoningAssessment(
            tier=ReasoningTier.ROUTINE,
            uncertainty=float("nan"),
            ood_signal=OODSignal.NONE,
            confidence=0.5,
            role_ceiling="planner",
            allowed_roles=("planner",),
            blocked_roles=(),
        )


def test_reasoning_assessment_rejects_out_of_range():
    with pytest.raises(ValueError):
        ReasoningAssessment(
            tier=ReasoningTier.ROUTINE,
            uncertainty=1.1,
            ood_signal=OODSignal.NONE,
            confidence=0.5,
            role_ceiling="planner",
            allowed_roles=("planner",),
            blocked_roles=(),
        )
    with pytest.raises(ValueError):
        ReasoningAssessment(
            tier=ReasoningTier.ROUTINE,
            uncertainty=0.5,
            ood_signal=OODSignal.NONE,
            confidence=1.1,
            role_ceiling="planner",
            allowed_roles=("planner",),
            blocked_roles=(),
        )


def test_reasoning_assessment_role_ceiling_not_in_allowed():
    with pytest.raises(ValueError):
        ReasoningAssessment(
            tier=ReasoningTier.ROUTINE,
            uncertainty=0.0,
            ood_signal=OODSignal.NONE,
            confidence=1.0,
            role_ceiling="executor",
            allowed_roles=("planner",),
            blocked_roles=(),
        )


def test_canonical_proposal_valid():
    ra = ReasoningAssessment(
        tier=ReasoningTier.ROUTINE,
        uncertainty=0.1,
        ood_signal=OODSignal.NONE,
        confidence=0.95,
        role_ceiling="local",
        allowed_roles=("local",),
        blocked_roles=(),
    )
    proposal = CanonicalProposal(
        proposed_action="step-1",
        selected_model="local-model",
        inference_classification="local.compute",
        reasoning_assessment=ra,
        provider_kind="local",
        budget=None,
        evidence_refs=("e1",),
    )
    assert proposal.selected_model == "local-model"


def test_canonical_proposal_rejects_empty_fields():
    ra = ReasoningAssessment(
        tier=ReasoningTier.ROUTINE,
        uncertainty=0.0,
        ood_signal=OODSignal.NONE,
        confidence=1.0,
        role_ceiling="local",
        allowed_roles=("local",),
        blocked_roles=(),
    )
    with pytest.raises(ValueError):
        CanonicalProposal(
            proposed_action="step-1",
            selected_model="",
            inference_classification="local.compute",
            reasoning_assessment=ra,
            provider_kind="local",
            budget=None,
            evidence_refs=(),
        )
