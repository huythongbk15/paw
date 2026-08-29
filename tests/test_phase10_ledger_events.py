"""
PAW Phase 10 — Extended Ledger Events (L) Integration Tests

Verify:
- Autonomy decision events logged
- Context compiled events logged
- Checkpoint created events logged
- Task resumed / paused / stalled events logged
- Repetition detected events logged
- Progress insufficient events logged
- All events retrievable by type
"""

from __future__ import annotations

import pytest

from paw.core.ledger import TaskLedger, TaskEventType
from paw.core.storage import db, set_db_path


@pytest.mark.asyncio
async def test_ledger_extended_autonomy_event(tmp_path):
    """AUTONOMY_DECISION event should be recorded and retrievable."""
    db_path = tmp_path / ".paw" / "paw.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(db_path)
    await db.initialize()

    # Create a task
    await db.execute(
        "INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("task-l1", "sess-l1", "ledger test", "running", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    from paw.core.ledger import log_autonomy_decision
    await log_autonomy_decision("task-l1", "continue", None, {"decisions": 1})

    events = await TaskLedger.get_events_by_type("task-l1", TaskEventType.AUTONOMY_DECISION)
    assert len(events) == 1
    assert events[0].payload["decision"] == "continue"


@pytest.mark.asyncio
async def test_ledger_extended_context_compiled_event(tmp_path):
    """CONTEXT_COMPILED event should be recorded."""
    db_path = tmp_path / ".paw" / "paw.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(db_path)
    await db.initialize()

    await db.execute(
        "INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("task-l2", "sess-l2", "ctx test", "running", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    from paw.core.ledger import log_context_compiled
    await log_context_compiled("task-l2", "query", 5, 3, 1200, ["memory", "skill"])

    events = await TaskLedger.get_events_by_type("task-l2", TaskEventType.CONTEXT_COMPILED)
    assert len(events) == 1
    assert events[0].payload["selected_count"] == 5
    assert events[0].payload["sources_used"] == ["memory", "skill"]


@pytest.mark.asyncio
async def test_ledger_extended_checkpoint_event(tmp_path):
    """CHECKPOINT_CREATED event should be recorded."""
    db_path = tmp_path / ".paw" / "paw.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(db_path)
    await db.initialize()

    await db.execute(
        "INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("task-l3", "sess-l3", "cp test", "running", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    from paw.core.ledger import log_checkpoint_created
    await log_checkpoint_created("task-l3", "cp-1", 0.5, 3, 10)

    events = await TaskLedger.get_events_by_type("task-l3", TaskEventType.CHECKPOINT_CREATED)
    assert len(events) == 1
    assert events[0].payload["checkpoint_id"] == "cp-1"
    assert events[0].payload["progress_ratio"] == 0.5


@pytest.mark.asyncio
async def test_ledger_extended_resume_pause_stall_events(tmp_path):
    """RESUMED / PAUSED / STALLED events should be recorded."""
    db_path = tmp_path / ".paw" / "paw.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(db_path)
    await db.initialize()

    await db.execute(
        "INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("task-l4", "sess-l4", "state test", "running", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    from paw.core.ledger import log_task_resumed, log_task_paused, log_task_stalled
    await log_task_resumed("task-l4", "cp-1")
    await log_task_paused("task-l4", "waiting approval")
    await log_task_stalled("task-l4", "no_progress", "stalled for 60s")

    resumed = await TaskLedger.get_events_by_type("task-l4", TaskEventType.TASK_RESUMED)
    paused = await TaskLedger.get_events_by_type("task-l4", TaskEventType.TASK_PAUSED)
    stalled = await TaskLedger.get_events_by_type("task-l4", TaskEventType.TASK_STALLED)

    assert len(resumed) == 1
    assert resumed[0].payload["from_checkpoint"] == "cp-1"
    assert len(paused) == 1
    assert paused[0].payload["reason"] == "waiting approval"
    assert len(stalled) == 1
    assert stalled[0].payload["reason"] == "no_progress"


@pytest.mark.asyncio
async def test_ledger_extended_repetition_progress_events(tmp_path):
    """REPETITION_DETECTED / PROGRESS_INSUFFICIENT events should be recorded."""
    db_path = tmp_path / ".paw" / "paw.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(db_path)
    await db.initialize()

    await db.execute(
        "INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("task-l5", "sess-l5", "rep test", "running", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    from paw.core.ledger import log_repetition_detected, log_progress_insufficient
    await log_repetition_detected("task-l5", "search", 5)
    await log_progress_insufficient("task-l5", 0.1, 0.5, 3)

    rep = await TaskLedger.get_events_by_type("task-l5", TaskEventType.REPETITION_DETECTED)
    prog = await TaskLedger.get_events_by_type("task-l5", TaskEventType.PROGRESS_INSUFFICIENT)

    assert len(rep) == 1
    assert rep[0].payload["tool_name"] == "search"
    assert len(prog) == 1
    assert prog[0].payload["current"] == 0.1
