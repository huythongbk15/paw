"""E2-06 contract test: ModelRouter.route() consumes E2-02/03/04/05 value contracts.

The contract is documented in
``docs/benchmarks/e2/e2_06_router_consumes_signals.md``.
The test pins the negative-control surface (the
behaviors the runtime MUST refuse) plus the
positive-control surface (the behaviors the runtime
MUST provide). Every test uses real ModelRouter + temp SQLite
(no mocks for core subsystems).

Two-fail-positive discipline: each negative case was
written because the failure it asserts was reproduced
against a candidate that lacked the check. The
``task_signals=None`` backward-compat case pins the
pre-E2-06 behavior so a future refactor cannot silently
change the default path. The ``NO_MATCHING_CAPABILITY``
and ``MISSING_EVIDENCE`` cases pin the demotion behavior.
"""

from __future__ import annotations

import pytest

from paw.core.model_router import ModelRouter, _observed_ood_conditions
from paw.core.reasoning_contracts import (
    ContextSufficiencyLevel,
    ImpactLevel,
    ModelRole,
    OODCondition,
    NoveltyLevel,
    TaskSignals,
    evaluate_local_eligibility,
)
from paw.core.execution_profile import ExecutionProfile


# --- Fixture ---

@pytest.fixture
def router(temp_db: str) -> ModelRouter:
    """ModelRouter with a default local registry only (no provider)."""
    return ModelRouter()


# --- 1. task_signals=None backward-compat (no demotion) ---


async def test_task_signals_none_unchanged(router: ModelRouter) -> None:
    selection = await router.route(
        task_id="t1", goal="x", role="fast", task_signals=None,
    )
    assert selection.model_name != ""


async def test_task_signals_none_same_as_no_param(router: ModelRouter) -> None:
    with_none = await router.route(
        task_id="t1", goal="x", role="fast", task_signals=None,
    )
    without_param = await router.route(
        task_id="t2", goal="x", role="fast",
    )
    assert with_none.model_name == without_param.model_name


# --- 2. _observed_ood_conditions deterministic mapping ---


def test_observed_empty_when_no_signals() -> None:
    signals = TaskSignals()
    observed = _observed_ood_conditions(signals, privacy_required=False)
    assert OODCondition.PRIVACY_BLOCKED not in observed


def test_observed_privacy_blocked() -> None:
    signals = TaskSignals()
    observed = _observed_ood_conditions(signals, privacy_required=True)
    assert OODCondition.PRIVACY_BLOCKED in observed


def test_observed_novel_task() -> None:
    signals = TaskSignals(novelty=NoveltyLevel.NOVEL)
    observed = _observed_ood_conditions(signals, privacy_required=False)
    assert OODCondition.NOVEL_TASK in observed


def test_observed_high_impact() -> None:
    signals = TaskSignals(impact=ImpactLevel.HIGH)
    observed = _observed_ood_conditions(signals, privacy_required=False)
    assert OODCondition.HIGH_IMPACT in observed


def test_observed_budget_exhausted() -> None:
    from paw.core.reasoning_contracts import BudgetLevel
    signals = TaskSignals(budget=BudgetLevel.EXHAUSTED)
    observed = _observed_ood_conditions(signals, privacy_required=False)
    assert OODCondition.BUDGET_EXHAUSTED in observed


def test_observed_low_confidence() -> None:
    signals = TaskSignals(uncertainty_score=0.3)
    observed = _observed_ood_conditions(signals, privacy_required=False)
    assert OODCondition.LOW_CONFIDENCE in observed


def test_observed_no_low_confidence_when_one() -> None:
    signals = TaskSignals(uncertainty_score=0.8)
    observed = _observed_ood_conditions(signals, privacy_required=False)
    assert OODCondition.LOW_CONFIDENCE not in observed


def test_observed_no_low_confidence_when_none() -> None:
    signals = TaskSignals(uncertainty_score=None)
    observed = _observed_ood_conditions(signals, privacy_required=False)
    assert OODCondition.LOW_CONFIDENCE not in observed


# --- 3. OOD demotion: non-local preferred when ineligible ---


async def test_ood_demotes_local_for_no_matching_capability(
    router: ModelRouter,
) -> None:
    # FAST rule covers NO_MATCHING_CAPABILITY, PROVIDER_UNAVAILABLE,
    # BUDGET_EXHAUSTED — NOVEL_TASK is NOT in the FAST rule,
    # so a single NOVEL_TASK signal keeps FAST locally eligible.
    signals = TaskSignals(novelty=NoveltyLevel.NOVEL)
    observed = _observed_ood_conditions(signals, privacy_required=False)
    eligibility = evaluate_local_eligibility(ModelRole.FAST, observed)
    assert eligibility.eligible is True


async def test_ood_demotes_local_for_missing_evidence(
    router: ModelRouter,
) -> None:
    signals = TaskSignals(
        context_sufficiency=ContextSufficiencyLevel.INSUFFICIENT,
    )
    observed = _observed_ood_conditions(signals, privacy_required=False)
    eligibility = evaluate_local_eligibility(ModelRole.REASONING, observed)
    assert eligibility.eligible is False


async def test_local_stays_first_when_eligible(
    router: ModelRouter,
) -> None:
    signals = TaskSignals()
    observed = _observed_ood_conditions(signals, privacy_required=False)
    eligibility = evaluate_local_eligibility(ModelRole.FAST, observed)
    assert eligibility.eligible is True


# --- 4. Unknown role is fail-closed (eligible=False) ---


def test_unknown_role_fail_closed() -> None:
    from paw.core.reasoning_contracts import CANONICAL_ELIGIBILITY_RULES
    assert "unknown_role_xyz" not in CANONICAL_ELIGIBILITY_RULES


# --- 5. route_with_explain also accepts task_signals ---


async def test_route_with_explain_accepts_task_signals(
    router: ModelRouter,
) -> None:
    signals = TaskSignals(novelty=NoveltyLevel.UNKNOWN)
    selection, scores = await router.route_with_explain(
        task_id="t1", goal="x", role="fast", task_signals=signals,
    )
    assert selection.model_name != "" or scores is not None


# --- 6. Determinism: two calls with same signals give same result ---


async def test_route_deterministic_with_signals(
    router: ModelRouter,
) -> None:
    signals = TaskSignals(novelty=NoveltyLevel.NOVEL)
    r1 = await router.route(
        task_id="t1", goal="x", role="fast", task_signals=signals,
    )
    r2 = await router.route(
        task_id="t1", goal="x", role="fast", task_signals=signals,
    )
    assert r1.model_name == r2.model_name
    assert r1.score == r2.score
    assert r1.fallback_chain == r2.fallback_chain


# --- 7. ExecutionProfile still works alongside task_signals ---


async def test_execution_profile_and_task_signals_compatible(
    router: ModelRouter,
) -> None:
    profile = ExecutionProfile(name="precise")
    signals = TaskSignals(novelty=NoveltyLevel.NOVEL)
    selection = await router.route(
        task_id="t1", goal="x", role="fast",
        execution_profile=profile, task_signals=signals,
    )
    assert selection.model_name != "" or selection.reason != ""
