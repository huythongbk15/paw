"""End-to-end proof for the durable ``paw chat`` vertical slice."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from paw.application.chat import ChatMessage, ChatService
from paw.core.approval import ApprovalStatus, ApprovalStore
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.models import Capability, ChatRole, ProposedAction, TaskStatus
from paw.core.storage import db
from paw.core.task import TaskManager


@pytest.mark.asyncio
async def test_chat_turn_runs_complete_runtime_path(temp_db):
    service = ChatService(provider_mode="local")
    session = await service.open()

    reply = await service.send("xin chào PAW")

    assert reply.status == "completed"
    assert reply.context_compiled is True
    assert reply.model == "local-fast"
    assert reply.executor == "mock"
    assert reply.content == "[local-standin] xin chào PAW"
    assert reply.task_id is not None

    task = await TaskManager.get(reply.task_id)
    assert task is not None
    assert task.status == TaskStatus.COMPLETED
    assert task.selected_model == "local-fast"
    assert task.selected_executor == "mock"

    events = await TaskLedger.get_events(reply.task_id)
    event_types = [event.event_type for event in events]
    assert TaskEventType.POLICY_GATE_EVALUATED in event_types
    assert TaskEventType.MODEL_SELECTED in event_types
    assert TaskEventType.EXECUTOR_SELECTED in event_types
    assert event_types.index(TaskEventType.POLICY_GATE_EVALUATED) < event_types.index(
        TaskEventType.MODEL_SELECTED
    )

    resumed = ChatService(provider_mode="local")
    await resumed.open(session.session_id)
    history = await resumed.history()
    assert [message.role.value for message in history] == ["user", "assistant"]
    assert history[0].content == "xin chào PAW"
    await service.close()
    await resumed.close()


def test_chat_model_prompt_is_bounded():
    messages = [
        ChatMessage(
            id=f"message-{index:02d}",
            session_id="session-demo",
            role=ChatRole.USER,
            content="x" * 1000,
        )
        for index in range(100)
    ]
    bounded = ChatService._bounded_model_messages(messages)
    assert len(bounded) <= ChatService.MAX_MODEL_MESSAGES
    assert sum(len(item["content"]) for item in bounded) <= ChatService.MAX_MODEL_CHARS


@pytest.mark.asyncio
async def test_ask_persists_then_approve_resume_consumes_exact_operation(temp_db):
    service = ChatService(provider_mode="local")
    session = await service.open()

    waiting = await service.send("hãy tạo file demo.txt")

    assert waiting.status == "waiting_approval"
    assert waiting.waiting_for_approval is True
    assert waiting.approval_id is not None
    assert waiting.checkpoint_id is not None
    assert waiting.task_id is not None

    task = await TaskManager.get(waiting.task_id)
    assert task is not None
    assert task.status == TaskStatus.BLOCKED
    events = await TaskLedger.get_events(task.id)
    assert TaskEventType.MODEL_SELECTED not in [event.event_type for event in events]
    assert TaskEventType.EXECUTOR_SELECTED not in [event.event_type for event in events]

    approved = await service.approve(execute=False)
    assert approved.status == ApprovalStatus.APPROVED.value
    approved_request = await ApprovalStore.get(waiting.approval_id)
    assert approved_request is not None
    assert await ApprovalStore.is_approved(task.id, approved_request.action) is True
    await service.close()
    await db.close()
    await db.initialize()

    # Simulate a process restart between approval and execution.
    resumed_service = ChatService(provider_mode="local")
    await resumed_service.open(session.session_id)
    reloaded_request = await ApprovalStore.get(waiting.approval_id)
    assert reloaded_request is not None
    assert await ApprovalStore.is_approved(task.id, reloaded_request.action) is True
    completed = await resumed_service.resume()

    assert completed.status == "completed"
    assert completed.task_id == task.id
    request = await ApprovalStore.get(waiting.approval_id)
    assert request is not None
    assert request.status == ApprovalStatus.CONSUMED
    assert await db.fetch_one(
        "SELECT * FROM operation_records WHERE task_id = ? AND op_id = ?",
        (task.id, request.operation_id),
    )
    history = await resumed_service.history()
    assert len(history) == 3
    await resumed_service.close()


@pytest.mark.asyncio
async def test_approval_cannot_authorize_changed_action(temp_db):
    service = ChatService(provider_mode="local")
    await service.open()
    waiting = await service.send("ghi file demo.txt")
    request = await ApprovalStore.approve(waiting.approval_id)
    assert request is not None

    changed = ProposedAction.model_validate(request.action.to_dict())
    changed.goal = "ghi file khác.txt"

    assert await ApprovalStore.is_approved(request.task_id, changed) is False
    refreshed = await ApprovalStore.request(request.task_id, changed)
    assert refreshed.status == ApprovalStatus.PENDING
    assert refreshed.action.goal == "ghi file khác.txt"
    await service.close()


@pytest.mark.asyncio
async def test_hard_deny_never_creates_approval_or_calls_model(temp_db):
    service = ChatService(provider_mode="local")
    await service.open()

    reply = await service.send("xóa file quan-trong.txt")

    assert reply.status == "denied"
    assert reply.approval_id is None
    assert reply.task_id is not None
    assert await ApprovalStore.latest_pending(reply.task_id) is None
    events = await TaskLedger.get_events(reply.task_id)
    event_types = [event.event_type for event in events]
    assert TaskEventType.MODEL_SELECTED not in event_types
    assert TaskEventType.EXECUTOR_SELECTED not in event_types
    await service.close()


@pytest.mark.asyncio
async def test_precreated_approval_cannot_override_hard_deny(temp_db):
    service = ChatService(provider_mode="local")
    session = await service.open()
    task = await TaskManager.create(
        session.session_id,
        "xóa file quan-trong.txt",
        requested_capabilities=[
            Capability.MODEL_INFERENCE,
            Capability.FILESYSTEM_DELETE,
        ],
    )
    action = ProposedAction(
        goal=task.goal,
        capabilities=task.requested_capabilities,
        operation_id=f"chat-{task.id}",
        metadata={"done": True},
    )
    request = await ApprovalStore.request(task.id, action)
    await ApprovalStore.approve(request.id)

    reply = await service._run_action(task, action)

    assert reply.status == "denied"
    events = await TaskLedger.get_events(task.id)
    assert TaskEventType.MODEL_SELECTED not in [event.event_type for event in events]
    assert TaskEventType.EXECUTOR_SELECTED not in [event.event_type for event in events]
    still_approved = await ApprovalStore.get(request.id)
    assert still_approved is not None
    assert still_approved.status == ApprovalStatus.APPROVED
    await service.close()


def test_cli_chat_one_shot_json(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PAW_PAW_HOME"] = str(tmp_path / ".paw-chat")
    result = subprocess.run(
        [sys.executable, "-m", "paw", "chat", "-m", "xin chào CLI", "--json"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["context_compiled"] is True
    assert payload["model"] == "local-fast"
    assert payload["executor"] == "mock"


def test_cli_chat_approval_survives_process_boundary(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PAW_PAW_HOME"] = str(tmp_path / ".paw-chat-approval")
    waiting_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "paw",
            "chat",
            "-m",
            "hãy tạo file demo.txt",
            "--json",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert waiting_process.returncode == 0, waiting_process.stderr
    waiting = json.loads(waiting_process.stdout)
    assert waiting["status"] == "waiting_approval"
    assert waiting["model"] is None
    assert waiting["executor"] is None

    resume_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "paw",
            "chat",
            "--session",
            waiting["session_id"],
            "--approve",
            "--json",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert resume_process.returncode == 0, resume_process.stderr
    completed = json.loads(resume_process.stdout)
    assert completed["status"] == "completed"
    assert completed["task_id"] == waiting["task_id"]
    assert completed["model"] == "local-fast"
    assert completed["executor"] == "mock"
