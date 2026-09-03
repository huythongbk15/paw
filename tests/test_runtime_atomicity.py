"""Crash-boundary proofs for runtime persistence transactions."""

from __future__ import annotations

import pytest

from paw.core.autonomy import AutonomyController
from paw.core.checkpoint import CheckpointStore, OperationRecordStore
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.models import Capability, ExecutionObservation, ProposedAction, TaskStatus
from paw.core.runtime import PawRuntime
from paw.core.session import SessionManager
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager


def _proposal(operation_id: str, *, done: bool = False) -> ProposedAction:
    return ProposedAction(
        goal="atomic operation",
        capabilities=[Capability.FILESYSTEM_READ],
        operation_id=operation_id,
        metadata={"done": done},
    )


async def _successful_step(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
    return ExecutionObservation(
        step_id="adapter-step",
        action_id=proposed.operation_id,
        result={"done": True, "progress": 1.0},
        success=True,
    )


async def _reopen(path) -> None:
    await db.close()
    await set_db_path(path)
    await db.initialize()


async def test_operation_and_ledger_roll_back_together_on_commit_failure(
    temp_db,
    monkeypatch,
) -> None:
    runtime = PawRuntime(AutonomyController())
    original_record = OperationRecordStore.record

    async def fail_after_record(record, **kwargs):
        await original_record(record, **kwargs)
        raise RuntimeError("crash after operation row")

    monkeypatch.setattr(OperationRecordStore, "record", fail_after_record)

    with pytest.raises(RuntimeError, match="crash after operation row"):
        await runtime._execute_unit(
            "atomic-task",
            _proposal("atomic-operation"),
            iteration_index=0,
            step_fn=_successful_step,
            operation_type="step",
            step_id="step-1",
        )

    await _reopen(temp_db)
    assert await OperationRecordStore.get_all("atomic-task") == []
    events = await TaskLedger.get_events("atomic-task")
    assert TaskEventType.STEP_EXECUTED not in {event.event_type for event in events}
    assert TaskEventType.OPERATION_RECORDED not in {
        event.event_type for event in events
    }


async def test_terminal_task_checkpoint_and_ledger_roll_back_together(
    temp_db,
    monkeypatch,
) -> None:
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, "atomic terminal")
    runtime = PawRuntime(AutonomyController())
    original_save = CheckpointStore.save

    async def fail_after_checkpoint(checkpoint, **kwargs):
        checkpoint_id = await original_save(checkpoint, **kwargs)
        if "completed" in checkpoint.tags:
            raise RuntimeError("crash after terminal checkpoint")
        return checkpoint_id

    monkeypatch.setattr(CheckpointStore, "save", fail_after_checkpoint)

    with pytest.raises(RuntimeError, match="crash after terminal checkpoint"):
        await runtime.run(
            task.id,
            task_goal=task.goal,
            step_fn=_successful_step,
        )

    await _reopen(temp_db)
    restored = await TaskManager.get(task.id)
    assert restored is not None
    assert restored.status == TaskStatus.RUNNING
    assert await CheckpointStore.get_latest(task.id) is None
    assert await OperationRecordStore.is_completed(task.id, f"op_{task.id}_1") is True
    events = await TaskLedger.get_events(task.id)
    assert TaskEventType.TASK_COMPLETED not in {event.event_type for event in events}


async def test_terminal_task_status_failure_rolls_back_checkpoint_and_ledger(
    temp_db,
    monkeypatch,
) -> None:
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, "atomic task status")
    runtime = PawRuntime(AutonomyController())
    original_update_status = TaskManager.update_status

    async def fail_after_status(task_id, status, error=None, **kwargs):
        result = await original_update_status(
            task_id,
            status,
            error=error,
            **kwargs,
        )
        if status == TaskStatus.COMPLETED:
            raise RuntimeError("crash after terminal task status")
        return result

    monkeypatch.setattr(TaskManager, "update_status", fail_after_status)

    with pytest.raises(RuntimeError, match="crash after terminal task status"):
        await runtime.run(
            task.id,
            task_goal=task.goal,
            step_fn=_successful_step,
        )

    await _reopen(temp_db)
    restored = await TaskManager.get(task.id)
    assert restored is not None
    assert restored.status == TaskStatus.RUNNING
    assert await CheckpointStore.get_latest(task.id) is None
    events = await TaskLedger.get_events(task.id)
    event_types = {event.event_type for event in events}
    assert TaskEventType.CHECKPOINT_CREATED not in event_types
    assert TaskEventType.TASK_COMPLETED not in event_types


async def test_terminal_ledger_failure_rolls_back_task_and_checkpoint(
    temp_db,
    monkeypatch,
) -> None:
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, "atomic terminal ledger")
    runtime = PawRuntime(AutonomyController())
    original_record = TaskLedger.record

    async def fail_after_terminal_event(
        task_id,
        event_type,
        payload=None,
        **kwargs,
    ):
        event = await original_record(
            task_id,
            event_type,
            payload,
            **kwargs,
        )
        if event_type == TaskEventType.TASK_COMPLETED:
            raise RuntimeError("crash after terminal ledger")
        return event

    monkeypatch.setattr(TaskLedger, "record", fail_after_terminal_event)

    with pytest.raises(RuntimeError, match="crash after terminal ledger"):
        await runtime.run(
            task.id,
            task_goal=task.goal,
            step_fn=_successful_step,
        )

    await _reopen(temp_db)
    restored = await TaskManager.get(task.id)
    assert restored is not None
    assert restored.status == TaskStatus.RUNNING
    assert await CheckpointStore.get_latest(task.id) is None
    events = await TaskLedger.get_events(task.id)
    event_types = {event.event_type for event in events}
    assert TaskEventType.CHECKPOINT_CREATED not in event_types
    assert TaskEventType.TASK_COMPLETED not in event_types
