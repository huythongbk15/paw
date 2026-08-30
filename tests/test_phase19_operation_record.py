"""
Phase 19 #5 — Checkpoint OperationRecord / minimal idempotency for replay safety.

Completed primitive operations are recorded durably. On resume/replay, the
runtime consults these records and skips already-completed operations, so
effects are never double-executed.
"""

from __future__ import annotations

import pytest

from paw.core.checkpoint import CheckpointManager, OperationRecordStore


async def test_operation_record_idempotent_replay(tmp_path):
    mgr = CheckpointManager()

    # First execution records completed operations.
    await mgr.record_operation("T", "step-1", status="completed")
    await mgr.record_operation("T", "step-2", status="completed")

    assert await mgr.is_operation_completed("T", "step-1") is True
    assert await mgr.is_operation_completed("T", "step-2") is True
    assert await mgr.is_operation_completed("T", "step-3") is False

    # Simulate resume/replay: only NOT-yet-completed ops should execute.
    planned = ["step-1", "step-2", "step-3", "step-4"]
    executed = [op for op in planned if not await mgr.is_operation_completed("T", op)]

    # step-1/step-2 are skipped -> replay safety proven.
    assert executed == ["step-3", "step-4"]


async def test_operation_record_durable_across_instances(tmp_path):
    mgr = CheckpointManager()
    await mgr.record_operation(
        "T", "step-1", status="completed", checkpoint_id="cpA", result_ref="result://x"
    )

    # A fresh manager instance must still observe the persisted record.
    mgr2 = CheckpointManager()
    assert await mgr2.is_operation_completed("T", "step-1") is True

    recs = await OperationRecordStore.get_all("T")
    assert len(recs) == 1
    assert recs[0].checkpoint_id == "cpA"
    assert recs[0].result_ref == "result://x"
    assert recs[0].status == "completed"
