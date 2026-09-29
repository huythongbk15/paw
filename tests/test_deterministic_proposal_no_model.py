"""
Deterministic operations must not be routed to a model (independent routing).

E2-49 builds a ``CanonicalProposal`` — which names a concrete model — for every
model-backed operation *before* the Policy/Autonomy gates, so Policy evaluates
the exact proposal. A deterministic adapter (a structured filesystem action)
sets ``model_required=False``, carries no ``MODEL_INFERENCE`` capability, and is
therefore never routed to a model at all.

The regression this pins: the pre-gate routing ran unconditionally, so a plain
``filesystem.write`` reported ``model='local-fast'`` and emitted a
``MODEL_SELECTED`` ledger event for a model that was never invoked. That is
model routing standing in for capability routing (ARCHITECTURE invariant 5,
ENGINEERING_RULES: "Deterministic adapters set ``model_required=False``; this
is normalized before the proposal reaches Policy").

Both halves matter: a deterministic proposal must route nothing, and a
model-backed proposal must still route — otherwise this test would pass on a
runtime where model selection is simply dead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.context_compiler import ContextCompiler
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.models import (
    Capability,
    ExecutionObservation,
    ProposedAction,
    ResourceUsage,
)
from paw.core.runtime import PawRuntime
from paw.core.storage import db


class _Verdict:
    def __init__(self) -> None:
        self.verdict = "go"
        self.stop_reason = None


class _Guard:
    async def evaluate_request(self, capabilities, context=None, task_id=None):
        return _Verdict()


class _SpyRouter:
    """Real routing behaviour is irrelevant here; count selection attempts."""

    def __init__(self) -> None:
        self.route_calls = 0

    async def route(self, *args, **kwargs):
        self.route_calls += 1
        raise AssertionError("model routing must not run for a deterministic operation")

    async def re_evaluate_routing(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("unreachable: route() must not have been called")


async def _insert_task(task_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    await db.execute(
        """INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (task_id, "session-det", "deterministic goal", "pending", now, now),
    )


async def _done_step(task_id: str, action: ProposedAction) -> ExecutionObservation:
    return ExecutionObservation(
        step_id=action.operation_id,
        action_id=action.operation_id,
        result={"done": True, "progress": 1.0},
        resources_used=ResourceUsage(tool_calls=1),
        success=True,
    )


def _runtime(router: Any) -> PawRuntime:
    return PawRuntime(
        AutonomyController(
            AutonomyBudget(max_iterations=2, max_decisions=5), policy_guard=_Guard()
        ),
        model_router=router,
        max_iterations=2,
    )


def _brain(*, deterministic: bool):
    """Mirror what ``ChatService`` proposes for a structured filesystem write."""

    async def _fn(task_id, goal, context, last_observation):
        return ProposedAction(
            goal=goal,
            capabilities=[Capability.FILESYSTEM_WRITE],
            context=context if isinstance(context, dict) else {},
            operation_id="op-deterministic",
            idempotency_key="k:deterministic",
            metadata={"model_required": not deterministic},
        )

    return _fn


class _CountingModelExecutor:
    """No provider call is expected in the deterministic case; fail loudly if there is."""

    def __init__(self) -> None:
        self.complete_calls = 0

    async def complete(self, selection, messages):
        self.complete_calls += 1
        raise AssertionError("a deterministic operation must not invoke a model")

    async def shutdown_all(self) -> None:
        return None


async def _run_with_brain(task_id: str, router: Any, *, deterministic: bool):
    runtime = PawRuntime(
        AutonomyController(
            AutonomyBudget(max_iterations=1, max_decisions=5), policy_guard=_Guard()
        ),
        context_compiler=ContextCompiler(auto_attach_embeddings=False),
        model_router=router,
        model_executor=_CountingModelExecutor(),
        max_iterations=1,
    )
    return await runtime.run_agent(
        task_id,
        task_goal="write a file deterministically",
        initial_context={},
        max_iterations=1,
        brain_fn=_brain(deterministic=deterministic),
    )


@pytest.mark.asyncio
async def test_deterministic_proposal_does_not_route_a_model():
    router = _SpyRouter()
    await _insert_task("task-det-01")

    outcome = await _run_with_brain("task-det-01", router, deterministic=True)

    assert router.route_calls == 0, "a model_required=False proposal must not be routed"
    assert outcome.model_selections == []

    events = await TaskLedger.get_events("task-det-01")
    event_types = [event.event_type for event in events]
    assert TaskEventType.MODEL_SELECTED not in event_types


@pytest.mark.asyncio
async def test_model_backed_proposal_still_routes():
    """Control: the deterministic opt-out is conditional, not a dead router."""
    calls: list[str] = []

    class _CountingRouter:
        async def route(self, task_id, goal, **kwargs):
            calls.append(task_id)
            from paw.core.model_router import ModelSelection

            return ModelSelection(model_name="local-fast")

        async def re_evaluate_routing(self, task_id, selection, recon):
            return selection

    await _insert_task("task-model-01")

    # ``model_required=True`` lets the runtime materialize ``model.inference``
    # on the proposal (the normal agent path), so the router must run.
    outcome = await _run_with_brain("task-model-01", _CountingRouter(), deterministic=False)

    assert calls == ["task-model-01"], "a model-backed proposal must still be routed"
    assert outcome.model_selections, "the routed model must be reported"
