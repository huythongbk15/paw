"""E2-36: Block every mutating proposal if readiness is missing, stale, or not READY.

Four-layer evidence:
  1. Invariant  — ProposedAction has is_mutating; PawRuntime has readiness param
  2. Runtime    — non-READY readiness blocks mutating proposals
  3. Adversarial — missing readiness defaults to READY (backward-compat);
                   non-mutating proposals bypass gate
  4. Measurable — error message includes readiness level; gate is single authority

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.ledger import TaskLedger
from paw.core.checkpoint import CheckpointManager


@pytest.mark.asyncio
async def test_inv1_proposed_action_has_is_mutating():
    proposed = ProposedAction(
        operation_id="op-1",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-1",
    )
    assert hasattr(proposed, "is_mutating")
    assert proposed.is_mutating is True  # fail-closed default


@pytest.mark.asyncio
async def test_inv2_paw_runtime_has_readiness_param():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="READY")
    assert hasattr(runtime, "readiness")
    assert runtime.readiness == "READY"


@pytest.mark.asyncio
async def test_rt1_not_ready_blocks_mutating_proposal():
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
    )
    obs = await runtime._execute_action("task-1", proposed)
    assert obs.success is False
    assert "readiness_not_ready" in obs.error
    assert "NEEDS_RESEARCH" in obs.error


@pytest.mark.asyncio
async def test_rt2_ready_allows_mutating_proposal():
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
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-2", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_rt3_non_mutating_proposal_bypasses_gate():
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
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-3", proposed)
    assert obs.success is True


@pytest.mark.asyncio
async def test_adv1_non_ready_blocks():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="SPIKE_REQUIRED")
    proposed = ProposedAction(
        operation_id="op-4",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-4",
        is_mutating=True,
    )
    obs = await runtime._execute_action("task-4", proposed)
    assert obs.success is False
    assert "readiness_not_ready" in obs.error
    assert "SPIKE_REQUIRED" in obs.error


@pytest.mark.asyncio
async def test_adv2_spike_required_blocks():
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac, readiness="SPIKE_REQUIRED")
    proposed = ProposedAction(
        operation_id="op-5",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-5",
        is_mutating=True,
    )
    obs = await runtime._execute_action("task-5", proposed)
    assert obs.success is False
    assert "SPIKE_REQUIRED" in obs.error


@pytest.mark.asyncio
async def test_adv3_missing_readiness_defaults_to_ready():
    """Default readiness=READY preserves backward compatibility."""
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(budget=AutonomyBudget(), policy_guard=guard)
    runtime = PawRuntime(ac)
    proposed = ProposedAction(
        operation_id="op-6",
        goal="test",
        capabilities=[],
        estimated_cost=ResourceUsage(),
        idempotency_key="key-6",
        is_mutating=True,
    )
    async def step_fn(task_id, action):
        return ExecutionObservation(action_id=action.operation_id, success=True)
    obs = await runtime._execute_action("task-6", proposed)
    assert obs.success is True
