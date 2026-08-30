"""
Phase 19 #4 — TaskGraph validates before persist/execute.

``TaskScheduler.build_graph`` must reject structurally invalid graphs rather
than persisting them: missing dependencies, self-cycles, and general cycles
are all rejected with ``TaskGraphValidationError``.
"""

from __future__ import annotations

import pytest

from paw.core.planner import TaskNode
from paw.core.task_scheduler import TaskGraphValidationError, TaskScheduler


async def test_valid_dag_builds(tmp_path):
    scheduler = TaskScheduler()
    nodes = [
        TaskNode(id="n1", task_id="task-1", goal="A", dependencies=[]),
        TaskNode(id="n2", task_id="task-1", goal="B", dependencies=["n1"]),
        TaskNode(id="n3", task_id="task-1", goal="C", dependencies=["n2"]),
    ]
    graph = await scheduler.build_graph("task-1", nodes)
    assert graph.task_id == "task-1"
    assert len(graph.nodes) == 3


async def test_missing_dependency_rejected(tmp_path):
    scheduler = TaskScheduler()
    nodes = [
        TaskNode(id="n1", task_id="task-1", goal="A", dependencies=["ghost"]),
    ]
    with pytest.raises(TaskGraphValidationError, match="missing node"):
        await scheduler.build_graph("task-1", nodes)


async def test_self_cycle_rejected(tmp_path):
    scheduler = TaskScheduler()
    nodes = [
        TaskNode(id="n1", task_id="task-1", goal="A", dependencies=["n1"]),
    ]
    with pytest.raises(TaskGraphValidationError, match="self-cycle"):
        await scheduler.build_graph("task-1", nodes)


async def test_cycle_rejected(tmp_path):
    scheduler = TaskScheduler()
    nodes = [
        TaskNode(id="n1", task_id="task-1", goal="A", dependencies=["n3"]),
        TaskNode(id="n2", task_id="task-1", goal="B", dependencies=["n1"]),
        TaskNode(id="n3", task_id="task-1", goal="C", dependencies=["n2"]),
    ]
    with pytest.raises(TaskGraphValidationError, match="cycle"):
        await scheduler.build_graph("task-1", nodes)
