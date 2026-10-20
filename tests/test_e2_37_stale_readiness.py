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
    assert "implementation_admission_refused" in obs.error
    assert "implementation_admission_refused" in obs.error
    assert "implementation_admission_refused" in obs.error
    assert "implementation_admission_refused" in obs.error


@pytest.mark.asyncio
async def test_rt2_revision_match_refuses_raw():
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
    assert obs.success is False


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
    assert "implementation_admission_refused" in obs.error
    assert "implementation_admission_refused" in obs.error
    assert "implementation_admission_refused" in obs.error
    assert "implementation_admission_refused" in obs.error


@pytest.mark.asyncio
async def test_rt4_empty_revision_refuses_raw():
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
    assert obs.success is False


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
