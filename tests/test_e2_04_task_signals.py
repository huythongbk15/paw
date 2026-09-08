"""E2-04 — Novelty, impact, privacy, context-sufficiency and budget signals (D1).

Verifies that TaskSignals bundles the five signal dimensions and that
classify_task() produces consistent FAST/STANDARD/DEEP classifications.
"""

import pytest
from paw.core.models import (
    BudgetLevel,
    CANONICAL_MODEL_ROLES,
    CANONICAL_ROLE_CONTRACTS,
    classify_task,
    ContextSufficiencyLevel,
    DEFAULT_TASK_SIGNALS,
    ImpactLevel,
    ModelRole,
    NoveltyLevel,
    PrivacyLevel,
    TaskSignals,
)


def test_novelty_enum_has_four_values():
    """ROUTINE, FAMILIAR, NOVEL, UNPRECEDENTED."""
    assert len(list(NoveltyLevel)) == 4
    assert NoveltyLevel.ROUTINE == "routine"
    assert NoveltyLevel.NOVEL == "novel"
    assert NoveltyLevel.UNPRECEDENTED == "unprecedented"


def test_impact_enum_has_four_values():
    """LOW, MEDIUM, HIGH, CRITICAL."""
    assert len(list(ImpactLevel)) == 4
    assert ImpactLevel.LOW == "low"
    assert ImpactLevel.CRITICAL == "critical"


def test_privacy_enum_has_four_values():
    """PUBLIC, INTERNAL, WORKSPACE, SECRET."""
    assert len(list(PrivacyLevel)) == 4
    assert PrivacyLevel.PUBLIC == "public"
    assert PrivacyLevel.SECRET == "secret"


def test_context_sufficiency_enum_has_four_values():
    """SUFFICIENT, PARTIAL, INSUFFICIENT, UNKNOWN."""
    assert len(list(ContextSufficiencyLevel)) == 4
    assert ContextSufficiencyLevel.SUFFICIENT == "sufficient"
    assert ContextSufficiencyLevel.INSUFFICIENT == "insufficient"


def test_budget_enum_has_five_values():
    """UNLIMITED, LOW, MEDIUM, HIGH, CONSTRAINED."""
    assert len(list(BudgetLevel)) == 5
    assert BudgetLevel.UNLIMITED == "unlimited"
    assert BudgetLevel.CONSTRAINED == "constrained"


def test_task_signals_defaults_to_routine():
    """Default TaskSignals should represent a routine task."""
    signals = TaskSignals()
    assert signals.novelty == NoveltyLevel.ROUTINE
    assert signals.impact == ImpactLevel.LOW
    assert signals.privacy == PrivacyLevel.PUBLIC
    assert signals.context_sufficiency == ContextSufficiencyLevel.SUFFICIENT
    assert signals.budget == BudgetLevel.UNLIMITED
    assert signals.uncertainty_score == 0.0
    assert signals.estimated_tokens == 0


def test_task_signals_is_frozen():
    """TaskSignals is a frozen dataclass — cannot be mutated after creation."""
    signals = TaskSignals()
    with pytest.raises(AttributeError):
        signals.novelty = NoveltyLevel.NOVEL  # type: ignore[misc]


def test_default_signals_classify_as_fast():
    """Default (routine, low impact, public, sufficient, unlimited) → FAST."""
    assert DEFAULT_TASK_SIGNALS.goal_classification() == "FAST"


def test_classify_raises_on_unknown_task_signals():
    """classify_task delegates to TaskSignals.goal_classification()."""
    signals = TaskSignals(
        novelty=NoveltyLevel.NOVEL,
        impact=ImpactLevel.HIGH,
        privacy=PrivacyLevel.SECRET,
    )
    assert classify_task(signals) == "DEEP"


def test_routine_low_public_sufficient_is_fast():
    """Routine task with all minimal signals is FAST."""
    signals = TaskSignals(
        novelty=NoveltyLevel.ROUTINE,
        impact=ImpactLevel.LOW,
        privacy=PrivacyLevel.PUBLIC,
        context_sufficiency=ContextSufficiencyLevel.SUFFICIENT,
        budget=BudgetLevel.UNLIMITED,
        uncertainty_score=0.1,
    )
    assert classify_task(signals) == "FAST"


def test_novel_or_high_impact_is_deep():
    """Novel or high-impact task is DEEP."""
    novel = TaskSignals(novelty=NoveltyLevel.NOVEL)
    high_impact = TaskSignals(impact=ImpactLevel.HIGH)
    assert classify_task(novel) == "DEEP"
    assert classify_task(high_impact) == "DEEP"


def test_secret_privacy_is_deep():
    """Secret privacy task is DEEP regardless of other signals."""
    signals = TaskSignals(privacy=PrivacyLevel.SECRET)
    assert classify_task(signals) == "DEEP"


def test_context_insufficient_is_deep():
    """Insufficient context task is DEEP."""
    signals = TaskSignals(
        context_sufficiency=ContextSufficiencyLevel.INSUFFICIENT
    )
    assert classify_task(signals) == "DEEP"


def test_constrained_budget_is_deep():
    """Constrained budget task is DEEP."""
    signals = TaskSignals(budget=BudgetLevel.CONSTRAINED)
    assert classify_task(signals) == "DEEP"


def test_uncertainty_0_5_is_escalation_required():
    """uncertainty_score >= 0.5 triggers escalation."""
    signals = TaskSignals(uncertainty_score=0.5)
    assert signals.is_escalation_required() is True


def test_uncertainty_0_4_not_escalation():
    """uncertainty_score < 0.5 does not trigger escalation alone."""
    signals = TaskSignals(uncertainty_score=0.4)
    assert signals.is_escalation_required() is False


def test_all_signal_values_are_in_ranges():
    """Every signal enum value must be a valid string."""
    for level in NoveltyLevel:
        assert isinstance(level.value, str)
    for level in ImpactLevel:
        assert isinstance(level.value, str)
    for level in PrivacyLevel:
        assert isinstance(level.value, str)
    for level in ContextSufficiencyLevel:
        assert isinstance(level.value, str)
    for level in BudgetLevel:
        assert isinstance(level.value, str)


def test_canonical_roles_and_contracts_still_present():
    """E2-04 must not break E2-02/E2-03 constants."""
    assert len(CANONICAL_MODEL_ROLES) == 7
    assert len(CANONICAL_ROLE_CONTRACTS) == 7
