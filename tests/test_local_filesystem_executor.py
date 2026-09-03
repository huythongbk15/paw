"""Regression proof for the first real, workspace-scoped PAW executor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from paw.application.chat import ChatService
from paw.core.approval import ApprovalStatus, ApprovalStore
from paw.core.executor import ExecutableTask
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.models import Capability
from paw.executors.filesystem import LocalFilesystemExecutor


async def test_filesystem_executor_writes_and_reads_inside_workspace(tmp_path):
    executor = LocalFilesystemExecutor(tmp_path)
    write = ExecutableTask(
        task_id="task-write",
        goal="create demo",
        capabilities=[Capability.FILESYSTEM_WRITE],
        operation_id="operation-write",
        metadata={
            "filesystem": {
                "operation": "write",
                "path": "notes/demo.txt",
                "content": "xin chào\n",
                "mode": "create",
            }
        },
    )

    written = await executor.execute(write, "{}")

    assert written.success is True
    assert (tmp_path / "notes" / "demo.txt").read_text() == "xin chào\n"
    assert written.artifacts == [
        {
            "type": "file",
            "path": "notes/demo.txt",
            "operation": "created",
            "bytes": 10,
        }
    ]

    read = ExecutableTask(
        task_id="task-read",
        goal="read demo",
        capabilities=[Capability.FILESYSTEM_READ],
        operation_id="operation-read",
        metadata={"filesystem": {"operation": "read", "path": "notes/demo.txt"}},
    )
    observed = await executor.execute(read, "{}")
    assert observed.success is True
    assert observed.output == "xin chào\n"


async def test_filesystem_executor_rejects_workspace_escape(tmp_path):
    executor = LocalFilesystemExecutor(tmp_path)
    task = ExecutableTask(
        task_id="task-escape",
        goal="escape",
        capabilities=[Capability.FILESYSTEM_WRITE],
        operation_id="operation-escape",
        metadata={
            "filesystem": {
                "operation": "write",
                "path": "../outside.txt",
                "content": "blocked",
                "mode": "replace",
            }
        },
    )

    result = await executor.execute(task, "{}")

    assert result.success is False
    assert "outside workspace" in (result.error or "")
    assert not (tmp_path.parent / "outside.txt").exists()


async def test_filesystem_executor_rejects_write_through_symlink(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("original")
    link = tmp_path / "linked.txt"
    link.symlink_to(target)
    executor = LocalFilesystemExecutor(tmp_path)
    task = ExecutableTask(
        task_id="task-symlink",
        goal="replace through symlink",
        capabilities=[Capability.FILESYSTEM_WRITE],
        operation_id="operation-symlink",
        metadata={
            "filesystem": {
                "operation": "write",
                "path": "linked.txt",
                "content": "overwritten",
                "mode": "replace",
            }
        },
    )

    result = await executor.execute(task, "{}")

    assert result.success is False
    assert "symbolic-link writes are denied" in (result.error or "")
    assert target.read_text() == "original"


async def test_chat_approval_executes_exact_filesystem_write_once(temp_db, tmp_path):
    service = ChatService(provider_mode="local", workspace_root=tmp_path)
    await service.open()

    waiting = await service.send("tạo file demo.txt nội dung: xin chào PAW")

    assert waiting.status == "waiting_approval"
    assert waiting.approval_id is not None
    assert "demo.txt" in waiting.content
    assert "+xin chào PAW" in waiting.content
    assert not (tmp_path / "demo.txt").exists()

    completed = await service.approve()

    assert completed.status == "completed"
    assert completed.executor == "local-filesystem"
    assert completed.model is None
    assert (tmp_path / "demo.txt").read_text() == "xin chào PAW"
    assert completed.artifacts[0]["path"] == "demo.txt"

    approval = await ApprovalStore.get(waiting.approval_id)
    assert approval is not None
    assert approval.status == ApprovalStatus.CONSUMED

    events = await TaskLedger.get_events(completed.task_id)
    event_types = [event.event_type for event in events]
    assert TaskEventType.MODEL_SELECTED not in event_types
    assert event_types.index(TaskEventType.POLICY_GATE_EVALUATED) < event_types.index(
        TaskEventType.EXECUTOR_SELECTED
    )

    plan = await service.plan()
    assert plan is not None
    assert plan["filesystem"]["path"] == "demo.txt"
    assert (await service.checkpoint())["tags"] == ["completed"]
    assert (await service.policy())["latest_verdict"]["verdict"] == "go"
    assert (await service.artifacts())[0]["path"] == "demo.txt"
    explanation = await service.explain()
    assert explanation["executor"]["executor"] == "local-filesystem"
    assert explanation["model"] is None

    resumed_again = await service.resume()
    assert resumed_again.status == "idle"
    assert (tmp_path / "demo.txt").read_text() == "xin chào PAW"
    await service.close()


def test_cli_filesystem_write_and_explain_across_processes(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = os.environ.copy()
    env["PAW_PAW_HOME"] = str(tmp_path / "paw-home")

    waiting_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "paw",
            "chat",
            "--provider",
            "local",
            "--workspace",
            str(workspace),
            "--message",
            "tạo file cli.txt nội dung: nội dung thật",
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
    assert not (workspace / "cli.txt").exists()

    approved_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "paw",
            "chat",
            "--provider",
            "local",
            "--workspace",
            str(workspace),
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
    assert approved_process.returncode == 0, approved_process.stderr
    approved = json.loads(approved_process.stdout)
    assert approved["executor"] == "local-filesystem"
    assert (workspace / "cli.txt").read_text() == "nội dung thật"

    why_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "paw",
            "chat",
            "--provider",
            "local",
            "--workspace",
            str(workspace),
            "--session",
            waiting["session_id"],
            "--why",
            "--json",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert why_process.returncode == 0, why_process.stderr
    explanation = json.loads(why_process.stdout)
    assert explanation["executor"]["executor"] == "local-filesystem"
    assert explanation["artifacts"][0]["path"] == "cli.txt"
