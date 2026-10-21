"""The runtime e2e harness must be a real engineering proof.

``benchmarks/runtime/run_e2e.py`` is the harness that claims to run one
real engineering task through PAW. Two things were missing from it:

* the write was proposed with **no Plan, no root binding and no reviewed
  decision**, so under the B-18 admission contract the runtime refused
  it. The harness could therefore not certify a change PAW never made;
* there was **no declared verification**. The oracle was a measurement,
  not an artifact, so nothing recorded that the change was checked.

This contract pins the corrected harness. It imports the real harness
module and drives its write path over a real temporary project, so what
is tested is the harness that ships, not a copy of it.

The corpus and a local model are not needed: the write path is a
deterministic filesystem write with no model call.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from paw.core.approval import ApprovalStore
from paw.core.storage import db, set_db_path

HARNESS = Path(__file__).resolve().parents[1] / "benchmarks" / "runtime" / "run_e2e.py"


def _harness():
    spec = importlib.util.spec_from_file_location("paw_run_e2e_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
async def _db(tmp_path: Path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    yield
    await db.close()


@pytest.mark.asyncio
async def test_the_harness_produces_a_reviewed_implementation_plan(tmp_path):
    """The harness records a decision, reviews it, and binds a Plan to it."""
    from paw.core.models import TaskStatus
    from paw.core.task import TaskManager

    harness = _harness()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "mod.py").write_text("x = 1\n")

    task = await TaskManager.create("session-harness", "change the corpus")
    plan_id = await harness.reviewed_plan(task.id, task.session_id, corpus)

    from paw.core.planner import Planner

    plan = await Planner(
        workspace_root=corpus, hard_constraints=harness.CONSTRAINTS,
    ).get_plan(plan_id)
    assert plan is not None
    assert plan.purpose == "implementation"
    assert plan.decision_version_id
    assert plan.project_revision
    assert plan.constraint_fingerprint

    # The decision it binds is FINAL and READY, and it was reviewed.
    from paw.core.storage import db as _db

    version = await _db.get_decision_version(plan.decision_version_id)
    assert version is not None
    assert version.state.value == "final"
    assert version.payload.get("readiness") == "ready"
    assert await ApprovalStore.is_decision_reviewed(task.id, version.version_id)


@pytest.mark.asyncio
async def test_the_harness_write_goes_through_the_gate_and_lands(tmp_path):
    """The write is asked for, approved, and performed by the executor."""
    from paw.core.task import TaskManager

    harness = _harness()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    target = corpus / "mod.py"
    target.write_text("x = 1\n")

    task = await TaskManager.create("session-harness", "change the corpus")
    result = await harness.paw_write(
        task.id, task.session_id, corpus, "mod.py", "x = 2\n", "op-harness-1",
    )

    assert result["policy_asked"] is True, "the mutating write did not ask"
    assert result["bytes_unchanged_before_approval"] is True, (
        "bytes were written before the approval"
    )
    assert result["written"] is True, "the approved write did not land"
    assert target.read_text() == "x = 2\n"
    assert result["ledger_events"] > 0


@pytest.mark.asyncio
async def test_the_harness_write_is_refused_without_a_reviewed_plan(tmp_path):
    """Without the reviewed Plan, the write must not happen."""
    from paw.core.autonomy import AutonomyBudget, AutonomyController
    from paw.core.executor import CapabilityRouter, ExecutorRegistry
    from paw.core.models import Capability, ProposedAction, ResourceUsage
    from paw.core.policy import PolicyGuard
    from paw.core.runtime import PawRuntime
    from paw.executors.filesystem import LocalFilesystemExecutor

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    target = corpus / "mod.py"
    target.write_text("x = 1\n")

    registry = ExecutorRegistry()
    registry.register(LocalFilesystemExecutor(corpus))
    action = ProposedAction(
        goal="change the corpus", capabilities=[Capability.FILESYSTEM_WRITE],
        context={},
        metadata={"filesystem": {"operation": "write", "path": "mod.py",
                                 "content": "x = 2\n", "mode": "replace"},
                  "preferred_executor": "local-filesystem", "model_required": False},
        operation_id="op-unreviewed", idempotency_key="op-unreviewed",
        estimated_cost=ResourceUsage(),
    )
    from paw.core.context_compiler import ContextCompiler
    from paw.core.model_executor import ModelExecutor
    from paw.core.model_router import ModelRouter, ProviderRegistry

    provider_registry = ProviderRegistry()
    runtime = PawRuntime(
        AutonomyController(AutonomyBudget(max_iterations=1),
                           policy_guard=PolicyGuard(interactive=True)),
        context_compiler=ContextCompiler(auto_attach_embeddings=False),
        capability_router=CapabilityRouter(registry),
        approval_store=ApprovalStore,
        model_router=ModelRouter(providers=provider_registry),
        model_executor=ModelExecutor(provider_registry=provider_registry),
        project_root=str(corpus), hard_constraints={"workspace_only": True},
    )

    async def brain(_t, _g, _c, _l):
        return action

    from paw.core.task import TaskManager

    task = await TaskManager.create("session-harness", "change the corpus")
    outcome = await runtime.run_agent(
        task.id, task_goal="change the corpus", session_id=task.session_id,
        initial_context={}, max_iterations=1, brain_fn=brain,
    )
    if outcome.approval_id:
        await ApprovalStore.approve(outcome.approval_id)
        await runtime.run_agent(
            task.id, task_goal="change the corpus", session_id=task.session_id,
            initial_context={}, max_iterations=1, brain_fn=brain,
            resume_from_checkpoint=outcome.checkpoint_id,
        )

    assert target.read_text() == "x = 1\n", (
        "an unreviewed write reached the workspace"
    )
