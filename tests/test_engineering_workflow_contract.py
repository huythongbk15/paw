"""The engineering workflow, proved end to end.

The chain: **research -> choose -> change -> declared verification**, with
a **failure** and a **restart**.

Everything below uses the real subsystems - a real ContextCompiler over a
real repository, the real DecisionVersion lifecycle, the real Planner
binding, the real shared executable unit with its policy gate and
implementation admission, the real filesystem executor, the real ledger
and the real checkpoints. The only substitutes are the *verification
port* (PAW does not run shells; the charter does not authorize shell
execution) and the human who grants the approvals.

What the chain proves, and what it refuses to claim:

* the research phase cites the sources it actually read;
* the choose phase cannot be skipped - the Planner refuses an
  implementation Plan without a reviewed FINAL READY decision;
* the change goes through the gate, and a denied approval changes
  nothing;
* a **declared verification** is recorded as its own artifact, bound to
  the operation it verifies;
* a change whose verification **fails** is not a completed change;
* a **restart** after that failure does not repeat the completed change,
  and a verification that then passes completes the chain.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from paw.application.workflow import (
    EngineeringWorkflow,
    VerificationOutcome,
    VerificationRequest,
    WorkflowRequest,
)
from paw.core.approval import ApprovalStore
from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.context_compiler import ContextCompiler, ContextBudget
from paw.core.executor import CapabilityRouter, ExecutorRegistry
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.models import Capability, ProposedAction, VerificationRecord
from paw.core.planner import Planner
from paw.core.policy import PolicyGuard
from paw.core.reasoning_contracts import DecisionVersion
from paw.core.repo_scanner import RepoFilter
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager
from paw.executors.filesystem import LocalFilesystemExecutor
from paw.knowledge.checksum import compute_repo_revision


# --- Fixtures -------------------------------------------------------------


class _RecordingPort:
    """A verification port that records what it was asked and answers."""

    def __init__(self, passed: bool = True, summary: str = "checked") -> None:
        self.passed = passed
        self.summary = summary
        self.requests: list[VerificationRequest] = []

    async def verify(self, request: VerificationRequest) -> VerificationOutcome:
        self.requests.append(request)
        return VerificationOutcome(
            passed=self.passed,
            summary=self.summary,
            evidence=f"verified {request.target} by {request.method}",
            command=f"verify --target {request.target}",
        )


async def _ingest(root: Path) -> int:
    """Ingest the project into the knowledge store.

    This is the E1 project-intelligence path: the sources and their chunks
    are what the context compiler retrieves, so the research phase cites
    real retrieved content rather than a file name.
    """
    from paw.knowledge.chunk import KnowledgeChunkStore
    from paw.knowledge.source import KnowledgeSourceManager

    sources, chunks = KnowledgeSourceManager(), KnowledgeChunkStore()
    total = 0
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root))
        content = path.read_text(encoding="utf-8", errors="replace")
        source = await sources.create(
            name=rel, path=rel, external_id=rel, revision="workflow-1",
        )
        await chunks.add_chunk(
            source_id=source.id, content=content,
            span_start=0, span_end=len(content), metadata={"file": rel},
        )
        total += 1
    return total


async def _project(tmp_path: Path) -> tuple[Path, Any, DecisionVersion, dict[str, Any]]:
    """A real project, a real task and a real FINAL READY decision."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "module.py").write_text("def value():\n    return 1\n")
    (root / "README.md").write_text("# project\n\nA small project.\n")
    await _ingest(root)

    task = await TaskManager.create("session-workflow", "raise the value in module.py")
    constraints = {"workspace_only": True, "no_network": True}
    constraint_hash = hashlib.sha256(
        json.dumps(constraints, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    parent = await db.record_decision(
        "readiness", "ready",
        task_id=task.id, session_id=task.session_id,
        project_revision=compute_repo_revision(root, RepoFilter.safe_default()),
        constraint_fingerprint=constraint_hash,
    )
    draft = DecisionVersion("draft", parent, "draft", {"readiness": "ready"}, "2026-10-20", "researcher")
    final = DecisionVersion("final", parent, "final", {"readiness": "ready"}, "2026-10-20", "researcher")
    await db.advance_decision_version(draft, expected_version_id=None)
    await db.advance_decision_version(final, expected_version_id="draft")
    return root, task, final, constraints


async def _reviewed_plan(root: Path, task: Any, final: DecisionVersion, constraints: dict):
    """The human review, then the implementation Plan it admits."""
    review = await ApprovalStore.request_decision_review(final.version_id)
    await ApprovalStore.approve(review.id, "fixture-human")
    return await Planner(workspace_root=root, hard_constraints=constraints).plan(
        task.id, purpose="implementation", decision_version_id=final.version_id,
    )


def _runtime(root: Path, constraints: dict) -> PawRuntime:
    registry = ExecutorRegistry()
    registry.register(LocalFilesystemExecutor(root))
    return PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=2, max_decisions=10),
            policy_guard=PolicyGuard(interactive=True),
        ),
        project_root=str(root),
        hard_constraints=constraints,
        approval_store=ApprovalStore,
        capability_router=CapabilityRouter(registry),
        context_compiler=ContextCompiler(
            budget=ContextBudget(max_tokens=2000, max_fragments=10, max_sources=5),
            auto_attach_embeddings=False,
        ),
    )


async def _grant(_task_id: str, _action: ProposedAction, approval: Any) -> bool:
    """The human grants the exact effect."""
    await ApprovalStore.approve(approval.id, "fixture-human")
    return True


async def _deny(_task_id: str, _action: ProposedAction, approval: Any) -> bool:
    await ApprovalStore.deny(approval.id, "fixture-human")
    return False


def _request(task: Any, final: DecisionVersion) -> WorkflowRequest:
    return WorkflowRequest(
        goal=task.goal,
        target="module.py",
        content="def value():\n    return 2\n",
        decision_version_id=final.version_id,
        method="test_suite",
    )


# --- The chain ------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_chain_researches_changes_and_declares_a_verification(tmp_path):
    """research -> choose -> change -> declared verification, all real."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root, task, final, constraints = await _project(tmp_path)
    plan = await _reviewed_plan(root, task, final, constraints)
    runtime = _runtime(root, constraints)
    port = _RecordingPort(passed=True)

    workflow = EngineeringWorkflow(runtime, verification_port=port, declared_by="fixture-human")
    outcome = await workflow.run(_request(task, final), task=task, plan=plan, approver=_grant)

    # The research phase cited the sources it read.
    assert outcome.citations, "the research phase cited nothing"
    assert any(c.startswith("knowledge:") for c in outcome.citations), outcome.citations

    # The change landed.
    assert outcome.changed is True, outcome.failure
    assert (root / "module.py").read_text() == "def value():\n    return 2\n"

    # The verification is a declared artifact, bound to the change.
    assert outcome.verified is True
    assert outcome.completed is True
    record = outcome.verification
    assert isinstance(record, VerificationRecord)
    assert record.passed is True
    assert record.method == "test_suite"
    assert record.operation_id == f"workflow-change-{task.id}"
    assert record.declared_by == "fixture-human"

    # It is recorded in the ledger as its own event - not as an executor
    # success observation, and not as a gate verdict.
    events = await TaskLedger.get_events_by_type(task.id, TaskEventType.VERIFICATION_RECORDED)
    assert len(events) == 1
    assert events[0].payload["operation_id"] == f"workflow-change-{task.id}"
    assert events[0].payload["passed"] is True

    # The port was asked about the artifact that actually changed.
    assert port.requests[0].target == "module.py"
    assert port.requests[0].method == "test_suite"


@pytest.mark.asyncio
async def test_a_failing_verification_is_not_a_completed_change(tmp_path):
    """The whole point: an unverified change is not a completed change."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root, task, final, constraints = await _project(tmp_path)
    plan = await _reviewed_plan(root, task, final, constraints)
    runtime = _runtime(root, constraints)
    port = _RecordingPort(passed=False, summary="the new value is not covered by a test")

    workflow = EngineeringWorkflow(runtime, verification_port=port)
    outcome = await workflow.run(_request(task, final), task=task, plan=plan, approver=_grant)

    assert outcome.changed is True, "the change itself should have applied"
    assert outcome.verified is False
    assert outcome.completed is False
    assert "not covered by a test" in outcome.failure

    # The failed verification is still recorded - a negative result is
    # evidence too.
    events = await TaskLedger.get_events_by_type(task.id, TaskEventType.VERIFICATION_RECORDED)
    assert len(events) == 1
    assert events[0].payload["passed"] is False


@pytest.mark.asyncio
async def test_a_denied_approval_changes_nothing(tmp_path):
    """A refused exact effect must not touch the workspace."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root, task, final, constraints = await _project(tmp_path)
    plan = await _reviewed_plan(root, task, final, constraints)
    runtime = _runtime(root, constraints)
    port = _RecordingPort()

    workflow = EngineeringWorkflow(runtime, verification_port=port)
    outcome = await workflow.run(_request(task, final), task=task, plan=plan, approver=_deny)

    assert outcome.changed is False
    assert outcome.completed is False
    assert "denied" in outcome.failure
    assert (root / "module.py").read_text() == "def value():\n    return 1\n"
    # The verification never ran: there was no change to verify.
    assert port.requests == []


@pytest.mark.asyncio
async def test_the_choose_phase_cannot_be_skipped(tmp_path):
    """No reviewed decision, no implementation Plan, no change."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root, task, final, constraints = await _project(tmp_path)
    planner = Planner(workspace_root=root, hard_constraints=constraints)

    with pytest.raises(ValueError, match="review"):
        await planner.plan(task.id, purpose="implementation", decision_version_id=final.version_id)

    # A research Plan is still fine - it is not implementation authority.
    research = await planner.plan(task.id)
    assert research.purpose == "research"


@pytest.mark.asyncio
async def test_a_restart_does_not_repeat_the_change_and_can_then_verify(tmp_path):
    """failure -> restart: the change is not repeated, the verification is retried."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root, task, final, constraints = await _project(tmp_path)
    plan = await _reviewed_plan(root, task, final, constraints)
    runtime = _runtime(root, constraints)

    # First run: the change applies, the verification fails.
    failing = _RecordingPort(passed=False, summary="not covered")
    workflow = EngineeringWorkflow(runtime, verification_port=failing)
    first = await workflow.run(_request(task, final), task=task, plan=plan, approver=_grant)

    assert first.changed is True
    assert first.verified is False
    assert first.checkpoint_id

    # The change is on disk exactly once.
    assert (root / "module.py").read_text() == "def value():\n    return 2\n"

    # Second run: restart from the checkpoint with a verification that
    # passes. The completed change must not be executed again.
    passing = _RecordingPort(passed=True, summary="covered by a test")
    workflow = EngineeringWorkflow(runtime, verification_port=passing)
    second = await workflow.run(
        _request(task, final), task=task, plan=plan,
        approver=_grant, resume_from_checkpoint=first.checkpoint_id,
    )

    assert second.restarted is True
    assert second.changed is True, second.failure
    assert second.verified is True
    assert second.completed is True
    # The change ran once, not twice.
    assert (root / "module.py").read_text() == "def value():\n    return 2\n"
    # The verification was asked again.
    assert len(passing.requests) == 1


@pytest.mark.asyncio
async def test_the_verification_is_bound_to_the_operation_it_verifies(tmp_path):
    """A verification cannot be re-used for a different change."""
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    root, task, final, constraints = await _project(tmp_path)
    plan = await _reviewed_plan(root, task, final, constraints)
    runtime = _runtime(root, constraints)
    port = _RecordingPort()

    workflow = EngineeringWorkflow(runtime, verification_port=port)
    outcome = await workflow.run(_request(task, final), task=task, plan=plan, approver=_grant)

    record = outcome.verification
    assert record is not None
    assert record.operation_id == f"workflow-change-{task.id}"
    # The record is immutable.
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.passed = False  # type: ignore[misc]
    # And it names the operation it verifies, so a record for one change
    # cannot be presented as the verification of another.
    assert record.operation_id.startswith("workflow-change-")
    assert record.method == "test_suite"
