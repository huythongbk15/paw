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
from datetime import UTC, datetime
from typing import Any, ClassVar

from .logging import get_logger
from .models import (
    Capability,
    CapabilityManifest,
    CapabilityScore,
    ErrorInfo,
    TaskResult,
    Usage,
)
from .task import Task

logger = get_logger(__name__)


def _get_enforcer():
    """Lazy import to avoid circular dependency."""
    from .executor_policy import get_enforcer
    return get_enforcer()


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
    capabilities: ClassVar[list[Capability]] = []

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

        required_set = {c.value for c in required_caps}
        executor_set = {c.value for c in executor_caps}

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
        required_set = {c.value for c in required_caps}
        executor_set = {c.value for c in executor_caps}
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
    capabilities: ClassVar[list[Capability]] = [
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
            "timestamp": datetime.now(UTC).isoformat(),
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

@dataclass
class ExecutorScore:
    """Score for an executor with full identity preserved.

    Extends CapabilityScore concept with executor identity for routing decisions.
    """
    executor_id: str
    executor_name: str
    total_score: float
    capability_scores: dict[str, float]
    reason: str
    matched_capabilities: list[Capability]
    missing_capabilities: list[Capability]

    def to_capability_score(self) -> CapabilityScore:
        """Convert to CapabilityScore for backward compatibility."""
        return CapabilityScore(
            capability=self.executor_name,
            required_score=10.0,
            executor_score=self.total_score,
            matched=max(self.total_score / 10.0, 0.0),
            reason=self.reason,
        )

    def __lt__(self, other: ExecutorScore) -> bool:
        """For sorting: higher score is better."""
        return self.total_score > other.total_score


class CapabilityRouter:
    """Routes tasks to the best executor based on capability matching.

    Per prompt spec: completely separate from Model Router.
    Uses CapabilityManifest for scoring and returns both ExecutorScore (detailed)
    and CapabilityScore (compatible) formats.
    """

    def __init__(self, registry: ExecutorRegistry | None = None):
        from .executor import executor_registry
        self.registry = registry or executor_registry
        self._executor_scores: dict[str, list[ExecutorScore]] = {}
        self._capability_scores: dict[str, list[CapabilityScore]] = {}
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
        """Score all executors for a task based on capabilities.

        Returns CapabilityScore for backward compatibility.
        Use route_detailed() for full ExecutorScore with executor identity.
        """
        executors = self.registry.list()

        executor_scores: list[ExecutorScore] = []
        for executor in executors:
            score = self._score_executor_detailed(
                executor, capabilities, context_size, complexity, privacy_required
            )
            executor_scores.append(score)

        # Sort by score descending
        executor_scores.sort(reverse=True)

        # Store both formats
        self._executor_scores[task_id] = executor_scores
        capability_scores = [s.to_capability_score() for s in executor_scores]
        self._capability_scores[task_id] = capability_scores

        logger.info("capability_routed", task_id=task_id, executors=len(capability_scores))
        return capability_scores

    async def route_detailed(
        self,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
    ) -> list[ExecutorScore]:
        """Score all executors and return detailed ExecutorScore with identity."""
        await self.route(task_id, goal, capabilities, context_size, complexity, privacy_required)
        return self._executor_scores.get(task_id, [])

    def _score_executor_detailed(
        self,
        executor: Executor,
        required_capabilities: list[Capability],
        context_size: int,
        complexity: str,
        privacy_required: bool,
    ) -> ExecutorScore:
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

        capability_scores_dict: dict[str, float] = {}
        matched_capabilities: list[Capability] = []
        missing_capabilities: list[Capability] = []

        if not required_capabilities:
            # No specific capabilities required - give neutral score
            for cap in Capability:
                capability_scores_dict[cap.value] = 0.5
            avg_matched = 0.5
            reason = f"No specific capabilities required for {executor.name}; neutral score"
        else:
            for cap_score in capability_scores:
                capability_scores_dict[cap_score.capability] = cap_score.executor_score
                if cap_score.matched >= 0.8:
                    matched_capabilities.append(Capability(cap_score.capability))
                else:
                    missing_capabilities.append(Capability(cap_score.capability))

            # Average of capability scores
            if capability_scores:
                avg_matched = sum(s.matched for s in capability_scores) / len(capability_scores)
            else:
                avg_matched = 0.0

            reason = (
                f"Matched {len(matched_capabilities)}/"
                f"{len(required_capabilities)} capabilities for {executor.name}"
            )

        # Complexity factor
        complexity_factor = {"low": 1.0, "medium": 0.9, "high": 0.8}
        total_score = avg_matched * 10.0 * complexity_factor.get(complexity, 0.9)

        # Privacy factor
        if privacy_required and not self._executor_supports_privacy(executor):
            total_score *= 0.7
            reason += " (privacy penalty)"

        # Context size factor
        if context_size > 12000:
            total_score *= 0.9
            reason += " (large context penalty)"

        return ExecutorScore(
            executor_id=executor.name,  # Use name as ID since executors don't have separate ID
            executor_name=executor.name,
            total_score=max(total_score, 0.0),
            capability_scores=capability_scores_dict,
            reason=reason,
            matched_capabilities=matched_capabilities,
            missing_capabilities=missing_capabilities,
        )

    def _score_executor(
        self,
        executor: Executor,
        required_capabilities: list[Capability],
        context_size: int,
        complexity: str,
        privacy_required: bool,
    ) -> CapabilityScore:
        """Legacy method for backward compatibility - delegates to detailed."""
        detailed = self._score_executor_detailed(
            executor, required_capabilities, context_size, complexity, privacy_required
        )
        return detailed.to_capability_score()

    def _executor_supports_privacy(self, executor: Executor) -> bool:
        """Check if executor supports privacy requirements."""
        return executor.name in ("local", "mock")

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
        detailed_scores = await self.route_detailed(
            task_id, goal, capabilities, context_size, complexity, privacy_required
        )

        if not detailed_scores:
            return None, None

        best_detailed = detailed_scores[0]
        best_executor = self.registry.get(best_detailed.executor_name)
        best_cap_score = best_detailed.to_capability_score()

        return best_executor, best_cap_score

    async def best_executor_for_task(
        self,
        task: Task,
    ) -> tuple[Executor | None, CapabilityScore | None]:
        """Get the best executor for a Task object."""
        return await self.best_executor(
            task.id, task.goal, task.requested_capabilities
        )

    def get_scores(self, task_id: str) -> list[CapabilityScore] | None:
        """Retrieve scores for a task (CapabilityScore format for backward compatibility)."""
        return self._capability_scores.get(task_id)

    def get_detailed_scores(self, task_id: str) -> list[ExecutorScore] | None:
        """Retrieve detailed scores for a task (ExecutorScore format with identity)."""
        return self._executor_scores.get(task_id)


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
    enforce_policy: bool = True,
) -> ExecutorResult:
    """Execute a task with full lifecycle (route capability → execute → return result).

    Args:
        task: Task to execute
        context: Context string for the task
        capabilities: Optional capability override
        executor: Optional explicit executor (skips routing)
        enforce_policy: If True, enforce policy before execution (default True)
    """
    if capabilities:
        task.requested_capabilities = capabilities

    if executor is None:
        # Route using capability router
        cap_router = CapabilityRouter()
        _, best = await cap_router.best_executor_for_task(task)
        if best:
            executor = executor_registry.get(best.capability) or executor_registry.list()[0]
        else:
            executor = executor_registry.get("mock") or next(iter(executor_registry.list()))

    if enforce_policy:
        # Use policy enforcer (lazy import to avoid circular dependency)
        enforcer = _get_enforcer()
        check, result = await enforcer.enforce(
            executor, task.id, task.goal, task.requested_capabilities, context
        )
        if not check.allowed:
            # Return blocked result
            task_result = TaskResult(
                task_id=task.id,
                status="blocked",
                summary=f"Execution blocked by policy: {check.message}",
                error=ErrorInfo(
                    code="POLICY_BLOCKED",
                    message=check.message,
                    recoverable=False,
                ),
            )
            return ExecutorResult(
                success=False,
                error=check.message,
                task_result=task_result,
                metadata={"policy_check": check.to_dict()},
            )
        return result

    result = await executor.execute(task, context)
    return result
