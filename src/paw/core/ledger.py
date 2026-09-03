"""
PAW Core — Task Ledger

Structured event log for every task. Immutable, append-only.
Used for debugging, audit, and evaluation (Phase 13+).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

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
        *,
        connection: Any | None = None,
    ) -> TaskEvent:
        """Append an event, optionally participating in a caller transaction.

        Runtime commit boundaries pass the active SQLite connection so ledger
        rows are committed (or rolled back) with the state they describe.
        The default path retains the standalone append contract for callers
        that do not need a larger atomic unit.
        """
        event = TaskEvent(
            task_id=task_id,
            event_type=event_type,
            payload=payload or {},
        )
        if connection is None:
            async with db.transaction() as conn:
                return await TaskLedger.record(
                    task_id,
                    event_type,
                    payload,
                    connection=conn,
                )

        cursor = await connection.execute(
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
    await TaskLedger.record(
        task_id,
        TaskEventType.SKILL_CANDIDATES_FOUND,
        {"count": len(candidates), "skills": candidates},
    )


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


async def log_policy_decision(
    task_id: ID,
    capability: str,
    decision: str,
    source: str,
    reason: str,
    interactive_resolved: bool,
) -> None:
    """Extended event: durable, explainable record of a policy decision (Phase 14).

    Carries provenance so the runtime is fully observable: which rule (or the
    default fallback) produced the decision, the human-readable reason, and
    whether a non-interactive ASK was resolved to DENY (fail-closed).
    """
    await TaskLedger.record(
        task_id,
        TaskEventType.POLICY_CHECKED,
        {
            "capability": capability,
            "decision": decision,
            "source": source,
            "reason": reason,
            "interactive_resolved": interactive_resolved,
        },
    )


async def log_execution_started(task_id: ID, executor: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.EXECUTION_STARTED, {"executor": executor})


async def log_tool_called(task_id: ID, tool: str, args: dict, result: Any) -> None:
    await TaskLedger.record(
        task_id,
        TaskEventType.TOOL_CALLED,
        {"tool": tool, "args": args, "result": str(result)[:500]},
    )


async def log_artifact_created(task_id: ID, artifact_type: str, path: str) -> None:
    await TaskLedger.record(
        task_id,
        TaskEventType.ARTIFACT_CREATED,
        {"type": artifact_type, "path": path},
    )


async def log_execution_completed(
    task_id: ID,
    success: bool,
    result: Any = None,
    error: str | None = None,
) -> None:
    await TaskLedger.record(
        task_id,
        TaskEventType.EXECUTION_COMPLETED,
        {"success": success, "result": str(result)[:500], "error": error},
    )


async def log_memory_proposed(task_id: ID, memory_type: str, content: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.MEMORY_PROPOSED, {"type": memory_type, "content": content[:200]})


async def log_memory_accepted(task_id: ID, memory_id: ID) -> None:
    await TaskLedger.record(task_id, TaskEventType.MEMORY_ACCEPTED, {"memory_id": memory_id})


async def log_task_completed(task_id: ID, status: str, summary: str) -> None:
    await TaskLedger.record(task_id, TaskEventType.TASK_COMPLETED, {"status": status, "summary": summary})


# ── Phase 10: Autonomy & Context Ledger Events (L) ──
async def log_autonomy_decision(
    task_id: ID,
    decision: str,
    stop_reason: str | None,
    usage: dict[str, Any] | None = None,
) -> None:
    """Record an autonomy controller decision."""
    await TaskLedger.record(
        task_id,
        TaskEventType.AUTONOMY_DECISION,
        {"decision": decision, "stop_reason": stop_reason, "usage": usage or {}},
    )


async def log_context_compiled(
    task_id: ID,
    query: str,
    selected_count: int,
    excluded_count: int,
    total_tokens: int,
    sources_used: list[str] | None = None,
) -> None:
    """Record context compilation result."""
    await TaskLedger.record(
        task_id,
        TaskEventType.CONTEXT_COMPILED,
        {
            "query": query,
            "selected_count": selected_count,
            "excluded_count": excluded_count,
            "total_tokens": total_tokens,
            "sources_used": sources_used or [],
        },
    )


async def log_checkpoint_created(
    task_id: ID,
    checkpoint_id: ID,
    progress_ratio: float,
    step: int,
    total_steps: int,
) -> None:
    """Record checkpoint creation."""
    await TaskLedger.record(
        task_id,
        TaskEventType.CHECKPOINT_CREATED,
        {
            "checkpoint_id": checkpoint_id,
            "progress_ratio": progress_ratio,
            "step": step,
            "total_steps": total_steps,
        },
    )


async def log_task_resumed(task_id: ID, from_checkpoint: ID | None = None) -> None:
    """Record task resume from checkpoint."""
    await TaskLedger.record(
        task_id,
        TaskEventType.TASK_RESUMED,
        {"from_checkpoint": from_checkpoint},
    )


async def log_task_paused(task_id: ID, reason: str | None = None) -> None:
    """Record task paused state."""
    await TaskLedger.record(task_id, TaskEventType.TASK_PAUSED, {"reason": reason})


async def log_task_stalled(task_id: ID, reason: str, detail: str | None = None) -> None:
    """Record task stall detection."""
    await TaskLedger.record(
        task_id, TaskEventType.TASK_STALLED, {"reason": reason, "detail": detail}
    )


async def log_repetition_detected(task_id: ID, tool_name: str, count: int) -> None:
    """Record repetition detection."""
    await TaskLedger.record(
        task_id, TaskEventType.REPETITION_DETECTED, {"tool_name": tool_name, "count": count}
    )


async def log_progress_insufficient(
    task_id: ID, current: float, required: float, stagnation: int
) -> None:
    """Record insufficient progress detection."""
    await TaskLedger.record(
        task_id,
        TaskEventType.PROGRESS_INSUFFICIENT,
        {"current": current, "required": required, "stagnation": stagnation},
    )


# ── Phase 19: Runtime Loop Ledger Events ──
async def log_step_proposed(
    task_id: ID,
    action_id: str,
    goal: str,
    capabilities: list[str],
    estimated_cost: dict[str, Any] | None = None,
) -> None:
    """Record a proposed action before policy/autonomy gate."""
    await TaskLedger.record(
        task_id,
        TaskEventType.STEP_PROPOSED,
        {
            "action_id": action_id,
            "goal": goal,
            "capabilities": capabilities,
            "estimated_cost": estimated_cost or {},
        },
    )


async def log_step_executed(
    task_id: ID,
    action_id: str,
    success: bool,
    resources_used: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Record step execution result."""
    await TaskLedger.record(
        task_id,
        TaskEventType.STEP_EXECUTED,
        {
            "action_id": action_id,
            "success": success,
            "resources_used": resources_used or {},
            "error": error,
        },
    )


async def log_step_completed(
    task_id: ID,
    action_id: str,
    done: bool,
    progress: float,
) -> None:
    """Record step completion with progress."""
    await TaskLedger.record(
        task_id,
        TaskEventType.STEP_COMPLETED,
        {
            "action_id": action_id,
            "done": done,
            "progress": progress,
        },
    )


async def log_operation_recorded(
    task_id: ID,
    op_id: str,
    op_type: str,
    status: str,
    checkpoint_id: str | None = None,
) -> None:
    """Record that an operation was persisted for replay safety."""
    await TaskLedger.record(
        task_id,
        TaskEventType.OPERATION_RECORDED,
        {
            "op_id": op_id,
            "op_type": op_type,
            "status": status,
            "checkpoint_id": checkpoint_id,
        },
    )


async def log_checkpoint_restored(
    task_id: ID,
    checkpoint_id: str,
    progress_ratio: float,
    skipped_ops: int,
) -> None:
    """Record checkpoint restore with replay info."""
    await TaskLedger.record(
        task_id,
        TaskEventType.CHECKPOINT_RESTORED,
        {
            "checkpoint_id": checkpoint_id,
            "progress_ratio": progress_ratio,
            "skipped_operations": skipped_ops,
        },
    )


async def log_policy_gate_evaluated(
    task_id: ID,
    action_id: str,
    verdict: str,
    capabilities: list[str],
) -> None:
    """Record policy gate evaluation result."""
    await TaskLedger.record(
        task_id,
        TaskEventType.POLICY_GATE_EVALUATED,
        {
            "action_id": action_id,
            "verdict": verdict,
            "capabilities": capabilities,
        },
    )


async def log_autonomy_gate_evaluated(
    task_id: ID,
    action_id: str,
    decision: str,
    stop_reason: str | None,
) -> None:
    """Record autonomy gate evaluation result."""
    await TaskLedger.record(
        task_id,
        TaskEventType.AUTONOMY_GATE_EVALUATED,
        {
            "action_id": action_id,
            "decision": decision,
            "stop_reason": stop_reason,
        },
    )
