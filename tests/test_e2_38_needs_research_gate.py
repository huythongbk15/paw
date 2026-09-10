"""E2-38: Make NEEDS_RESEARCH schedule only bounded research operations.

Four-layer evidence:
  1. Invariant  — ProposedAction has is_research field
  2. Runtime    — NEEDS_RESEARCH blocks non-research mutating proposals
  3. Adversarial — READY still allows everything; research proposals bypass NEEDS_RESEARCH gate
  4. Measurable — error message includes readiness level; is_research defaults to False (fail-closed)

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime


@pytest.mark.asyncio
async def test_inv1_proposed_action_has_is_research():
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
    )
    assert hasattr(proposed, "is_research")
    assert proposed.is_research is False  # fail-closed default


@pytest.mark.asyncio
async def test_rt1_needs_research_blocks_non_research_mutating():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="NEEDS_RESEARCH")
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
        is_mutating=True,
        is_research=False,
    )
    obs = await runtime._execute_action("task-1", proposed)
    assert obs.success is False
    assert "readiness_not_ready" in obs.error
    assert "NEEDS_RESEARCH" in obs.error


@pytest.mark.asyncio
async def test_rt2_needs_research_allows_research_proposals():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="NEEDS_RESEARCH")
    proposed = ProposedAction(
        operation_id="op-2",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-2",
        is_mutating=True,
        is_research=True,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-2", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt3_needs_research_allows_non_mutating():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="NEEDS_RESEARCH")
    proposed = ProposedAction(
        operation_id="op-3",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-3",
        is_mutating=False,
        is_research=False,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-3", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt4_ready_allows_non_research():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    proposed = ProposedAction(
        operation_id="op-4",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-4",
        is_mutating=True,
        is_research=False,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-4", proposed)
    assert obs.success is True
