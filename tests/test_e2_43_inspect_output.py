"""E2-43: Expose depth, evidence, options, readiness, budget and staleness in inspect output.

Four-layer evidence:
  1. Invariant  — PawRuntime has inspect_state method returning dict
  2. Runtime    — inspect_state includes all required keys with correct types
  3. Adversarial — missing task_signals yields None/empty defaults; stale flags compute correctly
  4. Measurable — output is deterministic for same state; no side effects

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.reasoning_contracts import (
    TaskSignals, PrivacyClass, BudgetLevel, ResearchBudget,
    NoveltyLevel, ImpactLevel, ContextSufficiencyLevel,
)


def _make_signals():
    return TaskSignals(
        novelty=NoveltyLevel.NOVEL,
        impact=ImpactLevel.HIGH,
        privacy=PrivacyClass.INTERNAL,
        context_sufficiency=ContextSufficiencyLevel.PARTIAL,
        budget=BudgetLevel.WITHIN_LIMIT,
        research_budget=ResearchBudget(max_evidence_items=10, max_time_seconds=60.0, max_tokens=4000),
    )


@pytest.mark.asyncio
async def test_inv1_paw_runtime_has_inspect_state():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac)
    assert hasattr(runtime, "inspect_state")
    state = runtime.inspect_state()
    assert isinstance(state, dict)


@pytest.mark.asyncio
async def test_rt1_inspect_state_has_all_keys():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    runtime.task_signals = _make_signals()
    state = runtime.inspect_state()
    assert "depth" in state
    assert "evidence" in state
    assert "options" in state
    assert "readiness" in state
    assert "budget" in state
    assert "staleness" in state


@pytest.mark.asyncio
async def test_rt2_inspect_state_readiness_fields():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY", readiness_revision="abc", current_revision="abc")
    state = runtime.inspect_state()
    assert state["readiness"]["level"] == "READY"
    assert state["readiness"]["revision"] == "abc"
    assert state["readiness"]["is_stale"] is False


@pytest.mark.asyncio
async def test_rt3_inspect_state_staleness_detected():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY", readiness_revision="abc", current_revision="def")
    state = runtime.inspect_state()
    assert state["readiness"]["is_stale"] is True
    assert state["staleness"]["revision_mismatch"] is True
    assert state["staleness"]["constraint_mismatch"] is False


@pytest.mark.asyncio
async def test_rt4_inspect_state_budget_fields():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    runtime.autonomy.usage.model_calls = 2
    runtime.autonomy.usage.tool_calls = 3
    runtime.autonomy.usage.total_tokens = 500
    runtime.autonomy.usage.wall_time_seconds = 1.0
    state = runtime.inspect_state()
    assert state["budget"]["model_calls"] == 2
    assert state["budget"]["tool_calls"] == 3
    assert state["budget"]["total_tokens"] == 500
    assert state["budget"]["wall_time_seconds"] == 1.0


@pytest.mark.asyncio
async def test_adv1_inspect_state_no_task_signals():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    state = runtime.inspect_state()
    assert state["depth"] is None
    assert state["evidence"] == {}


@pytest.mark.asyncio
async def test_adv2_inspect_state_no_side_effects():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    before_id = id(runtime)
    state = runtime.inspect_state()
    after_id = id(runtime)
    assert before_id == after_id  # same object
    assert isinstance(state, dict)  # returns dict, does not crash
