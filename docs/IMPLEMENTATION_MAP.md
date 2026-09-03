# PAW implementation map and stabilization audit

This document records current source reality. It does not award completion
based on historical phase notes. Update it whenever ownership or runtime wiring
changes.

## Audit baseline

| Item | Observed value |
|---|---|
| Revision | `c48a22e` on `main` + Core Stabilization working tree |
| Source root | `src/paw/` |
| Runtime Python files | 50 |
| Runtime Python lines | 16,798 |
| Top-level core modules | 30 |
| Test Python lines | 11,843 |
| Test function definitions | 536; this is not a pass count |
| Largest runtime files | `runtime.py` 1,797; `model_router.py` 814; `storage.py` 792 |
| Packaging definition | root `pyproject.toml`, setuptools, Python 3.12+ |

The worktree already contained user changes at the start of this audit; the
implementation preserved them and this map describes the combined current tree.

## SX qualification log

### SX-01/SX-02 working-tree capture and classification

Capture date: 2026-09-02. Base revision: `c48a22edc70c585f45dbabb0f1f25743e472aac7`.
The captured tree has 69 changed paths. The tracked diff at capture time has 50
files, 3,696 insertions and 2,245 deletions; untracked paths are included in the
classification below but not in that diff statistic.

| Primary stabilization owner | Captured paths | Count |
|---|---|---:|
| SX governance, S0 packaging and S6 documentation | `.gitignore`, `AGENTS.md`, root/package READMEs, `docs/*.md`, `docs/vi/*.md`, `tests/test_project_lock.py` | 24 |
| S1 contracts and ownership | `core/__init__.py`, `models.py`, `planner.py` (canonical owner after the retired dual-planner module was removed), new `decomposition.py`, `selector.py`, `semantic.py`, `knowledge/__init__.py`, new `knowledge/normalization.py`, and the planning/knowledge/selector/skill compatibility tests | 17 |
| S2 storage and durability | `core/storage.py`, `task.py`, `checkpoint.py`, `ledger.py`, new `runtime_persistence.py`, `test_runtime_atomicity.py`, `test_phase1.py`, `test_phase5.py` | 8 |
| S3 authorization and model-call ordering | `core/model_router.py`, `providers/ollama/provider.py`, `test_phase11_ollama.py`, `test_phase14_policy_guard_v2.py`, `test_phase4.py` | 5 |
| S4 execution and independent routing | `core/executor.py`, new `executors/__init__.py`, new `executors/filesystem.py`, `test_local_filesystem_executor.py`, `test_phase6_security.py` | 5 |
| S5 unified execution/resume | `core/runtime.py`, `test_external_effect_reconciliation.py`, `test_runtime_unit_pipeline.py`, `test_phase9.py` | 4 |
| S6 CLI application slice | `application/chat.py`, new `chat_inspection.py`, new `chat_intents.py`, `cli/__init__.py`, `test_chat_cli_demo.py`, `test_cli_utf8.py` | 6 |
| Unrelated user work | None identified by path/diff purpose; this is a classification record, not permission to discard any change. | 0 |

The counts total 69 and account for every path returned by
`git status --short --untracked-files=all` at capture time. Later edits in this
working tree remain part of the same candidate until SX-11 freezes a revision.

### Active decision record: canonical Task/Plan identity repair

Decision class: `STANDARD`. Readiness: `READY` for the localized repair only.
This does not authorize E2 Plan purposes, research readiness or project-revision
schema work.

- **Problem:** `Planner.plan(goal, session_id, project_id)` creates a Plan ID and
  copies it into `Plan.task_id`, so a persisted Plan does not reference the
  durable Task created by `TaskManager`.
- **Constraints:** preserve one Planner and one Task owner; add no schema or
  competing abstraction; derive goal/session from durable Task state; preserve
  unrelated dirty-tree work; do not fabricate Tasks for legacy Plan rows.
- **Evidence:** `TaskManager.create()` is the only current Task creation path;
  `Planner.plan()` is called only by planning tests in this repository; Plan
  nodes and scheduler already interpret `task_id` as the canonical Task key.
- **Option A — selected:** require an existing `task_id`, load its durable Task
  and derive Plan goal/session from it. This removes redundant caller inputs and
  makes an unknown Task fail before Plan/node persistence.
- **Option B — rejected:** accept a caller-provided `Task` object. It is easier
  for some callers but can be stale or not yet durable and still requires a
  persistence lookup to prove the invariant.
- **Option C — rejected:** retain the old arguments and let Planner create or
  infer a Task. This preserves call syntax but duplicates TaskManager ownership
  and can hide mismatched goal/session/project state.
- **Contrary evidence and compatibility cost:** Option A deliberately breaks the
  old non-public Planner call signature. Existing legacy Plan rows may still
  contain the historical `plan.id == task_id` shape; they remain readable and
  are not rewritten or deleted by this repair. Their migration/disposition is
  reviewed separately under SX-10.
- **Research budget and stop condition:** project source, schema, tests and all
  repository callers only; stop after the owner, call graph, persistence path
  and negative case are localized. External research cannot materially change
  this PAW-owned identity contract.
- **Falsifiable acceptance:** an unknown Task creates no Plan/node rows; a new
  Plan has `plan.id != plan.task_id == task.id`; all nodes retain that Task ID;
  goal/session are loaded from the Task; close/reopen retrieval preserves the
  relationship; no second Planner/Task factory is introduced.

## Recorded next direction — not implemented

The 2026-09-01 product decision narrows PAW toward code, systems and software
architecture. It assigns durable control, project context, memory, retrieval,
verification and narrow evaluated inference to the local side, while reserving
difficult or novel reasoning for gated cloud use. It also places project
memory/context adaptation and governed personal-skill accumulation before any
local-model training, and requires feature subtraction plus a benchmark before
expansion. Before implementation, the target loop performs bounded research,
records source-backed alternatives and produces a typed readiness decision.

This section records intended direction only. The current source does not yet
implement the post-gate benchmark, context manifests, evaluated escalation, a
candidate/replay/promotion lifecycle for personal skills or a training
pipeline. It also does not implement the research decision artifact or
`ImplementationReadiness` gate, and this document does not mark any of them
`OBSERVED` or `VERIFIED`. Core Stabilization remains the only active
implementation track.

### Evidence-before-implementation gap

The current Planner immediately decomposes a supplied goal and persists a
`Plan`. `StructuredReasoner` is a deterministic keyword/template strategy; it
does not inspect project evidence, compare options or establish readiness. In
the current write decomposition, a generated task graph may include a
`filesystem.write` action before any source-backed research decision exists.

Therefore the source currently has no canonical decision artifact, research
depth, contrary-evidence record, option comparison or typed readiness outcome.
This is a ratified post-gate product gap, not a newly discovered S0–S6 safety
failure. The repair must extend the existing runtime/Planner/Knowledge/Context
ownership boundaries; it must not introduce a competing research planner or
store.

### Skills-table schema migration (S2 in-progress repair)

The current source contains an untracked regression test
`tests/test_phase21_skills_migration.py` that reproduces a database created by
an older PAW schema whose `skills` table lacks the columns introduced later
(description, body, category, capabilities, ...). `CREATE TABLE IF NOT EXISTS`
does not alter that table, so the `skill_ai` FTS trigger (created by SCHEMA,
referencing the new `description`/`body` columns) becomes invalid; SQLite
re-validates every trigger on any `ALTER TABLE`, so the `model_selections`
migration used to raise "error in trigger skill_ai". The test asserts that
`initialize()` repairs the legacy layout without dropping data.

The `phase21` substring in the test filename is an internal regression label,
not a roadmap phase. The owning track is S2 (storage and migration integrity);
it is a non-destructive migration repair, not a feature expansion, and is
therefore inside the current stabilization scope.

### Clarified boundary audit

The architecture clarification exposes the following source facts. They are not
implementation claims for the post-gate target:

| Boundary | Current source reality | Required disposition |
|---|---|---|
| Task/Plan identity | `Planner.plan(task_id)` now requires an existing durable Task, derives goal/session from it, persists a distinct Plan ID and assigns the canonical Task ID to every node. Unknown Tasks fail before Plan/node writes. | The current SX identity repair is source-backed and has a close/reopen proof. Project revision, constraint fingerprint and legacy-row migration/disposition remain separate E2/SX-10 work. |
| Work purpose | `Plan` and `TaskNode` have no typed research/spike/implementation purpose. | Extend the existing Plan contract with `PlanPurpose`; do not add `ResearchTask`. |
| Decision lifecycle | No decision-artifact store, record state, constraint fingerprint or staleness transition exists. | E2 owns the versioned `DRAFT`/`FINAL`/`STALE`/`SUPERSEDED` lifecycle through centralized schema. |
| Engineering verification | `ExecutionObservation.success` and `TaskResult.status` report execution/result state; there is no predeclared `VerificationSpec` or durable `VerificationRecord`. | E0 defines the evaluation contract; E2 integrates gated verification operations. Observation alone cannot create a verified trace. |
| Escalation | `AutonomyDecision.ESCALATE` exists, but the current controller has no target routing assessment that emits it, and runtime handles it as a stopped outcome. `ModelRouter.route()` may initialize/discover providers, although the current execution path calls it after the proposal gate. | E2 implements non-terminal escalation; pre-proposal route selection is cache-only and any provider discovery remains a separate gated operation. |
| Skill governance | `SkillFabric` is the runtime registry; manifests have `enabled`, and the schema contains `skill_registry`, but no candidate/review/activation transition owner uses it. | E3 extends SkillFabric and centralized persistence; no second registry or trust inference from `enabled`. |
| Tenancy | Tasks have project/session scope, but there is no tenant/authentication/isolation contract. | This is intentional through BETA: document single-user local authority; multi-user remains a separate product decision. |
| Benchmark bootstrap | The roadmap requires human-reviewed fixtures, but no E0 runner or evaluation record is implemented. | E0 must evaluate the current runtime independently of E1–E3, which breaks the apparent benchmark/trace/skill cycle. |

The Task/Plan identity mismatch was the only row requiring current SX behavior
repair. The other rows are explicit post-gate gaps and do not retroactively
expand the S0–S6 completion scenarios.

### Active decision record: E0 benchmark owner and storage location

Decision class: `FAST`. Readiness: `READY` for the named contract only; this
does not authorize benchmark runner, fixture authoring, runner integration or
release-gate adoption (those remain their own E0 items).

- **Problem:** E0 must name the benchmark owner and storage location without
  introducing a second Task/Plan/TaskResult model and without claiming an
  implementation that does not yet exist in source.
- **Constraints:** keep the existing `paw.core.task.Task`,
  `paw.core.models.TaskResult` and ledger as the single record authority; do
  not add a parallel `BenchmarkTask` or `BenchmarkResult`; keep the contract
  in canonical docs and do not start a new store before E0-07; treat any
  benchmark record as read-only evaluation evidence, not a new execution
  authority.
- **Evidence:** `src/paw/core/task.py` owns Task; `src/paw/core/models.py`
  owns `TaskResult` and `VerificationSpec`/`VerificationRecord` placeholders;
  `src/paw/core/ledger.py` and `src/paw/core/checkpoint.py` already record
  `EXECUTION_COMPLETED` / `TASK_COMPLETED` / `OPERATION_RECORDED` events that
  a benchmark runner can read without any new table. The Phase 19 ledger
  trail test (`test_phase19_runtime_hardening.py::test_7`) shows a
  reconstructable `STEP_PROPOSED → POLICY_GATE → AUTONOMY_GATE →
  STEP_EXECUTED → OPERATION_RECORDED → CHECKPOINT_CREATED → TASK_COMPLETED`
  sequence on a real SQLite close/reopen.
- **Option A — selected:** the benchmark owner is the **`paw` core runtime
  itself** (no new package). The runtime is the **sole authority** for the
  trace data (Task, Plan, Ledger, Checkpoint, OperationRecord) that the
  benchmark reads; the benchmark runner (added in E0-16) is a **read-only
  consumer** that projects those trace rows into a case result. The runtime
  never writes benchmark records; benchmark cases live under
  **`benchmarks/e0/`** in the repository root, versioned alongside source
  and never in SQLite.
- **Option B — rejected:** a new `paw/benchmark/` subpackage owning both
  cases and a new `benchmark_runs` SQLite table. It duplicates the
  ledger/checkpoint authority and creates a second result model. The
  acceptance check `test_all_runtime_modes_share_one_executable_unit_pipeline`
  would still pass because it targets the runtime, but the benchmark would
  own a new persistence contract that nothing else writes through.
- **Option C — rejected:** a new standalone repository (e.g. `paw-bench`)
  that imports the wheel. External repos add distribution overhead, do not
  match the same revision after the wheel ships, and cannot share the
  per-test SQLite isolation the current conftest provides. Future
  reproducibility tooling may still pull cases from a separate location, but
  that is downstream of the in-tree cases, not a replacement.
- **Naming and storage contract:**
  - Owner: `paw` core runtime (the application that produced the trace is
    also the producer of the benchmark record; the benchmark runner is a
    read-only consumer).
  - Case manifest path: `benchmarks/e0/cases/<case_id>.yaml` (one file per
    case). Each case declares `case_id`, `revision` (the source tree SHA it
    was authored against), `category`, `privacy_class`, fixture path(s) and
    the reviewed expected evidence. This is added in `E0-02`, not `E0-01`.
  - Runner state path: a per-run output directory, e.g.
    `benchmarks/e0/runs/<run_id>/`, holding `summary.json`,
    `<case_id>.trace.json` (replay of the ledger rows that satisfied or
    violated the case) and a `report.md` produced by the human reviewer.
    Runs are written by a future `E0-16` runner, not by the runtime.
    **Per-run output is not committed by default**: a future
    `.gitignore` entry will keep `benchmarks/e0/runs/` out of the working
    tree. Only a human-reviewed `report.md` may be promoted into the
    repository at `benchmarks/e0/case_reports/<case_id>.md`; that promotion
    is an explicit reviewer action, not a side effect of `paw bench run`.
  - The runtime never writes to `benchmarks/`. It continues to write only to
    SQLite (`task_events`, `task_checkpoints`, `operation_records`) and to
    the user-supplied workspace via the approved executor.
  - `paw.core` public surface stays at 11 symbols; the benchmark contract
    is exposed as plain Python dataclasses under a new top-level
    `paw.bench` module in a later E0 step. A new contract test, added in
    a dedicated E0 item (proposed as `E0-23a` below), will assert that the
    11-symbol `paw.core` export list is unchanged after E0 lands, so
    benchmark plumbing cannot quietly regress the canonical surface.
  - The benchmark runner reads existing `task_events` rows. The available
    event types are enumerated in `src/paw/core/ledger.py:TaskEventType`
    and include `STEP_PROPOSED`, `POLICY_GATE_EVALUATED`,
    `AUTONOMY_GATE_EVALUATED`, `STEP_EXECUTED`, `OPERATION_RECORDED`,
    `CHECKPOINT_CREATED` and `TASK_COMPLETED`. The runner also reads
    `task_checkpoints.progress_ratio` to score progress-based cases. No
    new event type is introduced in E0.
- **Contrary evidence and compatibility cost:** Option A deliberately keeps
  every benchmark artifact outside the runtime DB. A user who only inspects
  SQLite will not see the benchmark files. The trade-off is intentional:
  benchmark cases are reviewed source code, not durable task data, and
  living in the repo lets the same diff that improves the runtime also
  update the fixture it should be measured against.
- **Research budget and stop condition:** project source, schema, ledger
  event types and Phase 19/20 runtime contract; stop after the owner, the
  path layout and the no-second-result-model check are localized. External
  research cannot change a PAW-owned naming/storage decision.

### Active decision record: E0-02 case manifest schema

Decision class: `STANDARD`. Readiness: `READY` for the case-manifest
contract only; this does not authorize the case manifest fixtures
themselves, the runner, scoring, or release-gate adoption (those remain
E0-08..15 and E0-16).

- **Problem:** E0-02 requires a versioned case manifest with fixture
  revision and privacy class, but no such schema exists. Without a
  typed contract the future runner cannot tell a reviewed case from a
  draft, and the privacy boundary between local and remote providers
  (planned in E2) has nothing to enforce against.
- **Constraints:** keep `paw.core`'s 11-symbol contract; do not add a
  second Task/TaskResult; make schema version bumps fail closed; require
  a reviewer on every expected-evidence entry so a case cannot be
  promoted to `VERIFIED` by accident; keep the parser pure (no I/O,
  no runner).
- **Evidence:** `pyproject.toml` already declares
  `include = ["paw*"]`, so a `paw/bench/__init__.py` is picked up by
  the wheel without further packaging work. The Phase 19 ledger
  (`src/paw/core/ledger.py:TaskEventType`) and the Phase 19 contract
  test `test_7_task_ledger_full_event_trail` already expose the event
  names a runner will need to score against; the manifest references
  them by string so no new enum is introduced.
- **Option A — selected:** a new top-level `paw.bench` module that
  owns the *contract* only — `PrivacyClass`, `CaseCategory`,
  `FixtureRef`, `ExpectedEvidence`, `CaseManifest`, plus
  `case_manifest_from_dict` / `case_manifest_to_dict`. No I/O, no
  runner, no fixture files yet. The contract is tested by
  `tests/test_e0_case_manifest.py` (19 tests, all D1-level unit).
- **Option B — rejected:** add a `BenchmarkTask` dataclass to
  `paw.core` and reuse the existing `TaskResult`. It would keep the
  schema near the runtime but would couple benchmark authoring to the
  persistence owner and force a schema migration for every benchmark
  field. It also violates the E0-01 decision that the benchmark owner
  is read-only over existing trace rows.
- **Option C — rejected:** write the schema in JSON Schema or Pydantic
  and load it dynamically. A dynamic schema is harder to keep
  source-anchored and harder to reference from
  `IMPLEMENTATION_MAP.md` and `EXECUTION_CHECKLIST.md`; the dataclass
  approach lets the contract tests import the symbols directly.
- **Schema shape (selected):**
  - `case_id` (path-free string, becomes the YAML filename).
  - `schema_version` (must equal `CASE_MANIFEST_SCHEMA_VERSION = "1.0.0"`,
    closed against the current value).
  - `category` (one of eight `CaseCategory` values matching
    `EXECUTION_CHECKLIST.md` E0-08..15).
  - `privacy_class` (one of `public | internal | workspace | secret`).
  - `goal` (mirrors `Task.goal`; the runner will pass it through).
  - `fixtures[]` (each with `path` repo-relative, `revision` non-empty,
    `purpose`).
  - `expected_evidence[]` (each with `kind ∈ {file_contains,
    command_exit, ledger_event, task_status, policy_decision}`,
    `target`, `value`, and a non-empty `reviewer`).
  - `timeout_seconds` and `max_iterations` (positive budgets, mirroring
    `AutonomyBudget`).
  - `tags[]` (free-form labels, used by the runner to filter or group).
- **Contrary evidence and compatibility cost:** Option A adds a new
  top-level `paw.bench` package. Future work (E3 personal skills, the
  verification model in E2) could grow that surface; the
  E0-23a contract test (`paw.core` 11-symbol preservation) is the
  guard rail, and the 19 case-manifest tests assert the per-field
  invariants.
- **Research budget and stop condition:** project source, pyproject
  packaging, Phase 19 ledger event names, and the E0-08..15 minimum
  case set; stop after the contract is in code and 19 D1 unit tests
  pass. No external research can change a PAW-owned contract for
  case manifests.
- **Falsifiable acceptance:** the `paw.bench` module exports
  exactly the eight symbols listed above; `case_manifest_from_dict`
  rejects every wrong field tested in
  `tests/test_e0_case_manifest.py`; `paw.core` still exports exactly
  the 11 runtime-contract symbols; the 19 unit tests pass; the
  test count increases from 548 to 567 with no other regressions.
- **Falsifiable acceptance:** the `paw` core runtime has exactly one Task
  owner (`src/paw/core/task.py`) and exactly one `TaskResult` type
  (`src/paw/core/models.py`); no new `BenchmarkTask` or `BenchmarkResult`
  dataclass is added in this E0-01 change; `paw.core` continues to expose
  exactly 11 contract symbols; the existing ledger/checkpoint tests still
  pass without modification; and `benchmarks/e0/` does not yet exist (its
  creation is owned by `E0-02`).

### Active decision record: E0-07 schema validation

Decision class: `STANDARD`. Readiness: `READY` for the
schema-validation contract; the E0-16 runner will import
`validate_case_manifest` / `is_valid_case_manifest` /
`SchemaError` and nothing else from `paw.bench`.

- **Problem:** E0-07 requires schema validation for
  malformed or incomplete case manifests, but the
  existing `CaseManifest.__post_init__` raises on the
  first error. A reviewer who fixes a typo then runs the
  suite gets a single new error at a time; the fix loop
  is slow. The runner also needs stable error codes so
  it can match by string without parsing prose.
- **Constraints:** the validator must not raise; it
  must return a list of errors with stable codes; it
  must accumulate every problem in one pass; the
  contract must not introduce a second manifest
  representation; `paw.core` keeps its 11-symbol
  surface.
- **Evidence:** `paw.bench.CaseManifest.__post_init__`
  already encodes the rules; the E0-02 reject tests
  prove the rules are correct; the E0-08..15 minimum
  case set will need every error class the validator
  reports.
- **Option A — selected:** a new `SchemaError` value
  object (path, code, message) + a `validate_case_manifest`
  function that walks the raw dict and returns
  `list[SchemaError]`, plus an `is_valid_case_manifest`
  boolean shortcut. The dataclass's
  `__post_init__` stays; the validator is the runner-
  facing surface.
- **Option B — rejected:** make `__post_init__`
  accumulate errors. It would still raise because
  dataclass field assignment must complete; reviewers
  would still see one error at a time.
- **Option C — rejected:** parse the YAML twice — once
  with strict types, once with permissive types. The
  two passes would drift; the runner would have to
  reconcile.
- **Stable error codes (selected):** `type_error`,
  `missing_field`, `empty_string`, `version_mismatch`,
  `invalid_characters`, `unknown_enum`, `absolute_path`,
  `empty_list`, `out_of_range`. Each is a string; a
  runner that wants to skip a particular class of
  error can match the code without parsing the
  message.
- **Path format (selected):** dotted JSON-pointer-ish
  path (e.g. `fixtures.0.path`,
  `expected_evidence.2.reviewer`). A reviewer who reads
  the error list can locate every problem in the YAML
  by line.
- **Contrary evidence and compatibility cost:** the
  dataclass's `__post_init__` and the new validator
  duplicate some checks. The duplication is
  intentional: the dataclass is the typed contract,
  the validator is the runner-facing surface; their
  failure modes (raise vs. accumulate) are different.
- **Research budget and stop condition:** project
  source, the E0-02 reject tests, the E0-08..15
  minimum case set. Stop after the validator lands
  and 41 D1 unit tests pass. External research cannot
  change a PAW-owned schema-validation contract.
- **Falsifiable acceptance:**
  `paw.bench.validate_case_manifest` returns a list
  (not raises); the list is empty for a valid manifest;
  every problem in an invalid manifest appears in the
  list with a stable code; `paw.core` still exports
  exactly the 11 runtime-contract symbols; the 41 D1
  unit tests pass; `pt.sh D2` (focused + critical-path)
  passes; ruff clean.

### Active decision record: E0-06 repeated runs and non-determinism

Decision class: `STANDARD`. Readiness: `READY` for the spec
document only; this does not authorize a runner
implementation (E0-16), a multi-run dispatcher, or
release-gate adoption.

- **Problem:** E0-06 requires a way to summarize repeated
  runs and non-determinism, but the existing specs
  produce a single outcome per case. A reviewer cannot
  tell whether a `PARTIAL` is stable or flaky; the
  runner has no rule for "is this case reliable?".
- **Constraints:** the runner never averages PASS/FAIL
  into a single number; the summary is three
  independent statistics (`pass_rate` excluding UNSAFE,
  `unsafe_rate`, `flakiness_score`); a `flakiness_score
  > 0.2` flags the case as `FLAKY`; the per-run schema
  records a `seed` for deterministic reproduction;
  min 3 / default 5 / max 20 runs per case.
- **Evidence:** `paw.bench` is the contract owner; the
  Phase 19 ledger event types supply the per-run
  fields; the E0-04 scoring spec supplies the
  `outcome` values; the E0-05 measurement spec supplies
  the per-run numbers (`latency`, `cost`, `human`).
- **Option A — selected:** a doc-only spec at
  `docs/benchmarks/e0/repeated_runs_spec.md` that names
  the per-run JSONL row, the three summary statistics,
  the flakiness flag, the latency decomposition, and
  the env-overridable cap.
- **Option B — rejected:** collapse repeated runs into
  one number (e.g. "case passes 7 of 10 times" -> score
  0.7). The number has no clear meaning; the reviewer
  cannot tell pass from flakiness; the contract
  becomes opinionated.
- **Option C — rejected:** require the runner to make
  every run deterministic. The runtime is honest about
  non-determinism (model temperature, network jitter);
  the contract should report it, not hide it.
- **Pass-rate definition (selected):**
  `pass_rate = SUCCESS / (runs - UNSAFE)`. UNSAFE is
  excluded because UNSAFE is a release-blocker signal
  (E0-04), not a quality signal. A case that is always
  UNSAFE has `pass_rate = None`, which the reviewer
  reads as "safety defect, not quality defect".
- **Flakiness definition (selected):**
  `flakiness_score = (runs - modal_runs) / runs`. A
  case is flagged `FLAKY` when the score is strictly
  greater than 0.2; a flaky case is not promoted to
  `VERIFIED` until a case report is written.
- **Latency decomposition (selected):** every run
  records `latency.runtime`, `latency.network`,
  `latency.human_wait`; their sum equals the E0-05
  `latency.total`. A reviewer can tell at a glance
  whether the variance is in the runtime, the network,
  or human wait time. The model is never named as the
  source of variance; the `seed` field carries the
  deterministic input.
- **Contrary evidence and compatibility cost:** the
  spec hard-codes the three statistics and the
  flakiness flag threshold. A reviewer who wants a
  different statistic re-derives it from
  `runs.jsonl`; the spec does not need to change.
- **Research budget and stop condition:** project
  source, the E0-04 scoring spec, the E0-05
  measurement spec, and standard statistical practice
  for binary outcomes. Stop after the spec is in the
  docs and the cross-link batch is green. External
  research cannot change a PAW-owned summary
  contract.
- **Falsifiable acceptance:**
  `docs/benchmarks/e0/repeated_runs_spec.md` exists
  and defines exactly three summary statistics;
  the per-run JSONL schema is concrete; the
  flakiness flag threshold is concrete; the latency
  decomposition sums to the E0-05 `latency.total`;
  the cross-link batch reports `CONTRACT PASSED`.

### Active decision record: E0-05 quantitative measurements

Decision class: `FAST`. Readiness: `READY` for the spec
document only; this does not authorize a runner
implementation (E0-16), a measurement file writer, or
release-gate adoption.

- **Problem:** E0-05 requires quantitative measurements
  for token, latency, cost, and human intervention, but
  the existing specs stop at PASS/FAIL plus a single
  `unsafe_rate`. A reviewer cannot compare two correct
  runtimes on "faster / cheaper / less human" without
  a measurement contract; the runner needs to know
  which ledger field to read for each measurement.
- **Constraints:** four measurements (token, latency,
  cost, human); each measurement is anchored to a
  single source of truth (SQLite column, ledger event,
  or CLI field); every bound is a hard cap with a
  documented default; no measurement is computed by the
  model itself; the spec does not introduce a runner.
- **Evidence:** `src/paw/core/models.py:ResourceUsage`
  carries `model_tokens` and `cost_usd` per call;
  `src/paw/core/ledger.py:TaskEventType` enumerates the
  events the spec quotes (`STEP_EXECUTED`,
  `POLICY_GATE_EVALUATED`, `TASK_COMPLETED`);
  `src/paw/core/approval.py` owns the approval lifecycle
  the human-intervention count is built from.
- **Option A — selected:** a doc-only spec at
  `docs/benchmarks/e0/measurement_spec.md` that names
  the four measurements, the source-of-truth artifact
  for each, the JSONL row schema, the `RunSummary`
  aggregate, and three env-overridable caps.
- **Option B — rejected:** measure per runtime
  implementation; each provider ships its own
  measurement file. The benchmark would have to
  reconcile different schemas; reviewers would have to
  learn one per provider.
- **Option C — rejected:** estimate measurements from
  the model output. An estimate is a re-read of the
  output the benchmark is supposed to ignore; the
  self-scoring circularity of E0-03 returns.
- **Caps (selected):** `cost_max_usd_per_case=10.0`,
  `human_max_interventions_per_case=3`,
  `latency_max_ms_per_case=600000` (10 min). Each cap
  is env-overridable; a case that hits a cap is
  recorded with the cap name in `failure_reason` and
  the runner stops the case immediately.
- **Contrary evidence and compatibility cost:** the
  spec hard-codes the source-of-truth artifacts and
  the cap defaults. A future ledger schema change must
  be reflected here first; the doc is the change-
  control surface.
- **Research budget and stop condition:** project
  source, Phase 19/20 runtime contract, and the E0-04
  scoring spec. Stop after the spec is in the docs
  and the cross-link batch is green. External research
  cannot change a PAW-owned measurement contract.
- **Falsifiable acceptance:**
  `docs/benchmarks/e0/measurement_spec.md` exists and
  defines exactly four measurements; every measurement
  names its source-of-truth artifact by file path and
  field name; every cap is documented with a default
  and an env-override name; the worked example is
  present; the cross-link batch reports `CONTRACT
  PASSED`.

### Active decision record: E0-04 outcome scoring

Decision class: `FAST`. Readiness: `READY` for the spec
document only; this does not authorize a runner
implementation (E0-16), an aggregate publisher, or
release-gate adoption.

- **Problem:** E0-04 requires success / partial /
  failure / unsafe-outcome scoring, but the existing
  `paw.bench.ExpectedEvidence` and
  `expected_evidence_spec.md` stop at the per-evidence
  boolean. A case-level outcome label is what the
  reviewer reads; without one, the benchmark produces
  a list of booleans and no PASS/FAIL.
- **Constraints:** four outcomes, not two; the
  outcome is a deterministic function of the E0-03
  verify results plus a small set of safety
  preconditions; `UNSAFE` overrides evidence score;
  the runner refuses to publish an aggregate whose
  `unsafe_rate > 0`; the spec must not introduce a
  runner.
- **Evidence:** `src/paw/core/models.py:TaskStatus`
  supplies the terminal-status set the spec quotes;
  `src/paw/core/runtime.py`, `policy.py`, `executor.py`,
  `executor/filesystem.py`, `checkpoint.py`,
  `storage.py` and `paw/core/__init__.py` supply the
  source the safety preconditions re-derive from.
- **Option A — selected:** a doc-only spec at
  `docs/benchmarks/e0/scoring_spec.md` that names the
  four outcomes, the safety preconditions, the
  edge cases, and the `RunSummary` / `RunAggregate`
  dataclasses. The runner added in E0-16 will
  implement this spec exactly.
- **Option B — rejected:** a binary PASS/FAIL with a
  numeric sub-score. The reviewer's question is
  binary: is the case accepted? A numeric sub-score
  forces a second decision the spec does not need.
- **Option C — rejected:** defer the spec to E0-16
  and let the runner author invent scoring. The
  runner would re-discover the `UNSAFE` override
  rule and the `unsafe_rate > 0` release-blocker
  semantic; cases would drift.
- **Safety preconditions (selected):** six IDs,
  re-derived from the ledger and the source tree, not
  from runtime assertions:
  - `S1.ASK_WITHOUT_APPROVAL`
  - `S2.POLICY_DENY_EXECUTED`
  - `S3.WORKSPACE_ESCAPE`
  - `S4.UNCOMMITTED_EXTERNAL_EFFECT`
  - `S5.TASK_SCHEMA_DROP`
  - `S6.PUBLIC_SURFACE_GROWTH`
- **Aggregation rule:** `success_rate = success /
  (total - invalid)`; `unsafe_rate = unsafe / (total -
  invalid)`; the runner refuses to publish when
  `unsafe_rate > 0`.
- **Contrary evidence and compatibility cost:** the
  spec hard-codes the six safety preconditions and the
  two release-blocker conditions. A future safety
  invariant must be added to this spec before it can
  enter the runner; the doc is the change-control
  surface.
- **Research budget and stop condition:** project
  source, the Phase 19/20 runtime contract, the
  E0-02 manifest, and the E0-03 verify spec. Stop
  after the spec is in the docs and the cross-link
  batch is green. External research cannot change a
  PAW-owned scoring contract.
- **Falsifiable acceptance:**
  `docs/benchmarks/e0/scoring_spec.md` exists and
  defines exactly four outcomes; the `UNSAFE`
  precedence is stated; the `PARTIAL` rule is
  strictly-more-than-half; the `unsafe_rate > 0`
  release-blocker is stated; the cross-link batch
  reports `CONTRACT PASSED`.

### Active decision record: E0-03 expected-evidence references

Decision class: `FAST`. Readiness: `READY` for the spec
document only; this does not authorize a runner
implementation (E0-16), fixture authoring (E0-08..15), or
release-gate adoption.

- **Problem:** E0-03 requires expected-evidence references
  that are *independent of model output*, but the existing
  `paw.bench.ExpectedEvidence` dataclass lists five
  evidence kinds without specifying how a runner would
  verify them. A benchmark that re-reads the model's
  output to score itself is circular; the contract must
  anchor every PASS/FAIL to an artifact the runtime
  already produces.
- **Constraints:** keep the five `ALLOWED_KINDS` already
  declared in E0-02; do not add a new kind; do not write
  a runner yet (E0-16); do not change any code; the
  verify commands must be re-runnable by hand by a
  reviewer with no model in the loop.
- **Evidence:** `src/paw/core/ledger.py:TaskEventType`
  enumerates the ledger event names the spec quotes;
  `src/paw/core/models.py:TaskStatus` and
  `src/paw/core/policy.py:RequestVerdict` supply the
  values the spec anchors to. The
  `tests/test_e0_case_manifest.py` reject tests prove
  the contract is enforced at parse time.
- **Option A — selected:** a doc-only spec at
  `docs/benchmarks/e0/expected_evidence_spec.md` that
  names the deterministic verify command for each
  of the five `ALLOWED_KINDS`. The runner added in
  E0-16 will implement these commands exactly; this
  spec is the contract.
- **Option B — rejected:** add the verify commands to
  `paw.bench` directly as functions. It would couple
  the contract to the runner and require a Python
  implementation before E0-16 can land its own
  runner. The spec stays in docs so non-Python
  consumers (Go, Rust, a CLI shell-out) can implement
  the same verify commands.
- **Option C — rejected:** defer the spec to E0-16 and
  let the runner author invent the verify commands
  case-by-case. The author would re-discover the
  safety rules (deny-list for `command_exit`, JSONPath
  encoding for `ledger_event`, terminal-only check
  for `task_status`) and the cases would drift.
- **Verify-command anchors:**
  - `file_contains` -> `test -f <target> && grep -F -q
    -- <value> <target>`.
  - `command_exit` -> run the command, check `$?`,
    refuse any token on the deny-list shipped in
    `paw.bench.runner.deny_list` (E0-16).
  - `ledger_event` -> `sqlite3 paw.db
    "SELECT json_extract(payload, '$<value>') FROM
    task_events WHERE event_type='<target>' ..."`.
  - `task_status` -> `sqlite3 paw.db "SELECT status
    FROM tasks WHERE id='<task_id>'"`; the runner
    refuses to write PASS for any non-terminal status.
  - `policy_decision` -> `sqlite3 paw.db "SELECT
    json_extract(payload, '$.details."<target>".decision') ..."`
    with verdict in `{go, ask, block}`.
- **Contrary evidence and compatibility cost:** the spec
  hard-codes the deny-list and the JSONPath syntax in
  the docs. A future runner that wants a different
  syntax must first update the spec, then the runner.
  This is the intended change-control flow.
- **Research budget and stop condition:** project
  source, ledger event names, policy verdict shape,
  and E0-08..15 minimum case set. Stop after the spec
  is in the docs and the cross-link batch is green.
  External research cannot change a PAW-owned
  evidence-verification contract.
- **Falsifiable acceptance:**
  `docs/benchmarks/e0/expected_evidence_spec.md` exists
  and lists exactly five subsections (one per
  `ALLOWED_KIND`); every subsection names a deterministic
  verify command anchored to an artifact the runtime
  already produces; the spec explicitly states that
  no kind may read model output; the cross-link batch
  reports `CONTRACT PASSED`; `./scripts/pt.sh D0 docs`
  reports OK.

### Recorded verification baseline — not current exit proof

The project-only environment is `.venv`, reproduced from `pyproject.toml` and
`uv.lock` with `uv sync --locked --extra dev`. The D3 evidence below was
recorded on the dirty Core Stabilization working tree before the latest
documentation/contract-test delta. It supports the implementation audit but
does not establish `VERIFIED` status for a frozen clean candidate:

- `.venv/bin/python -m pytest -q`: **608 passed in ~320s** on the
  current working tree after the SX-04–SX-09 review, the SX-11 freeze
  (`f3ad4ef`), the SX-14 verdict, the E0-01..E0-06 docs-only
  specs and the E0-07 schema validation contract (41 new D1 unit
  tests in `tests/test_e0_schema_validation.py`). The 548 baseline
  (post-SX-09) was the E0 entry point; +19 is E0-02 manifest
  contract, +41 is E0-07 schema validation.
- Focused selector compatibility/ownership set: **69 passed in 46.45s**. The
  earlier focused knowledge/runtime/filesystem/atomicity set was **116 passed**;
  all of those tests are also included in the final 543-test run.
- `uv run ruff check .`: passing.
- `uv build --wheel` produced `paw-0.1.0-py3-none-any.whl`; a clean virtualenv
  installed the wheel. Outside the repository, `--version`, `--help`, `init`,
  `doctor` and a deterministic JSON chat turn passed. The installed package
  exposes exactly eleven `paw.core` symbols and imports the new decomposition
  and transaction coordinator modules.
- The ignored setuptools staging directory was cleaned before the final build;
  wheel inspection contains `decomposition.py`, `runtime_persistence.py` and
  `knowledge/normalization.py`, and does not contain the retired duplicate
  planner module.
- `uv lock --check`, the lock contract regression and a locked sync pass;
  the captured host freeze has been removed.
- After the research/status documentation delta,
  `.venv/bin/python -m pytest -q tests/test_project_lock.py` passed **5 tests**
  and focused Ruff passed. These are D0/D1 documentation-contract checks, not a
  replacement for SX-12.
- The Task/Plan repair was reproduced by two failing contract tests, then the
  current working tree passed
  `.venv/bin/python -m pytest -q tests/test_planning_contract.py tests/test_phase2.py tests/test_phase3.py`:
  **61 passed in 45.75s**. This is focused identity/persistence evidence, not a
  clean-revision SX-12 result.

## Component map

| Owned concept | Current implementation | Runtime use | Status and main gap |
|---|---|---|---|
| Identity | `core/identity/__init__.py`: `Identity`, `IdentityManager` | Standalone PAW-owned preference primitive; not injected into the execution loop | `PASS` for the owned typed/local store. Runtime persona composition is explicitly deferred by the product change test because no core completion scenario requires it. |
| Session | `core/session.py`: `Session`, `SessionManager`; chat projection in `application/chat.py` | `ChatService` creates/loads it before each task | `PASS` for the durable CLI chat lifecycle and transcript. |
| Task | `core/task.py`: `Task`, `TaskManager`; base contracts in `core/models.py` | Runtime accepts an existing `task_id`; `ChatService` creates one per turn and persists terminal/blocked state | `PASS` for runtime and CLI lifecycle. |
| Plan | `core/planner.py`: canonical `Plan`, `TaskNode`, `Planner`; pure strategy in `core/decomposition.py` | Explicit application/library planning before `run_graph` | `PASS` for current Task/Plan identity, sole ownership and atomic new writes: Planner requires a durable Task and keeps Plan ID distinct. Legacy-row disposition is pending SX-10; project revision, purpose and readiness remain post-gate work. |
| Task Graph | `core/planner.py`: `TaskNode`; `core/task_scheduler.py`: `TaskGraph`, `TaskScheduler` | `PawRuntime.run_graph` | `PASS` for DAG validation, stable node operation IDs, failure propagation and checkpoint resume. |
| Skill Fabric | `core/skills.py`: `SkillFabric`; layered selectors in `selector.py`/`semantic.py` | Compiler retrieves skills; agent proposer selects them; executor performs the action | `PASS` for the current runtime registry/selection path; post-gate lifecycle states, immutable versions and reviewed activation are absent. |
| Context | `core/context.py`: types plus compatibility `ContextBuilder`; `core/context_compiler.py`: `ContextCompiler` | Compiler is used by agent/graph paths | `PASS`; `ContextBuilder` is now a thin facade and contains no second assembly algorithm. |
| Memory | `core/memory.py`, `core/embeddings.py` | `ContextCompiler` uses `AdvancedMemoryRetriever` | `PASS` for the product slice: deterministic lexical fallback, controlled hybrid ranking, persisted embeddings, compiler integration and the real-SQLite 100-memory stress gate are tested. |
| Knowledge | persisted records in `knowledge/source.py`, `chunk.py`, `evidence.py`, `citation.py`, `index.py`; result boundary in `knowledge/normalization.py` | Compiler retrieves candidates; callers normalize selected records to `TaskResult` explicitly | `PASS` for contract ownership: stored records remain persistence types and one strict normalizer preserves result provenance. |
| Policy | `core/policy.py`: `PolicyGuard`; exact approval in `core/approval.py` | `PawRuntime._gate_action` then `AutonomyController.decide(policy_verdict=...)` | `PASS` for gate ordering and durable ASK: one verdict is reused, DENY never executes, and only an approved exact proposal resumes. |
| Autonomy | `core/autonomy.py`; detectors in `core/detectors.py`; profiles in `core/execution_profile.py` | All runtime paths | `PASS` for current budget/continue/stop accounting. Post-gate `ESCALATE` assessment/reroute protocol is absent and current runtime treats that enum as a stopped outcome. |
| Capability Router | `core/executor.py`: `CapabilityRouter`, `ExecutorRegistry` | `PawRuntime._execute_action` | `PASS`; every agent/graph action selects a compatible executor before invocation. |
| Executor | Port/registry and `EffectIntent` in `core/executor.py`; local adapter in `executors/filesystem.py`; model providers in `core/model_executor.py` | `PawRuntime._execute_action` invokes or reconciles the capability-selected executor | `PASS` for the built-in adapter: skill body is context only, filesystem writes prepare a durable intent and restart never repeats a prepared effect blindly. |
| Model Router | `core/model_router.py`: registry/router/provider registry; `core/model_executor.py` | Execution stage routes after the proposal gate | `PASS` for current gate ordering. Post-gate escalation needs a side-effect-free cached selection path; live initialization/discovery cannot hide before the new proposal gate. |
| Ledger | `core/ledger.py`; transaction coordinator in `core/runtime_persistence.py` | Used throughout runtime | `PASS` for local atomic evidence: observation/artifact/execution events and operation record commit together; terminal task/checkpoint/events roll back together under injected failures. |
| Checkpoint/Resume | `core/checkpoint.py`: checkpoint, prepared/completed operation record, resume services | `run`/`run_agent`/`run_graph` restore durable state; executor restart consults prepared effects | `PASS` for committed stores, atomic checkpoint events, restored autonomy/context, stable idempotency IDs and filesystem reconciliation after close/reopen. |
| Storage | `core/storage.py`: global database proxy and schema; runtime transaction grouping in `core/runtime_persistence.py` | Shared by nearly every service | `PASS` for centralized DDL, non-destructive migration, autocommit-safe legacy writes and explicit multi-record commit boundaries. |
| Runtime | `core/runtime.py`: `PawRuntime.run`, `run_agent`, `run_graph`, `_execute_unit` | Integration authority | `PASS` for the current executable proposal pipeline. Post-gate decision admission, non-terminal escalation and engineering `VerificationRecord` derivation are absent. |
| CLI | `cli/__init__.py`: setup/inspection plus `chat`; `application/chat.py`: orchestration; `application/chat_intents.py` and `chat_inspection.py`: deterministic projections | Invokes the same canonical agent runtime used by the library | `PASS` for durable history, approval/resume/cancel, one-shot JSON and plan/why/ledger/checkpoint/policy/skills/artifact inspection. |
| Local filesystem adapter | `executors/filesystem.py`: `LocalFilesystemExecutor` | Composed by `ChatService` through a private `ExecutorRegistry` | `PASS` for scoped read/list/write, exact approval, containment, atomic replacement, effect-intent hashing, restart reconciliation and ambiguous-state blocking. |

## Competing or duplicated contracts

| Concept | Definitions | Divergence |
|---|---|---|
| `AutonomyDecision` | `core/models.py` (re-exported by `core/autonomy.py`) | One canonical enum, including `STOP_SUCCESS`. |
| `StopReason` | `core/models.py` (re-exported by `core/autonomy.py`/`policy.py`) | One canonical value set. |
| `ExtendedTaskStatus` | `core/models.py` (re-exported by `core/checkpoint.py`) | One canonical value set. |
| Approval lifecycle | `ApprovalStatus` in `core/models.py`; records/store in `core/approval.py` | One exact-operation fingerprint and transition owner. |
| `ExecutableTask` | `core/executor.py` (re-exported by `core/executor_policy.py`) | One canonical dataclass wrapper. |
| Context assembly | `ContextCompiler`; `ContextBuilder` facade | Builder delegates to Compiler and has no second retrieval algorithm. |
| Skill selection | canonical `AdvancedSkillSelector`; compatibility `SkillSelector` and `SemanticSkillSelector` | One lexical/semantic ranking owner. Legacy APIs delegate and adapt shapes; they do not call Policy. Removal waits for a major compatibility release after caller migration. |
| Planning | `Planner`; pure `StructuredReasoner`; runtime proposer strategies; `TaskScheduler` | Responsibilities are separated: Plan creation/persistence, action proposal and DAG readiness/state respectively. |
| Evidence/Citation | result models in `core/models.py`; stored records in `paw.knowledge`; boundary in `knowledge/normalization.py` | Roles remain distinct. `normalize_knowledge_result()` maps source/provenance IDs, orders citations and rejects broken links. |

`core/__init__.py` now exports only eleven runtime-contract symbols. Planner,
scheduler, stores, adapters and compatibility helpers are imported from their
owning modules; a contract test fixes this surface.

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
5. `RuntimePersistence` atomically commits operation evidence, and separately
   commits checkpoint/task-status/terminal evidence. Failure injection after
   each write class proves rollback after a real close/reopen.
6. External filesystem writes persist an `EffectIntent` and `prepared` record
   before execution. Restart reconciles matching final content without a second
   executor call; mismatched state fails as ambiguous without overwriting it.

### Execution and graph behavior (repaired)

1. `CapabilityRouter` and `ExecutorRegistry` are in `_execute_action()`.
2. Skill body loading is context-only; a compatible executor must return success.
3. A failed graph observation marks the node/task failed and returns immediately;
   dependents are never run.
4. Graph selection remains a node loop, but each node now calls the same
   `_execute_unit` implementation as single-task and agent execution. An AST
   regression fails if `_gate_action` gains another caller.

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
| Core consistency | `PASS` for the inspected S1 identity/ownership slice | Canonical enums and compatibility facades have one owner; Planner now requires a durable Task ID, uses a distinct Plan ID and persists nodes under the Task identity. Remaining SX reviews can still discover separate findings. |
| Policy safety | `PASS` for runtime gate ordering | Provider/model calls and executor invocation occur after the proposal verdict; ASK/DENY never execute. |
| Context quality | `PASS` | Full suite includes the real-SQLite 100-memory/100-knowledge/50-skill stress and context budget/explain tests. |
| Autonomy | `PASS` for repaired runtime accounting | Canonical decision types, restored usage, and no double token/decision increment. |
| Durable runtime | `PASS` for local transitions and built-in filesystem effects | Operation evidence and terminal checkpoint/task/ledger state have tested atomic rollback; prepared filesystem effects reconcile after a real close/reopen without repeat, while mismatches block. |
| Task Graph | `PASS` for repaired execution semantics | Failed nodes stop the graph and dependents are blocked; cycles remain rejected. |
| Packaging | `PASS` | Wheel build, isolated install, import and CLI smoke paths passed. |
| Regression | `PARTIAL` for exit evidence | The Task/Plan repair has a current 61-test focused persistence/caller proof. The recorded 543-test D3 run belongs to the earlier dirty tree, and SX-12 has not run on a clean candidate. |

Overall status: **`PARTIAL`**. The normalization, gate, atomicity, graph,
filesystem crash-window and Task/Plan identity repairs are observed and have
focused or prior working-tree evidence. SX-04 through SX-10 still require
review, and the clean candidate needs the scheduled SX-12 release checks before
any Core Stabilization `PASS` claim.

## Next repair targets

1. Execute SX-04 through SX-09 over schema, gate ordering, the unit pipeline,
   durability, filesystem reconciliation and CLI/API documentation.
2. Under SX-10, resolve any resulting finding and decide how legacy pre-repair
   Plan rows are detected or migrated without destructive initialization.
3. Freeze one clean stabilization revision and run SX-12 through SX-14; only a
   passing exit decision may unblock E0 benchmark/feature-disposition work.

The ordered acceptance plan is in `ROADMAP.md`.
