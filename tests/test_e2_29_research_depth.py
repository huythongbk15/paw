"""E2-29: Classify FAST, STANDARD, DEEP from recorded task signals.

Four-layer evidence:
  1. Invariant  — DecisionLevel enum has exactly FAST/STANDARD/DEEP
  2. Runtime    — classify_research_depth returns correct level for each signal combo
  3. Adversarial — unknown/incomplete signals never return FAST
  4. Measurable — decision level is exported and documented

Decision level: D1.
"""
from enum import StrEnum

import pytest

from paw.core.reasoning_contracts import (
    BudgetLevel,
    ContextSufficiencyLevel,
    DecisionLevel,
    ImpactLevel,
    NoveltyLevel,
    PrivacyClass,
    TaskSignals,
    classify_decision_level,
    classify_research_depth,
)


def make_signals(**kwargs):
    """Create TaskSignals with explicit defaults for all fields."""
    defaults = {
        "novelty": NoveltyLevel.ROUTINE,
        "impact": ImpactLevel.LOW,
        "privacy": PrivacyClass.INTERNAL,
        "context_sufficiency": ContextSufficiencyLevel.SUFFICIENT,
        "budget": BudgetLevel.WITHIN_LIMIT,
        "uncertainty_score": 0.1,
        "estimated_tokens": 100,
    }
    defaults.update(kwargs)
    return TaskSignals(**defaults)


class TestInvariantDecisionLevel:
    """E2-29 Invariant: DecisionLevel has exactly FAST/STANDARD/DEEP."""

    def test_inv1_has_three_levels(self):
        levels = list(DecisionLevel)
        assert len(levels) == 3

    def test_inv2_fast_exists(self):
        assert DecisionLevel.FAST.value == "fast"

    def test_inv3_standard_exists(self):
        assert DecisionLevel.STANDARD.value == "standard"

    def test_inv4_deep_exists(self):
        assert DecisionLevel.DEEP.value == "deep"

    def test_inv5_is_strenum(self):
        assert issubclass(DecisionLevel, StrEnum)


class TestRuntimeDepthClassification:
    """E2-29 Runtime: classify_research_depth returns correct level."""

    def test_rt1_high_impact_is_deep(self):
        assert classify_research_depth(make_signals(impact=ImpactLevel.HIGH)) is DecisionLevel.DEEP

    def test_rt2_critical_impact_is_deep(self):
        assert classify_research_depth(make_signals(impact=ImpactLevel.CRITICAL)) is DecisionLevel.DEEP

    def test_rt3_novel_is_deep(self):
        assert classify_research_depth(make_signals(novelty=NoveltyLevel.NOVEL)) is DecisionLevel.DEEP

    def test_rt4_unprecedented_is_deep(self):
        assert classify_research_depth(make_signals(novelty=NoveltyLevel.UNPRECEDENTED)) is DecisionLevel.DEEP

    def test_rt5_insufficient_context_is_deep(self):
        assert classify_research_depth(make_signals(context_sufficiency=ContextSufficiencyLevel.INSUFFICIENT)) is DecisionLevel.DEEP

    def test_rt6_high_uncertainty_is_deep(self):
        assert classify_research_depth(make_signals(uncertainty_score=0.7)) is DecisionLevel.DEEP

    def test_rt7_very_high_uncertainty_is_deep(self):
        assert classify_research_depth(make_signals(uncertainty_score=0.95)) is DecisionLevel.DEEP

    def test_rt8_medium_impact_is_standard(self):
        assert classify_research_depth(make_signals(impact=ImpactLevel.MEDIUM)) is DecisionLevel.STANDARD

    def test_rt9_familiar_novelty_is_standard(self):
        assert classify_research_depth(make_signals(novelty=NoveltyLevel.FAMILIAR)) is DecisionLevel.STANDARD

    def test_rt10_partial_context_is_standard(self):
        assert classify_research_depth(make_signals(context_sufficiency=ContextSufficiencyLevel.PARTIAL)) is DecisionLevel.STANDARD

    def test_rt11_moderate_uncertainty_is_standard(self):
        assert classify_research_depth(make_signals(uncertainty_score=0.5)) is DecisionLevel.STANDARD

    def test_rt12_routine_low_impact_is_fast(self):
        assert classify_research_depth(
            make_signals(
                impact=ImpactLevel.LOW,
                novelty=NoveltyLevel.ROUTINE,
                context_sufficiency=ContextSufficiencyLevel.SUFFICIENT,
                uncertainty_score=0.1,
                budget=BudgetLevel.WITHIN_LIMIT,
            )
        ) is DecisionLevel.FAST

    def test_rt13_near_limit_budget_is_standard(self):
        assert classify_research_depth(
            make_signals(
                impact=ImpactLevel.LOW,
                novelty=NoveltyLevel.ROUTINE,
                context_sufficiency=ContextSufficiencyLevel.SUFFICIENT,
                uncertainty_score=0.1,
                budget=BudgetLevel.NEAR_LIMIT,
            )
        ) is DecisionLevel.STANDARD

    def test_rt14_exhausted_budget_is_standard(self):
        assert classify_research_depth(
            make_signals(
                impact=ImpactLevel.LOW,
                novelty=NoveltyLevel.ROUTINE,
                context_sufficiency=ContextSufficiencyLevel.SUFFICIENT,
                uncertainty_score=0.1,
                budget=BudgetLevel.EXHAUSTED,
            )
        ) is DecisionLevel.STANDARD

    def test_rt15_alias_works(self):
        assert classify_decision_level(make_signals(impact=ImpactLevel.HIGH)) is DecisionLevel.DEEP


class TestAdversarialNeverFastUnknown:
    """E2-29 Adversarial: unknown/incomplete signals never return FAST."""

    def test_adv1_all_unknown_signals_are_standard(self):
        assert classify_research_depth(TaskSignals()) is DecisionLevel.STANDARD

    def test_adv2_unknown_impact_is_not_fast(self):
        assert classify_research_depth(make_signals(impact=ImpactLevel.UNKNOWN)) is not DecisionLevel.FAST

    def test_adv3_uncertainty_none_is_standard(self):
        assert classify_research_depth(make_signals(uncertainty_score=None)) is not DecisionLevel.FAST

    def test_adv4_boundary_07_is_deep(self):
        assert classify_research_depth(make_signals(uncertainty_score=0.7)) is DecisionLevel.DEEP

    def test_adv5_boundary_04_is_standard(self):
        assert classify_research_depth(make_signals(uncertainty_score=0.4)) is DecisionLevel.STANDARD

    def test_adv6_boundary_039_is_fast(self):
        assert classify_research_depth(make_signals(uncertainty_score=0.39)) is DecisionLevel.FAST


class TestMeasurableExport:
    """E2-29 Measurable: export and documentation."""

    def test_measure1_exported_in_all(self):
        from paw.core.reasoning_contracts import __all__
        assert "DecisionLevel" in __all__
        assert "classify_research_depth" in __all__
        assert "classify_decision_level" in __all__

    def test_measure2_returns_canonical_enum(self):
        assert isinstance(classify_research_depth(make_signals()), DecisionLevel)

    def test_measure3_fallback_to_standard_when_fast_conditions_partial(self):
        assert classify_research_depth(make_signals(novelty=NoveltyLevel.FAMILIAR)) is DecisionLevel.STANDARD
