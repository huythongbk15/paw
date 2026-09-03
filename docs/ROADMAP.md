# PAW Core Stabilization roadmap

This is the only active work sequence. Historical numbered phases describe how
the repository grew; they do not determine what should be built next.

Current track: **qualify one clean Core Stabilization candidate through SX**.
The S0–S6 repair behavior is `OBSERVED` in the current source, and its last
recorded full working-tree verification passed before the latest
documentation/contract-test delta. That evidence is not a clean-revision exit
proof. SX must review the combined tree, resolve findings, freeze one clean
candidate and run the scheduled D3 gate on that exact revision.

| Scope | Current result | Meaning |
|---|---|---|
| S0–S6 repair implementation | `OBSERVED`; prior working-tree verification recorded | Behavior exists, but current clean-candidate evidence is not established. |
| Core Stabilization exit gate | `PARTIAL` | SX-01 through SX-03 have focused evidence; 11 qualification items remain and the next is `SX-04`. |
| E0–E3 and BETA | `BLOCKED` | Their required SX/preceding gate has not passed. |
| E4 controlled adaptation | `BLOCKED`, optional | Requires E0–E3 and a verified dataset; it is not required for BETA. |

The engineering-intelligence direction dated 2026-09-01 is recorded in the
Product Charter and Architecture. It is a design constraint, not an active
implementation track while this exit gate remains `PARTIAL`.

## Sequencing rule

Complete tracks in order. Work may move within a track, but a later track does
not start while an earlier safety or durability acceptance item fails. A user
may explicitly reprioritize work; record the resulting risk and update this
roadmap rather than silently branching into another plan.

Atomic work is tracked in `EXECUTION_CHECKLIST.md`. Each item uses the smallest
risk-based verification level that can falsify its invariant. Full-suite and
release checks are reserved for the triggers in `ENGINEERING_RULES.md`,
including this stabilization exit gate and post-gate integration milestones.

## S0 — Reproducible baseline

Goal: make every future status claim reproducible from a clean checkout.

Work:

- maintain the PAW-only `uv.lock` derived from `pyproject.toml` and reject
  captured host-environment freezes;
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

Current result: `uv.lock` is the only project lock, the captured host freeze is
removed, and automated checks enforce locked manifest coverage and reject a
replacement host snapshot.

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
- every persisted Plan references an existing canonical Task identity distinct
  from the Plan identity;
- no runtime behavior changes are hidden inside the consolidation.

Current result: `Planner` alone creates/persists `Plan`; decomposition is a pure
strategy, runtime owns action proposal, and `TaskScheduler` owns DAG readiness
and node state. `paw.core` is fixed to eleven runtime-contract exports.
`normalize_knowledge_result()` is the only stored-knowledge/result boundary and
rejects broken provenance. `Planner.plan(task_id)` now requires an existing
durable Task, derives goal/session from it and persists a distinct Plan ID with
nodes under the canonical Task ID. The current identity/sole-owner slice has a
focused persistence proof. Legacy Plan-row disposition remains an SX-10 review;
project revision, purpose and readiness remain explicitly deferred to E2.

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

Current result: `RuntimePersistence` defines two tested SQLite boundaries:
operation observation/artifact/execution events/record and checkpoint/task-
status/terminal events. Injected failures after operation, checkpoint,
task-status and terminal-ledger writes prove full rollback after close/reopen.

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

Current result: every mode uses `_execute_unit`; completed operation IDs are
stable across resume. For built-in filesystem writes, PAW commits a prepared
`EffectIntent` before invocation. A real close/reopen test proves matching final
content is reconciled without another executor call, while a changed target is
blocked as ambiguous and left untouched.

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

## Approved post-gate sequence — not yet active

This sequence narrows PAW to engineering problem solving. It may start only
after the Core Stabilization exit gate passes on one clean revision. The tracks
are ordered: measurement and subtraction precede new model behavior;
source-backed research readiness precedes implementation planning;
memory/context adaptation and governed personal-skill learning precede training.
The required product path is E0 → E1 → E2 → E3 → BETA. E4 may start only
after E3, but is optional and never a prerequisite for BETA.

The architecture boundary is already ratified even though implementation is
deferred: one Task with typed Plan purpose; versioned decision readiness;
observation/engineering verification/benchmark evaluation kept distinct;
non-terminal escalation with split runtime/Autonomy/Model Router/Policy
ownership; SkillFabric as the sole governed registry; single-user authority
through BETA.

### E0 — Engineering benchmark and feature subtraction

Goal: establish what "better at code, systems and architecture" means before
changing the product surface.

Work:

- create versioned cases for repository understanding, defect localization,
  cross-module change, refactoring, architecture design and interrupted-task
  recovery;
- freeze the distinction between operation observation, engineering
  verification and benchmark/gate evaluation, including the minimum
  `VerificationSpec`/`VerificationRecord` fields;
- define successful verified-trace eligibility independently of model output;
- prove the benchmark runner can score the existing runtime from human-reviewed
  fixtures without requiring E1–E3 capabilities;
- add decision cases whose reviewed outcomes are `READY`, `REJECTED`,
  `NEEDS_CLARIFICATION` and `SPIKE_REQUIRED`, plus cases where more research is
  the only correct result;
- capture success, invariant violations, required-evidence recall, verification
  outcome, problem/root-cause accuracy, option coverage, readiness accuracy,
  unsafe-implementation rate, model tokens, cost and latency for the existing
  runtime;
- map every retained capability to the central engineering loop and at least
  one benchmark case;
- mark unrelated or duplicative capabilities as core, compatibility-only,
  quarantined or removal candidates before adding replacements.

Acceptance:

- both the deterministic offline path and the selected cloud baseline are
  reproducible from named commands and fixtures;
- benchmark expected evidence and success conditions are reviewed rather than
  generated by the model being evaluated;
- expected decision evidence, alternatives, contrary evidence and readiness are
  human-reviewed for every research-gate case;
- executor/model success cannot self-certify engineering correctness or a
  positive verified trace;
- every public capability has an owner, engineering scenario and disposition;
- no provider, swarm, marketplace or integration expansion is bundled into the
  measurement work.

### E1 — Local project intelligence and context efficiency

Goal: reduce repeated cloud context without weakening project understanding.

Work:

- derive source-backed repository, dependency, symbol, test and change views
  through existing Memory, Knowledge and Context Compiler ownership;
- expose project revision, current behavior, constraints, relevant decisions and
  verification history as source-backed inputs to the research decision;
- build context manifests containing source identity/hash, privacy class,
  selection reason and final token budget;
- represent claim status, confidence and freshness without promoting model
  summaries or external material to fact;
- use deterministic processing first, then evaluated local summarization,
  classification or ranking only for named narrow roles;
- preserve an inspectable reason for every included, excluded and compressed
  item.

Initial acceptance targets:

- at least 95% required-evidence recall on the versioned benchmark;
- at least 30% lower median cloud input tokens than the reviewed full-context
  baseline after project warm-up;
- no regression in verified task success, critical invariant correctness or
  unauthorized-action count;
- every byte of remote project context is attributable to an approved context
  manifest;
- a decision can identify which project evidence supports or contradicts it and
  detect when a changed project revision makes the decision stale.

### E2 — Evidence-backed research gate and selective local/cloud reasoning

Goal: choose the best sufficiently supported implementation approach before
production change, using cloud depth only when the decision needs it while PAW
keeps control.

Work:

- classify each goal as `FAST`, `STANDARD` or `DEEP` from novelty, impact,
  uncertainty, reversibility and external constraints;
- extend the existing Plan with `PlanPurpose`; require an existing `Task.id` and
  preserve distinct Plan identity plus project revision;
- create one source-backed decision artifact and typed
  `ImplementationReadiness` outcome without adding a second planner or store;
- implement immutable final decision versions with
  `DRAFT`/`FINAL`/`STALE`/`SUPERSEDED` record states and constraint/revision
  invalidation;
- begin with local project reconnaissance, then compare options, assumptions and
  contrary evidence; `STANDARD` and `DEEP` include at least the smallest viable
  option and do-nothing/defer;
- define evaluated cognitive roles and explicit local/cloud eligibility;
- route using task novelty, uncertainty, impact, privacy, budget and context
  sufficiency after reconnaissance without adding a second router;
- make escalation and fallback visible in the ledger and user-facing result;
- require model reasoning to return typed evidence, uncertainty and proposed
  actions that still pass Policy and verification;
- block an implementation-purpose Plan and every mutating proposal until the
  same task/project revision has a durable `READY` decision;
- make `NEEDS_RESEARCH`, `NEEDS_CLARIFICATION`, `REJECTED` and
  `SPIKE_REQUIRED` stop, ask or schedule only the corresponding bounded work;
- keep spikes isolated and disposable, then return their evidence to the same
  readiness gate instead of promoting spike code silently;
- execute declared engineering verification through gated operations and derive
  durable `VerificationRecord` values from exact observations;
- implement the typed assessment → runtime threshold → cached Model Router
  selection → exact proposal → Policy verdict → Autonomy budget → provider
  invocation escalation protocol.

Acceptance:

- verified engineering success is not below the reviewed cloud-only baseline
  for high-impact benchmark cases;
- 100% of mutating implementation proposals reference a current `READY`
  artifact, and negative controls prove every other readiness value cannot run;
- every `STANDARD`/`DEEP` decision compares at least two viable alternatives,
  records important contrary evidence and has an explicit research stop budget;
- every Plan references an existing Task; only `IMPLEMENTATION` with a current
  matching `READY` decision may reach project mutation;
- `ExecutionObservation.success` alone cannot satisfy verification or trace
  eligibility;
- `ESCALATE` either schedules a stronger gated inference non-terminally or stops
  with a typed reason when no eligible route exists;
- 100% of local and remote model calls have a gated proposal, context manifest,
  selected role, observed usage and routing reason;
- a low-confidence or out-of-distribution local result escalates or stops
  explicitly instead of silently executing;
- neither local nor cloud output can bypass the canonical execution loop.

### E3 — Governed personal-skill accumulation

Goal: turn repeated, verified engineering work into reusable personal
procedures without converting raw activity or model output into authority.

Entry conditions:

- E0–E2 pass and verified traces identify at least one repeated workflow;
- the Skill Fabric remains the sole owner of skill lifecycle and selection;
- memory facts, user preferences and procedural skills have distinct records
  and correction rules.

Work:

- derive a candidate only from an explicit user request or a verified trace;
- preserve the research → decision → implementation → verification chain in
  every trace used to derive a candidate;
- extend the existing `SkillFabric` lifecycle; do not add a second registry or
  treat `enabled` as reviewed activation;
- record trigger, non-applicability, inputs, allowed tools, policy class,
  procedure, required evidence, success/failure checks, provenance and version;
- deduplicate candidates against active and rejected skills;
- replay candidates on reviewed benchmark cases before activation;
- require explicit acceptance for promotion and retain previous versions for
  rollback;
- measure selection precision, verified outcome and maintenance cost, then
  deprecate skills that drift or overlap.

Acceptance:

- no raw conversation, failed attempt or unreviewed model output becomes an
  active skill;
- every active personal skill has reviewed replay evidence and an accountable
  source/version;
- activation, rejection, deprecation and rollback are durable and inspectable;
- skill selection improves at least one named E0 case without lowering safety
  or required-evidence recall, and a negative case proves the skill does not
  trigger outside its scope.

### BETA — Daily engineering-partner validation

Goal: prove that one clean install supports the daily analyze, ideate, change
and review profiles through the same runtime, evidence and readiness contracts.

Work:

- define profiles as configuration rather than separate runtimes;
- keep analyze/ideate read-only, change explicitly gated and review
  non-mutating by default;
- exercise research depth, decision evidence, readiness, routing, approval,
  restart, verification and inspection across the four profiles;
- build and run the beta wheel outside the repository and record limitations.
- validate the documented single-user/local-authority boundary and avoid any
  tenant-isolation claim.

Acceptance:

- all four profiles use the canonical runtime and expose evidence, uncertainty,
  readiness and next action;
- no completed effect repeats after restart and every remote payload passes
  privacy review;
- the installed-wheel demos pass and the beta decision records known limits;
- E4 training is not required to pass this gate.

### E4 — Controlled local model adaptation

Goal: train only where verified history proves a stable, narrow and valuable
local role.

Entry conditions:

- E0–E3 pass and a sufficient set of successful, reviewed traces exists;
- memory correction, retention and deletion semantics are operational;
- the same role has a non-trained local baseline and a cloud teacher baseline.

Work and acceptance:

- build a consented, redacted, versioned dataset only from verified examples;
- record base model, dataset lineage, training configuration, evaluation and
  rollback artifact;
- accept the trained artifact only if it beats the non-trained local baseline
  for the named role without lowering end-to-end quality or safety;
- keep cloud escalation available and reject continuous online self-training
  from raw activity.

These numeric targets are initial product gates. They may change only through a
documented benchmark review, never to make an underperforming implementation
appear complete.

## Next three safe tasks

1. Execute SX-04–SX-09: review schema, authorization ordering, the canonical
   unit pipeline, persistence/reconciliation and CLI/API documentation.
2. Under SX-10, repair each resulting finding and decide the non-destructive
   disposition of legacy pre-repair Plan rows.
3. Freeze one clean candidate and run SX-12–SX-14. Only a passing exit decision
   may begin E0; E1–E4/BETA and provider expansion remain blocked meanwhile.
