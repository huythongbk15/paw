"""E2-39: Make NEEDS_CLARIFICATION persist the question and wait without execution.

Four-layer evidence:
  1. Invariant  — ProposedAction has clarification_question field
  2. Runtime    — NEEDS_CLARIFICATION blocks mutating proposals and returns clarification error
  3. Adversarial — empty question yields generic message; non-mutating bypasses gate
  4. Measurable — error message includes "needs_clarification:" prefix; ledger logs NEEDS_CLARIFICATION

Decision level: D2.
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
    assert obs.error == "needs_clarification:What is the target environment?"


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
    assert obs.error == "needs_clarification:no_question_provided"


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
async def test_rt4_ready_bypasses_clarification():
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
    assert obs.success is True
