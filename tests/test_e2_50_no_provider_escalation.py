"""E2-50: Prove no-route, denied-disclosure and exhausted-budget escalation stop explicitly without provider invocation.

Four-layer evidence:
  1. Invariant  — Runtime has hard gates for no-route, denied-disclosure, exhausted-budget
  2. Runtime    — step_fn is never called when any gate blocks
  3. Adversarial — malformed/empty route, stale SECRET disclosure, zero budget
  4. Measurable — provider executor count stays at 0 in all blocking cases
"""
from __future__ import annotations

import pytest
from pathlib import Path

from paw.core.autonomy import AutonomyController, AutonomyBudget, StopReason
from paw.core.models import ModelSelection, ModelManifest, Capability, ProposedAction, ResourceUsage
from paw.core.privacy import PROVIDER_LOCAL
from paw.core.runtime import PawRuntime
from paw.core.session import SessionManager
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager


class CountingExecutor:
    def __init__(self):
        self.calls = 0

    async def complete(self, selection, messages):
        self.calls += 1
        return {"done": True, "progress": 1.0}


class NoRouteRouter:
    async def route(self, *args, **kwargs):
        return ModelSelection(
            model_name="",
            role="worker",
            reason="no_model",
            score=0.0,
            fallback_chain=[],
            model_manifest=ModelManifest(name="", provider=PROVIDER_LOCAL, roles=("worker",), capabilities=[]),
        )


class DenyRouter:
    async def route(self, *args, **kwargs):
        return ModelSelection(
            model_name="remote-model",
            role="worker",
            reason="remote",
            score=0.9,
            fallback_chain=[],
            model_manifest=ModelManifest(name="remote-model", provider="cloud_approved", roles=("worker",), capabilities=[]),
        )


class AlwaysRouteRouter:
    async def route(self, *args, **kwargs):
        return ModelSelection(
            model_name="local-model",
            role="worker",
            reason="local",
            score=0.5,
            fallback_chain=[],
            model_manifest=ModelManifest(name="local-model", provider=PROVIDER_LOCAL, roles=("worker",), capabilities=[]),
        )


@pytest.fixture()
async def runtime_env(tmp_path: Path):
    paw_home = tmp_path / ".paw"
    paw_home.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_home / "paw.db")
    await db.initialize()
    yield


def _make_runtime(router, executor, *, budget=None):
    budget = budget or AutonomyBudget(max_model_calls=1, max_iterations=3)
    ac = AutonomyController(budget)
    runtime = PawRuntime(
        ac,
        model_router=router,
        model_executor=executor,
        max_iterations=3,
    )
    runtime.default_role = "worker"
    return runtime


@pytest.mark.asyncio
async def test_no_route_does_not_invoke_provider(runtime_env):
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, goal="test", requested_capabilities=[])
    executor = CountingExecutor()
    runtime = _make_runtime(NoRouteRouter(), executor)
    outcome = await runtime.run(
        task.id,
        task_goal="test",
        step_fn=runtime._execute_action,
    )
    assert executor.calls == 0
    assert outcome.stopped is True


@pytest.mark.asyncio
async def test_denied_disclosure_blocks_before_provider(runtime_env):
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, goal="test", requested_capabilities=[])
    executor = CountingExecutor()
    runtime = _make_runtime(DenyRouter(), executor)
    runtime._current_manifest = {"privacy_class": "SECRET", "content": "secret"}
    outcome = await runtime.run(
        task.id,
        task_goal="test",
        step_fn=runtime._execute_action,
    )
    assert executor.calls == 0
    assert outcome.stopped is True


@pytest.mark.asyncio
async def test_exhausted_budget_blocks_before_provider(runtime_env):
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, goal="test", requested_capabilities=[])
    executor = CountingExecutor()
    budget = AutonomyBudget(max_model_calls=0, max_iterations=3)
    runtime = _make_runtime(AlwaysRouteRouter(), executor, budget=budget)
    outcome = await runtime.run(
        task.id,
        task_goal="test",
        step_fn=runtime._execute_action,
    )
    assert executor.calls == 0
    assert outcome.stopped is True
