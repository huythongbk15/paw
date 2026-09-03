"""Crash/restart proofs for prepared external executor effects."""

from __future__ import annotations

import pytest

from paw.core.autonomy import AutonomyController
from paw.core.checkpoint import OperationRecordStore
from paw.core.executor import CapabilityRouter, ExecutorRegistry
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.models import Capability, ProposedAction
from paw.core.runtime import PawRuntime
from paw.core.runtime_persistence import RuntimePersistence
from paw.core.storage import db, set_db_path
from paw.executors.filesystem import LocalFilesystemExecutor


class CountingFilesystemExecutor(LocalFilesystemExecutor):
    def __init__(self, workspace_root):
        super().__init__(workspace_root)
        self.execution_count = 0

    async def execute(self, task, context):
        self.execution_count += 1
        return await super().execute(task, context)


def _runtime(executor: LocalFilesystemExecutor) -> PawRuntime:
    registry = ExecutorRegistry()
    registry.register(executor)
    return PawRuntime(
        AutonomyController(),
        capability_router=CapabilityRouter(registry),
        auto_checkpoint=False,
    )


def _write_proposal() -> ProposedAction:
    return ProposedAction(
        goal="create durable file",
        capabilities=[Capability.FILESYSTEM_WRITE],
        operation_id="filesystem-operation-0001",
        idempotency_key="filesystem-idempotency-0001",
        metadata={
            "done": True,
            "preferred_executor": "local-filesystem",
            "filesystem": {
                "operation": "write",
                "path": "notes/durable.txt",
                "content": "durable content\n",
                "mode": "create",
            },
        },
    )


async def _crash_after_effect(
    *,
    runtime: PawRuntime,
    proposal: ProposedAction,
    monkeypatch,
) -> None:
    original_commit = RuntimePersistence.commit_operation

    async def simulate_crash(**kwargs):
        raise RuntimeError("crash before local operation commit")

    monkeypatch.setattr(RuntimePersistence, "commit_operation", simulate_crash)
    with pytest.raises(RuntimeError, match="crash before local operation commit"):
        await runtime._execute_unit(
            "external-effect-task",
            proposal,
            iteration_index=0,
            step_fn=runtime._execute_action,
            operation_type="step",
            step_id="step-1",
        )
    monkeypatch.setattr(RuntimePersistence, "commit_operation", original_commit)


async def _reopen(path) -> None:
    await db.close()
    await set_db_path(path)
    await db.initialize()


async def test_resume_reconciles_applied_filesystem_effect_without_repeating_it(
    temp_db,
    tmp_path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = CountingFilesystemExecutor(workspace)
    proposal = _write_proposal()

    await _crash_after_effect(
        runtime=_runtime(executor),
        proposal=proposal,
        monkeypatch=monkeypatch,
    )

    target = workspace / "notes" / "durable.txt"
    assert target.read_text() == "durable content\n"
    prepared = await OperationRecordStore.get(
        "external-effect-task",
        proposal.operation_id,
    )
    assert prepared is not None
    assert prepared.status == "prepared"
    interrupted_events = await TaskLedger.get_events("external-effect-task")
    interrupted_event_types = [event.event_type for event in interrupted_events]
    assert TaskEventType.OPERATION_RECORDED in interrupted_event_types
    assert TaskEventType.ARTIFACT_CREATED not in interrupted_event_types
    assert TaskEventType.EXECUTION_COMPLETED not in interrupted_event_types
    assert TaskEventType.STEP_EXECUTED not in interrupted_event_types

    await _reopen(temp_db)
    resumed_runtime = _runtime(executor)
    resumed = await resumed_runtime._execute_unit(
        "external-effect-task",
        proposal,
        iteration_index=0,
        step_fn=resumed_runtime._execute_action,
        operation_type="step",
        step_id="step-1",
    )

    assert resumed.observation is not None
    assert resumed.observation.success is True
    assert resumed.observation.result["executor_metadata"]["reconciliation"] == "applied"
    assert executor.execution_count == 1
    assert await OperationRecordStore.is_completed(
        "external-effect-task",
        proposal.operation_id,
    )
    completed_events = await TaskLedger.get_events("external-effect-task")
    assert sum(
        event.event_type == TaskEventType.ARTIFACT_CREATED
        for event in completed_events
    ) == 1


async def test_prepare_commit_failure_prevents_filesystem_effect(
    tmp_path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = CountingFilesystemExecutor(workspace)
    runtime = _runtime(executor)
    proposal = _write_proposal()

    async def fail_prepare(**kwargs):
        raise RuntimeError("prepared intent is not durable")

    monkeypatch.setattr(RuntimePersistence, "prepare_operation", fail_prepare)
    with pytest.raises(RuntimeError, match="prepared intent is not durable"):
        await runtime._execute_unit(
            "external-effect-task",
            proposal,
            iteration_index=0,
            step_fn=runtime._execute_action,
            operation_type="step",
            step_id="step-1",
        )

    assert executor.execution_count == 0
    assert not (workspace / "notes" / "durable.txt").exists()


async def test_resume_blocks_when_prepared_filesystem_effect_is_ambiguous(
    temp_db,
    tmp_path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = CountingFilesystemExecutor(workspace)
    proposal = _write_proposal()

    await _crash_after_effect(
        runtime=_runtime(executor),
        proposal=proposal,
        monkeypatch=monkeypatch,
    )
    target = workspace / "notes" / "durable.txt"
    target.write_text("external edit\n")

    await _reopen(temp_db)
    resumed_runtime = _runtime(executor)
    resumed = await resumed_runtime._execute_unit(
        "external-effect-task",
        proposal,
        iteration_index=0,
        step_fn=resumed_runtime._execute_action,
        operation_type="step",
        step_id="step-1",
    )

    assert resumed.observation is not None
    assert resumed.observation.success is False
    assert "ambiguous" in (resumed.observation.error or "")
    assert executor.execution_count == 1
    assert target.read_text() == "external edit\n"
