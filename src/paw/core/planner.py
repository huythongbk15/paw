"""
PAW Core — Planner

Decomposes goals into task graphs (DAGs).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paw.knowledge.checksum import compute_constraint_fingerprint, compute_repo_revision

from .approval import ApprovalStore
from .decomposition import StructuredReasoner
from .logging import get_logger
from .models import Capability, TaskStatus
from .policy import PolicyGuard
from .reasoning_contracts import DecisionVersionState, ImplementationReadiness, PlanPurpose
from .repo_filter import RepoFilter
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
    # E2-45: plan purpose + effect constraints
    purpose: str = "research"  # PlanPurpose value; decomposition is not implementation authority
    effect_constraints: list[str] = field(default_factory=list)
    decision_version_id: str = ""
    project_revision: str = ""
    constraint_fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "nodes": [n.to_dict() for n in self.nodes],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "purpose": self.purpose,
            "effect_constraints": self.effect_constraints,
            "decision_version_id": self.decision_version_id,
            "project_revision": self.project_revision,
            "constraint_fingerprint": self.constraint_fingerprint,
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
            purpose=row.get("purpose", "implementation"),
            effect_constraints=json.loads(row["effect_constraints"]) if row.get("effect_constraints") else [],
            decision_version_id=row.get("decision_version_id", ""),
            project_revision=row.get("project_revision", ""),
            constraint_fingerprint=row.get("constraint_fingerprint", ""),
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

    def __init__(
        self, reasoner: StructuredReasoner | None = None, *, workspace_root: str | Path | None = None,
        hard_constraints: dict[str, Any] | None = None, repo_filter: RepoFilter | None = None,
        policy_guard: PolicyGuard | None = None,
    ):
        self.reasoner = reasoner or StructuredReasoner()
        self._workspace_root = Path(workspace_root) if workspace_root is not None else None
        self._constraint_fingerprint = compute_constraint_fingerprint(hard_constraints) if hard_constraints else ""
        self._repo_filter = repo_filter or RepoFilter.safe_default()
        self._policy_guard = policy_guard or PolicyGuard(interactive=False)

    async def plan(
        self, task_id: str, *, purpose: str = "research", decision_version_id: str = "",
    ) -> Plan:
        """Create a plan for an existing durable Task.

        Task identity, goal and session belong to ``TaskManager``. Requiring the
        canonical ID prevents Planner from inventing a parallel work identity
        or persisting caller-provided metadata that disagrees with the Task.
        """
        task = await TaskManager.get(task_id)
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        purpose = PlanPurpose(purpose).value
        plan = Plan(task_id=task.id, goal=task.goal, session_id=task.session_id,
                    purpose=purpose, decision_version_id=decision_version_id)
        if purpose == PlanPurpose.IMPLEMENTATION:
            binding = await self._decision_binding(plan)
            plan.project_revision = binding["project_revision"]
            plan.constraint_fingerprint = binding["constraint_fingerprint"]
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

    async def _decision_binding(self, plan: Plan, *, require_current: bool = True) -> dict:
        if not plan.decision_version_id:
            raise ValueError("implementation Plan requires a decision version")
        version = await db.get_decision_version(plan.decision_version_id)
        if version is None or version.state != DecisionVersionState.FINAL:
            raise ValueError("implementation decision must be FINAL")
        current = await db.get_current_decision_version(version.decision_id)
        if ((require_current and current != version)
                or version.payload.get("readiness") != ImplementationReadiness.READY):
            raise ValueError("implementation decision must be current FINAL READY")
        parent = await db.get_decision(version.decision_id)
        if parent is None or parent["task_id"] != plan.task_id or parent["session_id"] != plan.session_id:
            raise ValueError("implementation decision belongs to a different Task/session")
        if not await ApprovalStore.is_decision_reviewed(plan.task_id, version.version_id):
            raise ValueError("implementation decision requires exact recorded human review")
        return parent

    async def implementation_binding(
        self, plan_id: str, task_id: str, *, recovery: bool = False,
        effect_constraints: list[str] | None = None,
    ) -> dict[str, str]:
        """Validate persisted authority without filesystem IO or a second Policy call.

        Recovery accepts original reviewed evidence only for read-only intent
        reconciliation. Runtime, not callers, selects that branch.
        """
        plan = await self.get_plan(plan_id)
        task = await TaskManager.get(task_id)
        if (plan is None or task is None or plan.task_id != task_id
                or plan.session_id != task.session_id or plan.goal != task.goal
                or plan.purpose != "implementation"):
            raise ValueError("implementation requires a persisted matching Plan")
        if any(item not in plan.effect_constraints for item in (effect_constraints or [])):
            raise ValueError("implementation effect constraints are outside the persisted Plan")
        parent = await self._decision_binding(plan, require_current=not recovery)
        if (self._workspace_root is None or not self._constraint_fingerprint
                or plan.constraint_fingerprint != self._constraint_fingerprint
                or parent["constraint_fingerprint"] != self._constraint_fingerprint
                or not plan.project_revision or plan.project_revision != parent["project_revision"]):
            raise ValueError("implementation constraints or revision binding is missing/stale")
        return {"plan_id": plan.id, "decision_version_id": plan.decision_version_id,
                "project_revision": plan.project_revision,
                "constraint_fingerprint": plan.constraint_fingerprint}

    async def _save(self, plan: Plan) -> None:
        """Persist the plan and all nodes in one transaction."""
        async with db.transaction() as conn:
            purpose = PlanPurpose(plan.purpose)
            if purpose == PlanPurpose.IMPLEMENTATION:
                binding = await self._decision_binding(plan)
                if (not self._workspace_root or not self._constraint_fingerprint
                        or binding["constraint_fingerprint"] != self._constraint_fingerprint
                        or plan.constraint_fingerprint != self._constraint_fingerprint):
                    raise ValueError("implementation decision constraints are missing or stale")
                verdict = await self._policy_guard.evaluate_request(
                    [Capability.FILESYSTEM_READ],
                    {"path": str(self._workspace_root), "operation": "readiness.freshness"},
                    task_id=plan.task_id,
                )
                if not verdict.allowed or verdict.verdict != "go":
                    raise PermissionError("planning freshness read refused by Policy")
                actual_revision = compute_repo_revision(self._workspace_root, self._repo_filter)
                if actual_revision != binding["project_revision"] or plan.project_revision != actual_revision:
                    raise ValueError("implementation decision project revision is stale")
            task_cursor = await conn.execute(
                "SELECT id, session_id, goal FROM tasks WHERE id = ?",
                (plan.task_id,),
            )
            task = await task_cursor.fetchone()
            if task is None:
                raise ValueError(f"Unknown task: {plan.task_id}")
            if task["session_id"] != plan.session_id or task["goal"] != plan.goal:
                raise ValueError("Plan must preserve durable Task identity, session and goal")
            if any(node.task_id != plan.task_id for node in plan.nodes):
                raise ValueError("Plan nodes must preserve durable Task identity")
            await conn.execute(
                """
                INSERT INTO plans (id, task_id, session_id, goal, purpose, effect_constraints,
                                   decision_version_id, project_revision, constraint_fingerprint,
                                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.id,
                    plan.task_id,
                    plan.session_id,
                    plan.goal,
                    plan.purpose,
                    json.dumps(plan.effect_constraints),
                    plan.decision_version_id,
                    plan.project_revision,
                    plan.constraint_fingerprint,
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
