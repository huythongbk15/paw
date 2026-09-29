"""
RuntimeOutcome task identity contract (Bước 0 repair).

``RuntimeOutcome.task_id`` was added as a *required* field, which broke every
caller that constructs an outcome directly (12 call sites raised
``TypeError: RuntimeOutcome.__init__() missing 1 required positional argument:
'task_id'``). The repair made the field defaulted for backward compatibility
while requiring every ``PawRuntime`` path to populate it.

Two properties are pinned here:

1. *Backward compatibility* — direct construction without ``task_id`` still
   works and yields the empty default.
2. *Runtime completeness* — every terminal ``PawRuntime.run`` path carries the
   real durable task identity, so ``/why``/``/ledger``/TUI projections can join
   an outcome to its task without extra plumbing.

A defaulted field can hide a *new* caller forgetting to pass it, so property 2
is asserted per terminal path rather than trusted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from paw.core.autonomy import (
    AutonomyBudget,
    AutonomyController,
    AutonomyDecision,
    StopReason,
)
from paw.core.models import (
    Capability,
    ExecutionObservation,
    ProposedAction,
    ResourceUsage,
)
from paw.core.planner import Plan
from paw.core.runtime import PawRuntime, RuntimeOutcome
from paw.core.storage import db


class _Verdict:
    def __init__(self, verdict: str, stop_reason: StopReason | None):
        self.verdict = verdict
        self.stop_reason = stop_reason


class _Guard:
    """Fake policy guard so the loop contract stays isolated from the DB."""

    def __init__(self, verdict: str = "go"):
        self.verdict = verdict

    async def evaluate_request(self, capabilities, context=None, task_id=None):
        if self.verdict == "block":
            return _Verdict("block", StopReason.POLICY_DENIED)
        if self.verdict == "ask":
            return _Verdict("ask", StopReason.POLICY_ASK_REQUIRED)
        return _Verdict("go", None)


async def _insert_task(task_id: str, goal: str = "goal") -> None:
    now = datetime.now(UTC).isoformat()
    await db.execute(
        """INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (task_id, "s1", goal, "pending", now, now),
    )


def _step(observation: ExecutionObservation):
    async def _run(task_id: str, action: Any) -> ExecutionObservation:
        return observation

    return _run


def _obs(*, done: bool, success: bool = True, error: str | None = None):
    return ExecutionObservation(
        step_id="s1",
        action_id="op_1",
        result={"done": done, "progress": 1.0 if done else 0.0},
        resources_used=ResourceUsage(model_calls=1, tokens=100),
        success=success,
        error=error,
    )


# ── 1. Backward compatibility ───────────────────────────────────────────


def test_outcome_can_be_constructed_without_task_id():
    """A defaulted field must keep direct construction working (the Bước 0 defect)."""
    outcome = RuntimeOutcome(stopped=True, reason=None, step_called=False)

    assert outcome.task_id == ""
    assert outcome.stopped is True


def test_task_id_is_not_positional_only():
    """Field order moved so the required fields stay first; keywords must work."""
    outcome = RuntimeOutcome(
        stopped=False,
        reason=StopReason.MAX_ITERATIONS_REACHED,
        step_called=True,
        task_id="t-explicit",
        iterations=3,
    )

    assert outcome.task_id == "t-explicit"
    assert outcome.iterations == 3


def test_to_answer_contract_is_unaffected_by_task_id():
    """``to_answer()`` is the CLI/TUI payload; adding ``task_id`` must not alter it.

    Note: ``task_id`` is intentionally NOT part of the answer dict. The CLI and
    TUI already own the task id from their own session scope, so exposing it
    twice would create a second source of identity. This test pins that the
    documented keys survive the field addition.
    """
    outcome = RuntimeOutcome(
        stopped=True, reason=None, step_called=False, task_id="t-answer"
    )

    answer = outcome.to_answer()

    assert set(answer) == {
        "stopped",
        "stop_reason",
        "steps",
        "operations_completed",
        "model_selections",
        "skills_used",
        "evidence",
        "uncertainty",
        "next_action",
        "reasoning",
    }
    assert answer["stopped"] is True


# ── 2. Runtime completeness ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_completion_path_populates_task_id():
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard("go")))
    await _insert_task("t-complete")

    outcome = await runtime.run(
        "t-complete",
        task_goal="finish",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(_obs(done=True)),
    )

    assert outcome.reason == StopReason.TASK_COMPLETED
    assert outcome.decision == AutonomyDecision.STOP_SUCCESS
    assert outcome.task_id == "t-complete"


@pytest.mark.asyncio
async def test_policy_denied_path_populates_task_id():
    """The gate stops before any step; the outcome must still identify the task."""
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard("block")))
    await _insert_task("t-denied")

    outcome = await runtime.run(
        "t-denied",
        task_goal="denied goal",
        initial_context={},
        available_skills=[{"name": "secret", "required_capabilities": ["secrets.read"]}],
        step_fn=_step(_obs(done=True)),
    )

    assert outcome.stopped is True
    assert outcome.reason == StopReason.POLICY_DENIED
    assert outcome.step_called is False
    assert outcome.task_id == "t-denied"


@pytest.mark.asyncio
async def test_policy_ask_path_populates_task_id():
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard("ask")))
    await _insert_task("t-ask")

    outcome = await runtime.run(
        "t-ask",
        task_goal="ask goal",
        initial_context={},
        available_skills=[{"name": "write", "required_capabilities": ["filesystem.write"]}],
        step_fn=_step(_obs(done=True)),
    )

    assert outcome.waiting_for_approval is True
    assert outcome.reason == StopReason.POLICY_ASK_REQUIRED
    assert outcome.task_id == "t-ask"


@pytest.mark.asyncio
async def test_failure_path_populates_task_id():
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard("go")))
    await _insert_task("t-failed")

    outcome = await runtime.run(
        "t-failed",
        task_goal="fail goal",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(_obs(done=False, success=False, error="boom")),
    )

    assert outcome.reason == StopReason.TASK_FAILED
    assert outcome.task_id == "t-failed"


@pytest.mark.asyncio
async def test_max_iterations_path_populates_task_id():
    """The hard iteration bound is a terminal path too, and must identify the task."""
    runtime = PawRuntime(
        AutonomyController(
            policy_guard=_Guard("go"),
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
        )
    )
    await _insert_task("t-maxiter")

    outcome = await runtime.run(
        "t-maxiter",
        task_goal="loop forever",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(_obs(done=False)),
    )

    assert outcome.stopped is True
    assert outcome.task_id == "t-maxiter"


@pytest.mark.asyncio
async def test_effect_constraint_denied_path_populates_task_id():
    """E2-46: a capability outside the plan's effect constraints is denied.

    Driven through ``_gate_action`` directly, matching the established pattern
    in ``tests/test_e2_46_effect_constraints_runtime.py``: the constraint check
    is an internal gate branch, and reaching it through the public loop would
    require a plan-aware proposal the simple loop cannot express.
    """
    runtime = PawRuntime(
        AutonomyController(AutonomyBudget(max_model_calls=1, max_iterations=3), policy_guard=_Guard("go")),
        plan=Plan(goal="test", effect_constraints=[]),
    )
    proposed = ProposedAction(
        goal="test",
        capabilities=[Capability.MODEL_INFERENCE],
        context={},
        estimated_cost=ResourceUsage(),
        effect_constraints=[Capability.FILESYSTEM_WRITE],
        plan_purpose="implementation",
    )

    outcome = await runtime._gate_action("task-constrained", proposed, 0)

    assert outcome is not None
    assert outcome.stopped is True
    assert outcome.step_called is False
    assert outcome.reason == StopReason.POLICY_DENIED
    assert outcome.task_id == "task-constrained"
