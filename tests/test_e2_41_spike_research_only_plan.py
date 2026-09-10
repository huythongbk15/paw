"""E2-41: Make SPIKE_REQUIRED create only an explicitly research-only Plan.

Four-layer evidence:
  1. Invariant  — ProposedAction has plan_purpose field with default "implementation"
  2. Runtime    — SPIKE_REQUIRED blocks non-research/spike plans
  3. Adversarial — research/spike plans bypass gate; READY bypasses gate
  4. Measurable — error message includes readiness level; plan_purpose defaults to implementation (fail-closed)

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime


@pytest.mark.asyncio
async def test_inv1_proposed_action_has_plan_purpose():
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
    )
    assert hasattr(proposed, "plan_purpose")
    assert proposed.plan_purpose == "implementation"  # fail-closed default


@pytest.mark.asyncio
async def test_rt1_spike_required_blocks_implementation_plan():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="SPIKE_REQUIRED")
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
        is_mutating=True,
        plan_purpose="implementation",
    )
    obs = await runtime._execute_action("task-1", proposed)
    assert obs.success is False
    assert "readiness_not_ready" in obs.error
    assert "SPIKE_REQUIRED" in obs.error


@pytest.mark.asyncio
async def test_rt2_spike_required_allows_research_plan():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="SPIKE_REQUIRED")
    proposed = ProposedAction(
        operation_id="op-2",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-2",
        is_mutating=True,
        plan_purpose="research",
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-2", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt3_spike_required_allows_spike_plan():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="SPIKE_REQUIRED")
    proposed = ProposedAction(
        operation_id="op-3",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-3",
        is_mutating=True,
        plan_purpose="spike",
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-3", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt4_spike_required_allows_non_mutating():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="SPIKE_REQUIRED")
    proposed = ProposedAction(
        operation_id="op-4",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-4",
        is_mutating=False,
        plan_purpose="implementation",
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-4", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt5_ready_bypasses_spike_gate():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    proposed = ProposedAction(
        operation_id="op-5",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-5",
        is_mutating=True,
        plan_purpose="implementation",
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-5", proposed)
    assert obs.success is True
