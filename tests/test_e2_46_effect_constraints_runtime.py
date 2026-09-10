"""E2-46: Enforce effect constraints at runtime before step_fn invocation.

Four-layer evidence:
  1. Invariant  — ProposedAction.effect_constraints exists
  2. Runtime    — _gate_action checks constraints against plan effect_constraints
  3. Adversarial — disallowed constraint blocks execution
  4. Measurable — step_fn never called when constraint denied
"""
from __future__ import annotations

import pytest

from paw.core.runtime import PawRuntime
from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ProposedAction, ResourceUsage, Capability
from paw.core.planner import Plan


class _CountingExecutor:
    def __init__(self):
        self.calls = 0

    async def complete(self, selection, messages):
        self.calls += 1
        return {"done": True, "progress": 1.0}


def _make_runtime(*, plan_effect_constants=None):
    plan = Plan(goal="test", effect_constraints=plan_effect_constants or [])
    budget = AutonomyBudget(max_model_calls=1, max_iterations=3)
    ac = AutonomyController(budget)
    runtime = PawRuntime(
        ac,
        model_executor=_CountingExecutor(),
        max_iterations=3,
        plan=plan,
    )
    runtime.default_role = "worker"
    return runtime


def _make_proposed(effect_constraints):
    return ProposedAction(
        goal="test",
        capabilities=[Capability.MODEL_INFERENCE],
        context={},
        estimated_cost=ResourceUsage(),
        effect_constraints=effect_constraints,
        plan_purpose="implementation",
    )


@pytest.mark.asyncio
async def test_effect_constraints_block_disallowed():
    runtime = _make_runtime(plan_effect_constants=["read"])
    proposed = _make_proposed(["network", "write"])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is not None
    assert outcome.stopped is True
    assert outcome.step_called is False


@pytest.mark.asyncio
async def test_effect_constraints_allow_when_none():
    runtime = _make_runtime(plan_effect_constants=[])
    proposed = _make_proposed([])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is None


@pytest.mark.asyncio
async def test_effect_constraints_allow_exact_match():
    runtime = _make_runtime(plan_effect_constants=["read", "model_inference"])
    proposed = _make_proposed(["read", "model_inference"])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is None


@pytest.mark.asyncio
async def test_effect_constraints_block_partial_overlap():
    runtime = _make_runtime(plan_effect_constants=["read"])
    proposed = _make_proposed(["read", "write"])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is not None
    assert outcome.stopped is True
