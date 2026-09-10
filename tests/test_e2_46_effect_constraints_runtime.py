"""E2-46: Enforce effect constraints at runtime before step_fn invocation.

Four-layer evidence:
  1. Invariant  — ProposedAction.effect_constraints exists
  2. Runtime    — _gate_action checks constraints against plan context
  3. Adversarial — disallowed constraint blocks execution
  4. Measurable — step_fn never called when constraint denied
"""
import pytest

from paw.core.runtime import PawRuntime
from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ProposedAction, ResourceUsage, Capability
from paw.core.reasoning_contracts import PlanPurpose


def _make_runtime():
    return PawRuntime(
        AutonomyController(AutonomyBudget()),
        max_iterations=3,
    )


def _make_proposed(effect_constraints, *, plan_effect_constants=None):
    context = {}
    if plan_effect_constants is not None:
        context["plan_effect_constraints"] = plan_effect_constants
    return ProposedAction(
        goal="test",
        capabilities=[Capability.MODEL_INFERENCE],
        context=context,
        estimated_cost=ResourceUsage(),
        effect_constraints=effect_constraints,
        plan_purpose="implementation",
    )


@pytest.mark.asyncio
async def test_effect_constraints_block_disallowed():
    runtime = _make_runtime()
    proposed = _make_proposed(["network", "write"], plan_effect_constants=["read"])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is not None
    assert outcome.stopped is True
    assert outcome.step_called is False


@pytest.mark.asyncio
async def test_effect_constraints_allow_when_none():
    runtime = _make_runtime()
    proposed = _make_proposed([], plan_effect_constants=[])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    # Returns None when no effect constraints (continue to autonomy/policy)
    assert outcome is None


@pytest.mark.asyncio
async def test_effect_constraints_allow_when_empty_proposed():
    runtime = _make_runtime()
    proposed = _make_proposed([], plan_effect_constants=["read", "write"])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is None


@pytest.mark.asyncio
async def test_effect_constraints_allow_exact_match():
    runtime = _make_runtime()
    proposed = _make_proposed(["read", "model_inference"], plan_effect_constants=["read", "model_inference"])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is None


@pytest.mark.asyncio
async def test_effect_constraints_block_partial_overlap():
    runtime = _make_runtime()
    proposed = _make_proposed(["read", "write"], plan_effect_constants=["read"])
    outcome = await runtime._gate_action("task-1", proposed, 0)
    assert outcome is not None
    assert outcome.stopped is True
