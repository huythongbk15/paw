"""E2-04 — task-signal value contracts, without routing decisions (D1)."""

from dataclasses import FrozenInstanceError

import pytest
from paw.core.privacy import PrivacyClass
from paw.core.reasoning_contracts import (
    BudgetLevel,
    ContextSufficiencyLevel,
    ImpactLevel,
    NoveltyLevel,
    TaskSignals,
)


def test_signal_taxonomies_include_fail_closed_unknown_values() -> None:
    assert NoveltyLevel.UNKNOWN == "unknown"
    assert ImpactLevel.UNKNOWN == "unknown"
    assert ContextSufficiencyLevel.UNKNOWN == "unknown"
    assert BudgetLevel.UNKNOWN == "unknown"


def test_task_signal_defaults_do_not_claim_fast_path_evidence() -> None:
    signals = TaskSignals()
    assert signals.novelty is NoveltyLevel.UNKNOWN
    assert signals.impact is ImpactLevel.UNKNOWN
    assert signals.privacy is PrivacyClass.INTERNAL
    assert signals.context_sufficiency is ContextSufficiencyLevel.UNKNOWN
    assert signals.budget is BudgetLevel.UNKNOWN
    assert signals.uncertainty_score is None
    assert signals.estimated_tokens is None
    assert signals.complete is False


def test_task_signals_reuse_the_canonical_privacy_contract() -> None:
    signals = TaskSignals(privacy=PrivacyClass.SECRET)
    assert signals.privacy is PrivacyClass.SECRET

    import paw.core.models as models

    assert not hasattr(models, "PrivacyLevel")


def test_complete_signals_are_recordable_without_classifying_the_task() -> None:
    signals = TaskSignals(
        novelty=NoveltyLevel.FAMILIAR,
        impact=ImpactLevel.MEDIUM,
        privacy=PrivacyClass.WORKSPACE,
        context_sufficiency=ContextSufficiencyLevel.SUFFICIENT,
        budget=BudgetLevel.WITHIN_LIMIT,
        uncertainty_score=0.2,
        estimated_tokens=2048,
    )
    assert signals.complete is True
    assert not hasattr(signals, "goal_classification")
    assert not hasattr(signals, "is_escalation_required")


def test_task_signals_are_frozen() -> None:
    signals = TaskSignals()
    with pytest.raises(FrozenInstanceError):
        signals.novelty = NoveltyLevel.NOVEL  # type: ignore[misc]


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_uncertainty_score_is_bounded(score: float) -> None:
    with pytest.raises(ValueError, match="between"):
        TaskSignals(uncertainty_score=score)


def test_negative_token_estimate_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        TaskSignals(estimated_tokens=-1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("novelty", "routine"),
        ("impact", "low"),
        ("privacy", "internal"),
        ("context_sufficiency", "sufficient"),
        ("budget", "within_limit"),
    ],
)
def test_untyped_signal_values_are_rejected(field: str, value: str) -> None:
    with pytest.raises(TypeError, match=field):
        TaskSignals(**{field: value})  # type: ignore[arg-type]


def test_e2_04_does_not_implement_later_depth_or_router_work() -> None:
    import paw.core.reasoning_contracts as contracts

    assert not hasattr(contracts, "classify_task")
    assert not hasattr(contracts, "DEFAULT_TASK_SIGNALS")
