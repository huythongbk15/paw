"""Reviewed implementation and read-only recovery through the shared unit."""

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from paw.core.approval import ApprovalStore
from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.executor import CapabilityRouter, ExecutorRegistry
from paw.core.models import Capability, ExecutionObservation, ProposedAction, PolicyDecision, ResourceUsage
from paw.core.planner import Planner
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.runtime_persistence import RuntimePersistence
from paw.core.storage import db
from paw.executors.filesystem import LocalFilesystemExecutor
from test_plan_decision_binding import setup_decision


async def admitted(tmp_path):
    root, task, final, constraints = await setup_decision(tmp_path)
    review = await ApprovalStore.request_decision_review(final.version_id)
    await ApprovalStore.approve(review.id, "fixture-human")
    plan = await Planner(workspace_root=root, hard_constraints=constraints).plan(
        task.id, purpose="implementation", decision_version_id=final.version_id,
    )
    guard = PolicyGuard(interactive=True)
    registry = ExecutorRegistry()
    executor = LocalFilesystemExecutor(root)
    registry.register(executor)
    runtime = PawRuntime(
        AutonomyController(budget=AutonomyBudget(), policy_guard=guard),
        project_root=str(root), hard_constraints=constraints,
        approval_store=ApprovalStore, capability_router=CapabilityRouter(registry),
    )
    action = ProposedAction(
        goal=task.goal, operation_id="reviewed-write", idempotency_key="write-key",
        capabilities=[Capability.FILESYSTEM_WRITE], is_mutating=False,
        metadata={"plan_id": plan.id, "done": True, "preferred_executor": "local-filesystem",
                  "filesystem": {"operation": "write", "path": "result.txt", "content": "result", "mode": "create"}},
    )
    action = runtime._scope_implementation(action)
    approval = await ApprovalStore.request(task.id, action)
    await ApprovalStore.approve(approval.id, "fixture-human")
    return root, task, runtime, action, executor


async def unit(task, runtime, action, step):
    return await runtime._execute_unit(task.id, action, iteration_index=0,
                                       step_fn=step, operation_type="step", step_id="step-1")


@pytest.mark.parametrize("isolated", [False, True])
async def test_reviewed_fresh_callback_passes_and_policy_runs_once(tmp_path, monkeypatch, isolated):
    _, task, runtime, action, _ = await admitted(tmp_path)
    action.isolated = isolated
    approval = await ApprovalStore.request(task.id, action)
    await ApprovalStore.approve(approval.id)
    check = AsyncMock(wraps=runtime.autonomy.policy_guard.evaluate_request)
    monkeypatch.setattr(runtime.autonomy.policy_guard, "evaluate_request", check)
    step = AsyncMock(return_value=ExecutionObservation(
        step_id="step-1", action_id=action.operation_id, success=True, resources_used=ResourceUsage(tool_calls=1),
    ))
    result = await unit(task, runtime, action, step)
    assert result.operation_completed
    step.assert_awaited_once()
    check.assert_awaited_once()
    assert check.call_args.kwargs["capability_contexts"][Capability.FILESYSTEM_READ]["path"]
    assert runtime.autonomy.usage.tool_calls == 1
    assert (await ApprovalStore.get(approval.id)).status.value == "consumed"


@pytest.mark.parametrize("failure", ["dirty", "foreign", "forged_plan", "constraints"])
async def test_bad_binding_never_calls_effect(tmp_path, failure):
    root, task, runtime, action, _ = await admitted(tmp_path)
    if failure == "dirty":
        (root / "a.py").write_text("external edit")
    elif failure == "foreign":
        from paw.core.task import TaskManager
        task = await TaskManager.create("foreign-session", "foreign goal")
    elif failure == "forged_plan":
        action.metadata["plan_id"] = "invented"
    else:
        runtime._implementation_planner._constraint_fingerprint = "different"
    # Approval is still over the exact candidate, never a hard-DENY override.
    approval = await ApprovalStore.request(task.id, action)
    await ApprovalStore.approve(approval.id)
    step = AsyncMock()
    result = await unit(task, runtime, action, step)
    step.assert_not_awaited()
    assert result.observation is not None and not result.observation.success
    assert result.step_called is False


async def test_read_policy_denial_prevents_snapshot_and_callback(tmp_path, monkeypatch):
    _, task, runtime, action, _ = await admitted(tmp_path)
    runtime.autonomy.policy_guard._default_decisions[Capability.FILESYSTEM_READ] = PolicyDecision.DENY
    snapshot = Mock(side_effect=AssertionError("Policy-denied freshness read"))
    monkeypatch.setattr("paw.knowledge.checksum.compute_repo_revision", snapshot)
    step = AsyncMock()
    result = await unit(task, runtime, action, step)
    snapshot.assert_not_called()
    step.assert_not_awaited()
    assert result.gate is not None and result.gate.step_called is False


async def test_direct_private_executor_call_cannot_use_reviewed_plan(tmp_path):
    root, task, runtime, action, _ = await admitted(tmp_path)
    result = await runtime._execute_action(task.id, action)
    assert not result.success and "shared_unit_required" in result.error
    assert not (root / "result.txt").exists()


@pytest.mark.parametrize("change", ["none", "ambiguous", "action", "callback", "stale_decision", "overridden_port"])
async def test_crash_reopen_reconciles_exact_intent_without_execute_or_callback(tmp_path, monkeypatch, change):
    root, task, runtime, action, executor = await admitted(tmp_path)
    commit = RuntimePersistence.commit_operation
    async def crash(**kwargs):
        raise RuntimeError("fixture crash after effect")
    monkeypatch.setattr(RuntimePersistence, "commit_operation", crash)
    with pytest.raises(RuntimeError, match="fixture crash"):
        await unit(task, runtime, action, runtime._execute_action)
    assert (root / "result.txt").read_text() == "result"
    monkeypatch.setattr(RuntimePersistence, "commit_operation", commit)
    await db.close()
    await db.initialize()
    execute = AsyncMock(side_effect=AssertionError("recovery repeated write"))
    monkeypatch.setattr(executor, "execute", execute)
    model = AsyncMock(side_effect=AssertionError("recovery called model"))
    monkeypatch.setattr(runtime, "_execute_model", model)
    if change == "ambiguous":
        (root / "result.txt").write_text("external edit")
    elif change == "action":
        action.metadata["filesystem"]["content"] = "changed"
        approval = await ApprovalStore.request(task.id, action)
        await ApprovalStore.approve(approval.id)
    elif change == "stale_decision":
        from paw.core.reasoning_contracts import DecisionVersion
        version = await db.get_decision_version("final")
        await db.advance_decision_version(
            DecisionVersion("stale", version.decision_id, "stale", version.payload, "2026-10-07", "fixture-human"),
            expected_version_id="final",
        )
    elif change == "overridden_port":
        monkeypatch.setattr(executor, "reconcile_effect", AsyncMock(side_effect=AssertionError("unsafe override")))
    callback = AsyncMock(side_effect=AssertionError("recovery called arbitrary callback"))
    result = await unit(task, runtime, action, callback)
    execute.assert_not_awaited()
    callback.assert_not_awaited()
    model.assert_not_awaited()
    assert result.observation.success == (change in {"none", "callback", "stale_decision"})


async def test_child_task_cannot_inherit_executor_admission(tmp_path):
    import asyncio
    root, task, runtime, action, _ = await admitted(tmp_path)
    async def callback(task_id, proposed):
        child = await asyncio.create_task(runtime._execute_action(task_id, proposed))
        assert not child.success and "shared_unit_required" in child.error
        return ExecutionObservation(step_id="step-1", action_id=proposed.operation_id, success=True)
    await unit(task, runtime, action, callback)
    assert not (root / "result.txt").exists()
