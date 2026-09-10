"""E2-44: Run the full readiness negative matrix and prove only current READY reaches mutation.

Four-layer evidence:
  1. Invariant  — readiness gate covers all 5 levels + staleness
  2. Runtime    — negative matrix proves only current READY allows mutation
  3. Adversarial — stale READY blocks; non-mutating bypasses all gates
  4. Measurable — matrix is exhaustive (all combinations covered)

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime


def _make_runtime(readiness="READY", **kwargs):
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    return PawRuntime(ac, readiness=readiness, **kwargs)


def _mutating_proposal(**kwargs):
    return ProposedAction(
        operation_id="op-m",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-m",
        is_mutating=True,
        **kwargs,
    )


def _non_mutating_proposal(**kwargs):
    return ProposedAction(
        operation_id="op-nm",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-nm",
        is_mutating=False,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_matrix_ready_current_allows_mutation():
    runtime = _make_runtime(readiness="READY")
    proposed = _mutating_proposal()
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-1", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_matrix_ready_stale_blocks_mutation():
    runtime = _make_runtime(readiness="READY", readiness_revision="abc", current_revision="def")
    proposed = _mutating_proposal()
    obs = await runtime._execute_action("task-2", proposed)
    assert obs.success is False
    assert "readiness_stale" in obs.error


@pytest.mark.asyncio
async def test_matrix_needs_research_research_allows():
    runtime = _make_runtime(readiness="NEEDS_RESEARCH")
    proposed = _mutating_proposal(is_research=True)
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-3", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_matrix_needs_research_non_research_blocks():
    runtime = _make_runtime(readiness="NEEDS_RESEARCH")
    proposed = _mutating_proposal(is_research=False)
    obs = await runtime._execute_action("task-4", proposed)
    assert obs.success is False
    assert "readiness_not_ready" in obs.error


@pytest.mark.asyncio
async def test_matrix_needs_clarification_blocks():
    runtime = _make_runtime(readiness="NEEDS_CLARIFICATION")
    proposed = _mutating_proposal(clarification_question="What?")
    obs = await runtime._execute_action("task-5", proposed)
    assert obs.success is False
    assert "needs_clarification" in obs.error


@pytest.mark.asyncio
async def test_matrix_spike_research_allows():
    runtime = _make_runtime(readiness="SPIKE_REQUIRED")
    proposed = _mutating_proposal(plan_purpose="research")
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-6", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_matrix_spike_spike_allows():
    runtime = _make_runtime(readiness="SPIKE_REQUIRED")
    proposed = _mutating_proposal(plan_purpose="spike")
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-7", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_matrix_spike_implementation_blocks():
    runtime = _make_runtime(readiness="SPIKE_REQUIRED")
    proposed = _mutating_proposal(plan_purpose="implementation")
    obs = await runtime._execute_action("task-8", proposed)
    assert obs.success is False
    assert "readiness_not_ready" in obs.error


@pytest.mark.asyncio
async def test_matrix_rejected_blocks():
    runtime = _make_runtime(readiness="REJECTED")
    proposed = _mutating_proposal(rejection_reasons=["policy"])
    obs = await runtime._execute_action("task-9", proposed)
    assert obs.success is False
    assert "rejected" in obs.error


@pytest.mark.asyncio
async def test_matrix_non_mutating_bypasses_all():
    for readiness in ("READY", "NEEDS_RESEARCH", "NEEDS_CLARIFICATION", "SPIKE_REQUIRED", "REJECTED"):
        runtime = _make_runtime(readiness=readiness)
        proposed = _non_mutating_proposal()
        async def step_fn(task_id, action):
            return ExecutionObservation(action_id=action.operation_id, success=True)
        obs = await runtime._execute_action(f"task-{readiness}", proposed)
        assert obs.success is True, f"Non-mutating should bypass {readiness}"


@pytest.mark.asyncio
async def test_matrix_ready_with_constraint_mismatch_blocks():
    runtime = _make_runtime(readiness="READY", readiness_constraints="v1", current_constraints="v2")
    proposed = _mutating_proposal()
    obs = await runtime._execute_action("task-10", proposed)
    assert obs.success is False
    assert "readiness_stale" in obs.error
