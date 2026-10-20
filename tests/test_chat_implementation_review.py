"""Explicit review and effect approval share durable identity, never authority."""

import pytest

from paw.application.chat import ChatService
from paw.core.approval import ApprovalStore
from paw.core.models import ApprovalStatus
from paw.core.storage import db


@pytest.mark.parametrize("streaming", [False, True])
async def test_review_reopen_operation_approval_and_real_write(tmp_path, streaming):
    root = tmp_path / "project"
    root.mkdir()
    service = ChatService("local", workspace_root=root)
    session = await service.open()
    message = "tạo file result.txt nội dung: exact content"
    if streaming:
        events = [event async for event in service.send_streaming(message)]
        review = events[-1].reply
        assert all(event.event_type == "complete" for event in events)
    else:
        review = await service.send(message)
    request = await ApprovalStore.get(review.approval_id)
    assert request.metadata["purpose"] == "decision_review"
    assert request.status == ApprovalStatus.PENDING
    assert not (root / "result.txt").exists()
    await service.approve(execute=False)
    await service.close()
    await db.close()
    await db.initialize()
    service = ChatService("local", workspace_root=root)
    await service.open(session.session_id)
    operation = await service.resume()
    assert operation.status == "waiting_approval"
    assert operation.approval_id != review.approval_id
    assert operation.task_id == review.task_id
    assert not (root / "result.txt").exists()
    completed = await service.approve()
    assert completed.status == "completed", completed.content
    assert completed.task_id == review.task_id
    assert completed.executor == "local-filesystem" and completed.model is None
    assert (root / "result.txt").read_text() == "exact content"
    assert (await ApprovalStore.get(review.approval_id)).status == ApprovalStatus.APPROVED
    assert (await ApprovalStore.get(operation.approval_id)).status == ApprovalStatus.CONSUMED
    assert (await service.resume()).status == "idle"
    await service.close()


@pytest.mark.parametrize("when", ["before_review", "before_operation"])
async def test_dirty_change_refuses_at_both_approval_boundaries(tmp_path, when):
    root = tmp_path / "project"
    root.mkdir()
    (root / "source.py").write_text("before")
    service = ChatService("local", workspace_root=root)
    await service.open()
    await service.send("tạo file result.txt nội dung: should not run")
    if when == "before_operation":
        assert (await service.approve()).status == "waiting_approval"
    (root / "source.py").write_text("dirty external edit")
    result = await service.approve()
    assert result.status == "failed"
    assert not (root / "result.txt").exists()
    await service.close()


async def test_declined_review_does_not_create_plan_or_file(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    service = ChatService("local", workspace_root=root)
    await service.open()
    review = await service.send("tạo file result.txt nội dung: should not run")
    await ApprovalStore.deny(review.approval_id)
    assert (await service.resume()).status == "denied"
    assert await db.fetch_all("SELECT * FROM plans") == []
    assert not (root / "result.txt").exists()
    await service.close()
