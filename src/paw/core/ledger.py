"""
PAW Core — Task Ledger

Structured event log for every task. Immutable, append-only.
Used for debugging, audit, and evaluation (Phase 13+).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import ID, TaskEventType
from .storage import db


@dataclass
class TaskEvent:
    """A single event in the task ledger."""
    id: int = 0  # Auto-increment from DB
    task_id: ID = ""
    event_type: TaskEventType = TaskEventType.TASK_CREATED
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> TaskEvent:
        payload = {}
        if row.get("payload"):
            payload = json.loads(row["payload"])
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            event_type=TaskEventType(row["event_type"]),
            payload=payload,
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class TaskLedger:
    """Append-only structured event log for tasks."""

    @staticmethod
    async def record(
        task_id: ID,
        event_type: TaskEventType,
        payload: dict[str, Any] | None = None,
    ) -> TaskEvent:
        event = TaskEvent(
            task_id=task_id,
            event_type=event_type,
            payload=payload or {},
        )
        async with db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO task_events (task_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event.task_id,
                    event.event_type.value,
                    json.dumps(event.payload),
                    event.created_at.isoformat(),
                ),
            )
            event.id = cursor.lastrowid
        return event

    @staticmethod
    async def get_events(task_id: ID, limit: int = 1000) -> list[TaskEvent]:
        rows = await db.fetchall(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at LIMIT ?",
            (task_id, limit),
        )
        return [TaskEvent.from_row(dict(r)) for r in rows]

    @staticmethod
    async def get_events_by_type(
        task_id: ID,
        event_type: TaskEventType,
        limit: int = 100,
    ) -> list[TaskEvent]:
        rows = await db.fetchall(
            "SELECT * FROM task_events WHERE task_id = ? AND event_type = ? ORDER BY created_at LIMIT ?",
            (task_id, event_type.value, limit),
        )
        return [TaskEvent.from_row(dict(r)) for r in rows]

    @staticmethod
    async def get_latest_event(task_id: ID, event_type: TaskEventType) -> TaskEvent | None:
        row = await db.fetchone(
            """
            SELECT * FROM task_events
            WHERE task_id = ? AND event_type = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (task_id, event_type.value),
        )
        if row:
            return TaskEvent.from_row(dict(row))
        return None


# Convenience functions for common events
async def log_task_created(task_id: ID, goal: str, session_id: ID) -> None:
    await TaskLedger.record(task_id, TaskEventType.TASK_CREATED, {"goal": goal, "session_id": session_id})


async def log_plan_created(task_id: ID, plan: dict) -> None:
    await TaskLedger.record(task_id, TaskEventType.PLAN_CREATED, {"plan": plan})


async def log_skill_candidates_found(task_id: ID, candidates: list[dict]) -> None:
    await TaskLedger.record(task_id, TaskEventType.SKILL_CANDIDATES_FOUND, {"count": len(candidates), "skills": candidates})


async def log_skill_selected(task_id: ID, skill_name: str, reason: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.SKILL_SELECTED, {"skill": skill_name, "reason": reason})


async def log_context_built(task_id: ID, context_summary: dict) -> None:
    await TaskLedger.record(task_id, TaskEventType.CONTEXT_BUILT, context_summary)


async def log_executor_selected(task_id: ID, executor: str, model: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.EXECUTOR_SELECTED, {"executor": executor, "model": model})


async def log_model_selected(task_id: ID, model: str, role: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.MODEL_SELECTED, {"model": model, "role": role})


async def log_policy_checked(task_id: ID, capability: str, decision: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.POLICY_CHECKED, {"capability": capability, "decision": decision})


async def log_execution_started(task_id: ID, executor: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.EXECUTION_STARTED, {"executor": executor})


async def log_tool_called(task_id: ID, tool: str, args: dict, result: Any) -> None:
    await TaskLedger.record(task_id, TaskEventType.TOOL_CALLED, {"tool": tool, "args": args, "result": str(result)[:500]})


async def log_artifact_created(task_id: ID, artifact_type: str, path: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.ARTIFACT_CREATED, {"type": artifact_type, "path": path})


async def log_execution_completed(task_id: ID, success: bool, result: Any = None, error: str | None = None) -> None:
    await TaskLedger.record(task_id, TaskEventType.EXECUTION_COMPLETED, {"success": success, "result": str(result)[:500], "error": error})


async def log_memory_proposed(task_id: ID, memory_type: str, content: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.MEMORY_PROPOSED, {"type": memory_type, "content": content[:200]})


async def log_memory_accepted(task_id: ID, memory_id: ID) -> None:
    await TaskLedger.record(task_id, TaskEventType.MEMORY_ACCEPTED, {"memory_id": memory_id})


async def log_task_completed(task_id: ID, status: str, summary: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.TASK_COMPLETED, {"status": status, "summary": summary})