"""Legacy raw readiness is diagnostic, never executable authority.

Migrated 2026-10-07: private mutating calls must refuse even with READY/research/
spike flags. Reviewed positive, real freshness and recovery proofs are in
 test_runtime_implementation_admission.py; no raw-string compatibility bypass.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime


@pytest.mark.asyncio
async def test_inv1_proposed_action_has_clarification_question():
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
    )
    assert hasattr(proposed, "clarification_question")
    assert proposed.clarification_question == ""


@pytest.mark.asyncio
async def test_rt1_needs_clarification_blocks_with_question():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="NEEDS_CLARIFICATION")
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
        is_mutating=True,
        clarification_question="What is the target environment?",
    )
    obs = await runtime._execute_action("task-1", proposed)
    assert obs.success is False
    assert "implementation_admission_refused" in obs.error


@pytest.mark.asyncio
async def test_rt2_needs_clarification_blocks_empty_question():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="NEEDS_CLARIFICATION")
    proposed = ProposedAction(
        operation_id="op-2",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-2",
        is_mutating=True,
        clarification_question="",
    )
    obs = await runtime._execute_action("task-2", proposed)
    assert obs.success is False
    assert "implementation_admission_refused" in obs.error


@pytest.mark.asyncio
async def test_rt3_needs_clarification_allows_non_mutating():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="NEEDS_CLARIFICATION")
    proposed = ProposedAction(
        operation_id="op-3",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-3",
        is_mutating=False,
        clarification_question="What is the target?",
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-3", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt4_ready_refuses_raw_clarification():
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
        clarification_question="What is the target?",
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-4", proposed)
    assert obs.success is False
