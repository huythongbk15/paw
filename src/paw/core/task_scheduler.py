"""
PAW Core — Task Scheduler (Phase 9)

TaskDependency, TaskGraph, TaskScheduler for managing complex task DAGs.
Per prompt spec: Task Graph first, agent swarm second.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .logging import get_logger
from .models import TaskStatus
from .planner import TaskNode
from .storage import db

logger = get_logger(__name__)


class TaskScheduleStatus(StrEnum):
    """Status of a scheduled task node."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class DependencyType(StrEnum):
    """Type of dependency between task nodes."""
    MUST_COMPLETE = "must_complete"    # Depends on completion
    MUST_START = "must_start"          # Depends on start
    PARALLEL = "parallel"              # Can run in parallel
    OPTIONAL = "optional"              # Optional dependency


@dataclass
class TaskDependency:
    """A dependency relationship between task nodes."""
    id: str = ""
    from_node_id: str = ""    # The node that must complete
    to_node_id: str = ""      # The node that depends on it
    dependency_type: str = DependencyType.MUST_COMPLETE.value
    condition: str = ""       # Optional condition
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "dependency_type": self.dependency_type,
            "condition": self.condition,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> TaskDependency:
        return cls(
            id=row["id"],
            from_node_id=row["from_node_id"],
            to_node_id=row["to_node_id"],
            dependency_type=row.get("dependency_type", DependencyType.MUST_COMPLETE.value),
            condition=row.get("condition", ""),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


@dataclass
class TaskGraph:
    """A directed acyclic graph (DAG) of task dependencies."""
    id: str = ""
    task_id: str = ""
    nodes: dict[str, TaskNode] = field(default_factory=dict)
    dependencies: list[TaskDependency] = field(default_factory=list)
    schedule_status: str = TaskScheduleStatus.PENDING.value
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "dependencies": [d.to_dict() for d in self.dependencies],
            "schedule_status": self.schedule_status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict, nodes: list[TaskNode], deps: list[TaskDependency]) -> TaskGraph:
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            nodes={n.id: n for n in nodes},
            dependencies=deps,
            schedule_status=row.get("schedule_status", TaskScheduleStatus.PENDING.value),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def add_node(self, node: TaskNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the graph."""
        if node_id in self.nodes:
            del self.nodes[node_id]
            # Remove related dependencies
            self.dependencies = [
                d for d in self.dependencies
                if d.from_node_id != node_id and d.to_node_id != node_id
            ]
            return True
        return False

    def add_dependency(self, dep: TaskDependency) -> None:
        """Add a dependency to the graph."""
        self.dependencies.append(dep)

    def get_node(self, node_id: str) -> TaskNode | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def node_count(self) -> int:
        return len(self.nodes)

    def dependency_count(self) -> int:
        return len(self.dependencies)


class TaskScheduler:
    """Schedules and executes task graphs with dependency resolution."""

    def __init__(self):
        self._graph: TaskGraph | None = None
        self._execution_order: list[str] = []
        self._execution_status: dict[str, TaskScheduleStatus] = {}

    async def build_graph(self, task_id: str, nodes: list[TaskNode]) -> TaskGraph:
        """Build a task graph from nodes."""
        graph = TaskGraph(task_id=task_id)

        # Load nodes from TaskNode list
        for node in nodes:
            graph.add_node(node)

        # Load dependencies from node dependencies
        for node in nodes:
            for dep_id in node.dependencies:
                dep = TaskDependency(
                    id=uuid.uuid4().hex[:16],
                    from_node_id=dep_id,
                    to_node_id=node.id,
                    dependency_type=DependencyType.MUST_COMPLETE.value,
                )
                graph.add_dependency(dep)

        await self._save_graph(graph)
        self._graph = graph
        logger.info("task_graph_built", task_id=task_id, nodes=len(nodes))
        return graph

    async def get_graph(self, task_id: str) -> TaskGraph | None:
        """Retrieve a task graph from database."""
        row = await db.fetchone("SELECT * FROM task_graphs WHERE task_id = ?", (task_id,))
        if not row:
            return None

        nodes_rows = await db.fetchall(
            "SELECT * FROM task_nodes WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        )
        nodes = [TaskNode.from_row(dict(r)) for r in nodes_rows]

        dep_rows = await db.fetchall(
            "SELECT * FROM task_dependencies WHERE task_id = ?",
            (task_id,),
        )
        deps = [TaskDependency.from_row(dict(r)) for r in dep_rows]

        graph = TaskGraph.from_row(dict(row), nodes, deps)
        self._graph = graph
        return graph

    async def topological_sort(self, task_id: str) -> list[TaskNode]:
        """Return nodes in topological order (dependencies first)."""
        graph = await self.get_graph(task_id)
        if not graph:
            return []

        return self._topo_sort(graph)

    def _topo_sort(self, graph: TaskGraph) -> list[TaskNode]:
        """Kahn's algorithm for topological sort."""
        visited = set()
        result: list[TaskNode] = []
        in_degree: dict[str, int] = {}
        node_map = graph.nodes

        # Initialize in-degree
        for node_id in node_map:
            in_degree[node_id] = 0

        for dep in graph.dependencies:
            if dep.to_node_id in in_degree:
                in_degree[dep.to_node_id] += 1

        # Find all nodes with in-degree 0
        queue = [node_id for node_id, deg in in_degree.items() if deg == 0]

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            result.append(node_map[node_id])

            # Reduce in-degree for dependent nodes
            for dep in graph.dependencies:
                if dep.from_node_id == node_id and dep.to_node_id in in_degree:
                    in_degree[dep.to_node_id] -= 1
                    if in_degree[dep.to_node_id] == 0:
                        queue.append(dep.to_node_id)

        # Check for cycles
        if len(result) != len(node_map):
            logger.warning("task_graph_cycle_detected", task_id=graph.task_id)
            # Return remaining nodes in arbitrary order
            remaining = [n for n in node_map.values() if n.id not in visited]
            result.extend(remaining)

        return result

    async def get_ready_nodes(self, task_id: str) -> list[TaskNode]:
        """Get nodes ready to execute (all dependencies satisfied)."""
        graph = await self.get_graph(task_id)
        if not graph:
            return []

        completed = set()
        for node_id, status in self._execution_status.items():
            if status == TaskScheduleStatus.COMPLETED:
                completed.add(node_id)

        ready = []
        for node in graph.nodes.values():
            if node.id in completed:
                continue
            if node.status == TaskStatus.COMPLETED:
                completed.add(node.id)
                continue
            # Check if all dependencies are satisfied
            all_deps_satisfied = all(
                dep.from_node_id in completed
                for dep in graph.dependencies
                if dep.to_node_id == node.id
            )
            if all_deps_satisfied:
                ready.append(node)

        return ready

    async def get_schedule_order(self, task_id: str) -> list[str]:
        """Get execution order for task graph."""
        sorted_nodes = await self.topological_sort(task_id)
        self._execution_order = [n.id for n in sorted_nodes]
        return self._execution_order

    async def detect_cycles(self, task_id: str) -> list[list[str]]:
        """Detect cycles in the task graph."""
        graph = await self.get_graph(task_id)
        if not graph:
            return []

        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node_id: str):
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            # Find all dependencies where this node is the "to" node
            # and also edges where this node is the "from" node
            for dep in graph.dependencies:
                # Edge: dep.from_node_id -> dep.to_node_id
                if dep.from_node_id == node_id and dep.to_node_id in graph.nodes:
                    neighbor = dep.to_node_id
                    if neighbor not in visited:
                        dfs(neighbor)
                    elif neighbor in rec_stack:
                        # Found cycle
                        cycle_start = path.index(neighbor)
                        cycle = [*path[cycle_start:], neighbor]
                        cycles.append(cycle)

            path.pop()
            rec_stack.discard(node_id)

        for node_id in graph.nodes:
            if node_id not in visited:
                dfs(node_id)

        return cycles

    async def estimate_parallelism(self, task_id: str) -> dict:
        """Estimate parallel execution potential."""
        sorted_nodes = await self.topological_sort(task_id)

        # Find levels (nodes at same depth can run in parallel)
        levels: dict[int, list[str]] = {}
        node_map = {n.id: n for n in sorted_nodes}
        depth: dict[str, int] = {}

        def get_depth(node_id: str) -> int:
            if node_id in depth:
                return depth[node_id]
            node = node_map.get(node_id)
            if not node:
                depth[node_id] = 0
                return 0
            # node.dependencies is list[str] (node IDs)
            deps = [dep for dep in node.dependencies if dep in node_map]
            if not deps:
                depth[node_id] = 0
            else:
                depth[node_id] = max(get_depth(d) for d in deps) + 1
            return depth[node_id]

        for node_id in node_map:
            get_depth(node_id)

        for node_id, d in depth.items():
            if d not in levels:
                levels[d] = []
            levels[d].append(node_id)

        max_parallel = max(len(nodes) for nodes in levels.values()) if levels else 1
        num_levels = len(levels)

        return {
            "task_id": task_id,
            "max_parallel": max_parallel,
            "num_levels": num_levels,
            "total_nodes": len(sorted_nodes),
            "levels": {str(k): v for k, v in levels.items()},
        }

    async def _save_graph(self, graph: TaskGraph) -> None:
        """Save graph to database."""
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO task_graphs
                (id, task_id, schedule_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    graph.id, graph.task_id, graph.schedule_status,
                    graph.created_at.isoformat(), graph.updated_at.isoformat(),
                ),
            )

            # Save nodes
            for node in graph.nodes.values():
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO task_nodes (
                        id, task_id, goal, dependencies, skills,
                        context_requirements, capability_requirements,
                        policy_requirements, executor, model, result,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.id, node.task_id, node.goal,
                        json.dumps(node.dependencies), json.dumps(node.skills),
                        json.dumps(node.context_requirements),
                        json.dumps(node.capability_requirements),
                        json.dumps(node.policy_requirements),
                        node.executor, node.model,
                        json.dumps(node.result) if node.result else None,
                        node.status.value,
                        node.created_at.isoformat(),
                        node.updated_at.isoformat(),
                    ),
                )

            # Save dependencies
            for dep in graph.dependencies:
                if not dep.id:
                    dep.id = uuid.uuid4().hex[:16]
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO task_dependencies
                    (id, task_id, from_node_id, to_node_id, dependency_type, condition, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dep.id, graph.task_id, dep.from_node_id, dep.to_node_id,
                        dep.dependency_type, dep.condition,
                        dep.created_at.isoformat(),
                    ),
                )

    async def update_node_status(self, node_id: str, status: TaskScheduleStatus) -> None:
        """Update node execution status."""
        self._execution_status[node_id] = status
        if self._graph is not None and node_id in self._graph.nodes:
            self._graph.nodes[node_id].status = TaskStatus(status.value)


# Initialize task_graphs and task_dependencies tables
async def ensure_task_scheduler_tables() -> None:
    """Ensure task graph tables exist (drop and recreate)."""
    await db.execute("DROP TABLE IF EXISTS task_dependencies")
    await db.execute("DROP TABLE IF EXISTS task_graphs")
    await db.execute("""
        CREATE TABLE task_graphs (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            schedule_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE task_dependencies (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            from_node_id TEXT NOT NULL,
            to_node_id TEXT NOT NULL,
            dependency_type TEXT NOT NULL DEFAULT 'must_complete',
            condition TEXT,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_dep_from ON task_dependencies(from_node_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_dep_to ON task_dependencies(to_node_id)")


# Global instance
_task_scheduler: TaskScheduler | None = None


def get_task_scheduler() -> TaskScheduler:
    """Get global task scheduler."""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler
