"""
PAW Phase 16 — Full Integration & Docs

Wires the whole PAW Core runtime loop end-to-end using the real public APIs
of every Phase 0–15 component, proving they compose into one coherent system:

    Session/Task -> ContextCompiler -> PolicyGuard -> AutonomyController
        -> ModelRouter -> ModelExecutor -> TaskScheduler (DAG)
        -> CheckpointManager -> TaskLedger

Two scenarios:
  * happy path: every stage runs and the ledger records a coherent trail.
  * policy gate: a DENY capability stops the autonomy loop before any execution
    (constitution: ASK/DENY = STOP, never execute).

Run against a real temp SQLite DB (no mocks for storage / core logic).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest

from paw.core.autonomy import AutonomyController, AutonomyDecision, StopReason
from paw.core.checkpoint import CheckpointManager, CheckpointStore
from paw.core.context_compiler import ContextCompiler
from paw.core.ledger import TaskLedger, log_autonomy_decision, log_context_compiled
from paw.core.ledger import log_execution_completed, log_model_selected
from paw.core.ledger import log_policy_checked, log_task_completed
from paw.core.model_executor import ModelExecutor
from paw.core.model_router import ModelRouter, ensure_model_selections_table
from paw.core.models import Capability, TaskStatus
from paw.core.planner import TaskNode
from paw.core.policy import PolicyGuard
from paw.core.session import SessionManager
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager
from paw.core.task_scheduler import TaskScheduler, ensure_task_scheduler_tables
from paw.providers import ModelProvider


# --- Inline mock provider (conforms to ModelProvider, Phase 15) ---


class _MockProvider:
    def __init__(self, name: str, available: bool = True, models: list[Any] | None = None):
        self.name = name
        self.version = "9.9.9"
        self._available = available
        self._models = models or []
        self.initialized = False

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def list_models(self) -> list[dict[str, Any]]:
        return [{"name": m.name} for m in self._models]

    async def get_model(self, name: str) -> dict[str, Any] | None:
        for m in self._models:
            if m.name == name:
                return {"name": m.name}
        return None

    async def discover_manifests(self) -> list[Any]:
        return list(self._models)

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"response": "ok", "model": request.get("model")}

    async def stream(self, request: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        yield {"response": "ok", "model": request.get("model")}


def _mock_llama_manifest() -> Any:
    from paw.core.models import ModelManifest

    return ModelManifest(
        name="mock-llama",
        provider="mockp",
        roles=["fast", "tools"],
        model_capabilities={"tool_calling": 9.0, "structured_output": 9.0},
        cost={"compute": "low", "monetary": "free"},
        features={"resumable": True, "streaming": True},
        max_context_tokens=32000,
        latency_tier="low",
        enabled=True,
    )


async def _bootstrap(tmp_path) -> None:
    paw_home = tmp_path / ".paw"
    paw_home.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_home / "paw.db")
    await db.initialize()
    await ensure_model_selections_table()
    await CheckpointStore.ensure_table()
    await ensure_task_scheduler_tables()


# --- Happy path: full runtime loop ---


@pytest.mark.asyncio
async def test_phase16_full_runtime_loop(tmp_path):
    await _bootstrap(tmp_path)

    # 1. Session + Task
    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id,
        goal="Summarize the project's context and propose next steps",
        requested_capabilities=[Capability.FILESYSTEM_READ],
    )

    # 2. Context compilation
    compiler = ContextCompiler()
    context, candidates = await compiler.compile(
        task.id, "Summarize the project's context", session_id=session.id, explain_mode=True
    )
    assert context is not None
    await log_context_compiled(
        task.id, "Summarize the project's context", len(context.fragments), 0, 0
    )

    # 3. Policy gate (single authority, fail-closed)
    guard = PolicyGuard(interactive=False)
    verdict = await guard.evaluate_request([Capability.FILESYSTEM_READ], task_id=task.id)
    assert verdict.verdict == "go"
    await log_policy_checked(task.id, Capability.FILESYSTEM_READ.value, "ALLOW")

    # 4. Autonomy decision (policy consulted BEFORE any side effect)
    ac = AutonomyController(policy_guard=guard)
    decision, stop = await ac.decide(
        task.id, required_capabilities=[Capability.FILESYSTEM_READ]
    )
    assert decision == AutonomyDecision.CONTINUE
    assert stop is None
    await log_autonomy_decision(task.id, decision.value, None, ac.usage.to_dict())

    # 5. Model routing (provider-aware, Phase 15) + execution
    mock = _MockProvider("mockp", available=True, models=[_mock_llama_manifest()])
    router = ModelRouter(providers=[mock])
    selection = await router.route(task.id, "Summarize", role="fast")
    assert selection.model_name  # non-empty -> a model was routed
    await log_model_selected(task.id, selection.model_name, selection.role)

    executor = ModelExecutor()  # default registers LocalModelExecutor fallback
    result = await executor.complete(selection, "Summarize now")
    assert result.get("response")
    await log_execution_completed(task.id, True, result.get("response"))

    # 6. Task graph (DAG) — plan sub-steps and verify ordering
    scheduler = TaskScheduler()
    n1 = TaskNode(id="n1", task_id=task.id, goal="gather context", status=TaskStatus.PENDING)
    n2 = TaskNode(
        id="n2", task_id=task.id, goal="write summary", dependencies=["n1"],
        status=TaskStatus.PENDING,
    )
    graph = await scheduler.build_graph(task.id, [n1, n2])
    assert graph.node_count() == 2
    order = await scheduler.topological_sort(task.id)
    assert [n.id for n in order] == ["n1", "n2"]
    assert await scheduler.detect_cycles(task.id) == []

    # 7. Checkpoint (durable state before/after long autonomy)
    cm = CheckpointManager()
    cm.set_checkpoint_interval(1)
    cp = await cm.maybe_checkpoint(
        task.id, "running", current_step=1, total_steps=3, progress_ratio=0.33,
        context={"query": "summarize"}, autonomy_usage=ac.usage,
        autonomy_profile=ac.profile.value, detectors_state={}, loop_state={},
    )
    assert cp is not None
    latest = await CheckpointStore.get_latest(task.id)
    assert latest is not None and latest.checkpoint_id == cp.checkpoint_id

    # 8. Task completion
    await log_task_completed(task.id, "completed", "runtime loop finished")

    # 9. Ledger coherence — a coherent trail of events was recorded
    events = await TaskLedger.get_events(task.id)
    types = {e.event_type.value for e in events}
    assert {
        "context_compiled",
        "policy_checked",
        "autonomy_decision",
        "model_selected",
        "execution_completed",
        "task_completed",
    }.issubset(types)


# --- Negative: policy DENY stops the loop before execution ---


@pytest.mark.asyncio
async def test_phase16_policy_deny_stops_loop(tmp_path):
    await _bootstrap(tmp_path)

    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id, goal="Read a secret and print it",
        requested_capabilities=[Capability.SECRETS_READ],
    )

    guard = PolicyGuard(interactive=False)
    # SECRETS_READ defaults to DENY
    verdict = await guard.evaluate_request([Capability.SECRETS_READ], task_id=task.id)
    assert verdict.verdict == "block"
    assert verdict.stop_reason == StopReason.POLICY_DENIED

    ac = AutonomyController(policy_guard=guard)
    decision, stop = await ac.decide(
        task.id, required_capabilities=[Capability.SECRETS_READ]
    )
    # Loop must STOP, never proceed to execution
    assert decision == AutonomyDecision.STOP
    assert stop == StopReason.POLICY_DENIED

    # No execution should have been logged for this denied task
    events = await TaskLedger.get_events(task.id)
    assert not any(e.event_type == "EXECUTION_COMPLETED" for e in events)
