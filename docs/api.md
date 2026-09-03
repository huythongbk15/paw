# PAW API reference (Core Stabilization)

This is the small, source-backed surface that Codex should use. `paw.core`
contains only the eleven-symbol runtime contract; import services, stores and
adapters from the concrete owner modules below.

## Runtime

`paw.core.runtime.PawRuntime` is the orchestration authority.

All public modes pass each proposal through the same internal executable-unit
pipeline: Policy → Autonomy → Capability/Model routing → execution → observation
→ operation record. `run_graph` owns dependency/node transitions only; it does
not duplicate the safety or side-effect pipeline.

- `await runtime.run(task_id, task_goal=..., step_fn=..., initial_context=None, available_skills=None, resume_from_checkpoint=None)` runs a typed `ProposedAction` → Policy/Autonomy gate → `ExecutionObservation` loop.
- `await runtime.run_agent(task_id, task_goal=..., session_id=..., brain_fn=None, resume_from_checkpoint=None)` uses the integrated context/skill/model path. Construct the runtime with `context_compiler`, `model_router`, and `model_executor`. Proposal is side-effect free; routing and model inference happen only after the gate.
- `await runtime.run_graph(task_id, nodes=[...], task_goal=..., task_scheduler=..., resume_from_checkpoint=None)` executes a validated DAG. A failed node marks the task failed and prevents dependents from running.

The result is `RuntimeOutcome`. Terminal success is
`AutonomyDecision.STOP_SUCCESS` with `StopReason.TASK_COMPLETED`; policy ASK
and DENY never call `step_fn` or an executor. When constructed with
`approval_store=ApprovalStore`, ASK writes an exact-operation request and an
approved fingerprint may resume that proposal once.

## Canonical contracts

All shared enums and typed boundaries live in `paw.core.models`:

```python
from paw.core.models import (
    ApprovalStatus, AutonomyDecision, Capability, ExecutionObservation,
    ExtendedTaskStatus, ProposedAction, ResourceUsage, StopReason,
)
```

`AutonomyController` (`paw.core.autonomy`) owns budget/progress decisions and
accepts an already evaluated policy verdict so a proposal is not checked twice.
`CapabilityRouter` and `ExecutorRegistry` (`paw.core.executor`) own tool
selection. `ExecutableTask` is the normalized executor wrapper and carries the
approved operation ID, idempotency key and adapter metadata across the port.
`EffectIntent` is the pre-execution receipt used only by external-effect
executors; the runtime persists it before invocation and calls the executor's
reconciliation hook after an interrupted completion commit.
`ContextCompiler` (`paw.core.context_compiler`) owns context
assembly; `ContextBuilder` is only a compatibility facade.

`Planner` (`paw.core.planner`) is the sole `Plan`/`TaskNode` factory and store.
`await Planner().plan(task_id)` requires an existing durable Task and derives
the Plan goal/session from that Task; it never creates or replaces Task
identity. Its `StructuredReasoner` (`paw.core.decomposition`) is a pure strategy.
Runtime proposer strategies create `ProposedAction`; `TaskScheduler`
(`paw.core.task_scheduler`) only owns DAG readiness and node state.

`AdvancedSkillSelector` (`paw.core.semantic`) is the canonical skill-ranking
implementation. `SkillSelector` and `SemanticSkillSelector` are legacy result-
shape facades; they delegate to it and do not run Policy. Authorization always
belongs to the exact proposal gate in `PawRuntime`.

## Local filesystem executor

`paw.executors.filesystem.LocalFilesystemExecutor(workspace_root)` is the first
real local adapter. It supports structured read/list/write operations, rejects
paths outside its resolved workspace, denies symbolic-link writes, caps reads
and listings, and writes through a same-directory temporary file. It never owns
Policy or approval; applications compose it behind `PawRuntime`. Write intents
persist path/mode/content-hash metadata. Restart accepts matching final content
without a second write and blocks an ambiguous mismatch.

## Knowledge/result normalization

Use `paw.knowledge.normalize_knowledge_result(...)` to convert persisted
`KnowledgeEvidence`, `KnowledgeChunk` and `KnowledgeCitation` records to the
canonical `TaskResult.evidence` and `TaskResult.citations` fields. The function
preserves evidence/chunk/citation IDs and source provenance, orders citations by
position and rejects broken cross-record references.

## Persistence

Call `await paw.core.storage.db.initialize()` once at process start. The schema
and migrations are centralized in `paw.core.storage`; feature modules must not
create tables. Checkpoints and idempotency records are exposed by
`CheckpointStore`, `OperationRecordStore`, and `ResumeManager` in
`paw.core.checkpoint`. Runtime commit groups are coordinated internally by
`paw.core.runtime_persistence`: operation evidence commits together, while a
terminal checkpoint, task status and terminal ledger evidence form a second
atomic boundary. External-effect executors additionally use a `prepared`
operation record before invocation; this is a reconciliation marker, not a
success acknowledgement.

## Durable approval

`paw.core.approval.ApprovalStore` owns ASK persistence. Its relevant methods
are `request`, `approve`, `deny`, `cancel`, `is_approved`, and `consume`.
Approval matches the full canonical JSON fingerprint of a `ProposedAction`,
not only its task or operation ID.

## Chat application service

`paw.application.chat.ChatService` is the user-facing vertical slice shared by
the CLI workflow:

```python
service = ChatService(provider_mode="local", workspace_root=".")
session = await service.open()                 # or open(existing_session_id)
reply = await service.send("xin chào")
status = await service.status()
history = await service.history()
plan = await service.plan()
explanation = await service.explain()
ledger = await service.ledger()
checkpoint = await service.checkpoint()
policy = await service.policy()
skills = await service.skills()
artifacts = await service.artifacts()
reply = await service.approve(execute=True)    # exact pending operation
reply = await service.resume()                 # approved after a restart
reply = await service.cancel()
await service.close()
```

`ChatReply` reports task/session IDs, status, stop reason, checkpoint,
approval, selected model/executor, artifacts and whether context was compiled.
The session persists its workspace binding; reopening it with another workspace
is rejected.
