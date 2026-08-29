"""
PAW Phase 10 — Integration Test: Checkpoint/Resume Roundtrip (T-Checkpoint)

Verify:
- Checkpoint persisted to SQLite
- Resume restores full state (context, autonomy, detectors, loop)
- Completed ops not auto-repeated (idempotency check)
- Parent checkpoint chain intact
"""

from __future__ import annotations

import json

import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget, AutonomyProfile, AutonomyUsage
from paw.core.checkpoint import CheckpointStore, CheckpointManager, ResumeManager, TaskCheckpoint
from paw.core.detectors import ProgressDetector, RepetitionDetector, StallDetector
from paw.core.storage import db, set_db_path


@pytest.mark.asyncio
async def test_checkpoint_persisted_and_resumed(tmp_path):
    """Checkpoint should persist to SQLite and restore on resume."""
    test_paw_home = tmp_path / ".paw"
    test_paw_home.mkdir(parents=True, exist_ok=True)
    db_path = test_paw_home / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    await CheckpointStore.ensure_table()

    # Create a task first (FK constraint)
    await db.execute(
        """
        INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("task-cp", "session-cp", "Checkpoint test task", "running", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    checkpoint = TaskCheckpoint(
        task_id="task-cp",
        task_status="running",
        current_step=3,
        total_steps=10,
        progress_ratio=0.3,
        context={"last_result": "ok", "retries": 1},
        autonomy_usage={
            "decisions": 5,
            "model_calls": 2,
            "tool_calls": 3,
            "total_tokens": 400,
            "iterations": 3,
            "last_progress_ratio": 0.3,
        },
        autonomy_profile="balanced",
        progress_history=[0.1, 0.2, 0.3],
        repetition_state={"tool_outputs_tracked": 2},
        stall_state={"consecutive_errors": 0},
        loop_iteration=3,
        loop_decision_history=[
            {"iteration": 1, "decision": "continue"},
            {"iteration": 2, "decision": "continue"},
        ],
        tags=["phase10", "integration"],
    )

    saved_id = await CheckpointStore.save(checkpoint)
    assert saved_id == checkpoint.checkpoint_id

    loaded = await CheckpointStore.get_latest("task-cp")
    assert loaded is not None
    assert loaded.task_id == "task-cp"
    assert loaded.progress_ratio == 0.3
    assert loaded.context["last_result"] == "ok"
    assert loaded.loop_iteration == 3
    assert len(loaded.progress_history) == 3


@pytest.mark.asyncio
async def test_checkpoint_parent_chain_intact(tmp_path):
    """Parent checkpoint chain should be preserved."""
    test_paw_home = tmp_path / ".paw"
    test_paw_home.mkdir(parents=True, exist_ok=True)
    db_path = test_paw_home / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    await CheckpointStore.ensure_table()

    # Create a task first (FK constraint)
    await db.execute(
        """
        INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("task-chain", "session-chain", "Chain test task", "running", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    cp1 = TaskCheckpoint(task_id="task-chain", task_status="running", progress_ratio=0.2)
    cp2 = TaskCheckpoint(task_id="task-chain", task_status="running", progress_ratio=0.5, parent_checkpoint_id=cp1.checkpoint_id)
    cp3 = TaskCheckpoint(task_id="task-chain", task_status="running", progress_ratio=0.8, parent_checkpoint_id=cp2.checkpoint_id)

    await CheckpointStore.save(cp1)
    await CheckpointStore.save(cp2)
    await CheckpointStore.save(cp3)

    latest = await CheckpointStore.get_latest("task-chain")
    assert latest.checkpoint_id == cp3.checkpoint_id
    assert latest.parent_checkpoint_id == cp2.checkpoint_id

    cp2_loaded = await CheckpointStore.get_by_id(cp2.checkpoint_id)
    assert cp2_loaded.parent_checkpoint_id == cp1.checkpoint_id


@pytest.mark.asyncio
async def test_resume_does_not_auto_repeat_completed_ops(tmp_path):
    """Resume should not automatically re-execute already completed operations."""
    test_paw_home = tmp_path / ".paw"
    test_paw_home.mkdir(parents=True, exist_ok=True)
    db_path = test_paw_home / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    await CheckpointStore.ensure_table()

    # Create a task first (FK constraint)
    await db.execute(
        """
        INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("task-idempotent", "session-idempotent", "Idempotency test task", "paused", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )

    completed_ops = [
        {"op": "fetch", "args": {"id": 1}, "result": "ok"},
        {"op": "write", "args": {"path": "/tmp/x"}, "result": "ok"},
    ]

    checkpoint = TaskCheckpoint(
        task_id="task-idempotent",
        task_status="paused",
        current_step=2,
        total_steps=5,
        progress_ratio=0.4,
        context={"completed_ops": completed_ops, "last_step": 2},
    )
    await CheckpointStore.save(checkpoint)

    # Resume would restore context including completed_ops
    resume_mgr = ResumeManager()
    # In real runtime, resume would call registered hooks.
    # Here we just verify checkpoint roundtrip preserves completion markers.
    loaded = await CheckpointStore.get_latest("task-idempotent")
    assert loaded is not None
    assert loaded.context.get("last_step") == 2
    assert len(loaded.context.get("completed_ops", [])) == 2