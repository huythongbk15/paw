"""
PAW Core — Task Checkpoint & Resume (Phase 10)

Provides durable checkpointing and resume capability for long-running tasks.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .autonomy import AutonomyUsage
from .ledger import TaskEventType, TaskLedger
from .logging import get_logger
from .models import ExtendedTaskStatus
from .storage import db

logger = get_logger(__name__)

__all__ = ["CheckpointStore", "ExtendedTaskStatus", "ResumeManager", "TaskCheckpoint"]


# --- Checkpoint ---

@dataclass
class TaskCheckpoint:
    """Complete task state for resume."""
    task_id: str
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Core state
    task_status: str = ""
    current_step: int = 0
    total_steps: int = 0
    progress_ratio: float = 0.0

    # Context
    context: dict[str, Any] = field(default_factory=dict)
    context_compiler_state: dict[str, Any] = field(default_factory=dict)

    # Autonomy
    autonomy_usage: dict[str, Any] = field(default_factory=dict)
    autonomy_profile: str = "balanced"

    # Detectors state
    progress_history: list[float] = field(default_factory=list)
    repetition_state: dict[str, Any] = field(default_factory=dict)
    stall_state: dict[str, Any] = field(default_factory=dict)

    # Loop state
    loop_iteration: int = 0
    loop_decision_history: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    parent_checkpoint_id: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "task_id": self.task_id,
            "checkpoint_id": self.checkpoint_id,
            "task_status": self.task_status,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "progress_ratio": self.progress_ratio,
            "context": self.context,
            "context_compiler_state": self.context_compiler_state,
            "autonomy_usage": self.autonomy_usage,
            "autonomy_profile": self.autonomy_profile,
            "progress_history": self.progress_history,
            "repetition_state": self.repetition_state,
            "stall_state": self.stall_state,
            "loop_iteration": self.loop_iteration,
            "loop_decision_history": self.loop_decision_history,
            "created_at": self.created_at.isoformat(),
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskCheckpoint:
        """Deserialize from dict."""
        cp = cls(
            task_id=data["task_id"],
            checkpoint_id=data.get("checkpoint_id", str(uuid.uuid4())[:8]),
            task_status=data.get("task_status", ""),
            current_step=data.get("current_step", 0),
            total_steps=data.get("total_steps", 0),
            progress_ratio=data.get("progress_ratio", 0.0),
            context=data.get("context", {}),
            context_compiler_state=data.get("context_compiler_state", {}),
            autonomy_usage=data.get("autonomy_usage", {}),
            autonomy_profile=data.get("autonomy_profile", "balanced"),
            progress_history=data.get("progress_history", []),
            repetition_state=data.get("repetition_state", {}),
            stall_state=data.get("stall_state", {}),
            loop_iteration=data.get("loop_iteration", 0),
            loop_decision_history=data.get("loop_decision_history", []),
            parent_checkpoint_id=data.get("parent_checkpoint_id"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        if "created_at" in data:
            cp.created_at = datetime.fromisoformat(data["created_at"])
        return cp


# --- Checkpoint Store ---

class CheckpointStore:
    """Manages task checkpoints in SQLite."""

    TABLE_NAME = "task_checkpoints"

    @classmethod
    async def ensure_table(cls) -> None:
        """Ensure the canonical runtime schema is loaded."""
        await db.initialize()

    @classmethod
    async def save(cls, checkpoint: TaskCheckpoint) -> str:
        """Save checkpoint to database."""
        await cls.ensure_table()

        data = checkpoint.to_dict()

        await db.execute(
            f"""
            INSERT OR REPLACE INTO {cls.TABLE_NAME} (
                checkpoint_id, task_id, task_status, current_step, total_steps,
                progress_ratio, context, context_compiler_state, autonomy_usage,
                autonomy_profile, progress_history, repetition_state, stall_state,
                loop_iteration, loop_decision_history, created_at,
                parent_checkpoint_id, tags, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["checkpoint_id"],
                data["task_id"],
                data["task_status"],
                data["current_step"],
                data["total_steps"],
                data["progress_ratio"],
                json.dumps(data["context"]),
                json.dumps(data["context_compiler_state"]),
                json.dumps(data["autonomy_usage"]),
                data["autonomy_profile"],
                json.dumps(data["progress_history"]),
                json.dumps(data["repetition_state"]),
                json.dumps(data["stall_state"]),
                data["loop_iteration"],
                json.dumps(data["loop_decision_history"]),
                data["created_at"],
                data.get("parent_checkpoint_id"),
                json.dumps(data["tags"]),
                json.dumps(data["metadata"]),
            ),
        )

        logger.info(
            "checkpoint_saved",
            task_id=checkpoint.task_id,
            checkpoint_id=checkpoint.checkpoint_id,
            progress=checkpoint.progress_ratio,
        )

        return checkpoint.checkpoint_id

    @classmethod
    async def get_latest(cls, task_id: str) -> TaskCheckpoint | None:
        """Get latest checkpoint for a task."""
        await cls.ensure_table()

        row = await db.fetchone(
            f"SELECT * FROM {cls.TABLE_NAME} WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        if not row:
            return None

        return cls._row_to_checkpoint(dict(row))

    @classmethod
    async def get_by_id(cls, checkpoint_id: str) -> TaskCheckpoint | None:
        """Get checkpoint by ID."""
        await cls.ensure_table()

        row = await db.fetchone(
            f"SELECT * FROM {cls.TABLE_NAME} WHERE checkpoint_id = ?",
            (checkpoint_id,),
        )
        if not row:
            return None

        return cls._row_to_checkpoint(dict(row))

    @classmethod
    async def list_for_task(cls, task_id: str, limit: int = 20) -> list[TaskCheckpoint]:
        """List checkpoints for a task."""
        await cls.ensure_table()

        rows = await db.fetchall(
            f"SELECT * FROM {cls.TABLE_NAME} WHERE task_id = ? ORDER BY created_at DESC LIMIT ?",
            (task_id, limit),
        )
        return [cls._row_to_checkpoint(dict(row)) for row in rows]

    @classmethod
    async def delete(cls, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        await cls.ensure_table()

        result = await db.execute(
            f"DELETE FROM {cls.TABLE_NAME} WHERE checkpoint_id = ?",
            (checkpoint_id,),
        )
        return result.rowcount > 0

    @classmethod
    def _row_to_checkpoint(cls, row: dict[str, Any]) -> TaskCheckpoint:
        return TaskCheckpoint(
            task_id=row["task_id"],
            checkpoint_id=row["checkpoint_id"],
            task_status=row["task_status"],
            current_step=row["current_step"],
            total_steps=row["total_steps"],
            progress_ratio=row["progress_ratio"],
            context=json.loads(row["context"]) if row["context"] else {},
            context_compiler_state=json.loads(row["context_compiler_state"]) if row["context_compiler_state"] else {},
            autonomy_usage=json.loads(row["autonomy_usage"]) if row["autonomy_usage"] else {},
            autonomy_profile=row["autonomy_profile"],
            progress_history=json.loads(row["progress_history"]) if row["progress_history"] else [],
            repetition_state=json.loads(row["repetition_state"]) if row["repetition_state"] else {},
            stall_state=json.loads(row["stall_state"]) if row["stall_state"] else {},
            loop_iteration=row["loop_iteration"],
            loop_decision_history=json.loads(row["loop_decision_history"]) if row["loop_decision_history"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            parent_checkpoint_id=row.get("parent_checkpoint_id"),
            tags=json.loads(row["tags"]) if row["tags"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


# --- Resume Manager ---

class ResumeManager:
    """Handles task resumption from checkpoints."""

    def __init__(self):
        self._resume_hooks: list[callable] = []

    def add_resume_hook(self, hook: callable) -> None:
        """Add a hook to run on resume."""
        self._resume_hooks.append(hook)

    async def resume(
        self,
        task_id: str,
        checkpoint_id: str | None = None,
    ) -> tuple[TaskCheckpoint, dict[str, Any]]:
        """
        Resume task from checkpoint.

        Returns: (checkpoint, restored_context)
        """
        # Get checkpoint
        if checkpoint_id:
            checkpoint = await CheckpointStore.get_by_id(checkpoint_id)
        else:
            checkpoint = await CheckpointStore.get_latest(task_id)

        if not checkpoint:
            raise ValueError(f"No checkpoint found for task {task_id}")

        logger.info(
            "task_resuming",
            task_id=task_id,
            checkpoint_id=checkpoint.checkpoint_id,
            progress=checkpoint.progress_ratio,
        )

        # Log resume event
        await TaskLedger.record(
            task_id=task_id,
            event_type=TaskEventType.TASK_RESUMED,
            payload={
                "checkpoint_id": checkpoint.checkpoint_id,
                "progress_ratio": checkpoint.progress_ratio,
                "loop_iteration": checkpoint.loop_iteration,
            },
        )

        # Run resume hooks
        for hook in self._resume_hooks:
            try:
                await hook(checkpoint)
            except Exception as e:
                logger.warning("resume_hook_failed", error=str(e))

        # Return checkpoint and restored context
        restored_context = checkpoint.context.copy()
        restored_context["_resumed_from"] = checkpoint.checkpoint_id
        restored_context["_resume_progress"] = checkpoint.progress_ratio

        return checkpoint, restored_context

    async def can_resume(self, task_id: str) -> bool:
        """Check if task can be resumed."""
        checkpoint = await CheckpointStore.get_latest(task_id)
        return checkpoint is not None

    async def list_resumable_tasks(self) -> list[dict[str, Any]]:
        """List all tasks with valid checkpoints."""
        # This would need a query across all tasks
        # For now, return empty - would need task listing
        return []


# --- Operation Records (replay safety) ---

@dataclass
class OperationRecord:
    """A record of a completed primitive operation, enabling idempotent replay.

    On resume, the runtime consults these records to skip operations that have
    already completed — proving replay safety (no double-execution of effects).
    """

    task_id: str
    op_id: str
    op_type: str = "step"               # step | tool_call | model_call | side_effect
    status: str = "completed"           # completed | failed | skipped
    checkpoint_id: str | None = None
    result_ref: str | None = None       # where the operation result lives
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "op_id": self.op_id,
            "op_type": self.op_type,
            "status": self.status,
            "checkpoint_id": self.checkpoint_id,
            "result_ref": self.result_ref,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OperationRecord:
        rec = cls(
            task_id=d["task_id"],
            op_id=d["op_id"],
            op_type=d.get("op_type", "step"),
            status=d.get("status", "completed"),
            checkpoint_id=d.get("checkpoint_id"),
            result_ref=d.get("result_ref"),
            metadata=d.get("metadata", {}),
        )
        if "created_at" in d:
            rec.created_at = datetime.fromisoformat(d["created_at"])
        return rec


class OperationRecordStore:
    """Persists operation records so replays skip already-completed work."""

    TABLE_NAME = "operation_records"

    @classmethod
    async def ensure_table(cls) -> None:
        await db.initialize()

    @classmethod
    async def record(cls, rec: OperationRecord) -> None:
        await cls.ensure_table()
        await db.execute(
            f"""
            INSERT OR REPLACE INTO {cls.TABLE_NAME}
            (task_id, op_id, op_type, status, checkpoint_id, result_ref, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rec.task_id, rec.op_id, rec.op_type, rec.status,
                rec.checkpoint_id, rec.result_ref, rec.created_at.isoformat(),
                json.dumps(rec.metadata),
            ),
        )

    @classmethod
    async def is_completed(cls, task_id: str, op_id: str) -> bool:
        await cls.ensure_table()
        row = await db.fetchone(
            f"SELECT status FROM {cls.TABLE_NAME} WHERE task_id = ? AND op_id = ?",
            (task_id, op_id),
        )
        return bool(row) and row["status"] == "completed"

    @classmethod
    async def get_completed_op_ids(cls, task_id: str) -> set[str]:
        await cls.ensure_table()
        rows = await db.fetchall(
            f"SELECT op_id FROM {cls.TABLE_NAME} WHERE task_id = ? AND status = 'completed'",
            (task_id,),
        )
        return {r["op_id"] for r in rows}

    @classmethod
    async def get_all(cls, task_id: str) -> list[OperationRecord]:
        await cls.ensure_table()
        rows = await db.fetchall(
            f"SELECT * FROM {cls.TABLE_NAME} WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        )
        return [OperationRecord.from_dict(dict(r)) for r in rows]


# --- Checkpoint Manager ---

class CheckpointManager:
    """High-level checkpoint management for autonomous tasks."""

    def __init__(self):
        self._checkpoint_interval = 5  # checkpoint every N iterations
        self._auto_checkpoint = True

    def set_checkpoint_interval(self, interval: int) -> None:
        """Set checkpoint interval (iterations)."""
        self._checkpoint_interval = interval

    def enable_auto_checkpoint(self, enabled: bool = True) -> None:
        """Enable/disable automatic checkpointing."""
        self._auto_checkpoint = enabled

    async def maybe_checkpoint(
        self,
        task_id: str,
        task_status: str,
        current_step: int,
        total_steps: int,
        progress_ratio: float,
        context: dict[str, Any],
        autonomy_usage: AutonomyUsage | dict[str, Any],
        autonomy_profile: str,
        detectors_state: dict[str, Any],
        loop_state: dict[str, Any],
    ) -> TaskCheckpoint | None:
        """
        Create checkpoint if interval reached.

        Returns checkpoint if created, None otherwise.
        """
        if not self._auto_checkpoint:
            return None

        # Check interval
        if current_step % self._checkpoint_interval != 0 and current_step > 0:
            return None

        # Get previous checkpoint for parent link
        prev = await CheckpointStore.get_latest(task_id)
        parent_id = prev.checkpoint_id if prev else None

        # Create checkpoint
        checkpoint = TaskCheckpoint(
            task_id=task_id,
            task_status=task_status,
            current_step=current_step,
            total_steps=total_steps,
            progress_ratio=progress_ratio,
            context=context,
            autonomy_usage=autonomy_usage.to_dict() if isinstance(autonomy_usage, AutonomyUsage) else autonomy_usage,
            autonomy_profile=autonomy_profile,
            progress_history=detectors_state.get("progress_history", []),
            repetition_state=detectors_state.get("repetition_state", {}),
            stall_state=detectors_state.get("stall_state", {}),
            loop_iteration=loop_state.get("iteration", 0),
            loop_decision_history=loop_state.get("decision_history", []),
            parent_checkpoint_id=parent_id,
        )

        await CheckpointStore.save(checkpoint)
        return checkpoint

    async def force_checkpoint(
        self,
        task_id: str,
        **kwargs,
    ) -> TaskCheckpoint:
        """Force create a checkpoint (e.g., on pause, error, user request)."""
        # Same as maybe_checkpoint but always creates
        prev = await CheckpointStore.get_latest(task_id)
        parent_id = prev.checkpoint_id if prev else None

        # Convert AutonomyUsage to dict if needed
        if "autonomy_usage" in kwargs:
            au = kwargs["autonomy_usage"]
            if hasattr(au, "to_dict"):
                kwargs["autonomy_usage"] = au.to_dict()

        checkpoint = TaskCheckpoint(
            task_id=task_id,
            parent_checkpoint_id=parent_id,
            **kwargs,
        )

        await CheckpointStore.save(checkpoint)
        return checkpoint

    async def record_operation(
        self,
        task_id: str,
        op_id: str,
        op_type: str = "step",
        status: str = "completed",
        checkpoint_id: str | None = None,
        result_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OperationRecord:
        """Persist a completed primitive operation (idempotent replay record)."""
        rec = OperationRecord(
            task_id=task_id,
            op_id=op_id,
            op_type=op_type,
            status=status,
            checkpoint_id=checkpoint_id,
            result_ref=result_ref,
            metadata=metadata or {},
        )
        await OperationRecordStore.record(rec)
        return rec

    async def is_operation_completed(self, task_id: str, op_id: str) -> bool:
        """True if the operation already completed — safe to skip on replay."""
        return await OperationRecordStore.is_completed(task_id, op_id)


# --- Integration with Task Manager ---

async def checkpoint_task(
    task_id: str,
    task_manager,
    autonomy_controller,
    progress_detector,
    repetition_detector,
    stall_detector,
    loop_controller,
) -> TaskCheckpoint:
    """Create a full checkpoint from all components."""

    task = await task_manager.get(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    checkpoint_mgr = CheckpointManager()
    return await checkpoint_mgr.force_checkpoint(
        task_id=task_id,
        task_status=task.status.value if hasattr(task.status, 'value') else str(task.status),
        current_step=loop_controller._iteration,
        total_steps=autonomy_controller.budget.max_iterations,
        progress_ratio=autonomy_controller.usage.last_progress_ratio,
        context=loop_controller.autonomy.usage.to_dict() if hasattr(autonomy_controller.usage, 'to_dict') else {},
        autonomy_usage=autonomy_controller.usage,
        autonomy_profile=autonomy_controller.profile.value,
        detectors_state={
            "progress_history": progress_detector._progress_history if progress_detector else [],
            "repetition_state": repetition_detector.get_stats() if repetition_detector else {},
            "stall_state": stall_detector.get_health() if stall_detector else {},
        },
        loop_state={
            "iteration": loop_controller._iteration,
            "decision_history": autonomy_controller._decision_history,
        },
    )
