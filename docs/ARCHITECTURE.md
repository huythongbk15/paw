# PAW core architecture

This document defines the target contract for PAW Core. It is intentionally
stable and independent of the current file layout. See
`IMPLEMENTATION_MAP.md` for what the repository actually implements today.

## System boundary

PAW Core accepts a user goal and owns the state transitions that turn it into a
terminal task result. It may call replaceable providers and executors through
ports, but those adapters do not decide policy, task state or resume behavior.

```text
CLI / library caller
        |
        v
ChatService / application runtime -----------------------------+
        |                                                      |
        +--> Task + Task Graph                                 |
        +--> Context Compiler <--> Memory / Knowledge / Skills |
        +--> Operation Proposal                                |
        +--> Policy Gate --> Autonomy Gate                     |
        +--> Capability Router --> Executor port               |
        +--> Model Router ------> Model provider port          |
        +--> Observation --> Progress evaluation -------------+
        |
        +--> Ledger + checkpoint + operation records
```

SQLite is the default durable adapter. Ollama is one optional model-provider
adapter. Neither belongs to the domain model.

## Dependency direction

The conceptual layers are:

1. **Domain contracts** — identifiers, task and graph state, capabilities,
   policy/autonomy decisions, proposals, observations and results. They contain
   no database, CLI, provider or executor implementation.
2. **Core services** — planning, skill selection, context compilation, policy,
   autonomy, routing and progress evaluation. They depend on domain contracts
   and declared ports.
3. **Application runtime** — the only owner of the execution state machine and
   transaction ordering. It composes core services; services do not start a
   competing loop.
4. **Ports and adapters** — stores, SQLite, model providers, executors and CLI.
   Adapters depend inward on PAW contracts; Core never depends on an adapter's
   private types.

Moving files is not required to respect these layers. Import and ownership
direction matter more than directory shape.

## Canonical runtime contract

There is one logical loop for single tasks and graph nodes. A graph changes how
the next ready unit is selected; it does not create another safety or execution
pipeline.

```text
1. Load or create durable Task state
2. Select ready TaskNode (or the task itself)
3. Discover skills and compile budgeted context
4. Propose the next operation
5. Authorize the proposal through Policy
6. Decide through Autonomy whether work may continue
7. Select executor through CapabilityRouter
8. Select a model through ModelRouter only when the operation needs one
9. Execute once with an idempotency key
10. Persist observation and operation completion atomically
11. Evaluate progress, dependency effects and terminal state
12. Persist checkpoint and ledger events
13. CONTINUE, REPLAN, WAIT, ESCALATE or STOP
```

If step 4 requires a model/provider call, that call is itself a proposed
operation and must pass policy, privacy and budget checks before network or
billable work occurs. “Planning” is not an exemption from the side-effect gate.

The runtime may internally optimize reads, but it may not reorder authorization
after execution or acknowledge durable progress before commit.

## Operation envelope

Every executable unit, including a model call, has one typed proposal carrying:

- stable operation and task/node identifiers;
- operation kind and explicit intent;
- required action capabilities;
- input/context references rather than hidden global state;
- estimated resource use and privacy requirements;
- selected skill, model role and executor constraints when applicable;
- an idempotency key stable across retry and resume.

Execution returns one typed observation carrying success/failure, result,
artifacts, resource usage, retryability, progress signal and a typed error.
Arbitrary dictionaries may exist at adapter boundaries but must be normalized
before entering runtime state.

## Decision ownership

| Decision | Sole owner | Notes |
|---|---|---|
| Is the action permitted? | Policy Engine | `ASK` is a wait state, never implicit permission. |
| Should the loop continue? | Autonomy Controller | Uses budget, progress, repetition, stall and terminal state. |
| Which executor can perform it? | Capability Router | Matches action capabilities, risk, privacy, cost and availability. |
| Which model should reason? | Model Router | Matches cognitive role and provider constraints; does not select executors. |
| What context is sent? | Context Compiler | Enforces budget, selection reason and provenance. |
| What runs next in a DAG? | Task Scheduler | Honors dependency and failure propagation rules. |
| What happened? | Task Ledger | Append-oriented audit record; not long-term memory. |
| What resumes? | Checkpoint/operation store | Durable runtime state plus completed idempotency keys. |

A service may request another owner's decision, but it may not duplicate the
decision logic.

## Task and runtime state

The domain needs one canonical task status model. At minimum it distinguishes:

```text
PENDING -> RUNNING -> COMPLETED
                  \-> FAILED
                  \-> PARTIAL
                  \-> BLOCKED
                  \-> WAITING_APPROVAL
                  \-> PAUSED / CHECKPOINTED -> RESUMING -> RUNNING
                  \-> CANCELLED
```

Autonomy decisions are not task statuses. A decision such as `WAIT`, `REPLAN`
or `STOP` produces an explicit state transition and typed stop reason.

For graphs:

- a node becomes ready only when all required predecessors completed;
- a failed required predecessor blocks its dependents;
- optional dependencies are explicit;
- cycles and missing dependencies are rejected before persistence/execution;
- a graph cannot be marked successful while a required node failed or never
  ran;
- resume restores node states and operation keys, not only graph order.

## Safety invariants

These are constitutional. Violating one makes the affected gate `FAIL` even if
the test suite is otherwise green.

1. **Single contract:** one canonical type and implementation per owned
   concept. Compatibility aliases have an owner and removal date/condition.
2. **Policy before effects:** filesystem writes, processes, network/model
   calls, financial actions and destructive work cannot occur before Policy.
3. **ASK waits:** ASK creates a durable approval request. Only a matching,
   recorded approval may resume the exact proposal.
4. **Bounded autonomy:** hard iteration/resource bounds and typed stop reasons
   apply to every runtime path.
5. **Independent routing:** capability and model routing never substitute for
   each other.
6. **Durable acknowledgement:** a successful operation is not reported until
   its observation and operation record commit.
7. **Idempotent resume:** retries and resumes reuse the operation key and do not
   repeat a completed side effect.
8. **Failure propagation:** required DAG failures block dependents and prevent
   false task completion.
9. **Explainable context:** every included fragment has provenance, score and
   reason; every budget limit is enforced on the final payload.
10. **Adapter isolation:** no external provider type leaks into domain models or
    owns PAW state.
11. **Observable decisions:** proposal, policy, autonomy, selection, execution,
    observation and terminal transition are reconstructable from the ledger.
12. **No destructive initialization:** normal initialization/migration never
    drops user tables or data.
13. **Immutable approval input:** runtime-owned resume state never mutates the
    `ProposedAction` whose fingerprint was approved.

## Persistence contract

Schema ownership is centralized. Feature modules may define repositories or
store interfaces, but must not create or drop tables on demand.

Required properties:

- an explicit schema version and ordered, idempotent migrations;
- all writes use explicit transaction boundaries;
- a store method does not claim durability before commit;
- checkpoints contain task/node state, autonomy usage, detector state, context
  references and completed operation keys needed for a faithful resume;
- ledger and operation completion are committed with the state transition they
  describe, or recovery rules explain the split;
- process-restart tests close and reopen SQLite instead of reading through the
  same connection.

## Context, memory and knowledge

- **Context** is the bounded payload for the current decision.
- **Memory** stores user/project facts and prior experience worth recalling.
- **Knowledge** stores sources, chunks, evidence and citations.
- **Ledger** stores what PAW did.
- **Skills** store how a capability should be applied.

These stores may contribute candidates to `ContextCompiler`; they do not append
their full contents directly to a model prompt. Retrieval and final payload
budgeting are separate steps, and final skill-body upgrades must be re-budgeted.

## Extension ports

The stable extension boundaries are:

- `ModelProvider`: discover/health/complete/embed/stream as supported;
- `Executor`: declare action capabilities and execute an approved proposal;
- `SkillProvider`: discover and import normalized skill manifests;
- memory/knowledge repositories: retrieve and persist PAW-owned records.

Adding an adapter must not require a new PAW task, policy, context or checkpoint
type. If it does, the port is incomplete or the adapter is leaking inward.

## Public application surface

The intended public surface is small:

- create/load a session and task;
- run or resume through the canonical runtime;
- inspect task state, ledger, checkpoint and approval requests;
- configure policies, skills, providers and execution profiles through typed
  PAW contracts.

The first source-backed application surface is
`paw.application.chat.ChatService`, exposed by `paw chat`. It stores the
transcript as an application projection while Session, Task, Policy, Approval,
Ledger and Checkpoint remain core-owned records.

Module-level helper proliferation and broad wildcard exports are not part of
the architectural contract. Public API is stabilized only after the contract
consolidation track in `ROADMAP.md` passes.
