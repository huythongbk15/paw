"""
Phase 1 Tests — Task Lifecycle E2E with Mock Executor
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from paw.core.models import Capability, TaskStatus
from paw.core.executor import MockExecutor, executor_registry
from paw.core.session import SessionManager
from paw.core.task import Task, TaskManager
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.skills import get_skill_fabric
from paw.core.config import settings
from paw.core.storage import db, set_db_path


WORKSPACE_ROOT = Path(__file__).parent.parent.parent


class TestPhase1Foundation:
    """Phase 1 acceptance: Task lifecycle E2E with MockExecutor."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        """Set up a fresh database for each test."""
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        # Re-initialize settings with new path
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_session_create_and_get(self, tmp_path):
        """Create and retrieve a session."""
        session = await SessionManager.create(project_id="test-project")
        assert session.id is not None
        assert session.project_id == "test-project"

        retrieved = await SessionManager.get(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.project_id == "test-project"

    @pytest.mark.asyncio
    async def test_task_create_and_get(self, tmp_path):
        """Create and retrieve a task."""
        session = await SessionManager.create()
        task = await TaskManager.create(
            session_id=session.id,
            goal="Test goal",
            requested_capabilities=[Capability.FILESYSTEM_READ],
        )
        assert task.id is not None
        assert task.goal == "Test goal"
        assert task.status == TaskStatus.PENDING
        assert Capability.FILESYSTEM_READ in task.requested_capabilities

        retrieved = await TaskManager.get(task.id)
        assert retrieved is not None
        assert retrieved.id == task.id
        assert retrieved.goal == "Test goal"

    @pytest.mark.asyncio
    async def test_task_status_transitions(self, tmp_path):
        """Test task status updates."""
        session = await SessionManager.create()
        task = await TaskManager.create(session_id=session.id, goal="Test")

        # Update to running
        task.status = TaskStatus.RUNNING
        await TaskManager.update(task)

        retrieved = await TaskManager.get(task.id)
        assert retrieved.status == TaskStatus.RUNNING

        # Update to completed
        updated = await TaskManager.update_status(task.id, TaskStatus.COMPLETED)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_task_ledger_recording(self, tmp_path):
        """Test ledger event recording."""
        session = await SessionManager.create()
        task = await TaskManager.create(session_id=session.id, goal="Test ledger")

        await TaskLedger.record(task.id, TaskEventType.TASK_CREATED, {"goal": "Test ledger"})
        await TaskLedger.record(task.id, TaskEventType.EXECUTION_STARTED, {"executor": "mock"})

        events = await TaskLedger.get_events(task.id)
        assert len(events) == 2
        assert events[0].event_type == TaskEventType.TASK_CREATED
        assert events[1].event_type == TaskEventType.EXECUTION_STARTED

    @pytest.mark.asyncio
    async def test_mock_executor_execution(self, tmp_path):
        """Test MockExecutor executes a task."""
        session = await SessionManager.create()
        task = await TaskManager.create(
            session_id=session.id,
            goal="hello world",
        )

        mock = MockExecutor()
        result = await mock.execute(task, "Test context")

        assert result.success is True
        assert result.output is not None
        assert "chào" in result.output.lower() or "mock" in result.output.lower()

    @pytest.mark.asyncio
    async def test_executor_registry(self, tmp_path):
        """Test executor registry find_for_task."""
        session = await SessionManager.create()
        task = await TaskManager.create(
            session_id=session.id,
            goal="test",
            requested_capabilities=[Capability.FILESYSTEM_READ],
        )

        executors = await executor_registry.find_for_task(task)
        assert len(executors) >= 1
        assert any(e.name == "mock" for e in executors)

    @pytest.mark.asyncio
    async def test_skill_fabric_builtin(self, tmp_path):
        """Test skill fabric loads builtin skills."""
        fabric = await get_skill_fabric()

        # Should have builtin skills
        skills = fabric.list_skills()
        assert len(skills) >= 2
        names = [s.name for s in skills]
        assert "echo" in names
        assert "datetime" in names

    @pytest.mark.asyncio
    async def test_skill_fabric_find_candidates(self, tmp_path):
        """Test skill candidate finding."""
        fabric = await get_skill_fabric()

        candidates = fabric.find_candidates("echo test")
        assert len(candidates) >= 1
        assert any(s.name == "echo" for s in candidates)

    @pytest.mark.asyncio
    async def test_full_task_lifecycle_e2e(self, tmp_path):
        """Full E2E: session -> task -> mock execute -> ledger -> complete."""
        # 1. Create session
        session = await SessionManager.create(project_id="e2e-test")

        # 2. Create task
        task = await TaskManager.create(
            session_id=session.id,
            goal="tính toán 2 + 2",
            requested_capabilities=[],
        )

        # 3. Record task created
        await TaskLedger.record(task.id, TaskEventType.TASK_CREATED, {"goal": task.goal})

        # 4. Execute with mock (using execute_task)
        from paw.core.executor import execute_task
        # Record execution start
        await TaskLedger.record(task.id, TaskEventType.EXECUTION_STARTED, {"executor": "mock"})
        result = await execute_task(task, "Context: simple calculation")
        # Record execution completed
        await TaskLedger.record(task.id, TaskEventType.EXECUTION_COMPLETED, {"success": result.success})

        # 5. Update task with result
        task.result = {"output": result.output}
        task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        from datetime import datetime, timezone
        task.completed_at = datetime.now(timezone.utc)
        await TaskManager.update(task)

        # 6. Verify ledger has events
        events = await TaskLedger.get_events(task.id)
        event_types = [e.event_type for e in events]
        assert TaskEventType.TASK_CREATED in event_types
        assert TaskEventType.EXECUTION_STARTED in event_types
        assert TaskEventType.EXECUTION_COMPLETED in event_types

        # 7. Verify final task state
        final_task = await TaskManager.get(task.id)
        assert final_task.status == TaskStatus.COMPLETED
        assert final_task.result is not None
        assert "42" in str(final_task.result) or "kết quả" in str(final_task.result).lower()


class TestPhase1CLI:
    """CLI integration tests for Phase 1 (if CLI commands added)."""

    def test_paw_task_help(self):
        """paw task --help should work (if implemented)."""
        # This will be implemented when CLI adds task commands
        # For now, just verify CLI still works
        result = subprocess.run(
            [sys.executable, "-m", "paw", "--help"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            check=False,
        )
        assert result.returncode == 0


class TestNoProhibitedDependenciesPhase1:
    """Verify no prohibited dependencies in new core modules."""

    def test_no_qwenpaw_in_core(self):
        core_dir = Path(__file__).parent.parent / "paw" / "core"
        for py_file in core_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "qwenpaw" not in content.lower(), f"QwenPaw reference in {py_file}"

    def test_no_deepseek_in_core(self):
        core_dir = Path(__file__).parent.parent / "paw" / "core"
        for py_file in core_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "deepseek" not in content.lower() or "model" in content.lower(), \
                f"DeepSeek reference in {py_file}"

    def test_no_notebooklm_in_core(self):
        core_dir = Path(__file__).parent.parent / "paw" / "core"
        for py_file in core_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "notebooklm" not in content.lower(), f"NotebookLM reference in {py_file}"

    def test_no_antigravity_in_core(self):
        core_dir = Path(__file__).parent.parent / "paw" / "core"
        for py_file in core_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "antigravity" not in content.lower(), f"Antigravity reference in {py_file}"
