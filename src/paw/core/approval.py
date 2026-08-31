"""Durable, exact-operation approval records for policy ASK decisions."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .ledger import TaskEventType, TaskLedger
from .models import ApprovalStatus, ProposedAction
from .storage import db


def _now() -> datetime:
    return datetime.now(UTC)


def action_fingerprint(action: ProposedAction) -> str:
    """Return a stable digest for the full proposed operation."""
    payload = json.dumps(
        action.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ApprovalRequest(BaseModel):
    """A human decision over one immutable proposed operation."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:24])
    task_id: str
    operation_id: str
    action: ProposedAction
    action_fingerprint: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=_now)
    decided_at: datetime | None = None
    consumed_at: datetime | None = None
    decided_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ApprovalRequest:
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            operation_id=row["operation_id"],
            action=ProposedAction.model_validate(json.loads(row["action"])),
            action_fingerprint=row["action_fingerprint"],
            status=ApprovalStatus(row["status"]),
            requested_at=datetime.fromisoformat(row["requested_at"]),
            decided_at=(
                datetime.fromisoformat(row["decided_at"])
                if row.get("decided_at")
                else None
            ),
            consumed_at=(
                datetime.fromisoformat(row["consumed_at"])
                if row.get("consumed_at")
                else None
            ),
            decided_by=row.get("decided_by"),
            metadata=json.loads(row.get("metadata") or "{}"),
        )


class ApprovalStore:
    """Persistence and transition rules for approval requests."""

    @staticmethod
    async def request(
        task_id: str,
        action: ProposedAction,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        await db.initialize()
        fingerprint = action_fingerprint(action)
        existing = await ApprovalStore.get_for_operation(task_id, action.operation_id)
        if existing and existing.action_fingerprint == fingerprint:
            return existing

        now = _now()
        if existing:
            # Reusing an operation id for a changed proposal invalidates any
            # previous decision and creates a fresh pending boundary.
            async with db.transaction() as conn:
                await conn.execute(
                    """UPDATE approval_requests
                    SET action = ?, action_fingerprint = ?, status = ?,
                        requested_at = ?, decided_at = NULL, consumed_at = NULL,
                        decided_by = NULL, metadata = ?
                    WHERE id = ?""",
                    (
                        json.dumps(action.to_dict(), ensure_ascii=False),
                        fingerprint,
                        ApprovalStatus.PENDING.value,
                        now.isoformat(),
                        json.dumps(metadata or {}, ensure_ascii=False),
                        existing.id,
                    ),
                )
            request = await ApprovalStore.get(existing.id)
            if request is None:  # pragma: no cover - storage invariant
                raise RuntimeError("approval update was not durably persisted")
        else:
            request = ApprovalRequest(
                task_id=task_id,
                operation_id=action.operation_id,
                action=action,
                action_fingerprint=fingerprint,
                metadata=metadata or {},
            )
            async with db.transaction() as conn:
                await conn.execute(
                    """INSERT INTO approval_requests (
                        id, task_id, operation_id, action, action_fingerprint,
                        status, requested_at, decided_at, consumed_at,
                        decided_by, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        request.id,
                        request.task_id,
                        request.operation_id,
                        json.dumps(request.action.to_dict(), ensure_ascii=False),
                        request.action_fingerprint,
                        request.status.value,
                        request.requested_at.isoformat(),
                        None,
                        None,
                        None,
                        json.dumps(request.metadata, ensure_ascii=False),
                    ),
                )

        await TaskLedger.record(
            task_id,
            TaskEventType.APPROVAL_REQUESTED,
            {
                "approval_id": request.id,
                "operation_id": request.operation_id,
                "fingerprint": request.action_fingerprint,
                "capabilities": [cap.value for cap in action.capabilities],
            },
        )
        return request

    @staticmethod
    async def get(request_id: str) -> ApprovalRequest | None:
        await db.initialize()
        row = await db.fetch_one(
            "SELECT * FROM approval_requests WHERE id = ?",
            (request_id,),
        )
        return ApprovalRequest.from_row(row) if row else None

    @staticmethod
    async def get_for_operation(task_id: str, operation_id: str) -> ApprovalRequest | None:
        await db.initialize()
        row = await db.fetch_one(
            """SELECT * FROM approval_requests
            WHERE task_id = ? AND operation_id = ?""",
            (task_id, operation_id),
        )
        return ApprovalRequest.from_row(row) if row else None

    @staticmethod
    async def latest_pending(task_id: str | None = None) -> ApprovalRequest | None:
        await db.initialize()
        if task_id:
            row = await db.fetch_one(
                """SELECT * FROM approval_requests
                WHERE task_id = ? AND status = ?
                ORDER BY requested_at DESC LIMIT 1""",
                (task_id, ApprovalStatus.PENDING.value),
            )
        else:
            row = await db.fetch_one(
                """SELECT * FROM approval_requests WHERE status = ?
                ORDER BY requested_at DESC LIMIT 1""",
                (ApprovalStatus.PENDING.value,),
            )
        return ApprovalRequest.from_row(row) if row else None

    @staticmethod
    async def is_approved(task_id: str, action: ProposedAction) -> bool:
        request = await ApprovalStore.get_for_operation(task_id, action.operation_id)
        return bool(
            request
            and request.status == ApprovalStatus.APPROVED
            and request.action_fingerprint == action_fingerprint(action)
        )

    @staticmethod
    async def approve(request_id: str, decided_by: str = "user") -> ApprovalRequest | None:
        return await ApprovalStore._decide(
            request_id,
            ApprovalStatus.APPROVED,
            decided_by,
        )

    @staticmethod
    async def deny(request_id: str, decided_by: str = "user") -> ApprovalRequest | None:
        return await ApprovalStore._decide(
            request_id,
            ApprovalStatus.DENIED,
            decided_by,
        )

    @staticmethod
    async def cancel(request_id: str, decided_by: str = "user") -> ApprovalRequest | None:
        return await ApprovalStore._decide(
            request_id,
            ApprovalStatus.CANCELLED,
            decided_by,
        )

    @staticmethod
    async def _decide(
        request_id: str,
        status: ApprovalStatus,
        decided_by: str,
    ) -> ApprovalRequest | None:
        await db.initialize()
        existing = await ApprovalStore.get(request_id)
        if existing is None:
            return None
        if existing.status != ApprovalStatus.PENDING:
            return existing
        decided_at = _now()
        async with db.transaction() as conn:
            await conn.execute(
                """UPDATE approval_requests
                SET status = ?, decided_at = ?, decided_by = ?
                WHERE id = ? AND status = ?""",
                (
                    status.value,
                    decided_at.isoformat(),
                    decided_by,
                    request_id,
                    ApprovalStatus.PENDING.value,
                ),
            )
        updated = await ApprovalStore.get(request_id)
        if updated:
            await TaskLedger.record(
                updated.task_id,
                TaskEventType.APPROVAL_DECIDED,
                {
                    "approval_id": updated.id,
                    "operation_id": updated.operation_id,
                    "status": updated.status.value,
                    "decided_by": decided_by,
                },
            )
        return updated

    @staticmethod
    async def consume(task_id: str, action: ProposedAction) -> ApprovalRequest | None:
        request = await ApprovalStore.get_for_operation(task_id, action.operation_id)
        if (
            request is None
            or request.status != ApprovalStatus.APPROVED
            or request.action_fingerprint != action_fingerprint(action)
        ):
            return request
        consumed_at = _now()
        async with db.transaction() as conn:
            await conn.execute(
                """UPDATE approval_requests
                SET status = ?, consumed_at = ?
                WHERE id = ? AND status = ?""",
                (
                    ApprovalStatus.CONSUMED.value,
                    consumed_at.isoformat(),
                    request.id,
                    ApprovalStatus.APPROVED.value,
                ),
            )
        updated = await ApprovalStore.get(request.id)
        if updated:
            await TaskLedger.record(
                task_id,
                TaskEventType.APPROVAL_CONSUMED,
                {
                    "approval_id": updated.id,
                    "operation_id": updated.operation_id,
                },
            )
        return updated


__all__ = [
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalStore",
    "action_fingerprint",
]
