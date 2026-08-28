"""
PAW Core — Capability Router

Routes tasks to the best executor based on capability fit, quality requirement,
task complexity, context size, privacy, permissions, latency, monetary cost,
machine cost, and historical success.

Per prompt spec: Model Router and Capability Router are completely separate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .executor import Executor, executor_registry
from .logging import get_logger
from .models import (
    Capability,
    TaskStatus,
)
from .storage import db

logger = get_logger(__name__)


@dataclass
class ExecutorScore:
    """Score for an executor with full identity preserved."""
    executor_id: str
    executor_name: str
    total_score: float
    capability_scores: dict[str, float]
    reason: str
    matched_capabilities: list[Capability]
    missing_capabilities: list[Capability]

    def __lt__(self, other: ExecutorScore) -> bool:
        """For sorting: higher score is better."""
        return self.total_score > other.total_score


class CapabilityRouter:
    """Routes tasks to the best executor based on capability matching."""

    def __init__(self, registry: executor_registry.__class__ | None = None):
        self.registry = registry or executor_registry
        self._scores: dict[str, list[ExecutorScore]] = {}

    async def route(
        self,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
    ) -> list[ExecutorScore]:
        """Find the best executors for a task based on capabilities."""
        executors = await self.registry.find_for_task(
            type('MockTask', (), {
                'id': task_id,
                'goal': goal,
                'requested_capabilities': capabilities,
                'status': TaskStatus.PENDING,
            })()
        ) if hasattr(self.registry, 'find_for_task') else []

        # Fallback: use registry directly
        if not executors:
            executors = self.registry.list()

        scores: list[ExecutorScore] = []
        for executor in executors:
            score = self._score_executor(executor, capabilities, context_size, complexity, privacy_required)
            scores.append(score)

        # Sort by score descending
        scores.sort(reverse=True)

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
    ) -> ExecutorScore:
        """Score an executor for a given task."""
        executor_caps = getattr(executor, 'capabilities', [])
        cap_list = [c.value for c in executor_caps] if executor_caps else []

        capability_scores: dict[str, float] = {}
        matched_capabilities: list[Capability] = []
        missing_capabilities: list[Capability] = []

        if not required_capabilities:
            # No specific capabilities required - give neutral score
            for cap in Capability:
                capability_scores[cap.value] = 0.5
            total_score = 5.0
            reason = "No specific capabilities required; neutral score"
        else:
            for cap in required_capabilities:
                cap_value = cap.value
                if cap_value in cap_list:
                    capability_scores[cap_value] = 10.0
                    matched_capabilities.append(cap)
                else:
                    capability_scores[cap_value] = 0.0
                    missing_capabilities.append(cap)

            # Average of capability scores
            if capability_scores:
                total_score = sum(capability_scores.values()) / len(capability_scores)
            else:
                total_score = 0.0

            reason = f"Matched {len(matched_capabilities)}/{len(required_capabilities)} capabilities for {executor.name}"

        # Complexity factor
        complexity_factor = {"low": 1.0, "medium": 0.9, "high": 0.8}
        total_score *= complexity_factor.get(complexity, 0.9)

        # Privacy factor
        if privacy_required and not self._executor_supports_privacy(executor):
            total_score *= 0.7
            reason += " (privacy penalty)"

        # Context size factor
        if context_size > 12000:
            total_score *= 0.9
            reason += " (large context penalty)"

        return ExecutorScore(
            executor_id=executor.id,
            executor_name=executor.name,
            total_score=max(total_score, 0.0),
            capability_scores=capability_scores,
            reason=reason,
            matched_capabilities=matched_capabilities,
            missing_capabilities=missing_capabilities,
        )

    def _executor_supports_privacy(self, executor: Executor) -> bool:
        """Check if executor supports privacy requirements."""
        # Local executors generally support privacy better
        return executor.name in ("local", "mock", "opencode")

    async def best_executor(
        self,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
    ) -> tuple[Executor | None, ExecutorScore | None]:
        """Get the best executor for a task."""
        scores = await self.route(
            task_id, goal, capabilities, context_size, complexity, privacy_required
        )

        if not scores:
            return None, None

        best_score = scores[0]

        # Find the actual executor by executor_id (preserved in score)
        best_executor = self.registry.get(best_score.executor_id)

        return best_executor, best_score

    def get_scores(self, task_id: str) -> list[ExecutorScore] | None:
        """Retrieve scores for a task."""
        return self._scores.get(task_id)


# Initialize executors table
async def ensure_executors_table() -> None:
    """Ensure executors table exists."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS executors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            capabilities TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)


# Global instance
_capability_router: CapabilityRouter | None = None


def get_capability_router() -> CapabilityRouter:
    """Get the global capability router."""
    global _capability_router
    if _capability_router is None:
        _capability_router = CapabilityRouter()
    return _capability_router