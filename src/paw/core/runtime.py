"""
PAW Core — Runtime Loop (Phase 19 + Agent Integration)

Unified black-box execution entry point with full observability, checkpointing,
and replay safety.

``PawRuntime.run`` drives the autonomy loop. It is the ONE place the whole
runtime loop is orchestrated, so integration tests call ``run`` as a black
box instead of re-implementing the loop and asserting on every subsystem.

Loop contract (per the PAW constitution):
  * The single policy authority is consulted — together with the autonomy
    controller — for the PROPOSED action's capabilities, BEFORE any side
    effect. ``ASK``/``DENY`` never map to execution.
  * An ``ActionProposer`` produces the next ``ProposedAction`` from state.
  * ``step_fn`` receives the full ``ProposedAction`` and returns an
    ``ExecutionObservation`` (typed, not arbitrary dict).
  * Resources are tracked per-resource-type (model, tool, tokens, wall time,
    network, destructive).
  * Completed primitive operations are recorded as ``OperationRecord`` for
    idempotent replay safety.
  * Checkpoints are created at intervals and on pause/resume.
  * Every decision is logged to ``TaskLedger`` for full audit trail.

Agent integration (``PawRuntime.run_agent``)
--------------------------------------------
``run_agent`` turns ``PawRuntime`` into the TRUE integration point that wires
every PAW subsystem into one feedback loop:

    TaskGraph (DAG)  ->  ContextCompiler  ->  SkillFabric
        ^                                            |
        |                                            v
        +-- Observation <-- Policy Gate <-- Autonomy Gate <--+
                            |
                            v
                       ModelRouter -> ModelExecutor
                            |
                            v
                    TaskLedger + CheckpointManager

At each iteration ``run_agent``:
  1. compiles context (ContextCompiler) from memory/knowledge/skills/ledger
  2. selects relevant skills (SkillFabric + semantic selector)
  3. creates a side-effect-free proposal from skills and compiled context
  4. gates the proposed action through Policy (single authority) + Autonomy
  5. routes/executes the approved model and action via the selected executor
  6. observes the result, feeds it back into context, logs to ledger,
     checkpoints, and repeats until completion / stop.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from .autonomy import AutonomyController, AutonomyDecision, StopReason
from .checkpoint import CheckpointManager, OperationRecordStore
from .executor import CapabilityRouter, get_capability_router
from .ledger import (
    TaskEventType,
    TaskLedger,
    log_autonomy_gate_evaluated,
    log_checkpoint_created,
    log_checkpoint_restored,
    log_operation_recorded,
    log_policy_gate_evaluated,
    log_step_completed,
    log_step_executed,
    log_step_proposed,
    log_task_completed,
)
from .logging import get_logger
from .models import (
    Capability,
    ExecutionObservation,
    PolicyDecision,
    ProposedAction,
    ResourceUsage,
    TaskStatus,
)
from .policy import RequestVerdict
from .task import TaskManager
from .task_scheduler import TaskScheduleStatus

logger = get_logger(__name__)


# --- Action Proposer ---

class ActionProposer:
    """
    Generates the next ProposedAction from runtime state.

    This is the single source of truth for what action to take next.
    It can be replaced or extended for different execution strategies
    (planning, reactive, skill-driven, etc.).
    """

    def __init__(
        self,
        *,
        default_role: str = "fast",
        max_proposals: int = 1,
    ):
        self.default_role = default_role
        self.max_proposals = max_proposals
        self._proposal_count = 0

    def propose(
        self,
        task_id: str,
        task_goal: str,
        context: dict[str, Any],
        skills: list[dict[str, Any]] | None = None,
        last_observation: ExecutionObservation | None = None,
        autonomy_usage: dict[str, Any] | None = None,
    ) -> ProposedAction:
        """
        Produce the next proposed action.

        Args:
            task_id: The task identifier.
            task_goal: The high-level goal of the task.
            context: Current compiled context (memories, knowledge, skills).
            skills: Available skills for this task.
            last_observation: Previous step's observation for continuity.
            autonomy_usage: Current autonomy budget usage.

        Returns:
            ProposedAction with goal, required capabilities, context, and metadata.
        """
        self._proposal_count += 1

        # Determine capabilities needed based on context/skills
        capabilities: list[Capability] = []
        if skills:
            for skill in skills:
                # Skills declare their required capabilities
                required = skill.get("required_capabilities", [])
                for cap in required:
                    if cap not in capabilities:
                        capabilities.append(Capability(cap))

        # Default to filesystem read if no capabilities specified
        if not capabilities:
            capabilities = [Capability.FILESYSTEM_READ]

        # Build metadata
        metadata = {
            "proposal_number": self._proposal_count,
            "task_goal": task_goal,
            "available_skills": [s.get("name") for s in (skills or [])],
            "has_last_observation": last_observation is not None,
        }

        # Estimate cost based on capabilities
        estimated_cost = self._estimate_cost(capabilities)

        return ProposedAction(
            goal=task_goal,
            capabilities=capabilities,
            context=context,
            metadata=metadata,
            operation_id=f"op_{task_id}_{self._proposal_count}",
            estimated_cost=estimated_cost,
        )

    def _estimate_cost(self, capabilities: list[Capability]) -> ResourceUsage:
        """Estimate resource cost for a set of capabilities."""
        # Base cost per capability type
        costs = {
            Capability.FILESYSTEM_READ: ResourceUsage(model_calls=0, tool_calls=1, tokens=100),
            Capability.FILESYSTEM_WRITE: ResourceUsage(model_calls=0, tool_calls=1, tokens=200, destructive_ops=1),
            Capability.FILESYSTEM_DELETE: ResourceUsage(model_calls=0, tool_calls=1, tokens=100, destructive_ops=2),
            Capability.SHELL_EXECUTE: ResourceUsage(model_calls=0, tool_calls=1, tokens=500, destructive_ops=5),
            Capability.NETWORK_HTTP: ResourceUsage(model_calls=0, tool_calls=1, tokens=200, network_bytes=1024),
            Capability.PROCESS_SPAWN: ResourceUsage(model_calls=0, tool_calls=1, tokens=500, destructive_ops=3),
            Capability.GIT_READ: ResourceUsage(model_calls=0, tool_calls=1, tokens=100),
            Capability.GIT_WRITE: ResourceUsage(model_calls=0, tool_calls=1, tokens=200, destructive_ops=2),
            Capability.SECRETS_READ: ResourceUsage(model_calls=0, tool_calls=1, tokens=100),
            Capability.DESTRUCTIVE: ResourceUsage(destructive_ops=10),
            Capability.FINANCIAL: ResourceUsage(destructive_ops=5),
        }

        total = ResourceUsage()
        for cap in capabilities:
            if cap in costs:
                total += costs[cap]

        # Add base model call cost
        total.model_calls = 1
        total.tokens += 1000

        return total


# --- Agent Action Proposer (real subsystem wiring) ---

class AgentActionProposer:
    """
    The agent "brain": produces the next ``ProposedAction`` from the real PAW
    context and skill subsystems. It is the single source of truth for the next
    action when ``PawRuntime`` runs as a genuine agent loop (``run_agent``).

    Proposal is intentionally pure. The returned action carries the selected
    skill and required capabilities for the policy gate; ModelRouter and
    ModelExecutor are invoked only by the approved execution stage.

    Offline / local-first note: when no real LLM provider is reachable the
    ``ModelExecutor`` resolves to ``LocalModelExecutor`` (deterministic echo),
    so the loop still completes end-to-end without an external model server.
    """

    def __init__(
        self,
        context_compiler: Any,
        model_router: Any,
        model_executor: Any,
        skill_fabric: Any | None = None,
        *,
        default_role: str = "fast",
        execution_profile: Any | None = None,
        session_id: str | None = None,
        complexity: str = "medium",
        privacy_required: bool = False,
    ):
        self.context_compiler = context_compiler
        self.model_router = model_router
        self.model_executor = model_executor
        self.skill_fabric = skill_fabric
        self.default_role = default_role
        self.execution_profile = execution_profile
        self.session_id = session_id
        self.complexity = complexity
        self.privacy_required = privacy_required
        self._proposal_count = 0

    async def propose(
        self,
        task_id: str,
        task_goal: str,
        context: Any = None,
        candidates: list[Any] | None = None,
        last_observation: ExecutionObservation | None = None,
        autonomy_usage: dict[str, Any] | None = None,
    ) -> ProposedAction:
        """
        Consult the subsystems and produce the next action.

        The runtime loop owns ContextCompiler and passes the already-compiled
        ``context`` (a ``TaskContext``) plus ``candidates`` into this method.
        Proposal is deliberately side-effect free: model/provider routing and
        inference happen only after the runtime policy gate in
        :meth:`PawRuntime._execute_action`.

        Pipeline:
          1. SkillFabric / semantic selector -> selected skill manifest(s)
          2. selected skills + context -> ProposedAction (goal/capabilities)
          3. policy/autonomy gate -> execution stage performs model/tool calls
        """
        self._proposal_count += 1

        compiled_ctx = context
        if candidates is None:
            candidates = _candidates_from_context(context)

        # --- 1. Select skills (from compiled candidates or SkillFabric) ---
        selected_skills = await self._select_skills(task_goal, candidates)

        # --- 2. Build a typed proposal (no provider/model side effect) ---
        model_result: dict[str, Any] = {}
        return self._to_proposed_action(
            task_id, task_goal, model_result, selected_skills, compiled_ctx
        )

    async def _select_skills(
        self, task_goal: str, candidates: list[Any]
    ) -> list[dict[str, Any]]:
        """Pick skill candidates relevant to the goal.

        Skills come from two sources:
          * compiled context candidates (``source == "skill"``) — these already
            carry a relevance score from the ContextCompiler / semantic selector;
          * the SkillFabric registry (defensive fallback / broader recall).

        Each candidate is (re)scored for goal relevance so the agent prefers the
        skill that actually matches what the user asked for (e.g. "echo a
        greeting" -> the ``echo`` skill) rather than an arbitrary first match.
        """
        goal_l = task_goal.lower()
        scored: dict[str, dict[str, Any]] = {}

        def _score(name: str, trigger: str, base: float) -> float:
            s = base
            if name and name.lower() in goal_l:
                s += 0.5
            if trigger and trigger.lower() and trigger.lower() in goal_l:
                s += 0.3
            # Token overlap between goal and name
            for tok in name.lower().split("_"):
                if len(tok) > 2 and tok in goal_l:
                    s += 0.1
            return s

        # 1. Compiled-context skill candidates (carry compiler relevance score)
        for c in candidates:
            if getattr(c, "source", "") != "skill":
                continue
            meta = getattr(c, "metadata", {}) or {}
            name = c.source_id
            if name in scored:
                continue
            base = float(getattr(c, "relevance_score", 0.0))
            scored[name] = {
                "name": name,
                "category": meta.get("category", ""),
                "risk": meta.get("risk", "low"),
                "capabilities": meta.get("capabilities", []),
                "relevance_score": _score(name, meta.get("trigger", ""), base),
            }

        # 2. SkillFabric registry (broader recall), merged without double-counting
        if self.skill_fabric is not None:
            try:
                for m in self.skill_fabric.list_skills():
                    name = m.name
                    if name in scored:
                        continue
                    trigger = getattr(m, "trigger", "") or ""
                    scored[name] = {
                        "name": name,
                        "category": m.category,
                        "risk": m.risk.value if hasattr(m.risk, "value") else str(m.risk),
                        "capabilities": [c.value for c in m.capabilities],
                        "relevance_score": _score(name, trigger, 0.4),
                    }
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("agent_skill_select_failed", error=str(exc))

        # Rank by goal relevance, keep top-k.
        ranked = sorted(scored.values(), key=lambda s: s["relevance_score"], reverse=True)
        return ranked[:3]

    def _build_messages(
        self,
        task_goal: str,
        compiled_ctx: Any,
        last_observation: ExecutionObservation | None,
        selected_skills: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Construct the conversation messages for the model call."""
        system = (
            "You are the planning brain of PAW (Personal Agent Workstation). "
            "Given the task goal, the compiled context, and the available skills, "
            "decide the next concrete action. Prefer reusing an available skill. "
            "Respond with a short plan and whether the task is complete."
        )
        context_text = ""
        try:
            frags = getattr(compiled_ctx, "fragments", []) or []
            context_text = "\n\n".join(
                getattr(f, "content", "") for f in frags
            )[:4000]
        except Exception:  # pragma: no cover - defensive
            context_text = ""

        skill_text = ", ".join(s.get("name", "") for s in selected_skills) or "none"

        user_parts = [
            f"GOAL: {task_goal}",
            f"AVAILABLE SKILLS: {skill_text}",
            f"COMPILED CONTEXT:\n{context_text}",
        ]
        if last_observation is not None:
            user_parts.append(
                f"LAST OBSERVATION: {json.dumps(_safe_obs(last_observation), default=str)[:1000]}"
            )
        user_parts.append("Next action (and is the task done?):")

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    def _to_proposed_action(
        self,
        task_id: str,
        task_goal: str,
        model_result: dict[str, Any],
        selected_skills: list[dict[str, Any]],
        compiled_ctx: Any,
    ) -> ProposedAction:
        """Parse the model result into a ``ProposedAction``."""
        response = str(model_result.get("response", ""))
        done = bool(model_result.get("done", False))

        # Capabilities come from the selected skill(s); default to read.
        capabilities: list[Capability] = []
        for s in selected_skills:
            for cap in s.get("capabilities", []):
                try:
                    capabilities.append(Capability(cap))
                except Exception:
                    capabilities.append(Capability.FILESYSTEM_READ)
        if not capabilities:
            capabilities = [Capability.FILESYSTEM_READ]

        selected_skill_name = selected_skills[0].get("name") if selected_skills else None

        metadata = {
            "proposal_number": self._proposal_count,
            "task_goal": task_goal,
            "selected_skill": selected_skill_name,
            "available_skills": [s.get("name") for s in selected_skills],
            "model_response": response[:500],
            "done": done,
        }

        return ProposedAction(
            goal=task_goal,
            capabilities=capabilities,
            context={"compiled_context": _context_summary(compiled_ctx)},
            metadata=metadata,
            operation_id=f"op_{task_id}_{self._proposal_count}",
            estimated_cost=ResourceUsage(model_calls=1, tool_calls=len(selected_skills)),
        )


def _safe_obs(obs: ExecutionObservation) -> dict[str, Any]:
    try:
        return obs.to_dict()
    except Exception:
        return {"success": getattr(obs, "success", None)}


def _candidates_from_context(context: Any) -> list[Any]:
    """Extract skill candidates from a compiled TaskContext (best-effort)."""
    if context is None:
        return []
    frags = getattr(context, "fragments", None)
    if not frags:
        return []
    out = []
    for f in frags:
        src = getattr(f, "source", "")
        if src == "skill":
            # Wrap a ContextFragment as a candidate-like object.
            class _C:
                source = "skill"
                source_id = getattr(f, "source_id", "")
                relevance_score = getattr(f, "relevance_score", 0.0)
                metadata = getattr(f, "metadata", {}) or {}
            out.append(_C())
    return out


def _token_count_from_context(context: Any) -> int:
    """Best-effort token count extraction from a compiled context."""
    if context is None:
        return 0
    return int(getattr(context, "token_count", 0) or 0)


def _context_summary(compiled_ctx: Any) -> dict[str, Any]:
    try:
        return {
            "fragment_count": len(getattr(compiled_ctx, "fragments", []) or []),
            "token_estimate": getattr(compiled_ctx, "token_count", 0),
        }
    except Exception:
        return {}


# --- Runtime Outcome ---

@dataclass
class RuntimeOutcome:
    """Result of a ``PawRuntime.run`` / ``run_agent`` invocation."""

    stopped: bool
    reason: StopReason | str | None
    step_called: bool
    iterations: int = 0
    waiting_for_approval: bool = False
    approval_id: str | None = None
    decision: AutonomyDecision | str | None = None
    last_observation: ExecutionObservation | None = None
    checkpoint_id: str | None = None
    operations_completed: int = 0
    # Agent-loop extras
    model_selections: list[str] = field(default_factory=list)
    skills_used: list[str] = field(default_factory=list)
    context_compiled: bool = False


# A step function receives the task id and the proposed action and returns an
# ExecutionObservation. Returning an observation with ``done=True`` signals
# task completion.
StepFn = Callable[[str, ProposedAction], Awaitable[ExecutionObservation]]

# A propose function produces the next ProposedAction from runtime state.
# It mirrors ``ActionProposer.propose`` but is async so the agent brain can
# consult the model / subsystems before deciding the next action. The runtime
# owns ContextCompiler and passes the already-compiled context (TaskContext)
# plus the compiled candidates into the proposer.
ProposeFn = Callable[
    [str, str, Any, list[Any] | None, ExecutionObservation | None, dict[str, Any] | None],
    Awaitable[ProposedAction],
]


class PawRuntime:
    """
    Black-box runtime loop with full observability and replay safety.

    This is the ONE place the whole runtime loop is orchestrated. It connects:

      * ``ActionProposer`` / ``AgentActionProposer`` (next action / brain)
      * ``PolicyGuard`` via ``AutonomyController`` (single authority gate)
      * ``AutonomyController`` (budget / progress / repetition / stall)
      * ``ContextCompiler`` (context assembly) — via ``run_agent``
      * ``SkillFabric`` (skill selection) — via ``run_agent``
      * ``ModelRouter`` + ``ModelExecutor`` (model routing/execution) — run_agent
      * ``TaskScheduler`` (TaskGraph DAG execution) — run_agent
      * ``TaskLedger`` (full audit trail)
      * ``CheckpointManager`` (durability / replay safety)

    Per iteration:
      1. Proposer produces ProposedAction from state.
      2. Policy gate (single authority) evaluates the action's capabilities.
      3. Autonomy gate evaluates budget/progress/repetition/stall.
      4. STOP / ASK / PAUSE / ESCALATE / DELEGATE -> return without calling
         ``step_fn`` (the loop never executes a gated-out action).
      5. CONTINUE -> invoke ``step_fn`` once, observe ExecutionObservation.
      6. Record OperationRecord for replay safety (if side effect).
      7. Maybe create checkpoint.
      8. Log to TaskLedger.
      9. Observation signals completion -> stop with TASK_COMPLETED.
    """

    def __init__(
        self,
        autonomy: AutonomyController,
        proposer: ActionProposer | None = None,
        checkpoint_mgr: CheckpointManager | None = None,
        *,
        # Agent-loop subsystems (optional for ``run``, required for ``run_agent``)
        context_compiler: Any | None = None,
        model_router: Any | None = None,
        model_executor: Any | None = None,
        skill_fabric: Any | None = None,
        capability_router: CapabilityRouter | None = None,
        approval_store: Any | None = None,
        task_scheduler: Any | None = None,
        max_iterations: int | None = None,
        checkpoint_interval: int = 5,
        auto_checkpoint: bool = True,
        default_role: str = "fast",
        complexity: str = "medium",
        privacy_required: bool = False,
        preferred_provider: str | None = None,
        execution_profile: Any | None = None,
    ):
        self.autonomy = autonomy
        self.proposer = proposer or ActionProposer()
        self.checkpoint_mgr = checkpoint_mgr or CheckpointManager()
        self.checkpoint_mgr.set_checkpoint_interval(checkpoint_interval)
        self.checkpoint_mgr.enable_auto_checkpoint(auto_checkpoint)

        # Agent-loop wiring
        self.context_compiler = context_compiler
        self.model_router = model_router
        self.model_executor = model_executor
        self.skill_fabric = skill_fabric
        self.capability_router = capability_router or get_capability_router()
        self.approval_store = approval_store
        self.task_scheduler = task_scheduler
        self.default_role = default_role
        self.complexity = complexity
        self.privacy_required = privacy_required
        self.preferred_provider = preferred_provider
        self.execution_profile = execution_profile or None

        self._max_iterations = max_iterations

    # ------------------------------------------------------------------
    # Public: black-box loop (user-supplied step_fn) — Phase 19 contract
    # ------------------------------------------------------------------

    async def run(
        self,
        task_id: str,
        *,
        task_goal: str,
        initial_context: dict[str, Any] | None = None,
        available_skills: list[dict[str, Any]] | None = None,
        step_fn: StepFn,
        resume_from_checkpoint: str | None = None,
    ) -> RuntimeOutcome:
        """
        Execute the autonomy loop for a task.

        Args:
            task_id: Task identifier.
            task_goal: High-level task goal.
            initial_context: Initial context (memories, knowledge, skills).
            available_skills: Skills available for this task.
            step_fn: Async function that executes a proposed action and returns
                     an ExecutionObservation.
            resume_from_checkpoint: Optional checkpoint ID to resume from.

        Returns:
            RuntimeOutcome with stop reason, iterations, and final observation.
        """
        async def _propose(
            tid: str,
            goal: str,
            ctx: Any,
            candidates: list[Any] | None,
            last_obs: ExecutionObservation | None,
            usage: dict[str, Any] | None,
        ) -> ProposedAction:
            return self.proposer.propose(
                task_id=tid,
                task_goal=goal,
                context=ctx,
                skills=available_skills,
                last_observation=last_obs,
                autonomy_usage=usage,
            )

        return await self._loop(
            task_id,
            task_goal=task_goal,
            propose_fn=_propose,
            step_fn=step_fn,
            initial_context=initial_context,
            available_skills=available_skills,
            resume_from_checkpoint=resume_from_checkpoint,
        )

    # ------------------------------------------------------------------
    # Public: TRUE agent loop — wires every PAW subsystem
    # ------------------------------------------------------------------

    async def run_agent(
        self,
        task_id: str,
        *,
        task_goal: str,
        session_id: str | None = None,
        project_id: str | None = None,
        execution_profile: Any | None = None,
        initial_context: dict[str, Any] | None = None,
        max_iterations: int | None = None,
        role: str | None = None,
        resume_from_checkpoint: str | None = None,
        # Optional injected "brain": given (goal, context, last_observation) it
        # returns the next ProposedAction. When omitted, the runtime wires the
        # real subsystems (ContextCompiler -> SkillFabric -> ModelRouter ->
        # ModelExecutor) as the brain.
        brain_fn: Callable[
            [str, str, dict[str, Any], ExecutionObservation | None],
            Awaitable[ProposedAction],
        ] | None = None,
    ) -> RuntimeOutcome:
        """
        Run the task as a genuine agent loop, wiring every PAW subsystem.

        This is the integration point that connects Context + TaskGraph +
        Autonomy + Policy + Execution + Observation + Ledger + Checkpoint into a
        single feedback loop. The next action is produced either by the
        injected ``brain_fn`` (real LLM) or by the built-in subsystem wiring
        (``AgentActionProposer``). The action is then executed via the selected
        skill / executor, observed, logged, and fed back into context.

        Requires ``context_compiler`` + ``model_router`` + ``model_executor`` to
        be set on the runtime; ``skill_fabric`` and ``task_scheduler`` are used
        when present (graceful degradation otherwise).
        """
        if self.context_compiler is None or self.model_router is None or self.model_executor is None:
            raise RuntimeError(
                "run_agent requires context_compiler, model_router, and "
                "model_executor to be set on PawRuntime"
            )

        # Context compilation must remain deterministic before policy. In
        # particular, do not auto-discover a remote embedding/provider during
        # the pre-gate phase of an agent loop.
        if hasattr(self.context_compiler, "auto_attach_embeddings"):
            self.context_compiler.auto_attach_embeddings = False

        role = role or self.default_role

        agent_proposer = AgentActionProposer(
            self.context_compiler,
            self.model_router,
            self.model_executor,
            self.skill_fabric,
            default_role=role,
            execution_profile=execution_profile,
            session_id=session_id,
            complexity=self.complexity,
            privacy_required=self.privacy_required,
        )

        async def _propose(
            tid: str,
            goal: str,
            ctx: Any,
            candidates: list[Any] | None,
            last_obs: ExecutionObservation | None,
            usage: dict[str, Any] | None,
        ) -> ProposedAction:
            if brain_fn is not None:
                # The brain works with a serializable context dict, not a
                # TaskContext object.
                brain_ctx = ctx.to_dict() if hasattr(ctx, "to_dict") else ctx
                return await brain_fn(tid, goal, brain_ctx, last_obs)
            return await agent_proposer.propose(
                task_id=tid,
                task_goal=goal,
                context=ctx,
                candidates=candidates,
                last_observation=last_obs,
                autonomy_usage=usage,
            )

        return await self._loop(
            task_id,
            task_goal=task_goal,
            propose_fn=_propose,
            step_fn=self._execute_action,
            initial_context=initial_context,
            available_skills=None,
            resume_from_checkpoint=resume_from_checkpoint,
            session_id=session_id,
            execution_profile=execution_profile,
            max_iterations=max_iterations,
        )

    # ------------------------------------------------------------------
    # Public: TaskGraph (DAG) execution — same gated loop per node
    # ------------------------------------------------------------------

    async def run_graph(
        self,
        task_id: str,
        *,
        nodes: list[Any],
        task_goal: str | None = None,
        session_id: str | None = None,
        execution_profile: Any | None = None,
        resume_from_checkpoint: str | None = None,
        brain_fn: Callable[
            [str, str, dict[str, Any], ExecutionObservation | None],
            Awaitable[ProposedAction],
        ] | None = None,
    ) -> RuntimeOutcome:
        """
        Execute a TaskGraph DAG through the same gated agent loop.

        Each node is treated as a sub-goal: the runtime compiles context,
        proposes the next action (brain or AgentActionProposer), runs the policy
        + autonomy single-authority gate, executes the action through the
        selected skill / executor, observes the result, and advances to dependent
        nodes — wiring Context + TaskGraph + Autonomy + Policy + Execution +
        Observation + Ledger + Checkpoint into one feedback loop.

        The graph is validated (missing deps / self-cycle / cycle rejected) by
        the scheduler before any node runs, so a malformed plan never enters the
        execution loop. Nodes run in topological order; a node that is blocked
        by policy/autonomy stops the whole graph (single authority).
        """
        if self.task_scheduler is None:
            raise RuntimeError("run_graph requires task_scheduler to be set on PawRuntime")
        if self.context_compiler is not None and hasattr(
            self.context_compiler, "auto_attach_embeddings"
        ):
            self.context_compiler.auto_attach_embeddings = False

        goal = task_goal or f"graph:{task_id}"
        completed_op_ids: set[str] = set()
        restored_context: dict[str, Any] = {}
        if resume_from_checkpoint:
            from .checkpoint import ResumeManager
            checkpoint, restored_context = await ResumeManager().resume(
                task_id, resume_from_checkpoint
            )
            self.autonomy.restore_state(
                checkpoint.autonomy_usage,
                checkpoint.loop_decision_history,
            )
            completed_op_ids = await OperationRecordStore.get_completed_op_ids(task_id)

        # On resume preserve the persisted graph/node statuses. A fresh graph
        # is built (and validated) only when no durable graph exists yet.
        existing_graph = await self.task_scheduler.get_graph(task_id) if resume_from_checkpoint else None
        if existing_graph is None:
            # build_graph validates (rejects missing deps / self-cycle / cycle)
            # before any node runs.
            await self.task_scheduler.build_graph(task_id, nodes)
        ordered = await self.task_scheduler.topological_sort(task_id)

        step_called = False
        operations_completed = 0
        last_observation: ExecutionObservation | None = None
        model_selections: list[str] = []
        skills_used: list[str] = []
        context_compiled = False
        completed_nodes = {
            node.id for node in ordered
            if getattr(getattr(node, "status", None), "value", getattr(node, "status", None))
            == TaskScheduleStatus.COMPLETED.value
        }
        failed_nodes = {
            node.id for node in ordered
            if getattr(getattr(node, "status", None), "value", getattr(node, "status", None))
            in (TaskScheduleStatus.FAILED.value, TaskScheduleStatus.BLOCKED.value)
        }

        await TaskLedger.record(
            task_id,
            TaskEventType.TASK_RESUMED if resume_from_checkpoint else TaskEventType.TASK_CREATED,
            {"goal": goal, "graph_nodes": len(ordered), "resumed_from": resume_from_checkpoint},
        )
        await self._set_task_status(task_id, TaskStatus.RUNNING)

        for idx, node in enumerate(ordered):
            node_operation_id = f"node_{task_id}_{node.id}"
            if node.id in completed_nodes or node_operation_id in completed_op_ids:
                completed_nodes.add(node.id)
                continue

            dependencies = list(getattr(node, "dependencies", []) or [])
            failed_dependencies = [dep for dep in dependencies if dep in failed_nodes]
            if failed_dependencies:
                await self.task_scheduler.update_node_status(node.id, TaskScheduleStatus.BLOCKED)
                failed_nodes.add(node.id)
                error = f"blocked by failed dependency: {', '.join(failed_dependencies)}"
                await TaskLedger.record(
                    task_id,
                    TaskEventType.EXECUTION_COMPLETED,
                    {"node": node.id, "executed": False, "blocked": True, "error": error},
                )
                checkpoint = await self._create_checkpoint(
                    task_id, restored_context, idx, 0.0, "graph_failed"
                )
                await log_task_completed(task_id, "failed", error)
                await self._set_task_status(task_id, TaskStatus.FAILED, error)
                return RuntimeOutcome(
                    stopped=True,
                    reason=StopReason.TASK_FAILED,
                    step_called=step_called,
                    iterations=idx,
                    last_observation=last_observation,
                    checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
                    operations_completed=operations_completed,
                    model_selections=model_selections,
                    skills_used=skills_used,
                    context_compiled=context_compiled,
                )

            node_goal = getattr(node, "goal", goal) or goal
            # --- Compile context for this node (runtime owns ContextCompiler) ---
            compiled_ctx = None
            candidates: list[Any] | None = None
            if self.context_compiler is not None:
                compiled_ctx, candidates = await self.context_compiler.compile(
                    task_id, node_goal, session_id=session_id, execution_profile=execution_profile,
                )
                await TaskLedger.record(
                    task_id, TaskEventType.CONTEXT_COMPILED,
                    {"fragment_count": len(compiled_ctx.fragments),
                     "token_estimate": compiled_ctx.token_count,
                     "candidate_count": len(candidates), "node": node.id},
                )
                context_compiled = True

            # --- Propose action for this node ---
            if brain_fn is not None:
                brain_ctx = compiled_ctx.to_dict() if hasattr(compiled_ctx, "to_dict") else (compiled_ctx or {})
                proposed = await brain_fn(task_id, node_goal, brain_ctx, last_observation)
            else:
                agent_proposer = AgentActionProposer(
                    self.context_compiler, self.model_router, self.model_executor,
                    self.skill_fabric, default_role=self.default_role,
                    execution_profile=execution_profile, session_id=session_id,
                    complexity=self.complexity, privacy_required=self.privacy_required,
                )
                proposed = await agent_proposer.propose(
                    task_id, node_goal, context=compiled_ctx, candidates=candidates,
                    last_observation=last_observation, autonomy_usage=self.autonomy.usage.to_dict(),
                )

            # Graph node operation IDs are stable across process restarts;
            # this is the idempotency key used by graph resume.
            proposed.operation_id = node_operation_id

            if proposed.metadata.get("selected_skill"):
                skills_used.append(proposed.metadata["selected_skill"])
                await TaskLedger.record(
                    task_id, TaskEventType.SKILL_SELECTED,
                    {"skills": [proposed.metadata["selected_skill"]], "node": node.id},
                )

            await log_step_proposed(
                task_id, proposed.operation_id, proposed.goal,
                [c.value for c in proposed.capabilities],
                proposed.estimated_cost.model_dump() if proposed.estimated_cost else None,
            )

            # --- Single authority gate (policy + autonomy) ---
            gate = await self._gate_action(task_id, proposed, idx)
            if gate is not None:
                return RuntimeOutcome(
                    stopped=True, reason=gate.reason, step_called=step_called,
                    iterations=idx, waiting_for_approval=gate.waiting_for_approval,
                    model_selections=model_selections, skills_used=skills_used,
                    context_compiled=context_compiled,
                )

            # --- CONTINUE -> Execute node ---
            step_called = True
            observation = await self._execute_action(task_id, proposed)
            observation.action_id = proposed.operation_id
            observation.step_id = f"node_{node.id}"
            await log_step_executed(
                task_id, proposed.operation_id, observation.success,
                observation.resources_used.model_dump() if observation.resources_used else None,
                observation.error,
            )
            if observation.resources_used:
                self.autonomy.usage.model_calls += observation.resources_used.model_calls
                self.autonomy.usage.tool_calls += observation.resources_used.tool_calls
                self.autonomy.usage.total_tokens += observation.resources_used.tokens
                self.autonomy.usage.wall_time_seconds += (
                    observation.resources_used.wall_time_ms / 1000.0
                )
            graph_progress = 0.0
            if isinstance(observation.result, dict):
                graph_progress = float(observation.result.get("progress", 0.0))
            await self.autonomy.record_iteration(graph_progress)
            if observation.success:
                await self.checkpoint_mgr.record_operation(
                    task_id=task_id, op_id=proposed.operation_id, op_type="node",
                    status="completed", result_ref=f"observation:{observation.step_id}",
                )
                await log_operation_recorded(task_id, proposed.operation_id, "node", "completed")
                operations_completed += 1
                completed_op_ids.add(proposed.operation_id)
                completed_nodes.add(node.id)
                await self.task_scheduler.update_node_status(node.id, TaskScheduleStatus.COMPLETED)
            else:
                await self.task_scheduler.update_node_status(node.id, TaskScheduleStatus.FAILED)
                failed_nodes.add(node.id)
                checkpoint = await self._create_checkpoint(
                    task_id, restored_context, idx + 1, 0.0, "graph_failed"
                )
                await log_task_completed(task_id, "failed", observation.error or f"node {node.id} failed")
                await self._set_task_status(task_id, TaskStatus.FAILED, observation.error)
                return RuntimeOutcome(
                    stopped=True,
                    reason=StopReason.TASK_FAILED,
                    step_called=True,
                    iterations=idx + 1,
                    last_observation=observation,
                    checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
                    operations_completed=operations_completed,
                    model_selections=model_selections,
                    skills_used=skills_used,
                    context_compiled=context_compiled,
                )

            last_observation = observation
            if isinstance(observation.result, dict) and observation.result.get("model"):
                model_selections.append(str(observation.result["model"]))

        # All nodes executed -> terminal completion (autonomy owns the decision)
        decision, stop = await self.autonomy.mark_complete()
        checkpoint = await self._create_checkpoint(
            task_id, restored_context, len(ordered), 1.0, "graph_completed"
        )
        await log_task_completed(task_id, "completed", f"graph:{len(ordered)} nodes")
        await self._set_task_status(task_id, TaskStatus.COMPLETED)

        return RuntimeOutcome(
            stopped=True, reason=stop, step_called=step_called, iterations=len(ordered),
            decision=decision, last_observation=last_observation,
            checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
            operations_completed=operations_completed, model_selections=model_selections,
            skills_used=skills_used, context_compiled=context_compiled,
        )

    # ------------------------------------------------------------------
    # Internal: the single authority gate (policy + autonomy)
    # ------------------------------------------------------------------

    async def _gate_action(
        self, task_id: str, proposed: ProposedAction, i: int
    ) -> RuntimeOutcome | None:
        """
        Run the policy + autonomy gates on a proposed action.

        Returns a ``RuntimeOutcome`` describing the stop when the action must NOT
        be executed (policy block / autonomy stop / ask / pause / escalate /
        delegate). Returns ``None`` when the loop should CONTINUE and execute
        the step. The gate is the single authority: a blocked/denied action
        never reaches ``step_fn``.
        """
        # --- Policy Gate (single authority, before any side effect) ---
        verdict = None
        approval_request = None
        if self.autonomy.policy_guard is not None and proposed.capabilities:
            verdict = await self.autonomy.policy_guard.evaluate_request(
                proposed.capabilities, proposed.context, task_id=task_id
            )
            needs_approval = verdict.verdict == "ask" or (
                verdict.verdict == "block"
                and verdict.stop_reason == StopReason.POLICY_ASK_REQUIRED
            )
            if needs_approval and self.approval_store is not None:
                if await self.approval_store.is_approved(task_id, proposed):
                    # A durable approval only overrides ASK for this exact
                    # fingerprint. A hard DENY can never reach this branch.
                    verdict = RequestVerdict(
                        verdict="go",
                        allowed=True,
                        decision=PolicyDecision.ALLOW,
                        blocked=[],
                        asked=verdict.asked,
                        details=verdict.details,
                        reason="Exact proposed operation approved by user",
                    )
                else:
                    approval_request = await self.approval_store.request(
                        task_id,
                        proposed,
                        metadata={"policy_reason": verdict.reason},
                    )
            await log_policy_gate_evaluated(
                task_id, proposed.operation_id, verdict.verdict,
                [c.value for c in proposed.capabilities],
            )
            if verdict.verdict == "block":
                await log_autonomy_gate_evaluated(
                    task_id, proposed.operation_id, "STOP",
                    verdict.stop_reason.value if verdict.stop_reason else "policy_denied",
                )
                await self.autonomy.record_decision(
                    AutonomyDecision.STOP,
                    verdict.stop_reason or StopReason.POLICY_DENIED,
                    context={"task_id": task_id, "action_id": proposed.operation_id},
                )
                waiting = verdict.stop_reason == StopReason.POLICY_ASK_REQUIRED
                return RuntimeOutcome(
                    stopped=True,
                    reason=verdict.stop_reason or StopReason.POLICY_DENIED,
                    step_called=False,
                    iterations=i,
                    waiting_for_approval=waiting,
                    approval_id=approval_request.id if approval_request else None,
                )

        # --- Autonomy Gate (budget, progress, repetition, stall) ---
        decision, stop_reason = await self.autonomy.decide(
            task_id,
            context=proposed.context,
            required_capabilities=proposed.capabilities,
            policy_verdict=verdict,
        )
        await log_autonomy_gate_evaluated(
            task_id, proposed.operation_id, decision.value,
            stop_reason.value if stop_reason else None,
        )
        await self.autonomy.record_decision(
            decision, stop_reason,
            context={"task_id": task_id, "action_id": proposed.operation_id},
        )

        if decision == AutonomyDecision.STOP:
            return RuntimeOutcome(
                stopped=True,
                reason=stop_reason or StopReason.UNKNOWN,
                step_called=False,
                iterations=i,
            )
        if decision == AutonomyDecision.ASK:
            return RuntimeOutcome(
                stopped=True,
                reason=StopReason.POLICY_ASK_REQUIRED,
                step_called=False,
                iterations=i,
                waiting_for_approval=True,
                approval_id=approval_request.id if approval_request else None,
            )
        if decision in (
            AutonomyDecision.PAUSE,
            AutonomyDecision.ESCALATE,
            AutonomyDecision.DELEGATE,
        ):
            if decision == AutonomyDecision.PAUSE:
                await self._create_checkpoint(
                    task_id, {}, i, 0.0, f"paused_{decision.value}"
                )
            return RuntimeOutcome(
                stopped=True,
                reason=stop_reason or decision.value,
                step_called=False,
                iterations=i,
            )
        return None  # CONTINUE

    # ------------------------------------------------------------------
    # Internal: the unified loop body
    # ------------------------------------------------------------------

    async def _loop(
        self,
        task_id: str,
        *,
        task_goal: str,
        propose_fn: ProposeFn,
        step_fn: StepFn,
        initial_context: dict[str, Any] | None = None,
        available_skills: list[dict[str, Any]] | None = None,
        resume_from_checkpoint: str | None = None,
        session_id: str | None = None,
        execution_profile: Any | None = None,
        max_iterations: int | None = None,
    ) -> RuntimeOutcome:
        """The single runtime loop body shared by ``run`` and ``run_agent``."""
        # Runtime-owned state must never alias/mutate the caller's proposal
        # context. In particular, checkpoint restore adds keys to ``context``;
        # mutating ProposedAction.context would invalidate an exact approval
        # fingerprint between ASK and resume.
        context = copy.deepcopy(initial_context or {})
        step_called = False
        iterations = 0
        operations_completed = 0
        last_observation: ExecutionObservation | None = None
        model_selections: list[str] = []
        skills_used: list[str] = []
        context_compiled = False
        max_iter = max_iterations or self._max_iterations or self.autonomy.budget.max_iterations
        completed_op_ids: set[str] = set()
        progress = 0.0

        await self._set_task_status(task_id, TaskStatus.RUNNING)

        # --- Resume from checkpoint if requested ---
        if resume_from_checkpoint:
            from .checkpoint import ResumeManager
            resume_mgr = ResumeManager()
            checkpoint, restored_context = await resume_mgr.resume(
                task_id, resume_from_checkpoint
            )
            context.update(restored_context)
            self.autonomy.restore_state(
                checkpoint.autonomy_usage,
                checkpoint.loop_decision_history,
            )

            # Get completed operation IDs to skip on replay
            completed_op_ids = await OperationRecordStore.get_completed_op_ids(task_id)
            logger.info(
                "runtime_resumed",
                task_id=task_id,
                checkpoint_id=checkpoint.checkpoint_id,
                progress=checkpoint.progress_ratio,
                skipped_operations=len(completed_op_ids),
            )

            await log_checkpoint_restored(
                task_id, checkpoint.checkpoint_id, checkpoint.progress_ratio, len(completed_op_ids)
            )

        # Log task started
        await TaskLedger.record(
            task_id,
            TaskEventType.TASK_RESUMED if resume_from_checkpoint else TaskEventType.TASK_CREATED,
            {"goal": task_goal, "resumed_from": resume_from_checkpoint},
        )

        # ``attempts`` is bounded independently from executed iterations so a
        # resume can skip an arbitrary number of completed operation IDs without
        # consuming the new-run iteration budget or looping forever.
        attempts = 0
        max_attempts = max_iter + len(completed_op_ids) + 1
        while iterations < max_iter and attempts < max_attempts:
            attempts += 1

            # --- 1. Compile context (the runtime owns ContextCompiler) ---
            compiled_ctx = None
            candidates: list[Any] | None = None
            if self.context_compiler is not None:
                compiled_ctx, candidates = await self.context_compiler.compile(
                    task_id,
                    task_goal,
                    session_id=session_id,
                    execution_profile=execution_profile,
                )
                await TaskLedger.record(
                    task_id,
                    TaskEventType.CONTEXT_COMPILED,
                    {
                        "fragment_count": len(compiled_ctx.fragments),
                        "token_estimate": compiled_ctx.token_count,
                        "candidate_count": len(candidates),
                    },
                )
                context_compiled = True
                if hasattr(compiled_ctx, "to_dict"):
                    context = compiled_ctx.to_dict()

            # --- 2. Propose next action ---
            propose_ctx: Any = compiled_ctx if compiled_ctx is not None else context
            proposed = await propose_fn(
                task_id,
                task_goal,
                propose_ctx,
                candidates,
                last_observation,
                self.autonomy.usage.to_dict(),
            )

            # A completed primitive operation is an idempotency boundary. It
            # is skipped before policy/autonomy/executor side effects on resume.
            if proposed.operation_id in completed_op_ids:
                await log_operation_recorded(
                    task_id, proposed.operation_id, "step", "skipped"
                )
                continue

            iterations += 1
            # Track agent-loop signals
            if proposed.metadata.get("selected_skill"):
                skills_used.append(proposed.metadata["selected_skill"])
                await TaskLedger.record(
                    task_id,
                    TaskEventType.SKILL_SELECTED,
                    {"skills": [proposed.metadata["selected_skill"]]},
                )
            if proposed.metadata.get("model_selection"):
                model_selections.append(proposed.metadata["model_selection"])

            # Log proposed step
            await log_step_proposed(
                task_id,
                proposed.operation_id,
                proposed.goal,
                [c.value for c in proposed.capabilities],
                proposed.estimated_cost.model_dump() if proposed.estimated_cost else None,
            )

            # --- Policy + Autonomy gate (single authority, before side effect) ---
            gate = await self._gate_action(task_id, proposed, iterations - 1)
            if gate is not None:
                if gate.waiting_for_approval:
                    checkpoint = await self._create_checkpoint(
                        task_id,
                        context,
                        iterations,
                        progress,
                        "awaiting_approval",
                    )
                    gate.checkpoint_id = checkpoint.checkpoint_id if checkpoint else None
                await self._set_task_status(
                    task_id,
                    TaskStatus.BLOCKED if gate.waiting_for_approval else TaskStatus.FAILED,
                    str(gate.reason) if gate.reason else None,
                )
                return gate

            # --- 4. CONTINUE -> Execute step ---
            step_called = True
            observation = await step_fn(task_id, proposed)

            # Ensure observation has the action_id for tracking
            observation.action_id = proposed.operation_id
            observation.step_id = f"step_{iterations}"

            # Log step execution
            await log_step_executed(
                task_id,
                proposed.operation_id,
                observation.success,
                observation.resources_used.model_dump() if observation.resources_used else None,
                observation.error,
            )

            # --- 5. Record OperationRecord for replay safety ---
            if observation.success:
                await self.checkpoint_mgr.record_operation(
                    task_id=task_id,
                    op_id=proposed.operation_id,
                    op_type="step",
                    status="completed",
                    result_ref=f"observation:{observation.step_id}",
                )
                await log_operation_recorded(
                    task_id, proposed.operation_id, "step", "completed"
                )
                operations_completed += 1
                completed_op_ids.add(proposed.operation_id)
                if self.approval_store is not None:
                    await self.approval_store.consume(task_id, proposed)
            else:
                await self.checkpoint_mgr.record_operation(
                    task_id=task_id,
                    op_id=proposed.operation_id,
                    op_type="step",
                    status="failed",
                    result_ref=f"observation:{observation.step_id}",
                )
                await log_operation_recorded(
                    task_id, proposed.operation_id, "step", "failed"
                )

            # --- 6. Update autonomy usage from observation ---
            if observation.resources_used:
                self.autonomy.usage.model_calls += observation.resources_used.model_calls
                self.autonomy.usage.tool_calls += observation.resources_used.tool_calls
                self.autonomy.usage.total_tokens += observation.resources_used.tokens
                self.autonomy.usage.wall_time_seconds += observation.resources_used.wall_time_ms / 1000.0

            # --- 7. Record iteration progress ---
            progress = 0.0
            if isinstance(observation.result, dict):
                progress = observation.result.get("progress", 0.0)
            await self.autonomy.record_iteration(progress)

            # Log step completion
            done = bool(isinstance(observation.result, dict) and observation.result.get("done", False))
            await log_step_completed(task_id, proposed.operation_id, done, progress)

            last_observation = observation
            if isinstance(observation.result, dict) and observation.result.get("model"):
                model_selections.append(str(observation.result["model"]))

            if not observation.success:
                checkpoint = await self._create_checkpoint(
                    task_id, context, iterations, progress, "failed"
                )
                await log_task_completed(task_id, "failed", observation.error or "execution failed")
                await self._set_task_status(task_id, TaskStatus.FAILED, observation.error)
                return RuntimeOutcome(
                    stopped=True,
                    reason=StopReason.TASK_FAILED,
                    step_called=True,
                    iterations=iterations,
                    last_observation=observation,
                    checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
                    operations_completed=operations_completed,
                    model_selections=model_selections,
                    skills_used=skills_used,
                    context_compiled=context_compiled,
                )

            # --- 8. Check for task completion ---
            if done:
                # Task observed complete -> autonomy owns the terminal decision
                decision, stop = await self.autonomy.mark_complete()

                # Final checkpoint on completion
                checkpoint = await self._create_checkpoint(
                    task_id, context, iterations, progress, "completed"
                )

                await log_task_completed(task_id, "completed", _summary(observation))
                await self._set_task_status(task_id, TaskStatus.COMPLETED)

                return RuntimeOutcome(
                    stopped=True,
                    reason=stop,
                    step_called=True,
                    iterations=iterations,
                    decision=decision,
                    last_observation=observation,
                    checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
                    operations_completed=operations_completed,
                    model_selections=model_selections,
                    skills_used=skills_used,
                    context_compiled=context_compiled,
                )

            # --- 9. Maybe create checkpoint ---
            checkpoint = await self.checkpoint_mgr.maybe_checkpoint(
                task_id=task_id,
                task_status="running",
                current_step=iterations,
                total_steps=max_iter,
                progress_ratio=progress,
                context=context,
                autonomy_usage=self.autonomy.usage,
                autonomy_profile=self.autonomy.profile.value,
                detectors_state={
                    "progress_history": [],
                    "repetition_state": {},
                    "stall_state": {},
                },
                loop_state={"iteration": iterations, "decision_history": self.autonomy._decision_history},
            )

            if checkpoint:
                await log_checkpoint_created(
                    task_id, checkpoint.checkpoint_id, checkpoint.progress_ratio,
                    checkpoint.current_step, checkpoint.total_steps
                )

            # Update context from observation if it provides new info
            if isinstance(observation.result, dict) and "context_update" in observation.result:
                context.update(observation.result["context_update"])

        # --- Max iterations reached ---
        checkpoint = await self._create_checkpoint(
            task_id, context, iterations, progress, "max_iterations"
        )

        return RuntimeOutcome(
            stopped=True,
            reason=StopReason.MAX_ITERATIONS_REACHED,
            step_called=step_called,
            iterations=iterations,
            last_observation=last_observation,
            checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
            operations_completed=operations_completed,
            model_selections=model_selections,
            skills_used=skills_used,
            context_compiled=context_compiled,
        )

    @staticmethod
    async def _set_task_status(
        task_id: str,
        status: TaskStatus,
        error: str | None = None,
    ) -> None:
        """Persist lifecycle status when the task exists; tolerate synthetic IDs."""
        try:
            await TaskManager.update_status(task_id, status, error=error)
        except Exception as exc:  # pragma: no cover - defensive for DB-less callers
            logger.warning("runtime_task_status_update_failed", task_id=task_id, error=str(exc))

    # ------------------------------------------------------------------
    # Action execution (the "do" half of the agent loop)
    # ------------------------------------------------------------------

    async def _execute_action(
        self,
        task_id: str,
        proposed: ProposedAction,
    ) -> ExecutionObservation:
        """
        Execute a proposed action through the canonical CapabilityRouter.

        Skill markdown is context/instruction only; loading it is not an
        execution success. A compatible registered executor must be selected
        and invoked. Model routing/inference also lives here, after
        ``_gate_action`` has completed, so no provider side effect occurs before
        policy authorization.
        """
        skill_name = proposed.metadata.get("selected_skill")
        skill_body = ""
        model_result: dict[str, Any] = {}
        selected_model_name: str | None = None

        # The runtime selects the model/executor that will carry out the action.
        # This is the execution-side model routing (distinct from the proposer's
        # planning-side model call) and is logged for both brain and proposer
        # paths so the ledger always records which model executed a step.
        if self.model_router is not None:
            token_count = _token_count_from_context(proposed.context)
            try:
                selection = await self.model_router.route(
                    task_id,
                    proposed.goal,
                    role=self.default_role,
                    context_size=token_count,
                    complexity=self.complexity,
                    privacy_required=self.privacy_required,
                    execution_profile=self.execution_profile,
                    preferred_provider=self.preferred_provider,
                )
                if selection.model_name:
                    selected_model_name = selection.model_name
                    await TaskLedger.record(
                        task_id,
                        TaskEventType.MODEL_SELECTED,
                        {
                            "model": selection.model_name,
                            "role": selection.role,
                            "score": selection.score,
                            "fallback_chain": selection.fallback_chain,
                            "stage": "execution",
                        },
                    )
                    if self.model_executor is not None:
                        messages = proposed.metadata.get("messages") or [
                            {"role": "user", "content": proposed.goal},
                        ]
                        model_result = await self.model_executor.complete(selection, messages) or {}
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("execute_model_route_failed", error=str(exc))

        if skill_name and self.skill_fabric is not None:
            try:
                skill = self.skill_fabric.get_skill(skill_name)
                if skill is not None and skill.manifest.body:
                    skill_body = skill.manifest.body
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("execute_skill_failed", skill=skill_name, error=str(exc))

        # Route and invoke the actual executor. The policy gate has already
        # authorized the exact capability set at this point.
        detailed_scores = await self.capability_router.route_detailed(
            task_id,
            proposed.goal,
            proposed.capabilities,
            context_size=_token_count_from_context(proposed.context),
            complexity=self.complexity,
            privacy_required=self.privacy_required,
        )
        best_detail = detailed_scores[0] if detailed_scores else None
        executor = (
            self.capability_router.registry.get(best_detail.executor_name)
            if best_detail is not None else None
        )
        executor_score = best_detail.to_capability_score() if best_detail else None
        if executor is None or (best_detail is not None and best_detail.missing_capabilities):
            error = "no executor supports the proposed capabilities"
            await TaskLedger.record(
                task_id,
                TaskEventType.EXECUTOR_SELECTED,
                {
                    "skill": skill_name,
                    "executor": None,
                    "executed": False,
                    "error": error,
                    "capabilities": [c.value for c in proposed.capabilities],
                },
            )
            await TaskLedger.record(
                task_id,
                TaskEventType.EXECUTION_COMPLETED,
                {"skill": skill_name, "executor": None, "executed": False, "error": error},
            )
            return ExecutionObservation(
                step_id="",
                action_id=proposed.operation_id,
                result={"done": False, "progress": 0.0, "skill": skill_name},
                resources_used=proposed.estimated_cost or ResourceUsage(tool_calls=1),
                success=False,
                error=error,
            )

        await TaskLedger.record(
            task_id,
            TaskEventType.EXECUTOR_SELECTED,
            {
                "skill": skill_name,
                "executor": executor.name,
                "score": executor_score.executor_score if executor_score else None,
                "capabilities": [c.value for c in proposed.capabilities],
            },
        )

        context_value = proposed.context
        if hasattr(context_value, "to_dict"):
            context_value = context_value.to_dict()
        if not isinstance(context_value, str):
            context_value = json.dumps(context_value or {}, default=str)
        executor_task = SimpleNamespace(
            id=task_id,
            goal=proposed.goal,
            requested_capabilities=proposed.capabilities,
        )
        executor_result = await executor.execute(executor_task, context_value)
        executed = bool(executor_result.success)

        done = bool(proposed.metadata.get("done", False)) or bool(model_result.get("done", False))
        result: dict[str, Any] = {
            "done": done,
            "progress": 1.0 if done else 0.0,
            "skill": skill_name,
            "skill_body": skill_body[:500] if skill_body else None,
            "model_response": model_result.get(
                "response", proposed.metadata.get("model_response", "")
            ),
            "model": selected_model_name,
            "output": executor_result.output,
            "executor": executor.name,
        }

        await TaskLedger.record(
            task_id,
            TaskEventType.EXECUTION_COMPLETED,
            {
                "skill": skill_name,
                "executed": executed,
                "done": result["done"],
                "error": executor_result.error,
            },
        )

        resources = proposed.estimated_cost or ResourceUsage(model_calls=1, tool_calls=1)
        return ExecutionObservation(
            step_id="",
            action_id=proposed.operation_id,
            result=result,
            resources_used=resources,
            success=executed,
            error=executor_result.error,
        )

    async def _create_checkpoint(
        self,
        task_id: str,
        context: dict[str, Any],
        iteration: int,
        progress: float,
        tag: str,
    ):
        """Create a forced checkpoint with the given tag."""
        checkpoint = await self.checkpoint_mgr.force_checkpoint(
            task_id=task_id,
            task_status="running" if tag == "running" else tag,
            current_step=iteration,
            total_steps=self._max_iterations or self.autonomy.budget.max_iterations,
            progress_ratio=progress,
            context=context,
            autonomy_usage=self.autonomy.usage,
            autonomy_profile=self.autonomy.profile.value,
            progress_history=self.autonomy.usage.progress_history,
            repetition_state={"decision_history": self.autonomy._decision_history[-10:]},
            stall_state={"last_activity": self.autonomy.usage.last_activity.isoformat()},
            loop_iteration=iteration,
            loop_decision_history=self.autonomy._decision_history,
            tags=[tag],
        )
        if checkpoint:
            await log_checkpoint_created(
                task_id, checkpoint.checkpoint_id, checkpoint.progress_ratio,
                checkpoint.current_step, checkpoint.total_steps
            )
        return checkpoint


def _summary(obs: ExecutionObservation) -> str:
    """Compact summary for the TASK_COMPLETED ledger event."""
    try:
        result = obs.result or {}
        return str(result.get("summary", result.get("skill", "completed")))[:200]
    except Exception:
        return "completed"
