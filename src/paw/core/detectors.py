"""
PAW Core — Detectors (Phase 10)

ProgressDetector, RepetitionDetector, and StallDetector for
monitoring autonomous execution health.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .autonomy import AutonomyDecision, StopReason
from .logging import get_logger

if TYPE_CHECKING:
    from .autonomy import AutonomyController

logger = get_logger(__name__)


# --- Progress Detector ---

@dataclass
class ProgressConfig:
    """Configuration for progress detection."""
    min_progress_per_iteration: float = 0.05
    stagnation_threshold: int = 3          # Iterations without progress before STALLED
    progress_window: int = 5               # Lookback window for trend analysis
    require_monotonic: bool = False        # Require strictly increasing progress


class ProgressDetector:
    """
    Detects insufficient progress or stalling.

    Tracks progress ratio per iteration, detects stagnation,
    and classifies as STALLED or INSUFFICIENT_PROGRESS.
    """

    def __init__(self, config: ProgressConfig | None = None):
        self.config = config or ProgressConfig()
        self._progress_history: list[float] = []
        self._stagnation_count = 0
        self._last_significant_progress = 0.0

    async def check(
        self,
        task_id: str,
        current_progress: float,
    ) -> tuple[bool, StopReason | None]:
        """
        Check if progress is sufficient.

        Returns: (continue_allowed, stop_reason_if_not)
        """
        self._progress_history.append(current_progress)

        # Keep only window
        if len(self._progress_history) > self.config.progress_window:
            self._progress_history.pop(0)

        # Check progress delta
        if len(self._progress_history) >= 2:
            prev = self._progress_history[-2]
            delta = current_progress - prev

            if delta >= self.config.min_progress_per_iteration:
                self._stagnation_count = 0
                self._last_significant_progress = current_progress
                return True, None
            else:
                self._stagnation_count += 1

        # Check stagnation threshold
        if self._stagnation_count >= self.config.stagnation_threshold:
            logger.warning(
                "progress_stalled",
                task_id=task_id,
                progress=current_progress,
                stagnation_count=self._stagnation_count,
            )
            return False, StopReason.STALLED

        # Check insufficient progress (not quite stalled but not enough)
        if len(self._progress_history) >= 2:
            prev = self._progress_history[-2]
            delta = current_progress - prev
            if delta > 0 and delta < self.config.min_progress_per_iteration:
                return False, StopReason.INSUFFICIENT_PROGRESS

        return True, None

    def get_trend(self) -> dict[str, Any]:
        """Get progress trend analysis."""
        if not self._progress_history:
            return {"trend": "unknown", "data": []}

        if len(self._progress_history) < 2:
            return {"trend": "insufficient_data", "data": self._progress_history}

        # Linear regression slope
        n = len(self._progress_history)
        x = list(range(n))
        y = self._progress_history

        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator > 0 else 0

        if slope > 0.01:
            trend = "improving"
        elif slope < -0.01:
            trend = "degrading"
        else:
            trend = "flat"

        return {
            "trend": trend,
            "slope": slope,
            "current": self._progress_history[-1],
            "data": self._progress_history,
        }

    def reset(self) -> None:
        """Reset detector state."""
        self._progress_history.clear()
        self._stagnation_count = 0
        self._last_significant_progress = 0.0


# --- Repetition Detector ---

@dataclass
class RepetitionConfig:
    """Configuration for repetition detection."""
    max_identical_outputs: int = 3
    similarity_threshold: float = 0.9      # Cosine similarity for fuzzy matching
    window_size: int = 20                  # History window
    ngram_size: int = 3                    # N-gram for content hashing
    detect_tool_repetition: bool = True
    detect_model_repetition: bool = True
    detect_action_repetition: bool = True


class RepetitionDetector:
    """
    Detects repetitive patterns in execution.

    Tracks:
    - Identical tool outputs
    - Similar model responses
    - Repeated action sequences
    - Loop patterns
    """

    def __init__(self, config: RepetitionConfig | None = None):
        self.config = config or RepetitionConfig()
        self._output_hashes: list[str] = []
        self._action_sequence: list[str] = []
        self._tool_output_hashes: dict[str, list[str]] = {}
        self._model_response_hashes: list[str] = []

    def _hash_content(self, content: str) -> str:
        """Create hash of content for comparison."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _hash_action(self, action: str, params: dict[str, Any]) -> str:
        """Create hash of action + key params."""
        key = f"{action}:{json.dumps(params, sort_keys=True)}"
        return self._hash_content(key)

    async def check(
        self,
        task_id: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, StopReason | None]:
        """
        Check for repetitive patterns.

        Returns: (repetition_detected, stop_reason_if_detected)
        """
        if not context:
            return False, None

        # Check tool output repetition
        if self.config.detect_tool_repetition:
            tool_output = context.get("tool_output")
            tool_name = context.get("tool_name")
            if tool_output and tool_name:
                output_hash = self._hash_content(str(tool_output))
                history = self._tool_output_hashes.setdefault(tool_name, [])
                history.append(output_hash)

                # Count recent identical outputs
                count = sum(1 for h in history[-self.config.max_identical_outputs:] if h == output_hash)
                if count >= self.config.max_identical_outputs:
                    logger.warning(
                        "tool_output_repetition",
                        task_id=task_id,
                        tool=tool_name,
                        count=count,
                    )
                    return True, StopReason.REPETITION_DETECTED

        # Check model response repetition
        if self.config.detect_model_repetition:
            model_response = context.get("model_response")
            if model_response:
                response_hash = self._hash_content(str(model_response))
                self._model_response_hashes.append(response_hash)

                # Check recent identical responses
                count = sum(
                    1 for h in self._model_response_hashes[-self.config.max_identical_outputs:]
                    if h == response_hash
                )
                if count >= self.config.max_identical_outputs:
                    logger.warning(
                        "model_response_repetition",
                        task_id=task_id,
                        count=count,
                    )
                    return True, StopReason.REPETITION_DETECTED

        # Check action sequence repetition
        if self.config.detect_action_repetition:
            action = context.get("action")
            params = context.get("params", {})
            if action:
                action_hash = self._hash_action(action, params)
                self._action_sequence.append(action_hash)

                # Detect loops: look for repeating subsequences
                if len(self._action_sequence) >= 6 and self._action_sequence[-6:] == self._action_sequence[-3:] * 2:
                        logger.warning(
                            "action_loop_detected",
                            task_id=task_id,
                            cycle=self._action_sequence[-3:],
                        )
                        return True, StopReason.REPETITION_DETECTED

        return False, None

    def record_tool_output(self, tool_name: str, output: Any) -> None:
        """Record a tool output for repetition tracking."""
        output_hash = self._hash_content(str(output))
        history = self._tool_output_hashes.setdefault(tool_name, [])
        history.append(output_hash)

        # Trim history
        if len(history) > self.config.window_size:
            history[:] = history[-self.config.window_size:]

    def record_model_response(self, response: str) -> None:
        """Record a model response for repetition tracking."""
        response_hash = self._hash_content(response)
        self._model_response_hashes.append(response_hash)

        if len(self._model_response_hashes) > self.config.window_size:
            self._model_response_hashes = self._model_response_hashes[-self.config.window_size:]

    def record_action(self, action: str, params: dict[str, Any]) -> None:
        """Record an action for sequence tracking."""
        action_hash = self._hash_action(action, params)
        self._action_sequence.append(action_hash)

        if len(self._action_sequence) > self.config.window_size * 2:
            self._action_sequence = self._action_sequence[-self.config.window_size * 2:]

    def get_stats(self) -> dict[str, Any]:
        """Get repetition statistics."""
        return {
            "tool_outputs_tracked": sum(len(h) for h in self._tool_output_hashes.values()),
            "model_responses_tracked": len(self._model_response_hashes),
            "actions_tracked": len(self._action_sequence),
            "tool_output_types": list(self._tool_output_hashes.keys()),
        }

    def reset(self) -> None:
        """Reset detector state."""
        self._output_hashes.clear()
        self._action_sequence.clear()
        self._tool_output_hashes.clear()
        self._model_response_hashes.clear()


# --- Stall Detector ---

@dataclass
class StallConfig:
    """Configuration for stall detection."""
    max_idle_seconds: int = 60
    max_consecutive_errors: int = 3
    max_same_error_type: int = 3
    health_check_interval: int = 30  # seconds


class StallDetector:
    """
    Detects execution stalls.

    Monitors:
    - Idle time (no activity)
    - Consecutive errors
    - Same error type repetition
    - Heartbeat/health checks
    """

    def __init__(self, config: StallConfig | None = None):
        self.config = config or StallConfig()
        self._last_activity: datetime | None = None
        self._consecutive_errors = 0
        self._error_types: Counter = Counter()
        self._health_checks: list[dict[str, Any]] = []

    async def check(
        self,
        task_id: str,
        idle_seconds: float,
    ) -> tuple[bool, StopReason | None]:
        """
        Check for stall conditions.

        Returns: (stalled, stop_reason_if_stalled)
        """
        # Check idle time
        if idle_seconds >= self.config.max_idle_seconds:
            logger.warning(
                "stall_idle_timeout",
                task_id=task_id,
                idle_seconds=idle_seconds,
                max_allowed=self.config.max_idle_seconds,
            )
            return True, StopReason.STALLED

        # Check consecutive errors
        if self._consecutive_errors >= self.config.max_consecutive_errors:
            logger.warning(
                "stall_consecutive_errors",
                task_id=task_id,
                errors=self._consecutive_errors,
            )
            return True, StopReason.STALLED

        # Check same error type repetition
        for error_type, count in self._error_types.items():
            if count >= self.config.max_same_error_type:
                logger.warning(
                    "stall_same_error_repeated",
                    task_id=task_id,
                    error_type=error_type,
                    count=count,
                )
                return True, StopReason.STALLED

        return False, None

    def record_activity(self) -> None:
        """Record activity (resets idle timer)."""
        self._last_activity = datetime.now(UTC)

    def record_error(self, error_type: str) -> None:
        """Record an error for stall detection."""
        self._consecutive_errors += 1
        self._error_types[error_type] += 1

    def record_success(self) -> None:
        """Record success (resets error counters)."""
        self._consecutive_errors = 0
        self._error_types.clear()

    def record_health_check(self, status: dict[str, Any]) -> None:
        """Record a health check result."""
        self._health_checks.append({
            "timestamp": datetime.now(UTC).isoformat(),
            "status": status,
        })
        if len(self._health_checks) > 100:
            self._health_checks = self._health_checks[-100:]

    def get_health(self) -> dict[str, Any]:
        """Get current health status."""
        idle = 0.0
        if self._last_activity:
            idle = (datetime.now(UTC) - self._last_activity).total_seconds()

        return {
            "idle_seconds": idle,
            "consecutive_errors": self._consecutive_errors,
            "error_types": dict(self._error_types),
            "last_activity": self._last_activity.isoformat() if self._last_activity else None,
            "health_checks": self._health_checks[-10:],
        }

    def reset(self) -> None:
        """Reset detector state."""
        self._last_activity = None
        self._consecutive_errors = 0
        self._error_types.clear()
        self._health_checks.clear()


# --- Loop Controller ---

class LoopController:
    """
    Orchestrates the autonomous execution loop.

    Coordinates:
    - AutonomyController (budget & decisions)
    - ProgressDetector
    - RepetitionDetector
    - StallDetector
    - ContextCompiler (for context refresh)

    Provides the main execution loop with proper stop conditions.
    """

    def __init__(
        self,
        autonomy: AutonomyController,
        progress: ProgressDetector | None = None,
        repetition: RepetitionDetector | None = None,
        stall: StallDetector | None = None,
    ):
        self.autonomy = autonomy
        self.progress = progress
        self.repetition = repetition
        self.stall = stall

        self._running = False
        self._current_task_id: str | None = None
        self._iteration = 0

    async def run(
        self,
        task_id: str,
        step_fn,  # Callable that executes one iteration
        initial_context: dict[str, Any] | None = None,
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        """
        Run the autonomous execution loop.

        Args:
            task_id: Task identifier
            step_fn: Async function(context) -> (result, progress_ratio, next_context)
            initial_context: Initial context for first iteration
            max_iterations: Override max iterations from budget

        Returns:
            Dict with final state, stop reason, and summary
        """
        self._running = True
        self._current_task_id = task_id
        self._iteration = 0

        context = initial_context or {}
        max_iter = max_iterations or self.autonomy.budget.max_iterations

        result = {
            "status": "running",
            "iterations": 0,
            "stop_reason": None,
            "final_context": None,
            "decision_history": [],
        }

        try:
            while self._running and self._iteration < max_iter:
                self._iteration += 1

                # Execute step
                _step_result, progress_ratio, next_context = await step_fn(context)

                # Record iteration
                await self.autonomy.record_iteration(progress_ratio)

                # Check progress
                if self.progress:
                    progress_ok, progress_reason = await self.progress.check(task_id, progress_ratio)
                    if not progress_ok:
                        result["status"] = "stopped"
                        result["stop_reason"] = progress_reason.value
                        break

                # Check repetition
                if self.repetition:
                    repeated, rep_reason = await self.repetition.check(task_id, context)
                    if repeated:
                        result["status"] = "stopped"
                        result["stop_reason"] = rep_reason.value
                        break

                # Check stall
                if self.stall:
                    self.autonomy.usage.update_wall_time()
                    stalled, stall_reason = await self.stall.check(task_id, self.autonomy.usage.idle_time_seconds)
                    if stalled:
                        result["status"] = "stopped"
                        result["stop_reason"] = stall_reason.value
                        break

                # Make autonomy decision
                decision, stop_reason = await self.autonomy.decide(task_id, context)
                await self.autonomy.record_decision(decision, stop_reason, context)

                result["decision_history"].append({
                    "iteration": self._iteration,
                    "decision": decision.value,
                    "progress": progress_ratio,
                    "stop_reason": stop_reason.value if stop_reason else None,
                })

                if decision == AutonomyDecision.STOP:
                    result["status"] = "stopped"
                    result["stop_reason"] = stop_reason.value if stop_reason else "unknown"
                    break
                elif decision == AutonomyDecision.PAUSE:
                    result["status"] = "paused"
                    result["stop_reason"] = "paused_for_user"
                    break
                elif decision == AutonomyDecision.ASK:
                    result["status"] = "awaiting_input"
                    result["stop_reason"] = "ask_user"
                    break

                # Continue
                context = next_context or context
                result["final_context"] = context
                result["iterations"] = self._iteration

        except Exception as e:
            logger.error("loop_controller_error", task_id=task_id, error=str(e))
            result["status"] = "error"
            result["stop_reason"] = "exception"
            result["error"] = str(e)

        self._running = False
        return result

    def stop(self) -> None:
        """Stop the loop gracefully."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running
