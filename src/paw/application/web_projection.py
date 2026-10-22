"""The read-only projections the local web surface exposes.

These are the **substance** of the surface: bounded, redacted views of
state the application already owns. They are transport-agnostic and hold
no HTTP type, so they are provable on their own and the transport stays
a replaceable shell.

What a projection promises:

* **Bounded.** A projection never returns an unbounded list. History,
  events and sessions are limited, and a caller-supplied limit is
  clamped rather than trusted.
* **Redacted.** A projection never returns a credential, a token, a
  secret or an absolute path. What it does return is the state a person
  needs to decide something.
* **Typed and stable.** Every projection has a shape, and an error has
  a stable code. A projection does not raise into the transport.
* **Read-only.** Nothing here mutates. The mutating routes are off
  until the storage concurrency question (F02) is settled.

The owners are the existing ones: sessions and transcripts come from
``ChatStateStore``, tasks from ``TaskManager``, events from
``TaskLedger``, checkpoints from ``CheckpointStore``, and the inspect
views from ``paw.application.chat_inspection``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..core.checkpoint import CheckpointStore
from ..core.ledger import TaskLedger
from ..core.models import TaskEventType
from ..core.storage import db
from ..core.task import TaskManager
from .chat import ChatStateStore

__all__ = [
    "ProjectionError",
    "capabilities_projection",
    "health_projection",
    "inspect_projection",
    "messages_projection",
    "session_projection",
    "sessions_projection",
    "task_projection",
    "tasks_events_projection",
]

# The ceilings. A caller may ask for less; it may never ask for more.
MAX_LIMIT = 200
DEFAULT_LIMIT = 50

# The inspect kinds the surface exposes. A fixed allowlist, not a
# method name the caller supplies.
INSPECT_KINDS = (
    "decision",
    "plan",
    "context",
    "routing",
    "policy",
    "ledger",
    "checkpoint",
    "verification",
    "artifacts",
)

# Anything that looks like a credential is never projected.
_SECRET_KEY = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|pwd|authorization|cookie|"
    r"csrf|credential)",
    re.IGNORECASE,
)
# An absolute path is not a secret, but it is not the user's business
# either - the workspace is already known to them.
_ABSOLUTE_PATH = re.compile(r"(^|[\s\"'=])(/[^\s\"']{2,})")


class ProjectionError(Exception):
    """A projection that cannot be produced.

    The code is stable and safe to show; the message never carries a
    payload, a path or a credential.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class Page:
    """A bounded slice of a longer list."""

    items: list[Any]
    next_cursor: str = ""
    limit: int = DEFAULT_LIMIT

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "next_cursor": self.next_cursor,
            "limit": self.limit,
        }


def _clamp_limit(raw: Any) -> int:
    """Clamp a caller-supplied limit. It is a request, not an instruction."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    if value <= 0:
        return DEFAULT_LIMIT
    return min(value, MAX_LIMIT)


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Remove anything credential-shaped from a projection value.

    Applied to every projection, so a new field cannot leak by being
    added without thinking about it.
    """
    if _depth > 6:
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_KEY.search(str(key)):
                out[str(key)] = "<redacted>"
                continue
            out[str(key)] = redact(item, _depth=_depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(item, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        if _ABSOLUTE_PATH.search(value):
            return _ABSOLUTE_PATH.sub(r"\1<path>", value)
        return value
    return value


# --- capabilities and health ---------------------------------------------


def capabilities_projection() -> dict[str, Any]:
    """What this build supports.

    ``supported`` is what the build can do now, ``experimental`` is what
    exists but is not a qualified answer, and ``unavailable`` is what the
    charter keeps out of scope. The list is static and truthful about
    the *shape* of the product, not about a live provider.
    """
    return {
        "supported": [
            "sessions.read", "messages.read", "tasks.read", "events.read",
            "inspect.read", "capabilities.read", "health.read",
        ],
        "experimental": [
            "skills.read", "memory.read", "knowledge.read",
            "models.read", "benchmarks.read",
        ],
        "unavailable": [
            "web.mutate", "training", "hosted.access", "tenancy",
            "provider.discovery.from.browser", "arbitrary.tool.endpoint",
        ],
        "mutations_enabled": False,
        "mutations_note": (
            "mutating requests are off until the storage concurrency "
            "question is settled"
        ),
    }


async def health_projection(*, revision: str = "", schema_version: int = 0) -> dict[str, Any]:
    """Build revision, schema version and redacted diagnostics.

    Cached and free of hidden I/O: it reads what is already in memory
    and the schema version, and it does not probe a provider.
    """
    return redact({
        "status": "ok",
        "revision": revision,
        "schema_version": schema_version,
        "diagnostics": {},
    })


# --- sessions ------------------------------------------------------------


async def sessions_projection(*, limit: Any = None, cursor: str = "") -> Page:
    """The durable chat sessions, newest first, bounded."""
    await db.initialize()
    bounded = _clamp_limit(limit)
    rows = await db.fetchall(
        "SELECT * FROM chat_sessions ORDER BY updated_at DESC, session_id LIMIT ?",
        (bounded + 1,),
    )
    has_more = len(rows) > bounded
    rows = rows[:bounded]
    items = [redact(_session_dto(dict(row))) for row in rows]
    return Page(
        items=items,
        next_cursor=str(rows[-1]["session_id"]) if (has_more and rows) else "",
        limit=bounded,
    )


def _session_dto(row: dict[str, Any]) -> dict[str, Any]:
    from .chat import ChatSessionRecord

    record = ChatSessionRecord.from_row(row)
    return {
        "session_id": record.session_id,
        "status": record.status.value,
        "current_task_id": record.current_task_id,
        "pending_approval_id": record.pending_approval_id,
        "last_checkpoint_id": record.last_checkpoint_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


async def session_projection(session_id: str) -> dict[str, Any]:
    """One session, or a typed refusal."""
    record = await ChatStateStore.get_session(session_id)
    if record is None:
        raise ProjectionError("web.session_not_found", "no such session")
    return redact({
        "session_id": record.session_id,
        "status": record.status.value,
        "current_task_id": record.current_task_id,
        "pending_approval_id": record.pending_approval_id,
        "last_checkpoint_id": record.last_checkpoint_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    })


async def messages_projection(
    session_id: str, *, limit: Any = None, cursor: str = "",
) -> Page:
    """The bounded transcript of a session."""
    record = await ChatStateStore.get_session(session_id)
    if record is None:
        raise ProjectionError("web.session_not_found", "no such session")
    bounded = _clamp_limit(limit)
    messages = await ChatStateStore.history(session_id, limit=bounded + 1)
    has_more = len(messages) > bounded
    messages = messages[:bounded]
    items = [
        redact({
            "id": message.id,
            "role": message.role.value,
            "content": message.content,
            "task_id": message.task_id,
            "created_at": message.created_at.isoformat(),
        })
        for message in messages
    ]
    return Page(
        items=items,
        next_cursor=str(messages[-1].id) if (has_more and messages) else "",
        limit=bounded,
    )


# --- tasks ---------------------------------------------------------------


async def task_projection(task_id: str) -> dict[str, Any]:
    """The durable state of a task."""
    task = await TaskManager.get(task_id)
    if task is None:
        raise ProjectionError("web.task_not_found", "no such task")
    return redact({
        "task_id": task.id,
        "session_id": task.session_id,
        "goal": task.goal,
        "status": task.status.value,
        "error": task.error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    })


async def tasks_events_projection(
    task_id: str, *, limit: Any = None, cursor: str = "",
) -> Page:
    """The bounded event projection of a task."""
    task = await TaskManager.get(task_id)
    if task is None:
        raise ProjectionError("web.task_not_found", "no such task")
    bounded = _clamp_limit(limit)
    events = await TaskLedger.get_events(task_id, limit=bounded + 1)
    has_more = len(events) > bounded
    events = events[:bounded]
    items = [
        redact({
            "id": event.id,
            "event_type": event.event_type.value,
            "payload": _safe_payload(event.payload),
            "created_at": event.created_at,
        })
        for event in events
    ]
    return Page(
        items=items,
        next_cursor=str(events[-1].id) if (has_more and events) else "",
        limit=bounded,
    )


def _safe_payload(payload: Any) -> Any:
    """A ledger payload as JSON, or a marker when it is not JSON-shaped."""
    if payload is None:
        return {}
    if isinstance(payload, (dict, list)):
        return payload
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return {"summary": str(payload)[:200]}


# --- inspect -------------------------------------------------------------


async def inspect_projection(task_id: str, kind: str) -> dict[str, Any]:
    """One inspect view of a task, from a fixed allowlist.

    The kind is chosen from a closed set. It is never a method name the
    caller supplies, so the surface cannot be used to reach an arbitrary
    function.
    """
    if kind not in INSPECT_KINDS:
        raise ProjectionError(
            "web.inspect_kind_unknown",
            "that inspect kind is not offered",
        )
    from . import chat_inspection

    if kind == "ledger":
        view: Any = await chat_inspection.ledger_projection(task_id)
    elif kind == "checkpoint":
        view = await chat_inspection.checkpoint_projection(task_id)
    elif kind == "policy":
        view = await chat_inspection.policy_projection(task_id)
    elif kind == "skills":
        view = await chat_inspection.skills_projection(task_id)
    elif kind == "artifacts":
        view = await chat_inspection.artifacts_projection(task_id)
    elif kind == "plan":
        view = await chat_inspection.plan_projection(task_id, None)
    elif kind == "decision":
        view = await _decision_view(task_id)
    elif kind == "verification":
        view = await _verification_view(task_id)
    elif kind == "context":
        view = await _context_view(task_id)
    else:  # routing
        view = await _routing_view(task_id)
    return redact({"kind": kind, "task_id": task_id, "view": view})


async def _decision_view(task_id: str) -> Any:
    rows = await db.fetchall(
        "SELECT * FROM decision_records WHERE task_id = ? ORDER BY created_at DESC LIMIT 20",
        (task_id,),
    )
    return [
        {
            "decision_id": row["id"],
            "decision_type": row["decision_type"],
            "decision_value": row["decision_value"],
            "reason": row["reason"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


async def _verification_view(task_id: str) -> Any:
    """The declared verifications recorded for a task."""
    events = await TaskLedger.get_events_by_type(
        task_id, TaskEventType.VERIFICATION_RECORDED,
    )
    return [event.payload for event in events]


async def _context_view(task_id: str) -> Any:
    events = await TaskLedger.get_events_by_type(
        task_id, TaskEventType.CONTEXT_COMPILED,
    )
    return [event.payload for event in events]


async def _routing_view(task_id: str) -> Any:
    events = await TaskLedger.get_events_by_type(
        task_id, TaskEventType.MODEL_SELECTED,
    )
    return [
        {
            "model": (event.payload or {}).get("model"),
            "role": (event.payload or {}).get("role"),
            "reason": (event.payload or {}).get("reason"),
            "created_at": event.created_at,
        }
        for event in events
    ]


async def checkpoint_projection(task_id: str) -> dict[str, Any]:
    """The latest checkpoint of a task."""
    checkpoint = await CheckpointStore.get_latest(task_id)
    if checkpoint is None:
        return {}
    return redact({
        "checkpoint_id": checkpoint.checkpoint_id,
        "task_status": checkpoint.task_status,
        "current_step": checkpoint.current_step,
        "total_steps": checkpoint.total_steps,
        "progress_ratio": checkpoint.progress_ratio,
        "created_at": checkpoint.created_at.isoformat(),
    })


# --- The pending approval ------------------------------------------------


async def pending_approval_projection(session_id: str) -> dict[str, Any]:
    """The effect a human is being asked to approve, in a readable form.

    There are two kinds of approval, and the surface must say which one it
    is showing:

    * an **evidence review** (``decision_review``) accepts the
      implementation-readiness evidence for a decision snapshot. It is not
      execution authority: a separate approval covers the effect.
    * an **effect approval** is the runtime's policy ASK for one exact
      operation.

    Both are shown with what they are: the operation, the capabilities it
    would use, what it would touch, and what the proposed change looks
    like. Nothing credential-shaped is projected, and the content is
    bounded - an approval is a summary, not a file dump.
    """
    from ..core.approval import ApprovalStatus, ApprovalStore

    session = await ChatStateStore.get_session(session_id)
    if session is None:
        raise ProjectionError("web.session_not_found", "no such session")
    if not session.pending_approval_id:
        raise ProjectionError(
            "web.no_pending_approval", "this session is not waiting for an approval",
        )
    approval = await ApprovalStore.get(session.pending_approval_id)
    if approval is None:
        raise ProjectionError(
            "web.no_pending_approval", "this session is not waiting for an approval",
        )
    if approval.status != ApprovalStatus.PENDING:
        raise ProjectionError(
            "web.approval_not_pending", "that approval was already decided",
        )
    action = approval.action
    metadata = action.metadata if isinstance(action.metadata, dict) else {}
    context = action.context if isinstance(action.context, dict) else {}

    if metadata.get("purpose") == "decision_review":
        decision = context.get("decision")
        decision = decision if isinstance(decision, dict) else {}
        payload = decision.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        implementation = payload.get("implementation_action")
        implementation = implementation if isinstance(implementation, dict) else {}
        # The action is serialised whole, so its metadata is nested.
        implementation_metadata = implementation.get("metadata")
        implementation_metadata = (
            implementation_metadata if isinstance(implementation_metadata, dict) else {}
        )
        intent = implementation_metadata.get("filesystem")
        intent = intent if isinstance(intent, dict) else {}
        return redact({
            "kind": "evidence_review",
            "approval_id": approval.id,
            "task_id": approval.task_id,
            "operation_id": approval.operation_id,
            "goal": action.goal,
            "decision_version_id": decision.get("version_id", ""),
            "capabilities": [c.value for c in action.capabilities],
            "selected": payload.get("selected", ""),
            "options": payload.get("options", []),
            "contrary": payload.get("contrary", []),
            "stop_condition": payload.get("stop_condition", ""),
            "acceptance": payload.get("acceptance", []),
            "operation": intent.get("operation", ""),
            "path": intent.get("path", ""),
            "change_preview": (implementation_metadata.get("change_preview") or "")[:4000],
            "requested_at": approval.requested_at.isoformat(),
        })

    filesystem = metadata.get("filesystem")
    filesystem = filesystem if isinstance(filesystem, dict) else {}
    preview = metadata.get("change_preview")
    return redact({
        "kind": "effect_approval",
        "approval_id": approval.id,
        "task_id": approval.task_id,
        "operation_id": approval.operation_id,
        "goal": action.goal,
        "capabilities": [c.value for c in action.capabilities],
        "policy_reason": (approval.metadata or {}).get("policy_reason", ""),
        "operation": filesystem.get("operation", ""),
        "path": filesystem.get("path", ""),
        "change_preview": (preview or "")[:4000],
        "requested_at": approval.requested_at.isoformat(),
    })
