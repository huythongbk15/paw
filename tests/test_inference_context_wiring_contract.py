"""The compiled project context must actually reach the model.

Before this, the outbound provider payload was the conversation history
(or the bare task goal). The compiled project context was summarised into
a fragment count and a token estimate, and the model never saw the
retrieved sources at all. The "research" phase existed, and nothing it
found reached the reasoning.

The payload is now built from the **manifest** - the reviewed, budgeted,
disclosure-checked view of the compiled context - so:

* the model receives the retrieved project content;
* what leaves the box is exactly what the evidence covers, which is what
  the B-19/F05 payload binding assumes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCompiler
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.model_executor import ModelExecutor
from paw.core.model_router import ModelRouter, ProviderRegistry
from paw.core.models import (
    Capability,
    ModelManifest,
    ProposedAction,
    ResourceUsage,
)
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager


PROJECT_CONTENT = "def secret_helper():\n    return 'the answer is 42'\n"


class _CapturingProvider:
    """A local provider that captures the payload it is given."""

    name = "local"
    initialized = True

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return True

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def list_models(self) -> list[dict[str, Any]]:
        return [{"name": "local-echo"}]

    async def get_model(self, name: str) -> dict[str, Any] | None:
        return {"name": name}

    async def discover_manifests(self):
        return [
            ModelManifest(
                name="local-echo",
                provider="local",
                roles=["fast", "reasoning"],
                model_capabilities={"tool_calling": 9.0},
                cost={"compute": "low", "monetary": "free"},
                features={"resumable": True, "streaming": True},
                max_context_tokens=32000,
                latency_tier="low",
                enabled=True,
            )
        ]

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(request)
        return {"response": "echo", "done": True}

    async def stream(self, request: dict[str, Any]):
        self.payloads.append(request)
        yield {"response": "echo"}


async def _ingest(root: Path) -> None:
    from paw.knowledge.chunk import KnowledgeChunkStore
    from paw.knowledge.source import KnowledgeSourceManager

    sources, chunks = KnowledgeSourceManager(), KnowledgeChunkStore()
    path = root / "module.py"
    path.write_text(PROJECT_CONTENT)
    source = await sources.create(
        name="module.py", path="module.py", external_id="module.py", revision="r1",
    )
    await chunks.add_chunk(
        source_id=source.id, content=PROJECT_CONTENT,
        span_start=0, span_end=len(PROJECT_CONTENT), metadata={"file": "module.py"},
    )


@pytest.mark.asyncio
async def test_the_model_receives_the_compiled_project_context(tmp_path):
    """The retrieved project content reaches the provider payload."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root = tmp_path / "project"
    root.mkdir()
    await _ingest(root)

    task = await TaskManager.create("session-infer", "what does the helper return?")

    provider = _CapturingProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(providers=registry)
    await router.discover_providers()

    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
            policy_guard=PolicyGuard(interactive=False),
        ),
        model_router=router,
        model_executor=ModelExecutor(provider_registry=registry),
        context_compiler=ContextCompiler(
            budget=ContextBudget(max_tokens=2000, max_fragments=10, max_sources=5),
            auto_attach_embeddings=False,
        ),
    )

    # The runtime compiles the manifest for the task before it proposes
    # (run_agent / run_graph do this); the payload is built from it.
    manifest = await runtime.context_compiler.compile_manifest(task.id, task.goal)
    runtime._current_manifest = manifest

    action = ProposedAction(
        goal=task.goal,
        capabilities=[Capability.MODEL_INFERENCE],
        context={},
        metadata={},
        operation_id="op-infer",
        idempotency_key="op-infer",
        estimated_cost=ResourceUsage(),
    )

    await runtime._execute_unit(
        task.id, action, iteration_index=0, step_fn=runtime._execute_action,
        operation_type="step", step_id="step-1",
    )

    assert provider.payloads, "the provider was never called"
    payload = provider.payloads[0]
    text = "\n".join(str(m.get("content", "")) for m in payload.get("messages", []))
    assert "the answer is 42" in text, (
        "the compiled project context did not reach the model payload:\n"
        f"{text[:800]}"
    )
    # The payload names the goal and the reviewed context explicitly.
    assert "REVIEWED PROJECT CONTEXT" in text


@pytest.mark.asyncio
async def test_the_payload_context_comes_from_the_manifest(tmp_path):
    """The payload's context is the manifest's included candidates."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root = tmp_path / "project"
    root.mkdir()
    await _ingest(root)

    task = await TaskManager.create("session-infer-2", "what does the helper return?")

    provider = _CapturingProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(providers=registry)
    await router.discover_providers()

    compiler = ContextCompiler(
        budget=ContextBudget(max_tokens=2000, max_fragments=10, max_sources=5),
        auto_attach_embeddings=False,
    )
    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
            policy_guard=PolicyGuard(interactive=False),
        ),
        model_router=router,
        model_executor=ModelExecutor(provider_registry=registry),
        context_compiler=compiler,
    )

    manifest = await compiler.compile_manifest(task.id, task.goal)
    runtime._current_manifest = manifest
    included = [c for c in manifest.included if c.source == "knowledge"]
    assert included, "the manifest included no retrieved content"

    action = ProposedAction(
        goal=task.goal,
        capabilities=[Capability.MODEL_INFERENCE],
        context={},
        metadata={},
        operation_id="op-infer-2",
        idempotency_key="op-infer-2",
        estimated_cost=ResourceUsage(),
    )
    await runtime._execute_unit(
        task.id, action, iteration_index=0, step_fn=runtime._execute_action,
        operation_type="step", step_id="step-1",
    )

    payload = provider.payloads[0]
    text = "\n".join(str(m.get("content", "")) for m in payload.get("messages", []))
    # Every retrieved chunk in the manifest appears in the payload.
    for cand in included:
        assert cand.content[:40] in text, (
            f"manifest content did not reach the payload: {cand.source_id}"
        )
    # And the context is recorded as compiled in the ledger.
    compiled = await TaskLedger.get_events_by_type(
        task.id, TaskEventType.CONTEXT_COMPILED
    )
