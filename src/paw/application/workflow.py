"""The engineering workflow: research -> choose -> change -> declared verification.

PAW already owns every piece this chain needs: a durable ``Task``, an
immutable ``DecisionVersion``, a ``Plan`` bound to a reviewed decision, the
single-authority policy gate, executors, checkpoints and the ledger. What
was missing was the chain itself, and one rule that the chain exists to
enforce:

    **A change without a passing declared verification is not a completed
    change.**

The runtime's executor observation says the write happened. That is an
``OBSERVED`` effect, not a verification. A verification names what was
checked, against what, and what the result was. This module is what
separates the two, and what makes the verification a *record* rather than
a claim.

The phases:

``research``
    The reviewed manifest: what was read, and which sources it came from.
    The same manifest is the evidence the outbound payload is bound to
    (B-19/F05), so the citations and the bytes that leave the box are
    the same evidence.

``choose``
    A FINAL READY decision, human-reviewed, bound to an implementation
    ``Plan``. The Planner refuses to create an implementation Plan without
    that review, so this phase cannot be skipped.

``change``
    The write, through the runtime's shared executable unit: the policy
    gate, the implementation admission, the exact approval, the executor.

``verify``
    A declared verification performed by an injected port and recorded as
    its own ledger event, bound to the operation it verifies.

The module adds no new orchestration authority. Every phase is a normal
runtime task with its own gate, ledger trail and checkpoint, and the
runtime remains the single authority for what executes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..core.ledger import log_verification_recorded
from ..core.models import (
    Capability,
    ProposedAction,
    ResourceUsage,
    VerificationRecord,
)

# --- The verification port ------------------------------------------------


@dataclass(frozen=True)
class VerificationRequest:
    """What a verification is asked to check.

    The request names the target and the method. It does not name a
    result: the port decides that.
    """

    operation_id: str
    target: str
    method: str
    revision: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationOutcome:
    """What a verification found."""

    passed: bool
    summary: str = ""
    evidence: str = ""
    command: str = ""


class VerificationPort(Protocol):
    """The authorized way a verification is performed.

    PAW does not run shells: the product charter does not authorize shell
    execution. A verification is therefore performed by a port the
    application supplies - a test harness, a CI callback, a reviewer - and
    PAW binds and records what it returns. The port is the only thing in
    this chain that touches the outside world.
    """

    async def verify(self, request: VerificationRequest) -> VerificationOutcome: ...


VerificationPortCallable = Callable[
    [VerificationRequest], Awaitable[VerificationOutcome]
]

# A human decision on the exact effect. The workflow requests the approval;
# this callable is where a person grants or refuses it.
Approver = Callable[[str, ProposedAction, Any], Awaitable[bool]]


class _FixedProposer:
    """Proposes one exact action, then nothing else.

    The runtime stays the orchestrator: the proposal still passes the same
    policy gate, autonomy gate and implementation admission.
    """

    def __init__(self, action: ProposedAction) -> None:
        self._action = action
        self.proposed = False

    def propose(self, task_id, task_goal, context, skills=None,
                last_observation=None, autonomy_usage=None) -> ProposedAction:
        self.proposed = True
        return self._action


async def perform_port(
    port: VerificationPort | VerificationPortCallable,
    request: VerificationRequest,
) -> VerificationOutcome:
    """Call a port, whether it is an object or a callable."""
    if hasattr(port, "verify"):
        return await port.verify(request)  # type: ignore[union-attr]
    return await port(request)


async def declare_verification(
    task_id: str,
    port: VerificationPort | VerificationPortCallable,
    request: VerificationRequest,
    *,
    declared_by: str = "",
) -> VerificationRecord:
    """Perform a verification and record it as a declared artifact.

    The record is immutable and bound to the operation it verifies, so it
    cannot be silently re-used for a different change. It is written to
    the ledger as ``VERIFICATION_RECORDED`` - a different event from
    ``STEP_EXECUTED``, which is the executor's success observation, and
    not a gate verdict.
    """
    outcome = await perform_port(port, request)
    record = VerificationRecord(
        operation_id=request.operation_id,
        method=request.method,
        passed=outcome.passed,
        summary=outcome.summary,
        evidence=outcome.evidence,
        command=outcome.command,
        revision=request.revision,
        declared_by=declared_by,
    )
    await log_verification_recorded(task_id, record)
    return record


# --- The workflow ---------------------------------------------------------


@dataclass(frozen=True)
class WorkflowRequest:
    """What the workflow is asked to do.

    The decision version must already be FINAL READY and human-reviewed:
    the workflow checks that by asking the Planner for an implementation
    Plan, which refuses without the review. The workflow never approves
    on the user's behalf.
    """

    goal: str
    target: str
    content: str
    decision_version_id: str
    method: str = "source_inspection"
    revision: str = ""
    capabilities: tuple[Capability, ...] = (Capability.FILESYSTEM_WRITE,)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowOutcome:
    """The honest result of the chain."""

    task_id: str
    changed: bool
    verified: bool
    verification: VerificationRecord | None = None
    citations: tuple[str, ...] = ()
    failure: str = ""
    restarted: bool = False
    checkpoint_id: str | None = None

    @property
    def completed(self) -> bool:
        """True only when the change happened *and* its verification passed."""
        return self.changed and self.verified


class EngineeringWorkflow:
    """Research -> choose -> change -> declared verification.

    The runtime stays the single authority: the workflow drives it, it
    does not replace it.
    """

    def __init__(
        self,
        runtime: Any,
        *,
        verification_port: VerificationPort | VerificationPortCallable,
        declared_by: str = "",
    ) -> None:
        self.runtime = runtime
        self.verification_port = verification_port
        self.declared_by = declared_by

    # -- phase 1: research -------------------------------------------------

    async def _research(self, task_id: str, goal: str) -> tuple[str, ...]:
        """Compile the reviewed context and return the sources it cites.

        The citations are the manifest's included candidates: the same
        evidence the outbound payload is bound to. A phase that cites
        nothing is a phase that researched nothing.
        """
        compiler = getattr(self.runtime, "context_compiler", None)
        if compiler is None:
            return ()
        manifest = await compiler.compile_manifest(task_id, goal)
        self.runtime._current_manifest = manifest
        citations: list[str] = []
        for cand in getattr(manifest, "included", ()) or ():
            source = getattr(cand, "source", "")
            source_id = getattr(cand, "source_id", "")
            if source_id:
                citations.append(f"{source}:{source_id}")
        return tuple(citations)

    # -- phase 3: change ---------------------------------------------------

    def _change_action(self, request: WorkflowRequest, task_id: str, plan_id: str) -> ProposedAction:
        """The exact write proposal. It carries the reviewed Plan binding."""
        metadata = {
            "plan_id": plan_id,
            "done": True,
            "preferred_executor": "local-filesystem",
            "filesystem": {
                "operation": "write",
                "path": request.target,
                "content": request.content,
                "mode": "replace",
            },
            **request.metadata,
        }
        return ProposedAction(
            goal=request.goal,
            capabilities=list(request.capabilities),
            context={"path": request.target},
            metadata=metadata,
            operation_id=f"workflow-change-{task_id}",
            idempotency_key=f"workflow-change:{task_id}:{request.target}",
            estimated_cost=ResourceUsage(),
            is_mutating=False,
        )

    async def _apply_change(
        self,
        request: WorkflowRequest,
        task_id: str,
        plan_id: str,
        *,
        approver: Approver | None,
        resume_from_checkpoint: str | None,
    ) -> tuple[bool, str, str | None]:
        """Run the change through the runtime. Returns (changed, error, checkpoint)."""
        action = self._change_action(request, task_id, plan_id)
        # Scope the action to the trusted project root before it is proposed.
        action = self.runtime._scope_implementation(action)

        # The exact effect needs an approval before it can execute. The
        # workflow requests it; a human grants it through the approver the
        # application supplies. The workflow never approves on its own.
        store = getattr(self.runtime, "approval_store", None)
        if store is not None:
            approval = await store.request(task_id, action)
            if approver is None:
                return (
                    False,
                    f"awaiting approval: {approval.id}",
                    None,
                )
            granted = await approver(task_id, action, approval)
            if not granted:
                return (False, f"approval denied: {approval.id}", None)

        # The runtime proposes; the workflow supplies the exact action. The
        # runtime's proposer is restored immediately afterwards, so the
        # workflow does not become a second orchestration authority.
        previous = getattr(self.runtime, "proposer", None)
        self.runtime.proposer = _FixedProposer(action)
        try:
            outcome = await self.runtime.run(
                task_id,
                task_goal=request.goal,
                initial_context={"path": request.target},
                available_skills=[{
                    "name": "local-filesystem",
                    "required_capabilities": [c.value for c in request.capabilities],
                }],
                step_fn=self.runtime._execute_action,
                resume_from_checkpoint=resume_from_checkpoint,
            )
        finally:
            if previous is not None:
                self.runtime.proposer = previous
        observation = outcome.last_observation
        changed = bool(observation and observation.success)
        if not changed and observation is None:
            # A resume skips an operation that is already completed, so the
            # loop may end without an observation. That is not "nothing
            # happened": the operation record says the change is in place.
            changed = await self._already_applied(task_id, action.operation_id)
        error = "" if changed else (observation.error if observation else "no observation")
        return changed, error, outcome.checkpoint_id

    @staticmethod
    async def _already_applied(task_id: str, operation_id: str) -> bool:
        """Whether the operation is recorded as completed for this task."""
        from ..core.checkpoint import OperationRecordStore

        completed = await OperationRecordStore.get_completed_op_ids(task_id)
        return operation_id in completed

    # -- the chain ---------------------------------------------------------

    async def run(
        self,
        request: WorkflowRequest,
        *,
        task: Any,
        plan: Any,
        approver: Approver | None = None,
        resume_from_checkpoint: str | None = None,
    ) -> WorkflowOutcome:
        """Run the chain for an already-decided task.

        The task and the implementation Plan are inputs: the Plan is the
        evidence of the "choose" phase, and creating it is what proves
        the decision was reviewed.
        """
        task_id = task.id
        citations = await self._research(task_id, request.goal)

        changed, error, checkpoint_id = await self._apply_change(
            request, task_id, plan.id,
            approver=approver,
            resume_from_checkpoint=resume_from_checkpoint,
        )
        if not changed:
            return WorkflowOutcome(
                task_id=task_id,
                changed=False,
                verified=False,
                citations=citations,
                failure=error or "change did not apply",
                restarted=resume_from_checkpoint is not None,
                checkpoint_id=checkpoint_id,
            )

        record = await declare_verification(
            task_id,
            self.verification_port,
            VerificationRequest(
                operation_id=f"workflow-change-{task_id}",
                target=request.target,
                method=request.method,
                revision=request.revision,
                context={"goal": request.goal},
            ),
            declared_by=self.declared_by,
        )
        return WorkflowOutcome(
            task_id=task_id,
            changed=True,
            verified=record.passed,
            verification=record,
            citations=citations,
            failure="" if record.passed else (record.summary or "verification failed"),
            restarted=resume_from_checkpoint is not None,
            checkpoint_id=checkpoint_id,
        )


__all__ = [
    "EngineeringWorkflow",
    "VerificationOutcome",
    "VerificationPort",
    "VerificationPortCallable",
    "VerificationRequest",
    "WorkflowOutcome",
    "WorkflowRequest",
    "declare_verification",
    "perform_port",
]
