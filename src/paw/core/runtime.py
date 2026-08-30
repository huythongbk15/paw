"""
PAW Core — Runtime Loop (Phase 19, #1 / #8)

Unified black-box execution entry point.

``PawRuntime.run`` drives the autonomy loop. It is the ONE place the whole
runtime loop is orchestrated, so integration tests call ``run`` as a black
box instead of re-implementing the loop and asserting on every subsystem.

Loop contract (per the PAW constitution):
  * The single policy authority is consulted — together with the autonomy
    controller — for the PROPOSED action's capabilities, BEFORE any side
    effect. ``ASK``/``DENY`` never map to execution.
  * Only when the gate returns ``CONTINUE`` is the injected ``step_fn``
    invoked with the proposed action.
  * The observation returned by ``step_fn`` drives progress tracking and
    completion detection; completion stops the loop with ``TASK_COMPLETED``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .autonomy import AutonomyController, AutonomyDecision, StopReason
from .logging import get_logger
from .models import Capability

logger = get_logger(__name__)


@dataclass
class ProposedAction:
    """What the runtime intends to do next, including the capabilities it needs."""

    goal: str
    capabilities: list[Capability] = field(default_factory=list)
    role: str = "fast"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeOutcome:
    """Result of a ``PawRuntime.run`` invocation."""

    stopped: bool
    reason: StopReason | str | None
    step_called: bool
    iterations: int = 0
    waiting_for_approval: bool = False
    last_observation: Any = None


# A step function receives the task id and the proposed action and returns an
# observation. Returning a mapping with ``done: True`` (or an object whose
# ``done`` attribute is True) signals task completion.
StepFn = Callable[[str, ProposedAction], Awaitable[Any]]


class PawRuntime:
    """Black-box runtime loop.

    Per iteration:
      1. Policy + autonomy gate via ``AutonomyController.decide`` using the
         proposed action's ``capabilities``. This is the single authority and
         runs BEFORE any step.
      2. STOP / ASK / PAUSE / ESCALATE / DELEGATE -> return without calling
         ``step_fn`` (the loop never executes a gated-out action).
      3. CONTINUE -> invoke ``step_fn`` once, observe, record progress.
      4. Observation signals completion -> stop with ``TASK_COMPLETED``.
    """

    def __init__(self, autonomy: AutonomyController, *, max_iterations: int | None = None):
        self.autonomy = autonomy
        self._max_iterations = max_iterations

    async def run(
        self,
        task_id: str,
        *,
        proposed_action: ProposedAction,
        step_fn: StepFn,
        initial_progress: float = 0.0,
    ) -> RuntimeOutcome:
        step_called = False
        max_iter = self._max_iterations or self.autonomy.budget.max_iterations

        for i in range(max_iter):
            # STEP 0 (single authority): policy + autonomy gate on the PROPOSED
            # action's capabilities, BEFORE any execution. This is the core of
            # #1 — the proposed action's capabilities are forwarded to the gate
            # and the step is never executed unless the gate returns CONTINUE.
            decision, stop = await self.autonomy.decide(
                task_id, required_capabilities=proposed_action.capabilities
            )

            if decision == AutonomyDecision.STOP:
                return RuntimeOutcome(
                    stopped=True,
                    reason=stop or StopReason.UNKNOWN,
                    step_called=step_called,
                    iterations=i,
                )
            if decision == AutonomyDecision.ASK:
                return RuntimeOutcome(
                    stopped=True,
                    reason=StopReason.POLICY_ASK_REQUIRED,
                    step_called=step_called,
                    iterations=i,
                    waiting_for_approval=True,
                )
            if decision in (
                AutonomyDecision.PAUSE,
                AutonomyDecision.ESCALATE,
                AutonomyDecision.DELEGATE,
            ):
                return RuntimeOutcome(
                    stopped=True,
                    reason=stop or decision.value,
                    step_called=step_called,
                    iterations=i,
                )

            # CONTINUE -> execute the proposed step exactly once this iteration.
            step_called = True
            observation = await step_fn(task_id, proposed_action)
            await self.autonomy.record_model_call()
            progress = self._progress_from_observation(observation, initial_progress)
            await self.autonomy.record_iteration(progress)

            if self._is_done(observation):
                return RuntimeOutcome(
                    stopped=True,
                    reason=StopReason.TASK_COMPLETED,
                    step_called=True,
                    iterations=i + 1,
                    last_observation=observation,
                )

        return RuntimeOutcome(
            stopped=True,
            reason=StopReason.MAX_ITERATIONS_REACHED,
            step_called=step_called,
            iterations=max_iter,
        )

    @staticmethod
    def _is_done(observation: Any) -> bool:
        if not isinstance(observation, dict):
            try:
                return observation.done is True
            except AttributeError:
                return False
        return observation.get("done") is True or observation.get("status") in (
            "completed",
            "done",
        )

    @staticmethod
    def _progress_from_observation(observation: Any, initial: float) -> float:
        if isinstance(observation, dict) and "progress" in observation:
            try:
                return float(observation["progress"])
            except (TypeError, ValueError):
                return initial
        return initial
