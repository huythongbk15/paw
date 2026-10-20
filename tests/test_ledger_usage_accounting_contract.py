"""Ledger usage-accounting contract: observed usage must be countable.

Two defects made the ledger unusable for cost/token analysis:

1. **Wrong key.** ``RuntimePersistence.commit_operation`` serialized
   ``ResourceUsage`` with ``model_dump()``, which emits only pydantic
   *fields* (``model_calls``, ``tokens``, ...). ``provider_calls`` is a
   *method* on ``ResourceUsage``, so it was absent from the payload.
   ``TaskLedger.get_model_call_count`` reads
   ``resources_used["provider_calls"]`` and therefore returned **0** for
   every runtime-written task, however many model calls actually happened.
   ``assert_model_calls_monotonic`` was vacuous for the same reason.

2. **Double-counted events.** ``commit_operation`` already writes one
   ``STEP_EXECUTED`` event (atomically with the ``OperationRecord``), and
   ``_execute_unit`` then wrote a *second* ``STEP_EXECUTED`` for the same
   operation. Every operation therefore produced two events, so even a
   corrected reader would have counted each call twice.

The contract pinned here is deliberately behavioural, not structural:

* the ledger count for a runtime task equals the usage the runtime observed;
* exactly one ``STEP_EXECUTED`` event exists per executed operation;
* the payload carries the keys the readers consume.

These are the properties a cost/token optimization needs. They were not
previously true.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from paw.core.autonomy import AutonomyController, AutonomyDecision
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.models import (
    ExecutionObservation,
    ResourceUsage,
)
from paw.core.runtime import PawRuntime
from paw.core.storage import db


class _Guard:
    """Allow-all policy guard so the loop contract stays isolated from policy."""

    async def evaluate_request(self, capabilities, context=None, task_id=None):
        class _Verdict:
            verdict = "go"
            stop_reason = None

        return _Verdict()


async def _insert_task(task_id: str, goal: str = "goal") -> None:
    now = datetime.now(UTC).isoformat()
    await db.execute(
        """INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (task_id, "s1", goal, "pending", now, now),
    )


def _obs(usage: ResourceUsage) -> ExecutionObservation:
    return ExecutionObservation(
        step_id="s1",
        action_id="op_1",
        result={"done": True, "progress": 1.0},
        resources_used=usage,
        success=True,
    )


def _step(usage: ResourceUsage):
    async def _run(task_id: str, action: Any) -> ExecutionObservation:
        return _obs(usage)

    return _run


# ── 1. The count is not zero ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runtime_model_calls_are_counted_not_zero():
    """A runtime task that observed model calls must not count as zero."""
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard()))
    await _insert_task("t-usage-count")

    usage = ResourceUsage(model_calls=3, tokens=120, tool_calls=1)
    outcome = await runtime.run(
        "t-usage-count",
        task_goal="use a model",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(usage),
    )

    assert outcome.reason is not None
    count = await TaskLedger.get_model_call_count("t-usage-count")
    assert count == 3, f"expected 3 observed model calls, ledger counted {count}"


@pytest.mark.asyncio
async def test_runtime_token_count_reaches_the_ledger():
    """Tokens observed by the runtime must survive into the ledger payload."""
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard()))
    await _insert_task("t-usage-tokens")

    usage = ResourceUsage(model_calls=1, tokens=256)
    await runtime.run(
        "t-usage-tokens",
        task_goal="spend tokens",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(usage),
    )

    events = await TaskLedger.get_events_by_type(
        "t-usage-tokens", TaskEventType.STEP_EXECUTED
    )
    assert events, "runtime must write a STEP_EXECUTED event"
    resources = events[0].payload.get("resources_used") or {}
    assert resources.get("tokens") == 256
    assert resources.get("provider_calls") == 1


# ── 2. Exactly one event per operation ──────────────────────────────────


@pytest.mark.asyncio
async def test_one_step_executed_event_per_operation():
    """A single operation must not produce two STEP_EXECUTED events."""
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard()))
    await _insert_task("t-usage-single")

    usage = ResourceUsage(model_calls=2, tokens=10)
    await runtime.run(
        "t-usage-single",
        task_goal="one operation",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(usage),
    )

    events = await TaskLedger.get_events_by_type(
        "t-usage-single", TaskEventType.STEP_EXECUTED
    )
    assert len(events) == 1, (
        f"expected exactly 1 STEP_EXECUTED event, got {len(events)}: "
        "the operation is being logged twice"
    )


@pytest.mark.asyncio
async def test_count_is_not_doubled_by_duplicate_events():
    """The counted total must equal the observed usage, not twice it."""
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard()))
    await _insert_task("t-usage-nodouble")

    usage = ResourceUsage(model_calls=4, tokens=40)
    await runtime.run(
        "t-usage-nodouble",
        task_goal="one operation",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(usage),
    )

    count = await TaskLedger.get_model_call_count("t-usage-nodouble")
    assert count == 4, f"expected 4, got {count} (double counting or a wrong key)"


# ── 3. Monotonicity check is no longer vacuous ─────────────────────────


@pytest.mark.asyncio
async def test_monotonic_check_sees_runtime_written_usage():
    """The monotonic guard must read real runtime usage, not always zero.

    ``assert_model_calls_monotonic`` historically read a key the runtime
    never wrote, so it could never observe a runtime-written task at all.
    """
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard()))
    await _insert_task("t-usage-monotonic")

    usage = ResourceUsage(model_calls=2, tokens=20)
    await runtime.run(
        "t-usage-monotonic",
        task_goal="monotonic",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(usage),
    )

    # Must not raise, and must observe the runtime's own event.
    await TaskLedger.assert_model_calls_monotonic("t-usage-monotonic")

    events = await TaskLedger.get_events_by_type(
        "t-usage-monotonic", TaskEventType.STEP_EXECUTED
    )
    resources = events[0].payload.get("resources_used") or {}
    assert int(resources.get("provider_calls", 0)) == 2


@pytest.mark.asyncio
async def test_completion_decision_is_unchanged_by_the_fix():
    """The usage fix must not alter the terminal decision."""
    runtime = PawRuntime(AutonomyController(policy_guard=_Guard()))
    await _insert_task("t-usage-decision")

    outcome = await runtime.run(
        "t-usage-decision",
        task_goal="finish",
        initial_context={},
        available_skills=[{"name": "noop", "required_capabilities": ["filesystem.read"]}],
        step_fn=_step(ResourceUsage(model_calls=1)),
    )

    assert outcome.decision == AutonomyDecision.STOP_SUCCESS
    assert outcome.operations_completed >= 1
