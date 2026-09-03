"""
PAW Core — Planner

Decomposes goals into task graphs (DAGs).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .decomposition import StructuredReasoner
from .logging import get_logger
from .models import TaskStatus
from .storage import db
from .task import TaskManager

logger = get_logger(__name__)


@dataclass
class TaskNode:
    """A single node in a task graph."""
    id: str = ""
    task_id: str = ""
    goal: str = ""
    dependencies: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    context_requirements: dict[str, Any] = field(default_factory=dict)
    capability_requirements: list[str] = field(default_factory=list)
    policy_requirements: list[str] = field(default_factory=list)
    executor: str | None = None
    model: str | None = None
    result: dict[str, Any] | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "goal": self.goal,
            "dependencies": self.dependencies,
            "skills": self.skills,
            "context_requirements": self.context_requirements,
            "capability_requirements": self.capability_requirements,
            "policy_requirements": self.policy_requirements,
            "executor": self.executor,
            "model": self.model,
            "result": self.result,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> TaskNode:
        deps = []
        if row.get("dependencies"):
            deps = json.loads(row["dependencies"])
        skills = []
        if row.get("skills"):
            skills = json.loads(row["skills"])
        caps = []
        if row.get("capability_requirements"):
            caps = json.loads(row["capability_requirements"])
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            goal=row["goal"],
            dependencies=deps,
            skills=skills,
            context_requirements=json.loads(row["context_requirements"]) if row.get("context_requirements") else {},
            capability_requirements=caps,
            policy_requirements=json.loads(row["policy_requirements"]) if row.get("policy_requirements") else [],
            executor=row.get("executor"),
            model=row.get("model"),
            result=json.loads(row["result"]) if row.get("result") else None,
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


@dataclass
class Plan:
    """A plan containing a task graph (DAG)."""
    id: str = ""
    task_id: str = ""
    session_id: str = ""
    goal: str = ""
    nodes: list[TaskNode] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "nodes": [n.to_dict() for n in self.nodes],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict, nodes: list[TaskNode]) -> Plan:
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            session_id=row["session_id"],
            goal=row["goal"],
            nodes=nodes,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def topological_sort(self) -> list[TaskNode]:
        """Return nodes in topological order (dependencies first)."""
        visited = set()
        result: list[TaskNode] = []
        node_map = {n.id: n for n in self.nodes}

        def visit(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            node = node_map.get(node_id)
            if node:
                for dep in node.dependencies:
                    visit(dep)
                result.append(node)

        for node in self.nodes:
            visit(node.id)
        return result


class Planner:
    """Sole owner of canonical ``Plan`` creation and persistence.

    A decomposition strategy produces ordered reasoning steps. ``Planner``
    normalizes them to ``TaskNode`` records and persists the plan atomically.
    Runtime action proposal and graph scheduling are separate responsibilities.
    """

    def __init__(self, reasoner: StructuredReasoner | None = None):
        self.reasoner = reasoner or StructuredReasoner()

    async def plan(self, task_id: str) -> Plan:
        """Create a plan for an existing durable Task.

        Task identity, goal and session belong to ``TaskManager``. Requiring the
        canonical ID prevents Planner from inventing a parallel work identity
        or persisting caller-provided metadata that disagrees with the Task.
        """
        task = await TaskManager.get(task_id)
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        plan = Plan(task_id=task.id, goal=task.goal, session_id=task.session_id)
        plan.id = uuid.uuid4().hex[:16]

        nodes = self._decompose(task.goal)
        for node in nodes:
            node.task_id = task.id
        plan.nodes = nodes

        await self._save(plan)

        logger.info("plan_created", task_id=task.id, goal=task.goal, nodes=len(nodes))
        return plan

    def _decompose(self, goal: str) -> list[TaskNode]:
        """Normalize pure structured decomposition into canonical task nodes."""
        decomposition = self.reasoner.decompose(goal)
        nodes: list[TaskNode] = []
        for step in decomposition.steps:
            previous = nodes[-1].id if nodes else None
            nodes.append(
                TaskNode(
                    id=step.id or uuid.uuid4().hex[:16],
                    goal=step.goal,
                    dependencies=[previous] if previous else [],
                    context_requirements={
                        "reasoning": step.reasoning,
                        "sub_goals": step.sub_goals,
                        "estimated_effort": step.estimated_effort,
                    },
                    capability_requirements=list(step.required_capabilities),
                )
            )
        return nodes

    async def _save(self, plan: Plan) -> None:
        """Persist the plan and all nodes in one transaction."""
        async with db.transaction() as conn:
            task_cursor = await conn.execute(
                "SELECT id FROM tasks WHERE id = ?",
                (plan.task_id,),
            )
            if await task_cursor.fetchone() is None:
                raise ValueError(f"Unknown task: {plan.task_id}")
            await conn.execute(
                """
                INSERT INTO plans (id, task_id, session_id, goal, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.id,
                    plan.task_id,
                    plan.session_id,
                    plan.goal,
                    plan.created_at.isoformat(),
                    plan.updated_at.isoformat(),
                ),
            )
            for node in plan.nodes:
                await conn.execute(
                    """
                    INSERT INTO task_nodes (
                        id, task_id, goal, dependencies, skills,
                        context_requirements, capability_requirements,
                        policy_requirements, executor, model, result,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.id,
                        plan.task_id,
                        node.goal,
                        json.dumps(node.dependencies),
                        json.dumps(node.skills),
                        json.dumps(node.context_requirements),
                        json.dumps(node.capability_requirements),
                        json.dumps(node.policy_requirements),
                        node.executor,
                        node.model,
                        json.dumps(node.result) if node.result else None,
                        node.status.value,
                        node.created_at.isoformat(),
                        node.updated_at.isoformat(),
                    ),
                )

    async def get_plan(self, plan_id: str) -> Plan | None:
        """Retrieve a plan by ID."""
        row = await db.fetchone("SELECT * FROM plans WHERE id = ?", (plan_id,))
        if not row:
            return None
        nodes_rows = await db.fetchall(
            "SELECT * FROM task_nodes WHERE task_id = ? ORDER BY created_at",
            (row["task_id"],),
        )
        nodes = [TaskNode.from_row(dict(r)) for r in nodes_rows]
        return Plan.from_row(dict(row), nodes)


# Initialize plans table if needed
async def ensure_plans_table() -> None:
    """Ensure the plans table exists."""
    await db.initialize()


__all__ = ["Plan", "Planner", "TaskNode", "ensure_plans_table"]
