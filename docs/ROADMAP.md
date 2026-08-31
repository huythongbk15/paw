# PAW Core Stabilization roadmap

This is the only active work sequence. Historical numbered phases describe how
the repository grew; they do not determine what should be built next.

Current track: **S5/S6 verification — the durable CLI chat slice is
implemented; final same-revision regression/package evidence and unit-loop
unification remain**.

## Sequencing rule

Complete tracks in order. Work may move within a track, but a later track does
not start while an earlier safety or durability acceptance item fails. A user
may explicitly reprioritize work; record the resulting risk and update this
roadmap rather than silently branching into another plan.

## S0 — Reproducible baseline

Goal: make every future status claim reproducible from a clean checkout.

Work:

- replace the captured host `requirements.lock.txt` with a PAW-only lock derived
  from `pyproject.toml`, or clearly rename/remove it after confirming its owner;
- document one Python 3.12+ setup path for runtime and dev dependencies;
- execute the full test suite and lint on the current revision;
- build a wheel, install it in a clean environment and smoke-test actual CLI
  commands outside the repository;
- record failures without repairing unrelated systems in the same change;
- add a small automated check that canonical docs do not claim unverified phase
  completion or reference missing source modules.

Acceptance:

- clean environment setup uses only project-declared dependencies;
- `pytest -q` and `ruff check .` produce captured current-revision results;
- wheel build, isolated import, `paw --version`, `paw --help` and `paw doctor`
  smoke paths are executed;
- no tracked environment file introduces prohibited runtime dependencies;
- `IMPLEMENTATION_MAP.md` is updated with the baseline evidence.

## S1 — Canonical contracts and public ownership

Goal: one source of truth for every PAW-owned concept.

Work:

- consolidate `AutonomyDecision`, `StopReason` and task statuses;
- define one operation proposal/executable-task contract;
- make `ContextCompiler` canonical and explicitly deprecate or remove the
  legacy builder after migrating callers;
- define how persisted Evidence/Citation types normalize to result contracts;
- distinguish planner, proposer and scheduler responsibilities;
- narrow `paw.core` exports to a deliberate public surface;
- add contract tests that fail when a second core definition appears.

Acceptance:

- one canonical definition per owned type;
- all runtime, policy, checkpoint and tests import the same decision/status
  types;
- compatibility aliases are documented and tested, with an explicit removal
  condition;
- no runtime behavior changes are hidden inside the consolidation.

## S2 — Storage and migration integrity

Goal: local state remains durable across commit, close, restart and upgrade.

Work:

- centralize schema ownership and introduce a schema version plus migrations;
- remove on-demand DDL from feature modules;
- eliminate destructive graph-table initialization;
- remove or constrain the legacy mutation API so writes cannot bypass commit;
- define atomic boundaries for task state, operation record, checkpoint and
  ledger events;
- test with real connection close/reopen and migration fixtures.

Acceptance:

- normal initialization never drops data;
- every acknowledged write survives process restart;
- migrations are ordered, idempotent and tested from supported old schemas;
- no `CREATE`, `ALTER` or `DROP` statement exists outside the schema/migration
  owner except test fixtures;
- checkpoint and operation records are durably visible after reopen.

## S3 — Authorization and autonomy correctness

Goal: no side effect or provider cost can occur before authorization, and every
budget counter has one meaning.

Work:

- turn model/provider planning calls into explicit gated operations;
- evaluate Policy once per proposal and pass the verdict to Autonomy;
- implement durable approval requests for ASK and exact-operation resume;
- make DENY, ASK, SANDBOX and ALLOW semantics consistent across runtime and
  executor wrappers;
- fix decision, token, model, tool, time and iteration accounting;
- restore detector state from checkpoints and prove hard bounds on all paths.

Acceptance:

- negative controls prove no executor, tool, network or model provider is
  called for DENY/ASK without matching approval;
- one ledger policy event and one autonomy event exist per proposal;
- resource counters equal observed calls/tokens without double counting;
- stop/wait reasons are typed and consistent across run modes;
- an approved ASK executes the original operation exactly once.

## S4 — Real execution and independent routing

Goal: the canonical runtime performs approved work through replaceable ports.

Work:

- wire `CapabilityRouter` and `ExecutorRegistry` into runtime execution;
- normalize executor output to `ExecutionObservation`/`TaskResult`;
- keep model selection independent and invoke a model only when the approved
  operation requires it;
- replace skill-body echo behavior with an explicit instruction-only executor
  or a real executor port; never label a no-op as successful execution;
- define availability, fallback and error behavior without broad exception
  swallowing.

Acceptance:

- capability requirements select a compatible executor or produce a typed
  unavailable result;
- model routing cannot satisfy an executor capability and vice versa;
- mock/local executor integration proves one actual side effect behind Policy;
- executor failure reaches task/graph state and the ledger;
- adapters use PAW domain contracts only.

## S5 — Unified graph, checkpoint and resume loop

Goal: single tasks and DAG nodes share one state machine and recover safely.

Work:

- factor graph execution through the canonical unit loop;
- implement dependency failure and optional-dependency semantics;
- persist node status and ready-set changes with observations;
- replace proposal-counter skipping with stable idempotency matching;
- restore task, graph, context, autonomy and detector state on resume;
- cover crash points before execution, after side effect and before/after
  commit.

Acceptance:

- valid DAG order, cycle/missing-dependency rejection and required-failure
  propagation pass;
- a failed required node prevents dependent execution and task success;
- restart/resume does not repeat a completed side effect in `run`, agent or
  graph modes;
- a checkpoint is sufficient to resume without hidden in-memory state;
- all modes emit the same proposal/gate/execution/observation event sequence.

## S6 — One coherent product slice

Goal: expose the stabilized core as a usable local workflow.

Work:

- add the smallest CLI/API flow for create, run, inspect, approve and resume;
- make the task result and ledger understandable without reading SQLite;
- document and execute one offline end-to-end example;
- verify context explanations, artifacts and stop reasons in user-facing
  output.

Acceptance:

- a clean install completes the core scenarios in `PRODUCT_CHARTER.md`;
- CLI and library use the same application service/runtime;
- no provider is required for the deterministic smoke path;
- generated API/examples are executed as tests and leave quarantine.

## Core Stabilization exit gate

Expansion work may be proposed only when:

- all S0–S6 acceptance items are `VERIFIED` on the same revision;
- the implementation map has no open safety/durability `FAIL`;
- full tests, lint, build and isolated-install checks pass;
- public contracts and migrations have compatibility tests;
- runtime source has one orchestration path for an executable unit;
- documentation contains no conflicting current-phase or status claim.

After the exit gate, evaluate one adapter or feature at a time against the
product change test. Do not revive automatic phase advancement.

## Next three safe tasks

1. Run the full suite and lint, build/install the wheel in a clean environment,
   and smoke-test `paw chat` outside the repository.
2. Factor graph nodes through the same executable-unit loop as single tasks.
3. Specify a real, narrowly scoped executor adapter only after the Core
   Stabilization exit gate; keep the offline demo explicitly non-destructive.
