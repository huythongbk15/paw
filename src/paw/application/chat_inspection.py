"""Bounded durable inspection projections for the chat CLI."""

from __future__ import annotations

from typing import Any

from paw.core.approval import ApprovalStore
from paw.core.checkpoint import CheckpointStore
from paw.core.ledger import TaskLedger
from paw.core.models import TaskEventType
from paw.core.task import TaskManager


def plan_projection(task_id: str | None, action: Any) -> dict[str, Any] | None:
    if not isinstance(action, dict):
        return None
    metadata = action.get("metadata") or {}
    return {
        "task_id": task_id,
        "operation_id": action.get("operation_id"),
        "goal": action.get("goal"),
        "capabilities": action.get("capabilities") or [],
        "filesystem": metadata.get("filesystem"),
        "change_preview": metadata.get("change_preview"),
    }


async def ledger_projection(task_id: str | None, limit: int = 100) -> list[dict[str, Any]]:
    if task_id is None:
        return []
    return [event.to_dict() for event in await TaskLedger.get_events(task_id, limit)]


async def checkpoint_projection(task_id: str | None) -> dict[str, Any] | None:
    if task_id is None:
        return None
    checkpoint = await CheckpointStore.get_latest(task_id)
    if checkpoint is None:
        return None
    return {
        "task_id": checkpoint.task_id,
        "checkpoint_id": checkpoint.checkpoint_id,
        "task_status": checkpoint.task_status,
        "current_step": checkpoint.current_step,
        "total_steps": checkpoint.total_steps,
        "progress_ratio": checkpoint.progress_ratio,
        "tags": checkpoint.tags,
        "created_at": checkpoint.created_at.isoformat(),
    }


async def policy_projection(
    task_id: str | None,
    pending_approval_id: str | None,
) -> dict[str, Any]:
    events = (
        await TaskLedger.get_events_by_type(
            task_id, TaskEventType.POLICY_GATE_EVALUATED, limit=20
        )
        if task_id
        else []
    )
    request = await ApprovalStore.get(pending_approval_id) if pending_approval_id else None
    approval = (
        {
            "id": request.id,
            "operation_id": request.operation_id,
            "status": request.status.value,
        }
        if request
        else None
    )
    return {
        "task_id": task_id,
        "latest_verdict": events[-1].payload if events else None,
        "approval": approval,
    }


async def skills_projection(task_id: str | None) -> dict[str, Any]:
    events = await ledger_projection(task_id)
    selected = [
        event["payload"]
        for event in events
        if event["event_type"] == TaskEventType.SKILL_SELECTED.value
    ]
    context = [
        event["payload"]
        for event in events
        if event["event_type"] == TaskEventType.CONTEXT_COMPILED.value
    ]
    return {"selected": selected, "context_compilations": context}


async def artifacts_projection(task_id: str | None) -> list[dict[str, Any]]:
    task = await TaskManager.get(task_id) if task_id else None
    if task is None or not isinstance(task.result, dict):
        return []
    artifacts = task.result.get("artifacts") or []
    return [dict(artifact) for artifact in artifacts if isinstance(artifact, dict)]


async def explain_projection(task_id: str | None, action: Any) -> dict[str, Any]:
    task = await TaskManager.get(task_id) if task_id else None
    events = await ledger_projection(task_id)
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["event_type"] in {
            TaskEventType.POLICY_GATE_EVALUATED.value,
            TaskEventType.AUTONOMY_GATE_EVALUATED.value,
            TaskEventType.MODEL_SELECTED.value,
            TaskEventType.EXECUTOR_SELECTED.value,
        }:
            latest[event["event_type"]] = event["payload"]
    return {
        "task_id": task_id,
        "task_status": task.status.value if task else None,
        "plan": plan_projection(task_id, action),
        "policy": latest.get(TaskEventType.POLICY_GATE_EVALUATED.value),
        "autonomy": latest.get(TaskEventType.AUTONOMY_GATE_EVALUATED.value),
        "model": latest.get(TaskEventType.MODEL_SELECTED.value),
        "executor": latest.get(TaskEventType.EXECUTOR_SELECTED.value),
        "checkpoint": await checkpoint_projection(task_id),
        "artifacts": await artifacts_projection(task_id),
    }


__all__ = [
    "artifacts_projection",
    "checkpoint_projection",
    "explain_projection",
    "ledger_projection",
    "plan_projection",
    "policy_projection",
    "skills_projection",
]
