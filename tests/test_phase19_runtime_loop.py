"""
PAW Phase 19 — #1 / #8 Runtime Loop hardening (black-box).

#1: The runtime loop must consult Policy + Autonomy for the PROPOSED action's
    capabilities BEFORE executing any step (``step_fn`` is never called when
    the gate blocks/asks).
#8: A black-box integration test calls ``PawRuntime.run`` (the unified loop
    entry) and asserts high-level outcomes — it does NOT re-orchestrate the
    subsystems inside the test.

Uses a fake policy guard (no DB dependency) so the loop contract is isolated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from paw.core.autonomy import AutonomyController, AutonomyDecision, AutonomyBudget, StopReason
from paw.core.models import Capability, ExecutionObservation, ResourceUsage
from paw.core.runtime import PawRuntime
from paw.core.storage import db


class _Verdict:
    def __init__(self, verdict: str, stop_reason: StopReason | None):
        self.verdict = verdict
        self.stop_reason = stop_reason


class RecordingPolicyGuard:
    """Fake policy guard: records evaluate_request calls, returns a verdict."""

    def __init__(self, verdict: str = "go"):
        self.calls: list[dict[str, Any]] = []
        self.verdict = verdict

    async def evaluate_request(self, capabilities, context=None, task_id=None):
        self.calls.append({"capabilities": list(capabilities), "task_id": task_id})
        if self.verdict == "block":
            return _Verdict("block", StopReason.POLICY_DENIED)
        if self.verdict == "ask":
            return _Verdict("ask", StopReason.POLICY_ASK_REQUIRED)
        return _Verdict("go", None)


def _spy_step(record: list, done_on_call: int = 1) -> Any:
    counter = {"n": 0}
    async def _step(task_id: str, action: Any):
        counter["n"] += 1
        record.append(action)
        if counter["n"] >= done_on_call:
            return ExecutionObservation(
                step_id=f"step_{counter['n']}",
                action_id=action.operation_id if hasattr(action, 'operation_id') else "op_1",
                result={"done": True, "progress": 1.0},
                resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
                success=True,
            )
        return ExecutionObservation(
            step_id=f"step_{counter['n']}",
            action_id=action.operation_id if hasattr(action, 'operation_id') else "op_1",
            result={"done": False, "progress": 0.0},
            resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
            success=True,
        )
    return _step


async def _insert_task(task_id: str, goal: str):
    """Insert a task into the tasks table to satisfy FK constraint."""
    await db.execute(
        """INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (task_id, "s1", goal, "pending", datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat())
    )


@pytest.mark.asyncio
async def test_runtime_gates_policy_before_step_and_passes_proposed_caps():
    guard = RecordingPolicyGuard(verdict="block")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac)

    await _insert_task("t1", "read secret")

    called: list = []
    outcome = await runtime.run(
        "t1",
        task_goal="read secret",
        initial_context={},
        available_skills=[{"name": "read_secret", "required_capabilities": ["secrets.read"]}],
        step_fn=_spy_step(called),
    )

    # Policy was consulted with the PROPOSED action's capabilities, before step.
    assert guard.calls == [
        {"capabilities": [Capability.SECRETS_READ], "task_id": "t1"}
    ]
    # Gate stopped the loop: step_fn was NEVER executed.
    assert outcome.step_called is False
    assert outcome.stopped is True
    assert outcome.reason == StopReason.POLICY_DENIED
    assert called == []


@pytest.mark.asyncio
async def test_runtime_ask_stops_before_step():
    guard = RecordingPolicyGuard(verdict="ask")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac)

    await _insert_task("t1", "x")

    called: list = []
    outcome = await runtime.run(
        "t1",
        task_goal="x",
        initial_context={},
        available_skills=[{"name": "read_file", "required_capabilities": ["filesystem.read"]}],
        step_fn=_spy_step(called),
    )

    assert outcome.step_called is False
    assert outcome.stopped is True
    assert outcome.waiting_for_approval is True
    assert outcome.reason == StopReason.POLICY_ASK_REQUIRED
    assert called == []


@pytest.mark.asyncio
async def test_runtime_executes_step_when_allowed_and_completes():
    guard = RecordingPolicyGuard(verdict="go")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac)

    await _insert_task("t1", "summarize")

    called: list = []
    outcome = await runtime.run(
        "t1",
        task_goal="summarize",
        initial_context={},
        available_skills=[{"name": "summarize", "required_capabilities": ["filesystem.read"]}],
        step_fn=_spy_step(called),
    )

    # Allowed -> step executed exactly once, then completion.
    assert outcome.step_called is True
    assert outcome.reason == StopReason.TASK_COMPLETED
    assert outcome.decision == AutonomyDecision.STOP_SUCCESS
    assert len(called) == 1
    # Policy gate received the proposed capabilities.
    assert guard.calls[0]["capabilities"] == [Capability.FILESYSTEM_READ]


@pytest.mark.asyncio
async def test_runtime_loops_until_completion_across_multiple_steps():
    guard = RecordingPolicyGuard(verdict="go")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac)

    await _insert_task("t1", "multi-step task")

    counter = {"n": 0}

    async def _step(task_id: str, action: Any):
        counter["n"] += 1
        if counter["n"] < 3:
            return ExecutionObservation(
                step_id=f"step_{counter['n']}",
                action_id=action.operation_id if hasattr(action, 'operation_id') else "op_1",
                result={"progress": counter["n"] / 3.0},
                resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
                success=True,
            )
        return ExecutionObservation(
            step_id=f"step_{counter['n']}",
            action_id=action.operation_id if hasattr(action, 'operation_id') else "op_1",
            result={"done": True, "progress": 1.0},
            resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
            success=True,
        )

    outcome = await runtime.run(
        "t1",
        task_goal="multi-step task",
        initial_context={},
        available_skills=[],
        step_fn=_step,
    )
    assert outcome.step_called is True
    assert counter["n"] == 3
    assert outcome.reason == StopReason.TASK_COMPLETED
    assert outcome.decision == AutonomyDecision.STOP_SUCCESS


@pytest.mark.asyncio
async def test_runtime_hard_iteration_bound_stops_loop():
    guard = RecordingPolicyGuard(verdict="go")
    ac = AutonomyController(
        budget=AutonomyBudget(max_iterations=3, max_decisions=10),
        policy_guard=guard,
    )
    runtime = PawRuntime(ac, max_iterations=3)

    await _insert_task("t1", "never completes")

    counter = {"n": 0}

    async def _step(task_id: str, action: Any):
        counter["n"] += 1
        return ExecutionObservation(
            step_id=f"step_{counter['n']}",
            action_id=action.operation_id if hasattr(action, 'operation_id') else "op_1",
            result={"progress": 0.0},  # never completes
            resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
            success=True,
        )

    outcome = await runtime.run(
        "t1",
        task_goal="never completes",
        initial_context={},
        available_skills=[],
        step_fn=_step,
    )
    assert outcome.step_called is True
    assert counter["n"] == 3
    assert outcome.reason == StopReason.MAX_ITERATIONS_REACHED


@pytest.mark.asyncio
async def test_runtime_emits_stop_success_on_completion():
    """#7: completion yields a deterministic STOP_SUCCESS (not ambiguous STOP)."""
    guard = RecordingPolicyGuard(verdict="go")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac)

    await _insert_task("t1", "finish")

    called: list = []
    outcome = await runtime.run(
        "t1",
        task_goal="finish",
        initial_context={},
        available_skills=[{"name": "finish", "required_capabilities": ["filesystem.read"]}],
        step_fn=_spy_step(called),
    )

    assert outcome.stopped is True
    assert outcome.step_called is True
    assert outcome.reason == StopReason.TASK_COMPLETED
    assert outcome.decision == AutonomyDecision.STOP_SUCCESS
    assert outcome.waiting_for_approval is False
    assert len(called) == 1


@pytest.mark.asyncio
async def test_autonomy_mark_complete_is_stop_success():
    """#7: mark_complete is a deterministic successful stop, budget-independent."""
    ac = AutonomyController()  # default budget
    # Exhaust the decision budget to prove completion overrides it.
    for _ in range(ac.budget.max_decisions + 5):
        ac.usage.record_decision()
    decision, stop = await ac.mark_complete()
    assert decision == AutonomyDecision.STOP_SUCCESS
    assert stop == StopReason.TASK_COMPLETED