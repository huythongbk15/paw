"""Atomic runtime persistence boundaries.

The runtime produces several records for one logical transition: an
observation, its replay/idempotency record, a checkpoint and task lifecycle
state.  This module is the single coordinator for the boundaries that must be
durable together.  Adapters may still have external side effects, but PAW's
local evidence is committed atomically and can therefore never claim a
partially persisted transition.
"""

from __future__ import annotations

from typing import Any

from .checkpoint import (
    CheckpointStore,
    OperationRecord,
    OperationRecordStore,
    TaskCheckpoint,
)
from .ledger import TaskEventType, TaskLedger
from .logging import get_logger
from .models import ExecutionObservation, TaskStatus
from .storage import db
from .task import TaskManager

logger = get_logger(__name__)


class RuntimePersistence:
    """Commit local evidence for one runtime transition as one SQLite unit."""

    @staticmethod
    async def prepare_operation(
        *,
        task_id: str,
        operation_id: str,
        op_type: str,
        effect_intent: dict[str, Any],
        ledger_context: dict[str, Any] | None = None,
    ) -> OperationRecord:
        """Durably record an external effect intent before invoking its adapter."""
        context = dict(ledger_context or {})
        record = OperationRecord(
            task_id=task_id,
            op_id=operation_id,
            op_type=op_type,
            status="prepared",
            metadata={"effect_intent": effect_intent},
        )
        await db.initialize()
        async with db.transaction() as connection:
            await OperationRecordStore.record(record, connection=connection)
            await TaskLedger.record(
                task_id,
                TaskEventType.OPERATION_RECORDED,
                {
                    "op_id": operation_id,
                    "op_type": op_type,
                    "status": "prepared",
                    "checkpoint_id": None,
                    "effect_intent": effect_intent,
                    **context,
                },
                connection=connection,
            )
        return record

    @staticmethod
    async def commit_operation(
        *,
        task_id: str,
        operation_id: str,
        op_type: str,
        status: str,
        result_ref: str | None,
        observation: ExecutionObservation,
        done: bool,
        progress: float,
        ledger_context: dict[str, Any] | None = None,
        operation_metadata: dict[str, Any] | None = None,
    ) -> OperationRecord:
        """Persist observation events and operation record atomically."""
        context = dict(ledger_context or {})
        observation_payload = {
            "action_id": operation_id,
            "success": observation.success,
            "resources_used": (
                observation.resources_used.model_dump()
                if observation.resources_used
                else None
            ),
            "error": observation.error,
            **context,
        }
        record = OperationRecord(
            task_id=task_id,
            op_id=operation_id,
            op_type=op_type,
            status=status,
            result_ref=result_ref,
            metadata=dict(operation_metadata or {}),
        )

        await db.initialize()
        async with db.transaction() as connection:
            await TaskLedger.record(
                task_id,
                TaskEventType.STEP_EXECUTED,
                observation_payload,
                connection=connection,
            )
            observation_result = (
                observation.result if isinstance(observation.result, dict) else {}
            )
            executor_name = observation_result.get("executor")
            for artifact in observation_result.get("artifacts") or []:
                await TaskLedger.record(
                    task_id,
                    TaskEventType.ARTIFACT_CREATED,
                    {
                        "executor": executor_name,
                        "operation_id": operation_id,
                        **artifact,
                    },
                    connection=connection,
                )
            if executor_name:
                await TaskLedger.record(
                    task_id,
                    TaskEventType.EXECUTION_COMPLETED,
                    {
                        "skill": observation_result.get("skill"),
                        "executor": executor_name,
                        "executed": observation.success,
                        "done": done,
                        "error": observation.error,
                    },
                    connection=connection,
                )
            await OperationRecordStore.record(record, connection=connection)
            await TaskLedger.record(
                task_id,
                TaskEventType.OPERATION_RECORDED,
                {
                    "op_id": operation_id,
                    "op_type": op_type,
                    "status": status,
                    "checkpoint_id": None,
                    **context,
                },
                connection=connection,
            )
            await TaskLedger.record(
                task_id,
                TaskEventType.STEP_COMPLETED,
                {
                    "action_id": operation_id,
                    "done": done,
                    "progress": progress,
                    **context,
                },
                connection=connection,
            )
        return record

    @staticmethod
    async def commit_checkpoint(
        *,
        checkpoint: TaskCheckpoint,
        task_status: TaskStatus | None = None,
        error: str | None = None,
        terminal_summary: str | None = None,
    ) -> TaskCheckpoint:
        """Commit checkpoint, checkpoint event and optional task terminal state.

        If any write fails, SQLite rolls back all writes in this boundary.  In
        particular, a terminal task status cannot be durable without its
        checkpoint and corresponding ledger evidence.
        """
        await db.initialize()
        async with db.transaction() as connection:
            await CheckpointStore.save(checkpoint, connection=connection)
            await TaskLedger.record(
                checkpoint.task_id,
                TaskEventType.CHECKPOINT_CREATED,
                {
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "progress_ratio": checkpoint.progress_ratio,
                    "current_step": checkpoint.current_step,
                    "total_steps": checkpoint.total_steps,
                    "tags": checkpoint.tags,
                },
                connection=connection,
            )
            if task_status is not None:
                await TaskManager.update_status(
                    checkpoint.task_id,
                    task_status,
                    error=error,
                    connection=connection,
                )
            if terminal_summary is not None:
                status_value = (
                    task_status.value
                    if isinstance(task_status, TaskStatus)
                    else checkpoint.task_status
                )
                await TaskLedger.record(
                    checkpoint.task_id,
                    TaskEventType.TASK_COMPLETED,
                    {"status": status_value, "summary": terminal_summary},
                    connection=connection,
                )
        logger.info(
            "runtime_checkpoint_committed",
            task_id=checkpoint.task_id,
            checkpoint_id=checkpoint.checkpoint_id,
            task_status=task_status.value if task_status else None,
        )
        return checkpoint


__all__ = ["RuntimePersistence"]
