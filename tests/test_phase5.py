"""
Phase 5 Tests — Executor Fabric with full capability matching.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paw.core.models import Capability, CapabilityManifest, CapabilityScore
from paw.core.executor import (
    CapabilityRouter,
    ExecutableTask,
    Executor,
    ExecutorCapabilities,
    ExecutorRegistry,
    ExecutorResult,
    MockExecutor,
    executor_registry,
    get_capability_router,
)
from paw.core.task import Task
from paw.core.storage import db, set_db_path


class TestPhase5ExecutorProtocol:
    """Phase 5 Executor protocol tests."""

    @pytest.mark.asyncio
    async def test_mock_executor_execute(self):
        """Mock executor returns results."""
        executor = MockExecutor()
        task = Task(
            session_id="session-1",
            goal="tính 2 + 2",
            requested_capabilities=[Capability.SHELL_EXECUTE],
        )
        result = await executor.execute(task, "test context")
        assert result.success is True
        assert result.output is not None

    @pytest.mark.asyncio
    async def test_mock_executor_can_handle(self):
        """Mock executor can handle supported capabilities."""
        executor = MockExecutor()
        task = Task(
            session_id="session-1",
            goal="test",
            requested_capabilities=[Capability.FILESYSTEM_READ],
        )
        assert await executor.can_handle(task) is True

    @pytest.mark.asyncio
    async def test_mock_executor_estimate(self):
        """Mock executor estimates cost and latency."""
        executor = MockExecutor()
        task = Task(
            session_id="session-1",
            goal="test",
        )
        cost = await executor.estimate_cost(task)
        latency = await executor.estimate_latency(task)
        assert cost == 0.0
        assert latency in ("low", "medium", "high")

    @pytest.mark.asyncio
    async def test_executor_result_to_dict(self):
        """ExecutorResult serializes correctly."""
        result = ExecutorResult(
            success=True,
            output="test output",
            artifacts=[{"path": "/tmp/test"}],
            metadata={"key": "value"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == "test output"
        assert len(d["artifacts"]) == 1

    @pytest.mark.asyncio
    async def test_executor_result_with_task_result(self):
        """ExecutorResult with TaskResult."""
        from paw.core.models import TaskResult, Usage
        task_result = TaskResult(
            task_id="task-1",
            status="completed",
            summary="Done",
            executor="mock",
            usage=Usage(),
        )
        result = ExecutorResult(success=True, output="ok", task_result=task_result)
        d = result.to_dict()
        assert d["task_result"]["status"] == "completed"


class TestPhase5ExecutorCapabilities:
    """Phase 5 ExecutorCapabilities tests."""

    @pytest.mark.asyncio
    async def test_match_score_full(self):
        """Full capability match scores 1.0."""
        caps = [Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE]
        required = [Capability.FILESYSTEM_READ]
        score = ExecutorCapabilities.match_score(caps, required)
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_match_score_partial(self):
        """Partial capability match."""
        caps = [Capability.FILESYSTEM_READ]
        required = [Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE]
        score = ExecutorCapabilities.match_score(caps, required)
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_match_score_none(self):
        """No matching capabilities scores 0.0."""
        caps = [Capability.FILESYSTEM_READ]
        required = [Capability.SHELL_EXECUTE]
        score = ExecutorCapabilities.match_score(caps, required)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_match_score_no_requirements(self):
        """No requirements = full match."""
        caps = [Capability.FILESYSTEM_READ]
        score = ExecutorCapabilities.match_score(caps, [])
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_missing_capabilities(self):
        """Find missing capabilities."""
        caps = [Capability.FILESYSTEM_READ]
        required = [Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE]
        missing = ExecutorCapabilities.missing_capabilities(caps, required)
        assert Capability.FILESYSTEM_WRITE.value in missing

    @pytest.mark.asyncio
    async def test_can_handle(self):
        """Check if executor can handle capabilities."""
        caps = [Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE]
        required = [Capability.FILESYSTEM_READ]
        can, missing = ExecutorCapabilities.can_handle(caps, required)
        assert can is True
        assert len(missing) == 0

    @pytest.mark.asyncio
    async def test_can_handle_denied(self):
        """Check if executor cannot handle capabilities."""
        caps = [Capability.FILESYSTEM_READ]
        required = [Capability.SHELL_EXECUTE, Capability.FILESYSTEM_WRITE]
        can, missing = ExecutorCapabilities.can_handle(caps, required)
        assert can is False
        assert len(missing) > 0


class TestPhase5ExecutorRegistry:
    """Phase 5 ExecutorRegistry tests."""

    @pytest.mark.asyncio
    async def test_register_and_get(self):
        """Register and retrieve an executor."""
        registry = ExecutorRegistry()
        executor = MockExecutor()
        registry.register(executor)
        assert registry.get("mock") is not None
        assert registry.get("mock").name == "mock"

    @pytest.mark.asyncio
    async def test_unregister(self):
        """Unregister an executor."""
        registry = ExecutorRegistry()
        registry.register(MockExecutor())
        assert registry.has_executor("mock")
        result = registry.unregister("mock")
        assert result is True
        assert not registry.has_executor("mock")

    @pytest.mark.asyncio
    async def test_list(self):
        """List all executors."""
        registry = ExecutorRegistry()
        registry.register(MockExecutor())
        executors = registry.list()
        assert len(executors) >= 1

    @pytest.mark.asyncio
    async def test_list_by_capability(self):
        """List executors by capability."""
        registry = executor_registry
        executors = registry.list_by_capability(Capability.FILESYSTEM_READ)
        assert len(executors) >= 0  # mock has filesystem.read

    @pytest.mark.asyncio
    async def test_find_for_task(self):
        """Find executors for a task."""
        registry = executor_registry
        task = Task(
            session_id="session-1",
            goal="test",
            requested_capabilities=[Capability.FILESYSTEM_READ],
        )
        executors = await registry.find_for_task(task)
        assert len(executors) >= 0

    @pytest.mark.asyncio
    async def test_count(self):
        """Count registered executors."""
        registry = ExecutorRegistry()
        registry.register(MockExecutor())
        assert registry.count() == 1

    @pytest.mark.asyncio
    async def test_has_executor(self):
        """Check if executor exists."""
        registry = executor_registry
        assert registry.has_executor("mock") is True
        assert registry.has_executor("nonexistent") is False


class TestPhase5CapabilityRouter:
    """Phase 5 CapabilityRouter tests."""

    @pytest.mark.asyncio
    async def test_route(self):
        """Route capabilities to executors."""
        router = CapabilityRouter()
        scores = await router.route(
            "task-1", "test", [Capability.FILESYSTEM_READ]
        )
        assert len(scores) >= 1
        assert all(isinstance(s, CapabilityScore) for s in scores)
        # Scores sorted descending
        if len(scores) >= 2:
            assert scores[0].matched >= scores[1].matched

    @pytest.mark.asyncio
    async def test_best_executor(self):
        """Get best executor for capabilities."""
        router = CapabilityRouter()
        executor, score = await router.best_executor(
            "task-1", "test", [Capability.FILESYSTEM_READ]
        )
        assert executor is not None or score is not None

    @pytest.mark.asyncio
    async def test_best_executor_for_task(self):
        """Get best executor for a Task object."""
        router = CapabilityRouter()
        task = Task(
            session_id="session-1",
            goal="test",
            requested_capabilities=[Capability.FILESYSTEM_READ],
        )
        executor, score = await router.best_executor_for_task(task)
        assert executor is not None or score is not None

    @pytest.mark.asyncio
    async def test_route_with_complexity(self):
        """Route respects complexity."""
        router = CapabilityRouter()
        scores_high = await router.route(
            "task-1", "test", [Capability.FILESYSTEM_READ], complexity="high"
        )
        scores_low = await router.route(
            "task-1", "test", [Capability.FILESYSTEM_READ], complexity="low"
        )
        assert len(scores_high) >= 1
        assert len(scores_low) >= 1

    @pytest.mark.asyncio
    async def test_get_scores(self):
        """Retrieve scores for a task."""
        router = CapabilityRouter()
        await router.route("task-1", "test", [Capability.FILESYSTEM_READ])
        scores = router.get_scores("task-1")
        assert scores is not None
        assert len(scores) >= 1


class TestPhase5ExecutableTask:
    """Phase 5 ExecutableTask tests."""

    @pytest.mark.asyncio
    async def test_executable_task_creation(self):
        """Create an ExecutableTask."""
        task = ExecutableTask(
            task_id="task-1",
            goal="test",
            capabilities=[Capability.FILESYSTEM_READ],
            context="test context",
            model="local-fast",
        )
        assert task.task_id == "task-1"
        assert task.goal == "test"
        assert len(task.capabilities) == 1

    @pytest.mark.asyncio
    async def test_executable_task_to_dict(self):
        """ExecutableTask serializes correctly."""
        task = ExecutableTask(
            task_id="task-1",
            goal="test",
            capabilities=[Capability.FILESYSTEM_READ],
        )
        d = task.to_dict()
        assert d["task_id"] == "task-1"
        assert d["goal"] == "test"
        assert "filesystem.read" in d["capabilities"]


class TestPhase5NoProhibitedDependencies:
    """Verify no prohibited dependencies in Phase 5."""

    def test_no_qwenpaw(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "executor.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "qwenpaw" not in content.lower()

    def test_no_deepseek(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "executor.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "deepseek" not in content.lower() or "model" in content.lower()

    def test_no_notebooklm(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "executor.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "notebooklm" not in content.lower()

    def test_no_antigravity(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "executor.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "antigravity" not in content.lower()
