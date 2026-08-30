"""
PAW Core — Autonomy Controller (Phase 10)

Manages autonomy budget, tracks usage, enforces limits, and provides
typed autonomy decisions with StopReason classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from .ledger import TaskEventType, TaskLedger
from .logging import get_logger

if TYPE_CHECKING:
    from .detectors import ProgressDetector, RepetitionDetector, StallDetector
    from .execution_profile import ExecutionProfile
    from .models import Capability
    from .policy import PolicyGuard

logger = get_logger(__name__)


# --- Autonomy Profiles ---

class AutonomyProfile(StrEnum):
    """Predefined autonomy profiles."""
    CONSERVATIVE = "conservative"      # Low budget, frequent ASK
    BALANCED = "balanced"              # Moderate budget, some ASK
    AGGRESSIVE = "aggressive"          # High budget, minimal ASK
    FULL_AUTO = "full_auto"            # Maximum budget, no ASK
    INTERACTIVE = "interactive"        # Session-aware, adaptive


@dataclass
class AutonomyBudget:
    """
    Budget for autonomous execution. Mirrors ContextBudget but for decisions/actions.

    All limits are HARD constraints — exceeding any limit forces STOP.
    """
    # Decision budget
    max_decisions: int = 50              # Max autonomous decisions (tool calls, model calls)
    max_model_calls: int = 20            # Max LLM calls
    max_tool_calls: int = 30             # Max tool invocations
    max_total_tokens: int = 100000       # Total tokens across all calls

    # Time budget
    max_wall_time_seconds: int = 300     # Hard wall-clock limit
    max_idle_seconds: int = 60           # Max time without progress

    # Loop budget
    max_iterations: int = 20             # Hard iteration limit (never exceeded)
    max_retries_per_step: int = 3        # Max retries for failed steps

    # Progress budget
    min_progress_per_iteration: float = 0.05  # Minimum progress ratio per iteration

    # Profile-based defaults
    @classmethod
    def from_profile(cls, profile: AutonomyProfile) -> AutonomyBudget:
        """Create budget from predefined profile."""
        profiles = {
            AutonomyProfile.CONSERVATIVE: cls(
                max_decisions=20,
                max_model_calls=5,
                max_tool_calls=10,
                max_total_tokens=25000,
                max_wall_time_seconds=120,
                max_iterations=10,
                max_retries_per_step=1,
                min_progress_per_iteration=0.1,
            ),
            AutonomyProfile.BALANCED: cls(
                max_decisions=50,
                max_model_calls=15,
                max_tool_calls=25,
                max_total_tokens=75000,
                max_wall_time_seconds=300,
                max_iterations=20,
                max_retries_per_step=2,
                min_progress_per_iteration=0.05,
            ),
            AutonomyProfile.AGGRESSIVE: cls(
                max_decisions=100,
                max_model_calls=30,
                max_tool_calls=60,
                max_total_tokens=150000,
                max_wall_time_seconds=600,
                max_iterations=40,
                max_retries_per_step=3,
                min_progress_per_iteration=0.03,
            ),
            AutonomyProfile.FULL_AUTO: cls(
                max_decisions=200,
                max_model_calls=50,
                max_tool_calls=100,
                max_total_tokens=300000,
                max_wall_time_seconds=1800,
                max_iterations=100,
                max_retries_per_step=5,
                min_progress_per_iteration=0.01,
            ),
            AutonomyProfile.INTERACTIVE: cls(
                max_decisions=30,
                max_model_calls=10,
                max_tool_calls=15,
                max_total_tokens=50000,
                max_wall_time_seconds=180,
                max_iterations=15,
                max_retries_per_step=2,
                min_progress_per_iteration=0.08,
            ),
        }
        return profiles[profile]


@dataclass
class AutonomyUsage:
    """Tracks consumption of autonomy budget."""
    decisions: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    total_tokens: int = 0
    wall_time_seconds: float = 0.0
    idle_time_seconds: float = 0.0
    iterations: int = 0
    retries: int = 0
    progress_history: list[float] = field(default_factory=list)
    last_progress_ratio: float = 0.0
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))

    def record_decision(self, tokens: int = 0) -> None:
        self.decisions += 1
        self.total_tokens += tokens
        self.last_activity = datetime.now(UTC)

    def record_model_call(self, tokens: int = 0) -> None:
        self.model_calls += 1
        self.total_tokens += tokens
        self.last_activity = datetime.now(UTC)

    def record_tool_call(self, tokens: int = 0) -> None:
        self.tool_calls += 1
        self.total_tokens += tokens
        self.last_activity = datetime.now(UTC)

    def record_iteration(self, progress_ratio: float) -> None:
        self.iterations += 1
        self.progress_history.append(progress_ratio)
        self.last_progress_ratio = progress_ratio
        self.last_activity = datetime.now(UTC)

    def record_retry(self) -> None:
        self.retries += 1

    def update_wall_time(self) -> None:
        now = datetime.now(UTC)
        self.wall_time_seconds = (now - self.start_time).total_seconds()
        self.idle_time_seconds = (now - self.last_activity).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": self.decisions,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "total_tokens": self.total_tokens,
            "wall_time_seconds": self.wall_time_seconds,
            "idle_time_seconds": self.idle_time_seconds,
            "iterations": self.iterations,
            "retries": self.retries,
            "progress_history": self.progress_history,
            "last_progress_ratio": self.last_progress_ratio,
        }


# --- Autonomy Decisions ---

class AutonomyDecision(StrEnum):
    """Typed autonomy decisions - replaces generic allow/deny."""
    CONTINUE = "continue"              # Proceed with autonomous execution
    PAUSE = "pause"                    # Pause and wait for user input
    ASK = "ask"                        # Request user clarification/approval
    ESCALATE = "escalate"              # Escalate to higher authority/review
    DELEGATE = "delegate"              # Delegate to another agent/executor
    STOP = "stop"                      # Hard stop - budget exhausted or error
    STOP_SUCCESS = "stop_success"      # Task completed successfully (terminal)


class StopReason(StrEnum):
    """Classified reasons for stopping autonomous execution."""
    # Budget exhaustion
    BUDGET_DECISIONS_EXHAUSTED = "budget_decisions_exhausted"
    BUDGET_MODEL_CALLS_EXHAUSTED = "budget_model_calls_exhausted"
    BUDGET_TOOL_CALLS_EXHAUSTED = "budget_tool_calls_exhausted"
    BUDGET_TOKENS_EXHAUSTED = "budget_tokens_exhausted"
    BUDGET_WALL_TIME_EXHAUSTED = "budget_wall_time_exhausted"

    # Loop limits
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"

    # Progress issues
    STALLED = "stalled"
    INSUFFICIENT_PROGRESS = "insufficient_progress"
    REPETITION_DETECTED = "repetition_detected"

    # Policy/Safety
    POLICY_DENIED = "policy_denied"
    POLICY_ASK_REQUIRED = "policy_ask_required"
    SAFETY_VIOLATION = "safety_violation"

    # Task completion
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    USER_CANCELLED = "user_cancelled"

    # External
    EXTERNAL_INTERRUPT = "external_interrupt"
    UNKNOWN = "unknown"


# --- Autonomy Controller ---

class AutonomyController:
    """
    Central controller for autonomous execution.

    Tracks budget, detects progress/repetition/stall, makes typed decisions.
    Integrates with ContextCompiler, ProgressDetector, RepetitionDetector, StallDetector.
    """

    def __init__(
        self,
        budget: AutonomyBudget | None = None,
        profile: AutonomyProfile = AutonomyProfile.BALANCED,
        progress_detector: ProgressDetector | None = None,
        repetition_detector: RepetitionDetector | None = None,
        stall_detector: StallDetector | None = None,
        execution_profile: ExecutionProfile | None = None,
        policy_guard: PolicyGuard | None = None,
    ):
        # ExecutionProfile takes precedence if provided
        if execution_profile is not None:
            self.budget = execution_profile.resolved_autonomy_budget()
            self.profile = execution_profile.autonomy_profile
        else:
            self.budget = budget or AutonomyBudget.from_profile(profile)
            self.profile = profile

        self.usage = AutonomyUsage()

        # Detectors (injected for testability)
        self.progress_detector = progress_detector
        self.repetition_detector = repetition_detector
        self.stall_detector = stall_detector

        # Policy guard — single authority consulted before any side effect.
        # Optional; when None the loop does not gate on policy (legacy behavior).
        self.policy_guard = policy_guard

        # State
        self._decision_history: list[dict[str, Any]] = []
        self._stop_reason: StopReason | None = None
        self.execution_profile = execution_profile

    async def check_budget(self) -> tuple[bool, StopReason | None]:
        """
        Check if budget allows continued execution.

        Returns: (allowed, stop_reason_if_denied)
        """
        self.usage.update_wall_time()

        # Hard iteration limit - never exceed
        if self.usage.iterations >= self.budget.max_iterations:
            return False, StopReason.MAX_ITERATIONS_REACHED

        # Decision budget
        if self.usage.decisions >= self.budget.max_decisions:
            return False, StopReason.BUDGET_DECISIONS_EXHAUSTED

        if self.usage.model_calls >= self.budget.max_model_calls:
            return False, StopReason.BUDGET_MODEL_CALLS_EXHAUSTED

        if self.usage.tool_calls >= self.budget.max_tool_calls:
            return False, StopReason.BUDGET_TOOL_CALLS_EXHAUSTED

        if self.usage.total_tokens >= self.budget.max_total_tokens:
            return False, StopReason.BUDGET_TOKENS_EXHAUSTED

        if self.usage.wall_time_seconds >= self.budget.max_wall_time_seconds:
            return False, StopReason.BUDGET_WALL_TIME_EXHAUSTED

        if self.usage.idle_time_seconds >= self.budget.max_idle_seconds:
            return False, StopReason.BUDGET_WALL_TIME_EXHAUSTED

        return True, None

    async def decide(
        self,
        task_id: str,
        context: dict[str, Any] | None = None,
        required_capabilities: list[ Capability] | None = None,
    ) -> tuple[AutonomyDecision, StopReason | None]:
        """
        Main decision point for autonomous execution.

        Evaluates policy, budget, progress, repetition, and stall (in that
        order). Policy is consulted FIRST: it is the single authority and a
        capability that is DENY / ASK (non-interactive) must stop the loop
        before any side effect — ASK never maps to execution.

        ``required_capabilities`` carries the capabilities the next action (the
        selected skill / executor) will need. When omitted the loop does not
        gate on policy (legacy behavior / pure budget-driven control).
        """
        # 0. Policy gate — single authority, fail-closed, before any side effect
        if self.policy_guard is not None and required_capabilities:
            verdict = await self.policy_guard.evaluate_request(
                required_capabilities, context or {}, task_id=task_id
            )
            if verdict.verdict == "block":
                self._stop_reason = verdict.stop_reason
                # Both hard DENY and non-interactive ASK halt the loop — ASK
                # never maps to execution (constitution: ASK = STOP, never run).
                return AutonomyDecision.STOP, verdict.stop_reason
            if verdict.verdict == "ask":
                # Interactive ASK: pause the loop and surface the request
                self._stop_reason = StopReason.POLICY_ASK_REQUIRED
                return AutonomyDecision.ASK, StopReason.POLICY_ASK_REQUIRED

        # 1. Check hard budget
        allowed, stop_reason = await self.check_budget()
        if not allowed:
            self._stop_reason = stop_reason
            return AutonomyDecision.STOP, stop_reason

        # 2. Check progress
        if self.progress_detector:
            progress_ok, progress_reason = await self.progress_detector.check(
                task_id, self.usage.last_progress_ratio
            )
            if not progress_ok:
                self._stop_reason = progress_reason
                return self._map_progress_reason(progress_reason), progress_reason

        # 3. Check repetition
        if self.repetition_detector:
            repeated, rep_reason = await self.repetition_detector.check(task_id, context)
            if repeated:
                self._stop_reason = rep_reason
                return AutonomyDecision.STOP, rep_reason

        # 4. Check stall
        if self.stall_detector:
            stalled, stall_reason = await self.stall_detector.check(
                task_id, self.usage.idle_time_seconds
            )
            if stalled:
                self._stop_reason = stall_reason
                return AutonomyDecision.STOP, stall_reason

        # 5. Check if task is done (from ledger)
        # This would check if recent events indicate completion
        # For now, assume continue if budgets OK

        return AutonomyDecision.CONTINUE, None

    async def mark_complete(self) -> tuple[AutonomyDecision, StopReason]:
        """Task observed complete -> deterministic successful stop.

        Returns ``(STOP_SUCCESS, TASK_COMPLETED)``. This is distinct from
        ``STOP`` (which signals budget/safety/error): completion is a
        *successful* terminal state. Kept free of any ledger side-effect so it
        is safe to call in an offline / DB-less context; the runtime loop is
        responsible for persisting the outcome.
        """
        return AutonomyDecision.STOP_SUCCESS, StopReason.TASK_COMPLETED

    def _map_progress_reason(self, reason: StopReason) -> AutonomyDecision:
        """Map progress-related stop reason to autonomy decision."""
        mapping = {
            StopReason.STALLED: AutonomyDecision.PAUSE,
            StopReason.INSUFFICIENT_PROGRESS: AutonomyDecision.ASK,
            StopReason.REPETITION_DETECTED: AutonomyDecision.ASK,
        }
        return mapping.get(reason, AutonomyDecision.STOP)

    async def record_decision(
        self,
        decision: AutonomyDecision,
        stop_reason: StopReason | None,
        context: dict[str, Any] | None = None,
        tokens: int = 0,
    ) -> None:
        """Record a decision for audit trail."""
        self.usage.record_decision(tokens)
        self._decision_history.append({
            "timestamp": datetime.now(UTC).isoformat(),
            "decision": decision.value,
            "stop_reason": stop_reason.value if stop_reason else None,
            "context": context,
            "usage_snapshot": self.usage.to_dict(),
        })

        # Log to task ledger
        await TaskLedger.record(
            task_id=context.get("task_id", "") if context else "",
            event_type=TaskEventType.AUTONOMY_DECISION,
            payload={
                "decision": decision.value,
                "stop_reason": stop_reason.value if stop_reason else None,
                "usage": self.usage.to_dict(),
            },
        )

    async def record_model_call(self, tokens: int = 0) -> None:
        """Record an LLM call."""
        self.usage.record_model_call(tokens)

    async def record_tool_call(self, tokens: int = 0) -> None:
        """Record a tool call."""
        self.usage.record_tool_call(tokens)

    async def record_iteration(self, progress_ratio: float) -> None:
        """Record iteration progress."""
        self.usage.record_iteration(progress_ratio)

    async def record_retry(self) -> None:
        """Record a retry."""
        self.usage.record_retry()

    def get_status(self) -> dict[str, Any]:
        """Get current autonomy status."""
        self.usage.update_wall_time()
        return {
            "profile": self.profile.value,
            "budget": {
                "max_decisions": self.budget.max_decisions,
                "max_model_calls": self.budget.max_model_calls,
                "max_tool_calls": self.budget.max_tool_calls,
                "max_total_tokens": self.budget.max_total_tokens,
                "max_wall_time_seconds": self.budget.max_wall_time_seconds,
                "max_iterations": self.budget.max_iterations,
                "max_retries_per_step": self.budget.max_retries_per_step,
                "min_progress_per_iteration": self.budget.min_progress_per_iteration,
            },
            "usage": self.usage.to_dict(),
            "stop_reason": self._stop_reason.value if self._stop_reason else None,
            "decision_history": self._decision_history[-10:],  # Last 10
        }


# --- Decision Log for persistence ---

async def log_autonomy_decision(
    task_id: str,
    decision: AutonomyDecision,
    stop_reason: StopReason | None,
    usage: AutonomyUsage,
) -> None:
    """Persist autonomy decision to task ledger."""
    await TaskLedger.record(
        task_id=task_id,
        event_type=TaskEventType.AUTONOMY_DECISION,
        payload={
            "decision": decision.value,
            "stop_reason": stop_reason.value if stop_reason else None,
            "usage": usage.to_dict(),
        },
    )
