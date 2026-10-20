"""The streaming client must honor the same intake guards as plain chat."""

from unittest.mock import AsyncMock

import pytest

from paw.application.chat import ChatService
from paw.core.storage import db


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("state", ["cancelled", "pending", "approved"])
async def test_refused_intake_keeps_task_history_and_approval(tmp_path, monkeypatch, streaming, state):
    service = ChatService("local", workspace_root=tmp_path)
    await service.open()
    if state == "cancelled":
        await service.cancel()
    else:
        await service.send("hãy tạo file demo.txt")
        if state == "approved":
            await service.approve(execute=False)
    approval = service.session.pending_approval_id
    previous_task = service.session.current_task_id
    before = await db.fetch_all("SELECT id FROM tasks ORDER BY id")
    history = await service.history()
    build = AsyncMock(side_effect=AssertionError("refused intake built runtime"))
    monkeypatch.setattr(service, "_build_runtime", build)
    if streaming:
        events = [event async for event in service.send_streaming("new request")]
        reply = events[-1].reply
    else:
        reply = await service.send("new request")
    assert reply.status == ("cancelled" if state == "cancelled" else "waiting_approval")
    assert service.session.pending_approval_id == approval
    assert service.session.current_task_id == previous_task
    assert await db.fetch_all("SELECT id FROM tasks ORDER BY id") == before
    assert await service.history() == history
    build.assert_not_awaited()
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_empty_intake_has_no_durable_effect(tmp_path, streaming):
    service = ChatService("local", workspace_root=tmp_path)
    await service.open()
    if streaming:
        reply = ([event async for event in service.send_streaming("  ")])[-1].reply
    else:
        reply = await service.send("  ")
    assert reply.status == "invalid_input"
    assert await db.fetch_all("SELECT id FROM tasks") == []
    assert await service.history() == []
    await service.close()


@pytest.mark.asyncio
async def test_accepted_stream_persists_the_same_chat_contract(tmp_path):
    service = ChatService("local", workspace_root=tmp_path)
    await service.open()
    events = [event async for event in service.send_streaming("xin chào PAW")]
    reply = events[-1].reply
    assert events[-1].event_type == "complete"
    assert reply.status == "completed"
    assert reply.content == "[local-standin] xin chào PAW"
    assert reply.context_compiled
    assert [message.role.value for message in await service.history()] == ["user", "assistant"]
    await service.close()


@pytest.mark.asyncio
async def test_multiple_stream_chunks_are_persisted_as_one_model_answer(tmp_path, monkeypatch):
    service = ChatService("local", workspace_root=tmp_path)
    session = await service.open()

    async def chunks(selection, messages):
        yield {"model": "local-fast", "response": "xin ", "done": False}
        yield {"model": "local-fast", "response": "chào", "done": False}
        yield {"model": "local-fast", "done": True}

    monkeypatch.setattr(service._model_executor, "stream", chunks)
    events = [event async for event in service.send_streaming("hello")]
    assert [event.content for event in events if event.event_type == "token"] == ["xin ", "chào"]
    assert events[-1].reply.content == "xin chào"
    await service.close()
    reopened = ChatService("local", workspace_root=tmp_path)
    await reopened.open(session.session_id)
    assert (await reopened.history())[-1].content == "xin chào"
    await reopened.close()
