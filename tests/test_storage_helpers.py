"""
Phase 6+ Storage Helpers Tests

Tests for the new storage helper methods: get_all, get_one, get_or_create, bulk_insert, upsert
"""

from __future__ import annotations

import pytest

from paw.core.storage import db


@pytest.fixture
async def temp_db(reset_db, session_db):
    """Shared session DB (Cấp 2, see tests/conftest.py)."""
    yield session_db


class TestStorageGetAll:
    """Tests for get_all helper."""

    @pytest.mark.asyncio
    async def test_get_all_empty_table(self, temp_db):
        """Get all from empty table returns empty list."""
        rows = await db.get_all("sessions")
        assert rows == []

    @pytest.mark.asyncio
    async def test_get_all_with_data(self, temp_db):
        """Get all returns all rows."""
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-1", "proj-1", "2024-01-01T00:00:00", "2024-01-01T00:00:00")
        )
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-2", "proj-1", "2024-01-02T00:00:00", "2024-01-02T00:00:00")
        )
        
        rows = await db.get_all("sessions")
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_get_all_with_where(self, temp_db):
        """Get all with WHERE clause."""
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-1", "proj-1", "2024-01-01T00:00:00", "2024-01-01T00:00:00")
        )
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-2", "proj-2", "2024-01-02T00:00:00", "2024-01-02T00:00:00")
        )
        
        rows = await db.get_all("sessions", where="project_id = ?", params=("proj-1",))
        assert len(rows) == 1
        assert rows[0]["id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_get_all_with_order_by(self, temp_db):
        """Get all with ORDER BY."""
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-1", "proj-1", "2024-01-02T00:00:00", "2024-01-02T00:00:00")
        )
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-2", "proj-1", "2024-01-01T00:00:00", "2024-01-01T00:00:00")
        )
        
        rows = await db.get_all("sessions", where="project_id = ?", params=("proj-1",), order_by="created_at ASC")
        assert rows[0]["id"] == "sess-2"  # older first
        assert rows[1]["id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_get_all_with_limit(self, temp_db):
        """Get all with LIMIT."""
        for i in range(5):
            await db.execute(
                "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (f"sess-{i}", "proj-1", f"2024-01-{i+1:02d}T00:00:00", f"2024-01-{i+1:02d}T00:00:00")
            )
        
        rows = await db.get_all("sessions", limit=3)
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_get_all_with_columns(self, temp_db):
        """Get all with specific columns."""
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-1", "proj-1", "2024-01-01T00:00:00", "2024-01-01T00:00:00")
        )
        
        rows = await db.get_all("sessions", columns="id, project_id")
        assert "id" in rows[0]
        assert "project_id" in rows[0]
        assert "created_at" not in rows[0]


class TestStorageGetOne:
    """Tests for get_one helper."""

    @pytest.mark.asyncio
    async def test_get_one_existing(self, temp_db):
        """Get one existing row."""
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-1", "proj-1", "2024-01-01T00:00:00", "2024-01-01T00:00:00")
        )
        
        row = await db.get_one("sessions", where="id = ?", params=("sess-1",))
        assert row is not None
        assert row["id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_get_one_not_found(self, temp_db):
        """Get one non-existent returns None."""
        row = await db.get_one("sessions", where="id = ?", params=("nonexistent",))
        assert row is None


class TestStorageGetOrCreate:
    """Tests for get_or_create helper."""

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, temp_db):
        """Get or create returns existing row."""
        await db.execute(
            "INSERT INTO sessions (id, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("sess-1", "proj-1", "2024-01-01T00:00:00", "2024-01-01T00:00:00")
        )
        
        row, created = await db.get_or_create(
            "sessions",
            where="id = ?",
            params=("sess-1",),
            defaults={"id": "sess-1", "project_id": "proj-2", "created_at": "2024-01-02T00:00:00", "updated_at": "2024-01-02T00:00:00"}
        )
        
        assert created is False
        assert row["id"] == "sess-1"
        assert row["project_id"] == "proj-1"  # original value preserved

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, temp_db):
        """Get or create inserts new row."""
        row, created = await db.get_or_create(
            "sessions",
            where="id = ?",
            params=("new-sess",),
            defaults={"id": "new-sess", "project_id": "proj-1", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"}
        )
        
        assert created is True
        assert row["id"] == "new-sess"
        assert row["project_id"] == "proj-1"


class TestStorageBulkInsert:
    """Tests for bulk_insert helper."""

    @pytest.mark.asyncio
    async def test_bulk_insert_empty(self, temp_db):
        """Bulk insert empty list returns 0."""
        count = await db.bulk_insert("sessions", [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_bulk_insert_multiple(self, temp_db):
        """Bulk insert multiple rows."""
        rows = [
            {"id": "sess-1", "project_id": "proj-1", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"},
            {"id": "sess-2", "project_id": "proj-1", "created_at": "2024-01-02T00:00:00", "updated_at": "2024-01-02T00:00:00"},
            {"id": "sess-3", "project_id": "proj-2", "created_at": "2024-01-03T00:00:00", "updated_at": "2024-01-03T00:00:00"},
        ]
        
        count = await db.bulk_insert("sessions", rows)
        assert count == 3
        
        # Verify
        all_rows = await db.get_all("sessions")
        assert len(all_rows) == 3

    @pytest.mark.asyncio
    async def test_bulk_insert_with_columns(self, temp_db):
        """Bulk insert with explicit columns."""
        rows = [
            {"id": "sess-1", "project_id": "proj-1", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"},
            {"id": "sess-2", "project_id": "proj-2", "created_at": "2024-01-02T00:00:00", "updated_at": "2024-01-02T00:00:00"},
        ]
        
        count = await db.bulk_insert("sessions", rows, columns=["id", "project_id", "created_at", "updated_at"])
        assert count == 2
        
        all_rows = await db.get_all("sessions", columns="id, project_id")
        assert len(all_rows) == 2


class TestStorageUpsert:
    """Tests for upsert helper."""

    @pytest.mark.asyncio
    async def test_upsert_insert(self, temp_db):
        """Upsert inserts new row."""
        row = await db.upsert(
            "sessions",
            {"id": "sess-1", "project_id": "proj-1", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"},
            conflict_columns=["id"]
        )
        
        assert row["id"] == "sess-1"
        assert row["project_id"] == "proj-1"

    @pytest.mark.asyncio
    async def test_upsert_update(self, temp_db):
        """Upsert updates existing row."""
        # Insert initial
        await db.upsert(
            "sessions",
            {"id": "sess-1", "project_id": "proj-1", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"},
            conflict_columns=["id"]
        )
        
        # Upsert with update
        row = await db.upsert(
            "sessions",
            {"id": "sess-1", "project_id": "proj-2", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-02T00:00:00"},
            conflict_columns=["id"],
            update_columns=["project_id", "updated_at"]
        )
        
        assert row["id"] == "sess-1"
        assert row["project_id"] == "proj-2"  # updated


class TestStorageHelpersIntegration:
    """Integration tests for storage helpers."""

    @pytest.mark.asyncio
    async def test_task_lifecycle_with_helpers(self, temp_db):
        """Test complete task lifecycle using helpers."""
        # Create task
        task_data = {
            "id": "task-1",
            "session_id": "sess-1",
            "project_id": "proj-1",
            "goal": "Test task",
            "status": "pending",
            "requested_capabilities": "[]",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        
        # Get or create task
        row, created = await db.get_or_create(
            "tasks",
            where="id = ?",
            params=("task-1",),
            defaults=task_data
        )
        assert created is True
        
        # Add event
        await db.bulk_insert("task_events", [
            {"id": "evt-1", "task_id": "task-1", "event_type": "task_created", "payload": "{}", "created_at": "2024-01-01T00:00:00"},
            {"id": "evt-2", "task_id": "task-1", "event_type": "plan_created", "payload": "{}", "created_at": "2024-01-01T00:00:01"},
        ])
        
        # Get all events for task
        events = await db.get_all("task_events", where="task_id = ?", params=("task-1",))
        assert len(events) == 2
        
        # Get task with updated status
        task = await db.get_one("tasks", where="id = ?", params=("task-1",))
        assert task["status"] == "pending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])