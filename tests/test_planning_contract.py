"""Ownership and public-surface regressions for PAW planning."""

from __future__ import annotations

import ast
from pathlib import Path

import paw.core as core
import pytest
from paw.core.planner import Plan, Planner
from paw.core.storage import db
from paw.core.task import TaskManager
from paw.core.task_scheduler import TaskScheduler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CORE = {
    "AutonomyDecision",
    "Capability",
    "ExecutionObservation",
    "PawRuntime",
    "PolicyDecision",
    "ProposedAction",
    "ResourceUsage",
    "RuntimeOutcome",
    "StopReason",
    "TaskResult",
    "TaskStatus",
}


def test_paw_core_exports_only_the_runtime_contract() -> None:
    assert set(core.__all__) == PUBLIC_CORE
    assert not hasattr(core, "IntelligentPlanner")
    assert not hasattr(core, "TaskScheduler")


async def test_planner_is_the_only_plan_factory(temp_db) -> None:
    task = await TaskManager.create(
        session_id="session-owner",
        goal="search files and summarize",
    )
    plan = await Planner().plan(task.id)

    assert isinstance(plan, Plan)
    assert len(plan.nodes) >= 2
    assert not hasattr(TaskScheduler, "plan")


async def test_planner_preserves_existing_task_identity_across_reopen(temp_db) -> None:
    task = await TaskManager.create(
        session_id="session-owner",
        goal="search files and summarize",
        project_id="project-owner",
    )

    plan = await Planner().plan(task.id)

    assert plan.id != task.id
    assert plan.task_id == task.id
    assert plan.session_id == task.session_id
    assert plan.goal == task.goal
    assert plan.nodes
    assert {node.task_id for node in plan.nodes} == {task.id}

    await db.close()
    await db.initialize()
    restored = await Planner().get_plan(plan.id)

    assert restored is not None
    assert restored.id == plan.id
    assert restored.task_id == task.id
    assert {node.task_id for node in restored.nodes} == {task.id}


async def test_planner_rejects_unknown_task_without_persisting_plan(temp_db) -> None:
    with pytest.raises(ValueError, match="Unknown task"):
        await Planner().plan("missing-task")

    assert await db.fetch_one("SELECT id FROM plans LIMIT 1") is None
    assert await db.fetch_one("SELECT id FROM task_nodes LIMIT 1") is None


def test_planner_proposer_scheduler_have_one_class_owner_each() -> None:
    assert not (
        PROJECT_ROOT / "src" / "paw" / "core" / "intelligent_planner.py"
    ).exists()
    owners: dict[str, list[str]] = {
        "Planner": [],
        "AgentActionProposer": [],
        "TaskScheduler": [],
        "IntelligentPlanner": [],
    }
    for path in (PROJECT_ROOT / "src" / "paw").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(path.relative_to(PROJECT_ROOT).as_posix())

    assert owners == {
        "Planner": ["src/paw/core/planner.py"],
        "AgentActionProposer": ["src/paw/core/runtime.py"],
        "TaskScheduler": ["src/paw/core/task_scheduler.py"],
        "IntelligentPlanner": [],
    }
