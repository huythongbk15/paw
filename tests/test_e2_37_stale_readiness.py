"""E2-37: Invalidate READY when the relevant project revision or hard constraint changes.

Four-layer evidence:
  1. Invariant  — PawRuntime accepts readiness_revision/current_revision
  2. Runtime    — stale revision or constraints blocks mutating proposals
  3. Adversarial — empty revision/constraints bypass staleness check (backward-compat)
  4. Measurable — error message includes stale dimension and old/new values

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime


@pytest.mark.asyncio
async def test_inv1_paw_runtime_has_revision_params():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    assert hasattr(runtime, "readiness_revision")
    assert hasattr(runtime, "current_revision")
    assert hasattr(runtime, "readiness_constraints")
    assert hasattr(runtime, "current_constraints")


@pytest.mark.asyncio
async def test_rt1_revision_mismatch_blocks():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(
        ac,
        readiness="READY",
        readiness_revision="abc",
        current_revision="def",  # mismatch
    )
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
        is_mutating=True,
    )
    obs = await runtime._execute_action("task-1", proposed)
    assert obs.success is False
    assert "readiness_stale" in obs.error
    assert "revision" in obs.error
    assert "abc" in obs.error
    assert "def" in obs.error


@pytest.mark.asyncio
async def test_rt2_revision_match_allows():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(
        ac,
        readiness="READY",
        readiness_revision="abc",
        current_revision="abc",  # match
    )
    proposed = ProposedAction(
        operation_id="op-2",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-2",
        is_mutating=True,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-2", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt3_constraint_mismatch_blocks():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(
        ac,
        readiness="READY",
        readiness_constraints="v1",
        current_constraints="v2",  # mismatch
    )
    proposed = ProposedAction(
        operation_id="op-3",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-3",
        is_mutating=True,
    )
    obs = await runtime._execute_action("task-3", proposed)
    assert obs.success is False
    assert "readiness_stale" in obs.error
    assert "constraints" in obs.error
    assert "v1" in obs.error
    assert "v2" in obs.error


@pytest.mark.asyncio
async def test_rt4_empty_revision_bypasses():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(
        ac,
        readiness="READY",
        readiness_revision="",  # empty -> no staleness check
        current_revision="def",
    )
    proposed = ProposedAction(
        operation_id="op-4",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-4",
        is_mutating=True,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-4", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_adv1_non_mutating_bypasses_staleness():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(
        ac,
        readiness="READY",
        readiness_revision="abc",
        current_revision="def",  # stale
    )
    proposed = ProposedAction(
        operation_id="op-5",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-5",
        is_mutating=False,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-5", proposed)
    assert obs.success is True
