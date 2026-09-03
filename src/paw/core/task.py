"""
PAW Core — Task Management

Task is the primary unit of work. It can be simple (single execution) or complex (task graph).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .models import (
    ID,
    Capability,
    TaskStatus,
    _generate_id,
)
from .storage import db


class Task(BaseModel):
    """A task with goal, status, and execution metadata."""
    id: ID = Field(default_factory=_generate_id)
    parent_id: ID | None = None
    session_id: ID
    project_id: ID | None = None
    goal: str = ""
    status: TaskStatus = TaskStatus.PENDING
    requested_capabilities: list[Capability] = Field(default_factory=list)
    selected_skills: list[str] = Field(default_factory=list)
    selected_executor: str | None = None
    selected_model: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    @classmethod
    def from_row(cls, row: dict) -> Task:
        caps = []
        if row.get("requested_capabilities"):
            caps = [Capability(c) for c in json.loads(row["requested_capabilities"])]
        skills = []
        if row.get("selected_skills"):
            skills = json.loads(row["selected_skills"])
        return cls(
            id=row["id"],
            parent_id=row.get("parent_id"),
            session_id=row["session_id"],
            project_id=row.get("project_id"),
            goal=row["goal"],
            status=TaskStatus(row["status"]),
            requested_capabilities=caps,
            selected_skills=skills,
            selected_executor=row.get("selected_executor"),
            selected_model=row.get("selected_model"),
            result=json.loads(row["result"]) if row.get("result") else None,
            error=row.get("error"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
        )


class TaskManager:
    """Manages task lifecycle."""

    @staticmethod
    async def create(
        session_id: ID,
        goal: str,
        project_id: ID | None = None,
        parent_id: ID | None = None,
        requested_capabilities: list[Capability] | None = None,
    ) -> Task:
        task = Task(
            session_id=session_id,
            project_id=project_id,
            parent_id=parent_id,
            goal=goal,
            requested_capabilities=requested_capabilities or [],
        )
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (
                    id, parent_id, session_id, project_id, goal, status,
                    requested_capabilities, selected_skills, selected_executor,
                    selected_model, result, error, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.parent_id,
                    task.session_id,
                    task.project_id,
                    task.goal,
                    task.status.value,
                    json.dumps([c.value for c in task.requested_capabilities]),
                    json.dumps(task.selected_skills),
                    task.selected_executor,
                    task.selected_model,
                    json.dumps(task.result) if task.result else None,
                    task.error,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                ),
            )
        return task

    @staticmethod
    async def get(task_id: ID) -> Task | None:
        row = await db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if row:
            return Task.from_row(dict(row))
        return None

    @staticmethod
    async def list(
        session_id: ID | None = None,
        project_id: ID | None = None,
        status: TaskStatus | None = None,
        parent_id: ID | None = None,
        limit: int = 100,
    ) -> list[Task]:
        conditions = []
        params: list[Any] = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if parent_id:
            conditions.append("parent_id = ?")
            params.append(parent_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        rows = await db.fetchall(
            f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ?",
            tuple(params),
        )
        return [Task.from_row(dict(r)) for r in rows]

    @staticmethod
    async def get_children(parent_id: ID) -> list[Task]:
        rows = await db.fetchall(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at",
            (parent_id,),
        )
        return [Task.from_row(dict(r)) for r in rows]

    @staticmethod
    async def update(task: Task, *, connection: Any | None = None) -> None:
        task.touch()
        if connection is None:
            async with db.transaction() as conn:
                await TaskManager._update_row(task, conn)
            return
        await TaskManager._update_row(task, connection)

    @staticmethod
    async def _update_row(task: Task, connection: Any) -> None:
        await connection.execute(
            """
            UPDATE tasks SET
                parent_id = ?, session_id = ?, project_id = ?, goal = ?, status = ?,
                requested_capabilities = ?, selected_skills = ?, selected_executor = ?,
                selected_model = ?, result = ?, error = ?, updated_at = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                task.parent_id,
                task.session_id,
                task.project_id,
                task.goal,
                task.status.value,
                json.dumps([c.value for c in task.requested_capabilities]),
                json.dumps(task.selected_skills),
                task.selected_executor,
                task.selected_model,
                json.dumps(task.result) if task.result else None,
                task.error,
                task.updated_at.isoformat(),
                task.completed_at.isoformat() if task.completed_at else None,
                task.id,
            ),
        )

    @staticmethod
    async def update_status(
        task_id: ID,
        status: TaskStatus,
        error: str | None = None,
        *,
        connection: Any | None = None,
    ) -> Task | None:
        if connection is not None:
            now = datetime.now(UTC)
            columns_cursor = await connection.execute("PRAGMA table_info(tasks)")
            columns = {row[1] for row in await columns_cursor.fetchall()}
            assignments = ["status = ?"]
            values: list[Any] = [status.value]
            if "error" in columns:
                assignments.append("error = ?")
                values.append(error)
            if "updated_at" in columns:
                assignments.append("updated_at = ?")
                values.append(now.isoformat())
            if "completed_at" in columns and status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                assignments.append("completed_at = ?")
                values.append(now.isoformat())
            values.append(task_id)
            await connection.execute(
                f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )
            # Transactional runtime callers only require the row mutation. A
            # direct update also preserves compatibility with old/synthetic
            # rows that predate current Pydantic ID validation.
            return None

        task = await TaskManager.get(task_id)
        if not task:
            return None
        task.status = status
        task.error = error
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.now(UTC)
        await TaskManager.update(task, connection=connection)
        return task

    @staticmethod
    async def delete(task_id: ID) -> bool:
        async with db.transaction() as conn:
            cursor = await conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0
