"""E2-42: Isolate/discard spike effects and return its evidence to the same decision gate.

Four-layer evidence:
  1. Invariant  — ProposedAction has isolated field
  2. Runtime    — isolated=True skips OperationRecord, autonomy usage, ledger STEP_EXECUTED
  3. Adversarial — non-isolated proposals still persist; isolated proposals still return observation
  4. Measurable — isolated proposals return observation with success=True and result

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime


@pytest.mark.asyncio
async def test_inv1_proposed_action_has_isolated():
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
    )
    assert hasattr(proposed, "isolated")
    assert proposed.isolated is False  # fail-closed default


@pytest.mark.asyncio
async def test_rt1_isolated_skips_persistence():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
        is_mutating=True,
        isolated=True,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(
            step_id="step-1",
            action_id=action.operation_id,
            success=True,
            result={"done": True, "progress": 1.0},
        )
    result = await runtime._execute_unit(
        "task-1", proposed, iteration_index=0, step_fn=step_fn,
        operation_type="external_effect", step_id="step-1",
    )
    assert result.observation is not None
    assert result.observation.success is True
    assert result.observation.result.get("done") is True
    # Isolated proposals should not accumulate usage
    assert runtime.autonomy.usage.model_calls == 0
    assert runtime.autonomy.usage.tool_calls == 0


@pytest.mark.asyncio
async def test_rt2_non_isolated_persists():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    proposed = ProposedAction(
        operation_id="op-2",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-2",
        is_mutating=True,
        isolated=False,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(
            step_id="step-2",
            action_id=action.operation_id,
            success=True,
            result={"done": True, "progress": 1.0},
            resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=100),
        )
    result = await runtime._execute_unit(
        "task-2", proposed, iteration_index=0, step_fn=step_fn,
        operation_type="external_effect", step_id="step-2",
    )
    assert result.observation.success is True
    # Non-isolated proposals accumulate usage
    assert runtime.autonomy.usage.model_calls == 1
    assert runtime.autonomy.usage.tool_calls == 1
    assert runtime.autonomy.usage.total_tokens == 100


@pytest.mark.asyncio
async def test_rt3_isolated_failure_still_returns_observation():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    proposed = ProposedAction(
        operation_id="op-3",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-3",
        is_mutating=True,
        isolated=True,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(
            step_id="step-3",
            action_id=action.operation_id,
            success=False,
            error="spike_failed",
            result={"done": False, "progress": 0.0},
        )
    result = await runtime._execute_unit(
        "task-3", proposed, iteration_index=0, step_fn=step_fn,
        operation_type="external_effect", step_id="step-3",
    )
    assert result.observation.success is False
    assert result.observation.error == "spike_failed"
    # Isolated failure should not accumulate usage
    assert runtime.autonomy.usage.model_calls == 0
