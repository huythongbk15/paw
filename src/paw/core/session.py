"""
PAW Core — Session Management
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .models import ID, Metadata, _generate_id
from .storage import db


class Session(BaseModel):
    """A conversation session with an optional project context."""
    id: ID = Field(default_factory=_generate_id)
    project_id: ID | None = None
    metadata: Metadata = Field(default_factory=Metadata)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    @classmethod
    def from_row(cls, row: dict) -> Session:
        metadata = Metadata()
        if row.get("metadata"):
            metadata.data = json.loads(row["metadata"])
        return cls(
            id=row["id"],
            project_id=row.get("project_id"),
            metadata=metadata,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class SessionManager:
    """Manages PAW sessions."""

    @staticmethod
    async def create(project_id: ID | None = None, metadata: Metadata | None = None) -> Session:
        session = Session(project_id=project_id, metadata=metadata or Metadata())
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (id, project_id, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.project_id,
                    json.dumps(session.metadata.data),
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
        return session

    @staticmethod
    async def get(session_id: ID) -> Session | None:
        row = await db.fetchone(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        )
        if row:
            return Session.from_row(dict(row))
        return None

    @staticmethod
    async def list(project_id: ID | None = None, limit: int = 50) -> list[Session]:
        if project_id:
            rows = await db.fetchall(
                "SELECT * FROM sessions WHERE project_id = ? ORDER BY updated_at DESC LIMIT ?",
                (project_id, limit),
            )
        else:
            rows = await db.fetchall(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        return [Session.from_row(dict(r)) for r in rows]

    @staticmethod
    async def update(session: Session) -> None:
        session.touch()
        async with db.transaction() as conn:
            await conn.execute(
                """
                UPDATE sessions SET project_id = ?, metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    session.project_id,
                    json.dumps(session.metadata.data),
                    session.updated_at.isoformat(),
                    session.id,
                ),
            )

    @staticmethod
    async def delete(session_id: ID) -> bool:
        async with db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,),
            )
            return cursor.rowcount > 0