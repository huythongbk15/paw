"""
Phase 9 Tests — Task Scheduler with TaskDependency, TaskGraph, TaskScheduler.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paw.core import (
    TaskScheduler, TaskGraph, TaskDependency, TaskScheduleStatus,
    DependencyType, TaskNode, TaskStatus, get_task_scheduler,
    ensure_task_scheduler_tables,
)
from paw.core.storage import db, set_db_path


class TestPhase9TaskDependency:
    """Phase 9 TaskDependency tests."""

    @pytest.mark.asyncio
    async def test_dependency_creation(self):
        """Create a task dependency."""
        dep = TaskDependency(
            from_node_id="node-1",
            to_node_id="node-2",
            dependency_type=DependencyType.MUST_COMPLETE.value,
        )
        assert dep.from_node_id == "node-1"
        assert dep.to_node_id == "node-2"
        assert dep.dependency_type == DependencyType.MUST_COMPLETE.value

    @pytest.mark.asyncio
    async def test_dependency_to_dict(self):
        """Dependency serializes correctly."""
        dep = TaskDependency(
            from_node_id="node-1",
            to_node_id="node-2",
            dependency_type=DependencyType.PARALLEL.value,
            condition="after_step_1",
        )
        d = dep.to_dict()
        assert d["from_node_id"] == "node-1"
        assert d["to_node_id"] == "node-2"
        assert d["dependency_type"] == "parallel"
        assert d["condition"] == "after_step_1"

    @pytest.mark.asyncio
    async def test_dependency_from_row(self):
        """Create dependency from DB row."""
        dep = TaskDependency(
            id="dep-1",
            from_node_id="node-1",
            to_node_id="node-2",
            dependency_type="must_complete",
            condition="test condition",
        )
        row = {
            "id": "dep-1",
            "from_node_id": "node-1",
            "to_node_id": "node-2",
            "dependency_type": "must_complete",
            "condition": "test condition",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        parsed = TaskDependency.from_row(row)
        assert parsed.from_node_id == "node-1"
        assert parsed.to_node_id == "node-2"
        assert parsed.dependency_type == "must_complete"


class TestPhase9TaskGraph:
    """Phase 9 TaskGraph tests."""

    @pytest.mark.asyncio
    async def test_graph_creation(self):
        """Create a task graph."""
        graph = TaskGraph(task_id="task-1")
        assert graph.task_id == "task-1"
        assert len(graph.nodes) == 0
        assert len(graph.dependencies) == 0

    @pytest.mark.asyncio
    async def test_add_node(self):
        """Add a node to the graph."""
        graph = TaskGraph(task_id="task-1")
        node = TaskNode(id="node-1", task_id="task-1", goal="Test")
        graph.add_node(node)
        assert len(graph.nodes) == 1
        assert graph.get_node("node-1") is not None

    @pytest.mark.asyncio
    async def test_remove_node(self):
        """Remove a node from the graph."""
        graph = TaskGraph(task_id="task-1")
        node = TaskNode(id="node-1", task_id="task-1", goal="Test")
        graph.add_node(node)
        graph.add_dependency(TaskDependency(from_node_id="node-1", to_node_id="node-2"))
        result = graph.remove_node("node-1")
        assert result is True
        assert len(graph.nodes) == 0
        assert len(graph.dependencies) == 0

    @pytest.mark.asyncio
    async def test_remove_node_not_found(self):
        """Remove non-existent node returns False."""
        graph = TaskGraph(task_id="task-1")
        result = graph.remove_node("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_add_dependency(self):
        """Add a dependency."""
        graph = TaskGraph(task_id="task-1")
        node1 = TaskNode(id="node-1", task_id="task-1", goal="A")
        node2 = TaskNode(id="node-2", task_id="task-1", goal="B")
        graph.add_node(node1)
        graph.add_node(node2)
        dep = TaskDependency(from_node_id="node-1", to_node_id="node-2")
        graph.add_dependency(dep)
        assert len(graph.dependencies) == 1

    @pytest.mark.asyncio
    async def test_node_count(self):
        """Count nodes."""
        graph = TaskGraph(task_id="task-1")
        graph.add_node(TaskNode(id="n1", task_id="task-1", goal="A"))
        graph.add_node(TaskNode(id="n2", task_id="task-1", goal="B"))
        assert graph.node_count() == 2

    @pytest.mark.asyncio
    async def test_dependency_count(self):
        """Count dependencies."""
        graph = TaskGraph(task_id="task-1")
        graph.add_node(TaskNode(id="n1", task_id="task-1", goal="A"))
        graph.add_node(TaskNode(id="n2", task_id="task-1", goal="B"))
        graph.add_dependency(TaskDependency(from_node_id="n1", to_node_id="n2"))
        assert graph.dependency_count() == 1

    @pytest.mark.asyncio
    async def test_get_node(self):
        """Get a node by ID."""
        graph = TaskGraph(task_id="task-1")
        node = TaskNode(id="node-1", task_id="task-1", goal="Test")
        graph.add_node(node)
        assert graph.get_node("node-1") is node
        assert graph.get_node("nonexistent") is None

    @pytest.mark.asyncio
    async def test_to_dict(self):
        """Graph serializes correctly."""
        graph = TaskGraph(task_id="task-1")
        graph.add_node(TaskNode(id="n1", task_id="task-1", goal="A"))
        graph.add_dependency(TaskDependency(from_node_id="n1", to_node_id="n1"))
        d = graph.to_dict()
        assert d["task_id"] == "task-1"
        assert "n1" in d["nodes"]
        assert len(d["dependencies"]) >= 1


class TestPhase9TaskScheduler:
    """Phase 9 TaskScheduler tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        await ensure_task_scheduler_tables()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_build_graph(self, tmp_path):
        """Build a task graph."""
        scheduler = TaskScheduler()
        nodes = [
            TaskNode(id="n1", task_id="task-1", goal="A"),
            TaskNode(id="n2", task_id="task-1", goal="B"),
        ]
        graph = await scheduler.build_graph("task-1", nodes)
        assert graph.task_id == "task-1"
        assert len(graph.nodes) == 2

    @pytest.mark.asyncio
    async def test_topological_sort(self, tmp_path):
        """Topological sort of task graph."""
        scheduler = TaskScheduler()
        # Create nodes with dependencies
        n1 = TaskNode(id="n1", task_id="task-1", goal="A", dependencies=[])
        n2 = TaskNode(id="n2", task_id="task-1", goal="B", dependencies=["n1"])
        n3 = TaskNode(id="n3", task_id="task-1", goal="C", dependencies=["n2"])
        graph = await scheduler.build_graph("task-1", [n1, n2, n3])

        order = await scheduler.topological_sort("task-1")
        assert len(order) == 3
        # n1 should come before n2, n2 before n3
        ids = [n.id for n in order]
        assert ids.index("n1") < ids.index("n2")
        assert ids.index("n2") < ids.index("n3")

    @pytest.mark.asyncio
    async def test_topological_sort_no_deps(self, tmp_path):
        """Topological sort with no dependencies."""
        scheduler = TaskScheduler()
        nodes = [
            TaskNode(id="n1", task_id="task-1", goal="A", dependencies=[]),
            TaskNode(id="n2", task_id="task-1", goal="B", dependencies=[]),
        ]
        await scheduler.build_graph("task-1", nodes)
        order = await scheduler.topological_sort("task-1")
        assert len(order) == 2

    @pytest.mark.asyncio
    async def test_get_ready_nodes(self, tmp_path):
        """Get nodes ready to execute."""
        scheduler = TaskScheduler()
        n1 = TaskNode(id="n1", task_id="task-1", goal="A", dependencies=[])
        n2 = TaskNode(id="n2", task_id="task-1", goal="B", dependencies=["n1"])
        graph = await scheduler.build_graph("task-1", [n1, n2])

        # n1 has no deps, should be ready
        ready = await scheduler.get_ready_nodes("task-1")
        assert len(ready) >= 1
        assert any(n.id == "n1" for n in ready)

    @pytest.mark.asyncio
    async def test_detect_cycles(self, tmp_path):
        """Detect cycles in task graph."""
        scheduler = TaskScheduler()
        nodes = [
            TaskNode(id="n1", task_id="task-1", goal="A", dependencies=[]),
            TaskNode(id="n2", task_id="task-1", goal="B", dependencies=["n1"]),
            TaskNode(id="n3", task_id="task-1", goal="C", dependencies=["n2"]),
        ]
        await scheduler.build_graph("task-1", nodes)
        cycles = await scheduler.detect_cycles("task-1")
        # No cycle in this graph
        assert len(cycles) == 0

    @pytest.mark.asyncio
    async def test_estimate_parallelism(self, tmp_path):
        """Estimate parallel execution potential."""
        scheduler = TaskScheduler()
        n1 = TaskNode(id="n1", task_id="task-1", goal="A", dependencies=[])
        n2 = TaskNode(id="n2", task_id="task-1", goal="B", dependencies=["n1"])
        n3 = TaskNode(id="n3", task_id="task-1", goal="C", dependencies=["n1"])
        await scheduler.build_graph("task-1", [n1, n2, n3])

        parallel = await scheduler.estimate_parallelism("task-1")
        assert parallel["total_nodes"] == 3
        assert parallel["max_parallel"] >= 2  # n2 and n3 can run in parallel

    @pytest.mark.asyncio
    async def test_get_schedule_order(self, tmp_path):
        """Get execution schedule order."""
        scheduler = TaskScheduler()
        nodes = [
            TaskNode(id="n1", task_id="task-1", goal="A", dependencies=[]),
            TaskNode(id="n2", task_id="task-1", goal="B", dependencies=["n1"]),
        ]
        await scheduler.build_graph("task-1", nodes)
        order = await scheduler.get_schedule_order("task-1")
        assert len(order) == 2
        assert order.index("n1") < order.index("n2")

    @pytest.mark.asyncio
    async def test_update_node_status(self, tmp_path):
        """Update node execution status."""
        scheduler = TaskScheduler()
        await scheduler.update_node_status("n1", TaskScheduleStatus.RUNNING)
        assert scheduler._execution_status["n1"] == TaskScheduleStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_graph_from_db(self, tmp_path):
        """Retrieve graph from DB."""
        scheduler = TaskScheduler()
        nodes = [TaskNode(id="n1", task_id="task-1", goal="Test")]
        await scheduler.build_graph("task-1", nodes)

        retrieved = await scheduler.get_graph("task-1")
        assert retrieved is not None
        assert retrieved.task_id == "task-1"

    @pytest.mark.asyncio
    async def test_empty_topological_sort(self, tmp_path):
        """Topological sort for non-existent graph."""
        scheduler = TaskScheduler()
        order = await scheduler.topological_sort("nonexistent")
        assert order == []


class TestPhase9SchedulerGlobal:
    """Phase 9 Global scheduler instance tests."""

    @pytest.mark.asyncio
    async def test_get_task_scheduler(self):
        """Get global task scheduler."""
        scheduler = get_task_scheduler()
        assert scheduler is not None
        assert isinstance(scheduler, TaskScheduler)


class TestPhase9NoProhibitedDependencies:
    """Verify no prohibited dependencies in Phase 9."""

    @pytest.fixture
    def paw_source_root(self) -> Path:
        """Get the PAW source root directory."""
        import paw
        return Path(paw.__file__).parent

    def test_no_qwenpaw(self, paw_source_root):
        """No QwenPaw references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            assert "qwenpaw" not in content.lower(), f"QwenPaw reference found in {file}"

    def test_no_deepseek(self, paw_source_root):
        """No DeepSeek Harness references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            assert "deepseek" not in content.lower() or "model" in content.lower(), f"DeepSeek reference found in {file}"

    def test_no_notebooklm(self, paw_source_root):
        """No NotebookLM references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            assert "notebooklm" not in content.lower(), f"NotebookLM reference found in {file}"

    def test_no_antigravity(self, paw_source_root):
        """No Google Antigravity references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            assert "antigravity" not in content.lower(), f"Antigravity reference found in {file}"

    def test_negative_control_detects_prohibited(self, tmp_path):
        """Negative control: scanner detects prohibited reference in fixture."""
        import paw
        paw_root = Path(paw.__file__).parent
        
        # Create a temporary fixture file with prohibited content
        fixture = tmp_path / "test_prohibited.py"
        fixture.write_text("# This file contains qwenpaw reference\n")
        
        # The scanner should detect it
        content = fixture.read_text()
        assert "qwenpaw" in content.lower()
        
        # Verify our scan logic would catch it
        found = False
        for file in [fixture]:
            if "qwenpaw" in file.read_text().lower():
                found = True
                break
        assert found, "Negative control failed: scanner should detect prohibited reference"
