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

from typing import Any

import pytest

from paw.core.autonomy import AutonomyController, AutonomyDecision, StopReason
from paw.core.models import Capability
from paw.core.runtime import PawRuntime, ProposedAction


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


def _spy_step(record: list) -> Any:
    async def _step(task_id: str, action: ProposedAction):
        record.append(action)
        return {"done": True, "progress": 1.0}
    return _step


@pytest.mark.asyncio
async def test_runtime_gates_policy_before_step_and_passes_proposed_caps():
    guard = RecordingPolicyGuard(verdict="block")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac)

    called: list[ProposedAction] = []
    action = ProposedAction(goal="read secret", capabilities=[Capability.SECRETS_READ])
    outcome = await runtime.run("t1", proposed_action=action, step_fn=_spy_step(called))

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

    called: list[ProposedAction] = []
    action = ProposedAction(goal="x", capabilities=[Capability.FILESYSTEM_READ])
    outcome = await runtime.run("t1", proposed_action=action, step_fn=_spy_step(called))

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

    called: list[ProposedAction] = []
    action = ProposedAction(goal="summarize", capabilities=[Capability.FILESYSTEM_READ])
    outcome = await runtime.run("t1", proposed_action=action, step_fn=_spy_step(called))

    # Allowed -> step executed exactly once, then completion.
    assert outcome.step_called is True
    assert outcome.reason == StopReason.TASK_COMPLETED
    assert called == [action]
    # Policy gate received the proposed capabilities.
    assert guard.calls[0]["capabilities"] == [Capability.FILESYSTEM_READ]


@pytest.mark.asyncio
async def test_runtime_loops_until_completion_across_multiple_steps():
    guard = RecordingPolicyGuard(verdict="go")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac)

    counter = {"n": 0}

    async def _step(task_id: str, action: ProposedAction):
        counter["n"] += 1
        if counter["n"] < 3:
            return {"progress": counter["n"] / 3.0}
        return {"done": True}

    outcome = await runtime.run(
        "t1", proposed_action=ProposedAction(goal="g", capabilities=[]), step_fn=_step
    )
    assert outcome.step_called is True
    assert counter["n"] == 3
    assert outcome.reason == StopReason.TASK_COMPLETED


@pytest.mark.asyncio
async def test_runtime_hard_iteration_bound_stops_loop():
    guard = RecordingPolicyGuard(verdict="go")
    ac = AutonomyController(policy_guard=guard)
    runtime = PawRuntime(ac, max_iterations=3)

    counter = {"n": 0}

    async def _step(task_id: str, action: ProposedAction):
        counter["n"] += 1
        return {"progress": 0.0}  # never completes

    outcome = await runtime.run(
        "t1", proposed_action=ProposedAction(goal="g", capabilities=[]), step_fn=_step
    )
    assert outcome.step_called is True
    assert counter["n"] == 3
    assert outcome.reason == StopReason.MAX_ITERATIONS_REACHED
