"""The engineering workflow, end to end: research -> choose -> change -> verify.

This demo runs the chain PAW is actually for, over a real throwaway
project, with real subsystems:

  research  the reviewed manifest over the ingested project
  choose    a FINAL READY decision, human-reviewed, bound to an implementation Plan
  change    the write, through the policy gate and the implementation admission
  verify    a declared verification, performed by the port below and recorded

The verification port is the only substitute in the whole demo. PAW does
not run shells - the product charter does not authorize shell execution -
so the port stands in for the engineering process that performs the
check. Here it is a real check: the demo reads the changed file back and
asserts that it contains what was written.

Run it:

    python -m demos.demo_engineering_workflow
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from paw.application.workflow import (
    EngineeringWorkflow,
    VerificationOutcome,
    VerificationRequest,
    WorkflowRequest,
)
from paw.core.approval import ApprovalStore
from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCompiler
from paw.core.executor import CapabilityRouter, ExecutorRegistry
from paw.core.models import ProposedAction
from paw.core.planner import Planner
from paw.core.policy import PolicyGuard
from paw.core.reasoning_contracts import DecisionVersion
from paw.core.repo_scanner import RepoFilter
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager
from paw.executors.filesystem import LocalFilesystemExecutor
from paw.knowledge.checksum import compute_repo_revision
from paw.knowledge.chunk import KnowledgeChunkStore
from paw.knowledge.source import KnowledgeSourceManager

ORIGINAL = "def value():\n    return 1\n"
REPLACEMENT = "def value():\n    return 2\n"


class FileContentVerification:
    """A verification that reads the changed file back.

    This is a *declared* verification: it names what it checked, against
    what, and what it found. It is not an executor's success observation
    - the executor already said the write happened.
    """

    def __init__(self, root: Path, expected: str) -> None:
        self.root = root
        self.expected = expected

    async def verify(self, request: VerificationRequest) -> VerificationOutcome:
        target = self.root / request.target
        if not target.exists():
            return VerificationOutcome(
                passed=False,
                summary=f"{request.target} does not exist",
                evidence="file not found",
            )
        content = target.read_text(encoding="utf-8", errors="replace")
        passed = self.expected in content
        return VerificationOutcome(
            passed=passed,
            summary=(
                f"{request.target} contains the expected content"
                if passed
                else f"{request.target} does not contain the expected content"
            ),
            evidence=content[:400],
            command=f"assert {self.expected!r} in {request.target}",
        )


class TestSuiteVerification:
    """A verification that runs the project's **own** test suite.

    This is the real harness the workflow's verification port exists for.
    It lives in the *application*, not in ``paw/``: the product charter
    does not authorize shell execution, and PAW's own runtime layers
    never spawn a process (``tests/test_no_shell_execution_in_runtime.py``
    checks that mechanically). The application supplies the port; the
    application may run whatever it needs to.

    The suite is run with an argv list and ``shell=False``.
    """

    def __init__(self, root: Path, timeout: int = 300) -> None:
        self.root = root
        self.timeout = timeout
        self.runs: list[dict] = []

    async def verify(self, request: VerificationRequest) -> VerificationOutcome:
        import subprocess
        import sys

        command = [sys.executable, "-m", "pytest", "-q", "--no-header",
                   "-p", "no:cacheprovider", str(self.root)]
        completed = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=str(self.root),
            shell=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        passed = completed.returncode == 0
        self.runs.append({"command": command, "returncode": completed.returncode})
        tail = "\n".join(output.strip().splitlines()[-6:])
        return VerificationOutcome(
            passed=passed,
            summary=(
                f"the project's own test suite {'passed' if passed else 'failed'}"
                f" (exit {completed.returncode})"
            ),
            evidence=tail[:2000],
            command=" ".join(command),
        )


async def _ingest(root: Path) -> int:
    """Ingest the project so the research phase has real content to find."""
    sources, chunks = KnowledgeSourceManager(), KnowledgeChunkStore()
    total = 0
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root))
        content = path.read_text(encoding="utf-8", errors="replace")
        source = await sources.create(
            name=rel, path=rel, external_id=rel, revision="demo-1",
        )
        await chunks.add_chunk(
            source_id=source.id, content=content,
            span_start=0, span_end=len(content), metadata={"file": rel},
        )
        total += 1
    return total


async def _grant(_task_id: str, _action: ProposedAction, approval) -> bool:
    """The human grants the exact effect."""
    await ApprovalStore.approve(approval.id, "demo-human")
    return True


async def run_demo(work_dir: str | Path | None = None) -> dict:
    work_dir = Path(work_dir or tempfile.mkdtemp(prefix="paw-workflow-"))
    root = work_dir / "project"
    root.mkdir(parents=True, exist_ok=True)
    (root / "module.py").write_text(ORIGINAL)
    # The project's own test suite. It asserts the *new* behaviour, so it
    # is red before the change and green after it. This is what the
    # verification port will run.
    (root / "test_module.py").write_text(
        "from module import value\n\n\n"
        "def test_value_is_raised():\n"
        "    assert value() == 2\n"
    )
    # A second test that needs an environment marker. It is red until the
    # marker exists, which is the realistic "the change is right but the
    # environment is not ready" failure the restart then clears.
    (root / "test_environment.py").write_text(
        "from pathlib import Path\n\n\n"
        "def test_environment_is_ready():\n"
        "    assert Path('environment.marker').exists()\n"
    )

    await set_db_path(work_dir / "demo.db")
    await db.initialize()

    ingested = await _ingest(root)

    task = await TaskManager.create("session-demo", "raise the value returned by value()")
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

    # The human reviews the decision. The Planner refuses an implementation
    # Plan without it.
    review = await ApprovalStore.request_decision_review(final.version_id)
    await ApprovalStore.approve(review.id, "demo-human")
    plan = await Planner(workspace_root=root, hard_constraints=constraints).plan(
        task.id, purpose="implementation", decision_version_id=final.version_id,
    )

    registry = ExecutorRegistry()
    registry.register(LocalFilesystemExecutor(root))
    runtime = PawRuntime(
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

    workflow = EngineeringWorkflow(
        runtime,
        verification_port=TestSuiteVerification(root),
        declared_by="demo-human",
    )
    request = WorkflowRequest(
        goal=task.goal,
        target="module.py",
        content=REPLACEMENT,
        decision_version_id=final.version_id,
        # The declared verification names the check that was actually
        # performed. A record that mislabels its method is not evidence.
        method="target_test_suite",
    )

    # First pass: the change applies, then the project's own test suite is
    # run. It is still red because a second test depends on an
    # environment marker that nobody has created yet - a realistic
    # "the change is right but the environment is not ready" failure.
    first = await EngineeringWorkflow(
        runtime, verification_port=TestSuiteVerification(root), declared_by="demo-human",
    ).run(request, task=task, plan=plan, approver=_grant)

    # The human fixes the environment: the marker the second test needs.
    (root / "environment.marker").write_text("ready\n")

    # Second pass: restart from the checkpoint. The completed change is
    # not repeated; the test suite is run again and now passes.
    second = await workflow.run(
        request, task=task, plan=plan, approver=_grant,
        resume_from_checkpoint=first.checkpoint_id,
    )

    report = {
        "work_dir": str(work_dir),
        "ingested_files": ingested,
        "citations": list(second.citations),
        "first_pass": {
            "changed": first.changed,
            "verified": first.verified,
            "failure": first.failure,
        },
        "restart": {
            "restarted": second.restarted,
            "changed": second.changed,
            "verified": second.verified,
            "completed": second.completed,
        },
        "file_after": (root / "module.py").read_text(encoding="utf-8"),
        "verification": second.verification.to_dict() if second.verification else None,
    }
    await db.close()
    return report


async def _main() -> int:
    report = await run_demo()
    print(json.dumps(report, indent=2, default=str))
    shutil.rmtree(report["work_dir"], ignore_errors=True)
    return 0 if report["restart"]["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
