"""
Phase 20 — PawRuntime as the TRUE agent-loop integration point.

Verifies that ``PawRuntime.run_agent`` wires every PAW subsystem into one
feedback loop:

    ContextCompiler -> SkillFabric -> ModelRouter -> ModelExecutor
         ^                                         |
         |                                         v
    Observation <- Policy Gate <- Autonomy Gate <-+

and that the full loop produces a coherent ledger trail (context_compiled,
skill_selected, model_selected, execution_completed, policy gate, autonomy gate,
step_executed, operation_recorded, checkpoint_created, task_completed).

Two scenarios:
  * A: real subsystem wiring (AgentActionProposer) runs N iterations without a
       brain_fn, proving Context + Skill + Model + Execution connect end-to-end.
  * B: injected brain_fn (real LLM stand-in) drives completion; verifies the
       loop contract (policy/autonomy gated BEFORE execution) + STOP_SUCCESS.

Run against a real temp SQLite DB (no mocks for storage / core logic).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest

from paw.core.autonomy import AutonomyController, AutonomyBudget, AutonomyDecision, StopReason
from paw.core.checkpoint import CheckpointManager, CheckpointStore
from paw.core.context_compiler import ContextCompiler
from paw.core.ledger import TaskLedger
from paw.core.model_executor import ModelExecutor
from paw.core.model_router import ModelRouter, ensure_model_selections_table
from paw.core.models import Capability, ModelManifest, ProposedAction, TaskStatus
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.session import SessionManager
from paw.core.skills import SkillFabric
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager


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
        # Deterministic echo so the loop runs end-to-end offline.
        return {"response": "next: use skill", "model": request.get("model"), "done": False}

    async def stream(self, request: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        yield {"response": "next: use skill", "model": request.get("model")}


def _mock_llama_manifest() -> ModelManifest:
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


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _seed_skill(tmp_path) -> SkillFabric:
    """Create a SkillFabric backed by a temp dir and register one skill in DB."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    fabric = SkillFabric(skills_dir)

    async with db.transaction():
        await db.write(
            """INSERT INTO skills
               (id, name, version, description, category, capabilities, risk, network,
                write, trigger, body, source, enabled, created_at, updated_at,
                executors, dependencies, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "skill_echo_1", "echo", "1.0.0", "Echo a message back",
                "utility", '["filesystem.read"]', "low", 0, 0,
                "echo something", "Echo the input verbatim for the agent to observe.",
                "builtin", 1, _now(), _now(), "[]", "[]", "{}",
            ),
        )
    await fabric.initialize()
    return fabric


async def _seed_memory_and_register_models(tmp_path) -> None:
    async with db.transaction():
        await db.write(
            """INSERT INTO memory_records
               (id, memory_type, content, summary, keywords, metadata, project_id,
                task_id, confidence, created_at, updated_at, last_accessed, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "mem_1", "semantic", "The project goal is to ship PAW Core.",
                "PAW goal", "paw,core", "{}", None, None, 0.9,
                _now(), _now(), _now(), 1,
            ),
        )
        # Register the mock model so ModelRouter can route it.
        m = _mock_llama_manifest()
        await db.write(
            """INSERT INTO model_registry
               (id, name, provider, roles, capabilities, cost, features,
                max_context_tokens, latency_tier, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m.name, m.name, "mockp",
                '["fast","tools"]', "{}",
                '{"compute":"low"}', '{"streaming":true}',
                m.max_context_tokens, "low", 1, _now(), _now(),
            ),
        )


# --- Scenario A: real subsystem wiring (no brain_fn) runs end-to-end ---


@pytest.mark.asyncio
async def test_agent_loop_wires_context_skill_model_execution(tmp_path):
    await _bootstrap(tmp_path)
    fabric = await _seed_skill(tmp_path)
    await _seed_memory_and_register_models(tmp_path)

    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id, goal="Echo a greeting to the user",
        requested_capabilities=[Capability.FILESYSTEM_READ],
    )

    compiler = ContextCompiler()
    router = ModelRouter(providers=[_MockProvider("mockp", models=[_mock_llama_manifest()])])
    executor = ModelExecutor(provider_registry=router._provider_registry)
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(
        budget=AutonomyBudget(max_iterations=3, max_decisions=10),
        policy_guard=guard,
    )

    runtime = PawRuntime(
        ac,
        context_compiler=compiler,
        model_router=router,
        model_executor=executor,
        skill_fabric=fabric,
        max_iterations=3,
    )

    # No brain_fn -> the runtime uses AgentActionProposer (real subsystem wiring).
    outcome = await runtime.run_agent(
        task.id,
        task_goal="Echo a greeting to the user",
        session_id=session.id,
    )

    # The loop ran and stopped (here at max_iterations because the mock model
    # never signals done). Crucially, every subsystem was consulted.
    assert outcome.stopped is True
    assert outcome.reason == StopReason.MAX_ITERATIONS_REACHED
    assert outcome.iterations == 3
    assert outcome.step_called is True

    events = await TaskLedger.get_events(task.id)
    types = {e.event_type.value for e in events}
    # Every subsystem is wired for the graph path too.
    # Context + Skill + Model + Execution were all wired into the loop.
    assert "context_compiled" in types
    assert "skill_selected" in types
    assert "model_selected" in types
    assert "execution_completed" in types
    assert "policy_gate_evaluated" in types
    assert "autonomy_gate_evaluated" in types
    assert "step_executed" in types
    assert "operation_recorded" in types
    assert "checkpoint_created" in types
    # The selected skill was actually loaded + executed by the loop.
    assert "echo" in outcome.skills_used


# --- Scenario B: injected brain drives completion; loop contract + STOP_SUCCESS ---


@pytest.mark.asyncio
async def test_agent_loop_brain_completes_with_stop_success(tmp_path):
    await _bootstrap(tmp_path)
    fabric = await _seed_skill(tmp_path)
    await _seed_memory_and_register_models(tmp_path)

    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id, goal="Finish the task in one step",
        requested_capabilities=[Capability.FILESYSTEM_READ],
    )

    compiler = ContextCompiler()
    router = ModelRouter(providers=[_MockProvider("mockp", models=[_mock_llama_manifest()])])
    executor = ModelExecutor(provider_registry=router._provider_registry)
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(
        budget=AutonomyBudget(max_iterations=10, max_decisions=20),
        policy_guard=guard,
    )

    runtime = PawRuntime(
        ac,
        context_compiler=compiler,
        model_router=router,
        model_executor=executor,
        skill_fabric=fabric,
        max_iterations=10,
    )

    counter = {"n": 0}

    async def brain_fn(task_id, goal, ctx, last_obs):
        """Real-LLM stand-in: complete on the first step."""
        counter["n"] += 1
        return ProposedAction(
            goal=goal,
            capabilities=[Capability.FILESYSTEM_READ],
            context=ctx,
            metadata={"selected_skill": "echo", "done": True},
            operation_id=f"op_{task_id}_{counter['n']}",
        )

    outcome = await runtime.run_agent(
        task.id,
        task_goal="Finish the task in one step",
        session_id=session.id,
        brain_fn=brain_fn,
    )

    # Completion -> deterministic STOP_SUCCESS (constitution: done == STOP_SUCCESS).
    assert outcome.stopped is True
    assert outcome.reason == StopReason.TASK_COMPLETED
    assert outcome.decision == AutonomyDecision.STOP_SUCCESS
    assert outcome.iterations == 1
    assert outcome.operations_completed == 1
    assert outcome.last_observation is not None
    assert outcome.last_observation.result["done"] is True

    events = await TaskLedger.get_events(task.id)
    types = [e.event_type.value for e in events]
    # Coherent full trail.
    for required in (
        "task_created", "context_compiled", "skill_selected", "model_selected",
        "execution_completed", "policy_gate_evaluated", "autonomy_gate_evaluated",
        "step_proposed", "step_executed", "operation_recorded", "step_completed",
        "checkpoint_created", "task_completed",
    ):
        assert required in types, f"missing ledger event: {required}"


# --- Scenario C: policy DENY blocks the agent loop before execution ---


@pytest.mark.asyncio
async def test_agent_loop_policy_deny_blocks_before_execution(tmp_path):
    await _bootstrap(tmp_path)
    fabric = await _seed_skill(tmp_path)
    await _seed_memory_and_register_models(tmp_path)

    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id, goal="Read a secret",
        requested_capabilities=[Capability.SECRETS_READ],
    )

    compiler = ContextCompiler()
    router = ModelRouter(providers=[_MockProvider("mockp", models=[_mock_llama_manifest()])])
    executor = ModelExecutor(provider_registry=router._provider_registry)
    guard = PolicyGuard(interactive=False)  # SECRETS_READ defaults to DENY
    ac = AutonomyController(policy_guard=guard)

    runtime = PawRuntime(
        ac,
        context_compiler=compiler,
        model_router=router,
        model_executor=executor,
        skill_fabric=fabric,
        max_iterations=5,
    )

    async def brain_fn(task_id, goal, ctx, last_obs):
        # Proposes an action that needs SECRETS_READ -> must be blocked.
        return ProposedAction(
            goal=goal,
            capabilities=[Capability.SECRETS_READ],
            context=ctx,
            metadata={"selected_skill": "echo", "done": False},
            operation_id=f"op_{task_id}_1",
        )

    outcome = await runtime.run_agent(
        task.id,
        task_goal="Read a secret",
        session_id=session.id,
        brain_fn=brain_fn,
    )

    # Single authority gate: DENY stops the loop, step_fn never executed.
    assert outcome.stopped is True
    assert outcome.reason == StopReason.POLICY_DENIED
    assert outcome.step_called is False

    events = await TaskLedger.get_events(task.id)
    assert not any(e.event_type.value == "step_executed" for e in events)
    assert any(e.event_type.value == "policy_gate_evaluated" for e in events)


# --- Scenario D: TaskGraph (DAG) executed through the same gated loop ---


@pytest.mark.asyncio
async def test_agent_loop_runs_task_graph_dag(tmp_path):
    await _bootstrap(tmp_path)
    fabric = await _seed_skill(tmp_path)
    await _seed_memory_and_register_models(tmp_path)
    from paw.core.task_scheduler import (
        TaskScheduler,
        TaskGraphValidationError,
        ensure_task_scheduler_tables,
    )
    from paw.core.planner import TaskNode

    await ensure_task_scheduler_tables()

    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id, goal="Build a feature end-to-end",
        requested_capabilities=[Capability.FILESYSTEM_READ],
    )

    compiler = ContextCompiler()
    router = ModelRouter(providers=[_MockProvider("mockp", models=[_mock_llama_manifest()])])
    executor = ModelExecutor(provider_registry=router._provider_registry)
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(
        budget=AutonomyBudget(max_iterations=20, max_decisions=50),
        policy_guard=guard,
    )
    scheduler = TaskScheduler()

    runtime = PawRuntime(
        ac,
        context_compiler=compiler,
        model_router=router,
        model_executor=executor,
        skill_fabric=fabric,
        task_scheduler=scheduler,
        max_iterations=20,
    )

    # A 3-node DAG: plan -> implement (depends on plan) -> verify (depends on implement)
    nodes = [
        TaskNode(id="plan", task_id=task.id, goal="Plan the echo feature"),
        TaskNode(id="implement", task_id=task.id, goal="Echo the implementation",
                 dependencies=["plan"]),
        TaskNode(id="verify", task_id=task.id, goal="Verify the echo output",
                 dependencies=["implement"]),
    ]

    outcome = await runtime.run_graph(
        task.id,
        nodes=nodes,
        task_goal="Build a feature end-to-end",
        session_id=session.id,
    )

    # All 3 nodes executed via the gated loop; terminal completion.
    assert outcome.stopped is True
    assert outcome.reason == StopReason.TASK_COMPLETED
    assert outcome.decision == AutonomyDecision.STOP_SUCCESS
    assert outcome.iterations == 3
    assert outcome.operations_completed == 3

    events = await TaskLedger.get_events(task.id)
    types = {e.event_type.value for e in events}
    # Every subsystem is wired for the graph path too.
    for required in (
        "task_created", "context_compiled", "skill_selected", "model_selected",
        "execution_completed", "policy_gate_evaluated", "autonomy_gate_evaluated",
        "step_proposed", "step_executed", "operation_recorded", "checkpoint_created",
        "task_completed",
    ):
        assert required in types, f"missing ledger event: {required}"

    # All 3 DAG nodes were executed + recorded as operations (graph + Ledger
    # coherent: one operation_recorded event per node).
    node_ops = [e for e in events if e.event_type.value == "operation_recorded"]
    assert len(node_ops) == 3


@pytest.mark.asyncio
async def test_agent_loop_rejects_cyclic_task_graph(tmp_path):
    await _bootstrap(tmp_path)
    fabric = await _seed_skill(tmp_path)
    await _seed_memory_and_register_models(tmp_path)
    from paw.core.task_scheduler import (
        TaskScheduler,
        TaskGraphValidationError,
        ensure_task_scheduler_tables,
    )
    from paw.core.planner import TaskNode

    await ensure_task_scheduler_tables()

    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id, goal="Cyclic plan",
        requested_capabilities=[Capability.FILESYSTEM_READ],
    )

    compiler = ContextCompiler()
    router = ModelRouter(providers=[_MockProvider("mockp", models=[_mock_llama_manifest()])])
    executor = ModelExecutor(provider_registry=router._provider_registry)
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(policy_guard=guard)
    scheduler = TaskScheduler()

    runtime = PawRuntime(
        ac,
        context_compiler=compiler,
        model_router=router,
        model_executor=executor,
        skill_fabric=fabric,
        task_scheduler=scheduler,
    )

    # A cycle: a -> b -> a
    nodes = [
        TaskNode(id="a", task_id=task.id, goal="Do a", dependencies=["b"]),
        TaskNode(id="b", task_id=task.id, goal="Do b", dependencies=["a"]),
    ]

    # A malformed plan must be rejected BEFORE entering the execution loop.
    with pytest.raises(TaskGraphValidationError):
        await runtime.run_graph(task.id, nodes=nodes, task_goal="Cyclic")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
