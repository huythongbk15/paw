# PAW implementation map and stabilization audit

This document records current source reality. It does not award completion
based on historical phase notes. Update it whenever ownership or runtime wiring
changes.

## Audit baseline

| Item | Observed value |
|---|---|
| Revision | `ffdd017` on `main` + Core Stabilization working tree |
| Source root | `src/paw/` |
| Runtime Python files | 44 |
| Runtime Python lines | 15,774 |
| Top-level core modules | 28 |
| Test Python lines | 10,489 |
| Test function definitions | 507; this is not a pass count |
| Largest runtime files | `runtime.py` 1,659; `model_router.py` 789; `context_compiler.py` 758 |
| Packaging definition | root `pyproject.toml`, setuptools, Python 3.12+ |

The worktree was clean at the start of this audit.

### Verification baseline

The project-only environment is `.venv`, created from `pyproject.toml` with
`uv sync --extra dev` after explicit approval. Current checks:

- `.venv/bin/python -m pytest -q`: **514 passed in 270.53s** on the current
  working tree, including the 8-test chat/approval/process-boundary suite.
- Focused policy/runtime/chat regressions: 47 passed.
- `.venv/bin/python -m ruff check .`: passing.
- `uv build --wheel` produced `paw-0.1.0-py3-none-any.whl`; a clean virtualenv
  installed the wheel and `paw --version`, `paw init`, and
  `paw chat --message ... --json` passed outside the repository.
- `requirements.lock.txt` remains a host-environment snapshot and is not the
  PAW project lock.

## Component map

| Owned concept | Current implementation | Runtime use | Status and main gap |
|---|---|---|---|
| Identity | `core/identity/__init__.py`: `Identity`, `IdentityManager` | Not part of the main loop | `OBSERVED`; persistent key/value service exists but is not composed by `PawRuntime`. |
| Session | `core/session.py`: `Session`, `SessionManager`; chat projection in `application/chat.py` | `ChatService` creates/loads it before each task | `PASS` for the durable CLI chat lifecycle and transcript. |
| Task | `core/task.py`: `Task`, `TaskManager`; base contracts in `core/models.py` | Runtime accepts an existing `task_id`; `ChatService` creates one per turn and persists terminal/blocked state | `PASS` for runtime and CLI lifecycle. |
| Plan | `core/planner.py`: `Plan`, `Planner`; `core/intelligent_planner.py`: `IntelligentPlanner` | Not wired into `PawRuntime.run_agent` | `PARTIAL`; multiple planning paths, no declared canonical planner. |
| Task Graph | `core/planner.py`: `TaskNode`; `core/task_scheduler.py`: `TaskGraph`, `TaskScheduler` | `PawRuntime.run_graph` | `PASS` for DAG validation, stable node operation IDs, failure propagation and checkpoint resume. |
| Skill Fabric | `core/skills.py`: `SkillFabric`; layered selectors in `selector.py`/`semantic.py` | Compiler retrieves skills; agent proposer selects them; executor performs the action | `PASS` for the runtime path; selector layering is documented. |
| Context | `core/context.py`: types plus compatibility `ContextBuilder`; `core/context_compiler.py`: `ContextCompiler` | Compiler is used by agent/graph paths | `PASS`; `ContextBuilder` is now a thin facade and contains no second assembly algorithm. |
| Memory | `core/memory.py`, `core/embeddings.py` | `ContextCompiler` uses `AdvancedMemoryRetriever` | `OBSERVED`; lexical/embedding paths exist, current stress and restart behavior are unverified. |
| Knowledge | `knowledge/source.py`, `chunk.py`, `evidence.py`, `citation.py`, `index.py` | Compiler retrieves knowledge candidates | `OBSERVED`; implemented as SQLite-backed primitives, with boundary duplication against result-level Evidence/Citation models. |
| Policy | `core/policy.py`: `PolicyGuard`; exact approval in `core/approval.py` | `PawRuntime._gate_action` then `AutonomyController.decide(policy_verdict=...)` | `PASS` for gate ordering and durable ASK: one verdict is reused, DENY never executes, and only an approved exact proposal resumes. |
| Autonomy | `core/autonomy.py`; detectors in `core/detectors.py`; profiles in `core/execution_profile.py` | All runtime paths | `PASS` for canonical decision types, restored usage and per-resource accounting. |
| Capability Router | `core/executor.py`: `CapabilityRouter`, `ExecutorRegistry` | `PawRuntime._execute_action` | `PASS`; every agent/graph action selects a compatible executor before invocation. |
| Executor | `core/executor.py`: `Executor`, registry and mock; `core/model_executor.py` handles model providers | `PawRuntime._execute_action` invokes selected executor | `PASS` for the registered executor contract; skill body is context only and cannot produce success by itself. |
| Model Router | `core/model_router.py`: registry/router/provider registry; `core/model_executor.py` | Execution stage routes after the proposal gate | `PASS` for gate ordering; one execution-stage route/call is recorded. |
| Ledger | `core/ledger.py`: `TaskLedger` and typed event helpers | Used throughout runtime | `OBSERVED`; core writes use a transaction, but event/state atomicity with checkpoints and operation records is not established. |
| Checkpoint/Resume | `core/checkpoint.py`: checkpoint, operation record, resume services | `run`/`run_agent`/`run_graph` restore durable state | `PASS` for committed stores, restored autonomy/context, stable idempotency IDs and graph node resume. |
| Storage | `core/storage.py`: global database proxy and schema | Shared by nearly every service | `PASS` for centralized DDL, non-destructive migration and autocommit-safe legacy writes. |
| Runtime | `core/runtime.py`: `PawRuntime.run`, `run_agent`, `run_graph` | Integration authority | `PASS` for the repaired core path; graph remains a separate node loop pending a later unification refactor. |
| CLI | `cli/__init__.py`: setup/inspection plus `chat`; `application/chat.py`: `ChatService` | Invokes the same canonical agent runtime used by the library | `PASS` for the offline demo slice: durable history/status, approve/resume/cancel and one-shot JSON. Real automation executors remain out of scope. |

## Competing or duplicated contracts

| Concept | Definitions | Divergence |
|---|---|---|
| `AutonomyDecision` | `core/models.py` (re-exported by `core/autonomy.py`) | One canonical enum, including `STOP_SUCCESS`. |
| `StopReason` | `core/models.py` (re-exported by `core/autonomy.py`/`policy.py`) | One canonical value set. |
| `ExtendedTaskStatus` | `core/models.py` (re-exported by `core/checkpoint.py`) | One canonical value set. |
| Approval lifecycle | `ApprovalStatus` in `core/models.py`; records/store in `core/approval.py` | One exact-operation fingerprint and transition owner. |
| `ExecutableTask` | `core/executor.py` (re-exported by `core/executor_policy.py`) | One canonical dataclass wrapper. |
| Context assembly | `ContextCompiler`; `ContextBuilder` facade | Builder delegates to Compiler and has no second retrieval algorithm. |
| Skill selection | `SkillSelector`, `SemanticSkillSelector`, `AdvancedSkillSelector` | Responsibilities and canonical call path are not documented as one layered selector. |
| Planning | `Planner`, `IntelligentPlanner`, `TaskScheduler`, runtime proposer | Decomposition, proposal and scheduling ownership overlap without a single application contract. |
| Evidence/Citation | result models in `core/models.py`; stored knowledge models in `paw.knowledge` | Different roles may be valid, but there is no explicit normalization boundary. |

`core/__init__.py` re-exports a broad surface, including legacy and replacement
types, which makes accidental coupling more likely.

## Runtime inconsistencies requiring repair

### Safety and authorization (repaired)

1. `AgentActionProposer.propose()` is side-effect free. Model routing and
   inference happen in `_execute_action()` only after `_gate_action()`.
2. `_gate_action()` passes its single policy verdict into
   `AutonomyController.decide(policy_verdict=...)`; the proposal is not checked
   twice.
3. `ExecutorPolicyEnforcer.enforce()` treats ASK as a non-executing decision.

### Durability and resume (repaired)

1. Database writes commit immediately outside an explicit transaction; checkpoint
   and operation stores use the canonical schema.
2. Runtime resume matches completed operation IDs and skips them without running
   the gate/executor again.
3. Agent autonomy usage/decision history and graph node statuses are restored.
4. Graph node IDs are stable idempotency keys across process restarts.

### Execution and graph behavior (repaired)

1. `CapabilityRouter` and `ExecutorRegistry` are in `_execute_action()`.
2. Skill body loading is context-only; a compatible executor must return success.
3. A failed graph observation marks the node/task failed and returns immediately;
   dependents are never run.
4. Graph orchestration is still a separate node loop and is a future refactor,
   but it now shares the same policy/autonomy/executor/checkpoint boundaries.

### Storage ownership (repaired)

1. Runtime DDL is centralized in `core/storage.py`; feature ensure helpers only
   call `db.initialize()`.
2. `ensure_task_scheduler_tables()` is non-destructive.
3. Legacy mutation calls commit safely when no explicit transaction is active.

## Documentation drift found by this audit

- Root README and architecture claimed phases 0–16 complete, while the latest
  commit and tests are labelled Phase 19/20.
- Ignored workspace instructions claimed Phase 10 was current, while ignored
  profile notes claimed later phases and historical green counts.
- Packaged architecture described target directories and adapters that do not
  exist in the current source tree.
- `docs/api.md` and `docs/examples.md` contain method names, arguments, enum
  members and return shapes that do not match current implementations.
- Root architecture listed provider adapter directories that were moved out of
  the package.

The canonical documentation set now avoids phase completion claims; API and
example references are source-backed and have been smoke-tested.

## Core gate assessment

This is a source audit, not a substitute for executing tests.

| Gate | Status | Evidence |
|---|---|---|
| Core consistency | `PASS` for repaired contracts/storage | Canonical enums, compatibility facades, central schema and runtime router wiring are in place. |
| Policy safety | `PASS` for runtime gate ordering | Provider/model calls and executor invocation occur after the proposal verdict; ASK/DENY never execute. |
| Context quality | `PASS` | Full suite includes the real-SQLite 100-memory/100-knowledge/50-skill stress and context budget/explain tests. |
| Autonomy | `PASS` for repaired runtime accounting | Canonical decision types, restored usage, and no double token/decision increment. |
| Durable runtime | `PASS` for repaired stores/resume | Checkpoint and operation writes commit; agent/graph restore state and skip completed operations. |
| Task Graph | `PASS` for repaired execution semantics | Failed nodes stop the graph and dependents are blocked; cycles remain rejected. |
| Packaging | `PASS` | Wheel build, isolated install, import and CLI smoke paths passed. |
| Regression | `PASS` for current checks | 514 tests, focused runtime/chat regressions, and ruff are green in `.venv`. |

Overall status: **Core Stabilization repaired; CLI demo slice verified**.
The offline chat application slice is implemented and covered by end-to-end
tests. The remaining architectural gap is graph-node loop unification and the
absence of a real non-mock executor; neither is hidden behind the demo status.

## First repair targets

1. Factor graph nodes through the same executable-unit implementation as a
   single task without changing safety semantics.
2. Define the next real executor adapter only after the stabilization exit
   gate; the bundled mock remains an explicit demo stand-in.

The ordered acceptance plan is in `ROADMAP.md`.
