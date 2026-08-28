"""
PAW Core — Executor Fabric (Phase 5)

Executor protocol, registry, capability matching, and execution lifecycle.
All executors implement the Executor protocol. MockExecutor enables E2E testing.

Per prompt spec: Model Router and Capability Router are completely separate.
This module owns the Executor protocol, ExecutorRegistry, and CapabilityRouter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .logging import get_logger
from .models import (
    Capability,
    CapabilityManifest,
    CapabilityScore,
    TaskResult,
    Usage,
)
from .task import Task

logger = get_logger(__name__)


# --- Executor Result ---

@dataclass
class ExecutorResult:
    """Standardized result from any executor."""
    success: bool
    output: Any = None
    error: str | None = None
    artifacts: list[dict] = None  # type: ignore
    metadata: dict[str, Any] = None  # type: ignore
    task_result: TaskResult | None = None

    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "artifacts": self.artifacts or [],
            "metadata": self.metadata or {},
            "task_result": self.task_result.to_dict() if self.task_result else None,
        }


# --- Executable Task Wrapper ---

@dataclass
class ExecutableTask:
    """A task wrapped for executor execution with full metadata."""
    task_id: str = ""
    goal: str = ""
    capabilities: list[Capability] = field(default_factory=list)
    context: str = ""
    model: str | None = None
    policy_check: str = "allow"  # allow, ask, deny, sandbox
    max_retries: int = 3
    timeout: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "capabilities": [c.value for c in self.capabilities],
            "context": self.context,
            "model": self.model,
            "policy_check": self.policy_check,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }


# --- Executor Protocol ---

class Executor(ABC):
    """Base protocol for all executors. Per prompt spec."""

    name: str = "base"
    capabilities: list[Capability] = []

    @abstractmethod
    async def execute(self, task: Task, context: str) -> ExecutorResult:
        """Execute the task with given context. Return structured result."""
        ...

    async def can_handle(self, task: Task) -> bool:
        """Check if this executor can handle the task's capabilities."""
        if not self.capabilities:
            return True  # No restriction — can handle anything
        task_caps = set(task.requested_capabilities)
        executor_caps = set(self.capabilities)
        return task_caps.issubset(executor_caps)

    async def estimate_cost(self, task: Task) -> float:
        """Estimate execution cost for a task."""
        return 0.0  # Default: free

    async def estimate_latency(self, task: Task) -> str:
        """Estimate latency tier for a task."""
        return "medium"


class ExecutorCapabilities:
    """Capability matching for executors."""

    @staticmethod
    def match_score(
        executor_caps: list[Capability],
        required_caps: list[Capability],
    ) -> float:
        """Calculate capability match score (0.0 to 1.0)."""
        if not required_caps:
            return 1.0  # No requirements = full match

        if not executor_caps:
            return 0.5  # No restrictions = partial match

        required_set = set(c.value for c in required_caps)
        executor_set = set(c.value for c in executor_caps)

        matched = required_set & executor_set
        if not matched:
            return 0.0

        return len(matched) / len(required_set)

    @staticmethod
    def missing_capabilities(
        executor_caps: list[Capability],
        required_caps: list[Capability],
    ) -> list[str]:
        """Find capabilities the executor is missing."""
        required_set = set(c.value for c in required_caps)
        executor_set = set(c.value for c in executor_caps)
        return sorted(required_set - executor_set)

    @staticmethod
    def can_handle(
        executor_caps: list[Capability],
        required_caps: list[Capability],
    ) -> tuple[bool, list[str]]:
        """Check if executor can handle required capabilities."""
        match = ExecutorCapabilities.match_score(executor_caps, required_caps)
        missing = ExecutorCapabilities.missing_capabilities(executor_caps, required_caps)
        return match >= 0.5, missing


# --- Mock Executor ---

class MockExecutor(Executor):
    """Mock executor for testing. Returns deterministic responses."""

    name = "mock"
    capabilities = [
        Capability.FILESYSTEM_READ,
        Capability.FILESYSTEM_WRITE,
        Capability.SHELL_EXECUTE,
    ]

    def __init__(self, predefined_responses: dict[str, ExecutorResult] | None = None):
        self.predefined_responses = predefined_responses or {}
        self.call_log: list[dict] = []
        self.execution_count = 0

    async def execute(self, task: Task, context: str) -> ExecutorResult:
        self.execution_count += 1
        self.call_log.append({
            "task_id": task.id,
            "goal": task.goal,
            "context_length": len(context),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Check for predefined response
        if task.id in self.predefined_responses:
            result = self.predefined_responses[task.id]
            logger.info("mock_executor_predefined", task_id=task.id)
            return result

        # Default: generate mock output based on goal
        output = self._generate_mock_output(task.goal)

        # Build TaskResult
        task_result = TaskResult(
            task_id=task.id,
            status="completed",
            summary=f"Mock execution of: {task.goal[:100]}",
            artifacts=[],
            decisions=[],
            evidence=[],
            files_changed=[],
            executor=self.name,
            usage=Usage(),
        )

        logger.info("mock_executed", task_id=task.id, output_length=len(output))
        return ExecutorResult(success=True, output=output, task_result=task_result, metadata={"mock": True})

    def _generate_mock_output(self, goal: str) -> str:
        """Generate a deterministic mock output based on goal."""
        goal_lower = goal.lower()

        if any(w in goal_lower for w in ["hello", "chào"]):
            return "Xin chào! Đây là mock response từ MockExecutor."
        elif any(w in goal_lower for w in ["tính", "calculate"]):
            return "Kết quả tính toán: 42"
        elif any(w in goal_lower for w in ["tóm tắt", "summary", "summarize"]):
            return "Tóm tắt: Đây là nội dung được tóm tắt bởi MockExecutor."
        elif any(w in goal_lower for w in ["tìm", "search"]):
            return "Kết quả tìm kiếm: [Mock] 3 kết quả liên quan được tìm thấy."
        elif any(w in goal_lower for w in ["viết", "write", "code"]):
            return "# Mock Code\nprint('Hello from MockExecutor')"
        elif any(w in goal_lower for w in ["phân tích", "analyze"]):
            return "Phân tích: MockExecutor đã phân tích và đưa ra kết luận mẫu."
        elif any(w in goal_lower for w in ["lập kế hoạch", "plan"]):
            return "Kế hoạch:\n1. Bước 1\n2. Bước 2\n3. Bước 3"
        else:
            return f"MockExecutor đã xử lý: {goal[:100]}..."

    async def estimate_cost(self, task: Task) -> float:
        return 0.0

    async def estimate_latency(self, task: Task) -> str:
        return "low"

    def get_call_log(self) -> list[dict]:
        return self.call_log


# --- Capability Router ---

class CapabilityRouter:
    """Routes tasks to the best executor based on capability matching.

    Per prompt spec: completely separate from Model Router.
    Uses CapabilityManifest for scoring and CapabilityScore for results.
    """

    def __init__(self, registry: "ExecutorRegistry" | None = None):
        from .executor import executor_registry
        self.registry = registry or executor_registry
        self._scores: dict[str, list[CapabilityScore]] = {}
        self._scorer = CapabilityScorer()

    async def route(
        self,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
    ) -> list[CapabilityScore]:
        """Score all executors for a task based on capabilities."""
        executors = self.registry.list()

        scores: list[CapabilityScore] = []
        for executor in executors:
            score = self._score_executor(
                executor, capabilities, context_size, complexity, privacy_required
            )
            scores.append(score)

        # Sort by score descending
        scores.sort(key=lambda s: s.matched, reverse=True)

        self._scores[task_id] = scores
        logger.info("capability_routed", task_id=task_id, executors=len(scores))
        return scores

    def _score_executor(
        self,
        executor: Executor,
        required_capabilities: list[Capability],
        context_size: int,
        complexity: str,
        privacy_required: bool,
    ) -> CapabilityScore:
        """Score an executor for a given task using CapabilityManifest."""
        cap_scorer = CapabilityScorer()

        # Build CapabilityManifest from executor
        exec_capabilities = {cap.value: 10.0 for cap in executor.capabilities}
        manifest = CapabilityManifest(
            name=executor.name,
            capabilities=exec_capabilities,
            cost={"compute": "low", "monetary": "free"},
            features={"local": True, "free": True},
        )

        # Score each capability
        capability_scores = cap_scorer.score_capabilities(manifest, required_capabilities)

        # Aggregate score
        if capability_scores:
            avg_matched = sum(s.matched for s in capability_scores) / len(capability_scores)
        else:
            avg_matched = 0.5  # No capability requirements = neutral

        # Complexity penalty
        complexity_penalty = {"low": 0.0, "medium": -0.1, "high": -0.2}
        avg_matched += complexity_penalty.get(complexity, 0.0)

        # Privacy penalty
        if privacy_required and not self._executor_supports_privacy(executor):
            avg_matched -= 0.3

        # Context size factor
        if context_size > 12000:
            avg_matched -= 0.1

        best_cap_score = capability_scores[0] if capability_scores else CapabilityScore(
            capability="*", required_score=10.0, executor_score=5.0, matched=0.5,
            reason="Default score",
        )

        return CapabilityScore(
            capability="*",
            required_score=10.0,
            executor_score=avg_matched * 10.0,
            matched=max(avg_matched, 0.0),
            reason=f"Aggregated score for {executor.name} across {len(capability_scores)} capabilities",
        )

    def _executor_supports_privacy(self, executor: Executor) -> bool:
        """Check if executor supports privacy requirements."""
        return executor.name in ("local", "mock", "opencode")

    async def best_executor(
        self,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
    ) -> tuple[Executor | None, CapabilityScore | None]:
        """Get the best executor for a task."""
        scores = await self.route(task_id, goal, capabilities, context_size, complexity, privacy_required)

        if not scores:
            return None, None

        best_score = scores[0]

        # Find the actual executor by name
        best_executor = self.registry.get(best_score.capability)
        for e in self.registry.list():
            if e.name == best_score.capability:
                best_executor = e
                break

        return best_executor, best_score

    async def best_executor_for_task(
        self,
        task: Task,
    ) -> tuple[Executor | None, CapabilityScore | None]:
        """Get the best executor for a Task object."""
        return await self.best_executor(
            task.id, task.goal, task.requested_capabilities
        )

    def get_scores(self, task_id: str) -> list[CapabilityScore] | None:
        """Retrieve scores for a task."""
        return self._scores.get(task_id)


# --- Capability Scorer ---

class CapabilityScorer:
    """Scores capabilities against executor manifests."""

    def score_capabilities(
        self,
        manifest: CapabilityManifest,
        required_capabilities: list[Capability],
    ) -> list[CapabilityScore]:
        """Score each required capability against a manifest."""
        if not required_capabilities:
            return [CapabilityScore(
                capability="*",
                required_score=0.0,
                executor_score=5.0,
                matched=0.5,
                reason="No capability requirements specified",
            )]

        scores: list[CapabilityScore] = []
        for cap in required_capabilities:
            cap_value = cap.value
            cap_score = manifest.capabilities.get(cap_value, 0.0)

            if cap_score >= 8.0:
                reason = f"Strong capability match: {cap_value} ({cap_score}/10)"
            elif cap_score >= 5.0:
                reason = f"Moderate capability match: {cap_value} ({cap_score}/10)"
            elif cap_score > 0:
                reason = f"Weak capability match: {cap_value} ({cap_score}/10)"
            else:
                reason = f"No capability match: {cap_value}"

            scores.append(CapabilityScore(
                capability=cap_value,
                required_score=10.0,
                executor_score=cap_score,
                matched=cap_score / 10.0,
                reason=reason,
            ))

        return scores


# --- Executor Registry ---

class ExecutorRegistry:
    """Registry of available executors with full lifecycle management."""

    def __init__(self):
        self._executors: dict[str, Executor] = {}
        self._capability_index: dict[str, list[str]] = {}  # capability -> executor names

    def register(self, executor: Executor) -> None:
        """Register an executor and update capability index."""
        self._executors[executor.name] = executor
        # Update capability index
        for cap in executor.capabilities:
            cap_value = cap.value
            if cap_value not in self._capability_index:
                self._capability_index[cap_value] = []
            if executor.name not in self._capability_index[cap_value]:
                self._capability_index[cap_value].append(executor.name)
        logger.info("executor_registered", name=executor.name)

    def unregister(self, name: str) -> bool:
        """Remove an executor."""
        executor = self._executors.get(name)
        if executor:
            # Remove from capability index
            for cap in executor.capabilities:
                cap_value = cap.value
                if cap_value in self._capability_index:
                    self._capability_index[cap_value] = [
                        n for n in self._capability_index[cap_value] if n != name
                    ]
            del self._executors[name]
            logger.info("executor_unregistered", name=name)
            return True
        return False

    def get(self, name: str) -> Executor | None:
        """Get an executor by name."""
        return self._executors.get(name)

    def list(self) -> list[Executor]:
        """List all registered executors."""
        return list(self._executors.values())

    def list_by_capability(self, capability: Capability) -> list[Executor]:
        """List executors supporting a specific capability."""
        cap_value = capability.value
        names = self._capability_index.get(cap_value, [])
        return [self._executors[name] for name in names if name in self._executors]

    async def find_for_task(self, task: Task) -> list[Executor]:
        """Find all executors that can handle the task."""
        result = []
        for e in self._executors.values():
            if await e.can_handle(task):
                result.append(e)
        return result

    def count(self) -> int:
        """Count registered executors."""
        return len(self._executors)

    def has_executor(self, name: str) -> bool:
        """Check if an executor is registered."""
        return name in self._executors


# Global registry
executor_registry = ExecutorRegistry()

# Register mock by default
executor_registry.register(MockExecutor())


# Global capability router
_capability_router: CapabilityRouter | None = None


def get_capability_router() -> CapabilityRouter:
    """Get global capability router."""
    global _capability_router
    if _capability_router is None:
        _capability_router = CapabilityRouter()
    return _capability_router


# --- Execute with full lifecycle ---

async def execute_task(
    task: Task,
    context: str,
    capabilities: list[Capability] | None = None,
    executor: Executor | None = None,
) -> ExecutorResult:
    """Execute a task with full lifecycle (route capability → execute → return result)."""
    if executor is None:
        # Route using capability router
        cap_router = CapabilityRouter()
        _, best = await cap_router.best_executor_for_task(task)
        if best:
            executor = executor_registry.get(best.capability) or executor_registry.list()[0]
        else:
            executor = executor_registry.get("mock") or list(executor_registry.list())[0]

    if capabilities:
        task.requested_capabilities = capabilities

    result = await executor.execute(task, context)
    return result
