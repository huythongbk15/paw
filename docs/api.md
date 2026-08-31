# PAW API reference (Core Stabilization)

This is the small, source-backed surface that Codex should use. Import from
the concrete modules below; the broad `paw.core` re-export is compatibility
only.

## Runtime

`paw.core.runtime.PawRuntime` is the orchestration authority.

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
selection. `ContextCompiler` (`paw.core.context_compiler`) owns context
assembly; `ContextBuilder` is only a compatibility facade.

## Persistence

Call `await paw.core.storage.db.initialize()` once at process start. The schema
and migrations are centralized in `paw.core.storage`; feature modules must not
create tables. Checkpoints and idempotency records are exposed by
`CheckpointStore`, `OperationRecordStore`, and `ResumeManager` in
`paw.core.checkpoint`.

## Durable approval

`paw.core.approval.ApprovalStore` owns ASK persistence. Its relevant methods
are `request`, `approve`, `deny`, `cancel`, `is_approved`, and `consume`.
Approval matches the full canonical JSON fingerprint of a `ProposedAction`,
not only its task or operation ID.

## Chat application service

`paw.application.chat.ChatService` is the user-facing vertical slice shared by
the CLI workflow:

```python
service = ChatService(provider_mode="local")
session = await service.open()                 # or open(existing_session_id)
reply = await service.send("xin chào")
status = await service.status()
history = await service.history()
reply = await service.approve(execute=True)    # exact pending operation
reply = await service.resume()                 # approved after a restart
reply = await service.cancel()
await service.close()
```

`ChatReply` reports task/session IDs, status, stop reason, checkpoint,
approval, selected model/executor and whether context was compiled.
