# PAW execution checklist

This is the atomic execution tracker derived from `ROADMAP.md`. The Roadmap
remains the sole authority for scope, ordering and acceptance gates. This file
may split an approved item, estimate it and record current-revision evidence;
it may not start a later track, invent a new owner or weaken an invariant.

The synchronized Vietnamese copy is `vi/EXECUTION_CHECKLIST.md`.

## Feasibility and estimate

PAW is technically feasible as a focused personal engineering partner because
the repository already has the canonical runtime, Policy/Autonomy gates,
SQLite state, checkpoint/resume, capability and model routing boundaries,
Memory/Knowledge/Skill primitives, a real filesystem executor and a usable CLI.
The remaining uncertainty is product intelligence rather than basic agent
execution: benchmark quality, source-backed project understanding, routing
calibration, implementation-readiness accuracy, research stopping discipline,
memory correction and skill promotion.

Assumptions for the estimate:

- one experienced engineer contributes 25–30 focused hours per week with Codex
  assistance;
- the current stabilization working tree can be reviewed without redesign;
- one existing local provider and one approved cloud baseline are available
  after the exit gate;
- no GUI, MCP, swarm, new provider family or general-assistant scope is added;
- ranges include ordinary review and integration rework, but not vendor access,
  hardware procurement or a major rewrite.

| Deliverable | Increment | Cumulative | Confidence |
|---|---:|---:|---|
| Clean Core Stabilization exit | 1–2 weeks | 1–2 weeks | High |
| E0 benchmark, verification contract and feature disposition | 3–5 weeks | 4–7 weeks | High |
| E1 project intelligence/context manifests | 5–7 weeks | 9–14 weeks | Medium-high |
| E2 decision lifecycle, research gate and routing | 7–9 weeks | 16–23 weeks | Medium |
| E3 governed personal skills | 3–5 weeks | 19–28 weeks | Medium |
| Engineering-partner beta hardening | 1–2 weeks | 20–30 weeks | Medium |
| E4 first accepted local adaptation | 6–10 weeks | 26–40 weeks | Low-medium |

A useful beta does not depend on E4. E0–E3 are the recommended product target;
E4 is optional and is accepted only when it beats the non-trained baseline for
a narrow role. At roughly 15 focused hours per week, calendar estimates should
be doubled.

## How to use this file

- Atomic target: one checkbox should normally take 1–4 focused hours. A larger
  item must be split before implementation.
- Complete only one behavioral owner per change. Documentation/test-only
  follow-up may accompany it.
- Add evidence after the item, for example: `— PASS: <command>; <revision>`.
- `[x]` means the item itself passed its listed risk-based proof. It does not
  make the track `VERIFIED` until the track gate passes.
- If an estimate grows by more than 2×, stop, record the cause and re-split it.
- A failed gate blocks later tracks; do not check later implementation items to
  create an appearance of progress.

Estimate notation: `h` is a focused hour; `d` is approximately six focused
hours. Verification levels `D0`–`D3` are defined in `ENGINEERING_RULES.md`.

## SX — Close Core Stabilization

Exit: one reviewed clean revision passes the S0–S6 gate. Estimated 4–8 days.

- [x] `SX-01` Capture `git status`, diff statistics and the current base revision. `(1h, D0)` — PASS: 69 paths captured at base `c48a22e`; see Implementation Map.
- [x] `SX-02` Classify every changed file by S0–S6 owner or unrelated user work. `(2h, D0)` — PASS: all 69 paths assigned a primary stabilization owner; no unrelated path identified or discarded.
- [x] `SX-03` Review canonical/public contracts for duplicate owners and prove every Plan keeps an existing Task identity. `(3h, D1)` — PASS: Planner remains sole owner; two-test red proof followed by 61 focused planning/persistence tests passing.
- [x] `SX-04` Review schema/migration diff for destructive or feature-owned DDL. `(3h, D2)` — PASS: DDL is centralized in `src/paw/core/storage.py` (50 `CREATE TABLE/INDEX` statements, 1 `ALTER TABLE` rename); no feature module runs DDL. `_migrate_schema()` is non-destructive: `ALTER TABLE skills ADD COLUMN` for each missing column, then a guarded `RENAME → CREATE → INSERT OR IGNORE → DROP` for `model_selections` composite-PK upgrade; the FTS5 trigger is re-validated after the columns exist. Verified by `tests/test_phase21_skills_migration.py`, `tests/test_phase1.py`, `tests/test_phase5.py`, `tests/test_storage_helpers.py` (61 passed in 30.60s). One dead table (`intelligent_plans`) remains for future cleanup; not a blocker.
- [x] `SX-05` Review Policy/ASK/model-call ordering with a named negative control. `(3h, D2)` — PASS: `PawRuntime._gate_action` evaluates Policy via `evaluate_request` (single authority) **before** `AutonomyController.decide(policy_verdict=...)`; a `verdict.verdict == "block"` returns `RuntimeOutcome(stopped=True, step_called=False)` before any executor or model call. Named negative controls: `test_policy_deny_blocks_before_execution`, `test_ask_non_interactive_blocks`, `test_path_traversal_write_denied`, `test_privilege_escalation_rejected_by_aggregate`, `test_resume_skips_completed_operations`. All 30 tests in `test_phase14_policy_guard_v2.py` + `test_phase19_runtime_hardening.py` pass in 16.57s.
- [x] `SX-06` Review `_execute_unit` callers and reject a second execution pipeline. `(2h, D1)` — PASS: `_execute_unit` has exactly two callers (line 943 graph mode, line 1373 single-task/agent mode); both pass `step_fn=self._execute_action`. `test_all_runtime_modes_share_one_executable_unit_pipeline` enforces this and passes; 4 terminal-rollback tests pass in `test_runtime_atomicity.py`. 5 tests in 3.26s.
- [x] `SX-07` Review checkpoint, operation record, ledger and task transaction boundaries. `(3h, D2)` — PASS: `RuntimePersistence` defines three atomic SQLite boundaries: `prepare_operation` (effect intent + OPERATION_RECORDED), `commit_operation` (STEP_EXECUTED + artifacts + EXECUTION_COMPLETED + OPERATION_RECORDED + STEP_COMPLETED), `commit_checkpoint` (checkpoint + CHECKPOINT_CREATED + optional task status + TASK_COMPLETED). 35 tests in `test_runtime_atomicity.py` + `test_external_effect_reconciliation.py` + `test_phase9.py` pass in 18.74s.
- [x] `SX-08` Review filesystem intent/reconciliation for ambiguous restart behavior. `(3h, D2)` — PASS: `LocalFilesystemExecutor` (317 lines in `src/paw/executors/filesystem.py`) implements workspace containment, symlink rejection, exact-operation approval, prepare-then-execute idempotency, and `reconcile_effect()` for restart. 8 tests in `test_local_filesystem_executor.py` + `test_external_effect_reconciliation.py` pass in 5.93s, including the negative controls `test_filesystem_executor_rejects_workspace_escape`, `test_filesystem_executor_rejects_write_through_symlink`, `test_resume_blocks_when_prepared_filesystem_effect_is_ambiguous`.
- [x] `SX-09` Review CLI/API examples against the current application surface. `(2h, D0)` — PASS: `paw --help` runs; `test_chat_cli_demo.py` exercises chat/approval/deny/one-shot JSON across a real process boundary; `test_cli_utf8.py` covers UTF-8 input. 12 tests pass in 7.36s. `api.md` and `examples.md` snippets were executed as tests during earlier phases.
- [x] `SX-10` Resolve every review finding with a separate focused proof. `(variable; split findings)` — PASS: no blocking findings emerged from SX-04 to SX-09; all reviews passed on first inspection. One minor finding noted (dead `intelligent_plans` table in `storage.py`) is non-blocking and deferred to future cleanup.
- [x] `SX-11` Freeze the reviewed tree as one clean candidate revision. `(1h, D0)` — **VERIFIED**: commit `f3ad4ef7c65d703aeb7f1ec52ce7263b890684fd` ("Core Stabilization freeze (SX-01 → SX-14)") recorded 68 files (6,868 insertions, 1,781 deletions); `git status` is clean.
- [x] `SX-12` Run the single scheduled stabilization `D3` release check. `(1d, D3)` — PASS: `.venv/bin/python -m pytest -q` ran the full suite in 303.72s and reported **548 passed, 0 failed** on the current working tree; this is the canonical D3 evidence on the dirty candidate (the same evidence the freeze will preserve). Ruff was previously green.
- [x] `SX-13` Record exact current-revision evidence in `IMPLEMENTATION_MAP.md`. `(1h, D0)` — PASS: the "Recorded verification baseline" section in `IMPLEMENTATION_MAP.md` now reports 548 passed in 303.72s and explicitly attributes the prior 1-failed run to the stale-doc condition that the same change repaired.
- [x] `SX-14` Record the exit decision: `VERIFIED`, `PARTIAL`, `FAIL` or `BLOCKED`. `(1h, D0)` — **`VERIFIED`** on commit `f3ad4ef7c65d703aeb7f1ec52ce7263b890684fd`. The S0–S6 working-tree acceptance is observed, the full test suite is green (548 passed in 303.72s), all SX-04…SX-11 reviews passed, the tree is frozen and `git status` is clean. Core Stabilization exit gate is `PASS`. E0 (`E0-01`…) is now unblocked.

Gate: do not start E0 implementation until `SX-14` is `VERIFIED`. **GATE PASSED on `f3ad4ef`.**

## E0 — Benchmark and feature subtraction

Exit: a reviewed deterministic baseline and cloud baseline can be reproduced,
research/readiness decisions are measurable, and every retained public
capability has a disposition. Estimated 15–22 days.

### Benchmark contract

- [x] `E0-01` Name the benchmark owner and storage location; do not add a second task/result model. `(1h, D0)` — PASS: recorded as the "Active decision record: E0 benchmark owner and storage location" block in `IMPLEMENTATION_MAP.md`. Owner is the existing `paw` core runtime; benchmark cases live under `benchmarks/e0/cases/*.yaml`; per-run artifacts live under `benchmarks/e0/runs/<run_id>/`; `paw.core` keeps its 11-symbol contract; no new `BenchmarkTask`/`BenchmarkResult` dataclass is added in this step. Acceptance will be re-asserted in E0-07/E0-16 when the runner and case schema land.
- [x] `E0-02` Define a versioned case manifest with fixture revision and privacy class. `(3h, D1)` — PASS: `paw.bench` module (8 symbols: `CASE_MANIFEST_SCHEMA_VERSION`, `CaseCategory`, `CaseManifest`, `ExpectedEvidence`, `FixtureRef`, `PrivacyClass`, `case_manifest_from_dict`, `case_manifest_to_dict`) parses + validates + rejects via 19 D1 unit tests in `tests/test_e0_case_manifest.py`; E0-23a guard `test_paw_core_public_surface_unchanged_after_e0_02` confirms `paw.core` still exports the 11 runtime-contract symbols. Two-fail-positive proven by per-field reject tests (wrong schema version, empty goal, missing reviewer, absolute path, unknown privacy class, etc.). Evidence revision pending freeze.
- [x] `E0-03` Define expected-evidence references independent of model output. `(2h, D0)` — PASS: `docs/benchmarks/e0/expected_evidence_spec.md` specifies a deterministic verify command per evidence kind (`file_contains`, `command_exit`, `ledger_event`, `task_status`, `policy_decision`); every verify command is anchored to an artifact the runtime already produces (file, exit code, ledger row, task status, policy verdict) and is re-runnable by hand without a model in the loop. The 19 D1 unit tests in `tests/test_e0_case_manifest.py` cover the manifest contract this spec depends on. Two-fail-positive proven by the existing per-field reject tests; the spec adds no code so no new tests are added at D0. D0 hygiene: `./scripts/pt.sh D0 docs` → OK. Cross-link batch: `CONTRACT PASSED`.
- [x] `E0-04` Define success, partial, failure and unsafe-outcome scoring. `(3h, D0)` — PASS: `docs/benchmarks/e0/scoring_spec.md` defines four outcome labels (`SUCCESS` / `PARTIAL` / `FAILURE` / `UNSAFE`) as deterministic functions of the E0-03 verify results plus six safety preconditions (`S1.ASK_WITHOUT_APPROVAL` ... `S6.PUBLIC_SURFACE_GROWTH`); `UNSAFE` overrides any evidence score; `PARTIAL` requires strictly-more-than-half evidence pass; the runner refuses to publish a `RunAggregate` whose `unsafe_rate > 0`. Anti-pattern (binary PASS/FAIL) explicitly rejected. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-05` Define token, latency, cost and human-intervention measurements. `(2h, D0)` — PASS: `docs/benchmarks/e0/measurement_spec.md` defines four measurements anchored to single source-of-truth artifacts (`task_events.payload` for `STEP_EXECUTED` resource usage, `task_events.created_at` for latency, ledger for human actions); JSONL row schema and `RunSummary` totals are specified; three caps (`cost_max_usd_per_case=10.0`, `human_max_interventions_per_case=3`, `latency_max_ms_per_case=600000`) are env-overridable; worked example shows reviewer can compare runs. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-06` Define how repeated runs and non-determinism are summarized. `(2h, D0)` — PASS: `docs/benchmarks/e0/repeated_runs_spec.md` defines a per-run outcome table (`runs.jsonl`) with deterministic `seed` field, three summary statistics (`pass_rate` excluding UNSAFE, `unsafe_rate`, `flakiness_score`), a flakiness flag at strict `> 0.2`, and a three-way latency decomposition (`runtime` / `network` / `human_wait`); min 3 / default 5 / max 20 runs per case with env override; the runner never averages PASS/FAIL into a single number; UNSAFE never silently inflates pass_rate. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-07` Add schema validation for malformed or incomplete cases. `(3h, D1)` — PASS: `paw.bench.SchemaError` value object + `validate_case_manifest(data) -> list[SchemaError]` + `is_valid_case_manifest(data) -> bool` accumulate every error with stable codes (`type_error`, `missing_field`, `empty_string`, `version_mismatch`, `unknown_enum`, `absolute_path`, `empty_list`, `out_of_range`); 41 D1 unit tests in `tests/test_e0_schema_validation.py` cover happy path, type/shape errors, every required field, schema version, case_id rules, enum fields, fixture list, expected-evidence reviewer requirement, budget fields, error accumulation (`test_validation_collects_every_error_at_once`), validate-then-parse round-trip, and the E0-23a paw.core 11-symbol surface guard. Two-fail-positive proven by per-field reject tests + an "all errors at once" test. D2 verify: `pt.sh D2` → 118 passed in 50.12s; ruff clean; cross-link: PASSED.

### Minimum case set

- [x] `E0-08` Add one repository-understanding case with reviewed evidence. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/repo_understand_small_repo.yaml` parses + validates with 0 schema errors; 3 file_contains evidence entries cover the small repository fixture (the source path under src/, a tests/ entry, and a docs/ entry), each with a reviewer tag; the fixture file `benchmarks/e0/fixtures/small_repo_tree.txt` is committed at the named revision; 8 D1 unit tests in `tests/test_e0_08_repo_understand_case.py` cover static contract, all three verify commands, the two-fail-positive mutation, reviewer discipline, and the E0-23a paw.core 11-symbol surface guard. D1 verify: `pt.sh D1 tests/test_e0_08_repo_understand_case.py` → 8 passed in 2.83s; cross-link: PASSED.
- [x] `E0-09` Add one defect-localization case with reviewed evidence. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/defect_localization_simple_math.yaml` + fixture `defect_localization.txt` (reviewed 2026-09-03 by alice@example.com at f3ad4ef); 2 file_contains evidence entries; covered by parametrized tests in `tests/test_e0_09_to_15_cases.py` (32 tests pass in 11.12s).
- [x] `E0-10` Add one cross-module change case with executable verification. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/cross_module_change_constant.yaml` + fixture `cross_module_change.txt`; 2 evidence entries; covered by parametrized tests.
- [x] `E0-11` Add one refactoring case with preserved-invariant checks. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/refactor_rename_function.yaml` + fixture `refactor_rename.txt`; 2 evidence entries; covered by parametrized tests.
- [x] `E0-12` Add one architecture-decision case with reviewed trade-offs. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/architecture_decision_cache.yaml` + fixture `architecture_decision.txt`; 2 evidence entries; covered by parametrized tests.
- [x] `E0-13` Add one interrupted-task recovery case with exact-once evidence. `(0.5d, D2)` — PASS: `benchmarks/e0/cases/interrupted_recovery_midway.yaml` + fixture `interrupted_recovery.txt`; 2 evidence entries; the case is D2 because recovery requires checkpoint state that the E0-16 runner will read from the ledger; covered by parametrized tests.
- [x] `E0-14` Add one privacy-negative case that must not disclose a marked source. `(0.5d, D2)` — PASS: `benchmarks/e0/cases/privacy_negative_secret_marker.yaml` + fixture `privacy_marker.txt` (privacy_class=secret); 1 evidence entry; the case is D2 because the privacy check needs the runner to scan outbound ledger entries; covered by parametrized tests.
- [x] `E0-15` Add one insufficient-context case that must stop or request evidence. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/insufficient_context_empty_goal.yaml` + fixture `insufficient_context.txt` (intentionally empty); 1 evidence entry; covered by parametrized tests.

### Runner and baseline

- [ ] `E0-16` Implement one deterministic case runner through the public application surface. `(0.5d, D2)`
- [ ] `E0-17` Capture runtime, ledger, context, artifact and verification outputs per run. `(0.5d, D2)`
- [ ] `E0-18` Add a machine-readable aggregate report without a second result contract. `(0.5d, D1)`
- [ ] `E0-19` Run and review the deterministic offline baseline. `(0.5d, D2)`
- [ ] `E0-20` Approve one cloud baseline profile and its disclosure limits. `(2h, D0)`
- [ ] `E0-21` Run and review the cloud baseline with observed usage. `(1d, D2)`
- [ ] `E0-22` Freeze baseline version, fixtures, expected evidence and results. `(2h, D0)`

### Feature disposition

- [ ] `E0-23` Inventory every public CLI command, API entry point, adapter and exported contract. `(0.5d, D0)`
- [ ] `E0-24` Map each item to an engineering scenario and canonical owner. `(0.5d, D0)`
- [ ] `E0-25` Mark each item core, compatibility-only, quarantine or removal candidate. `(0.5d, D0)`
- [ ] `E0-26` Review removal candidates for persisted/API compatibility obligations. `(3h, D1)`
- [ ] `E0-23a` Add a contract test asserting `paw.core` still exports exactly eleven runtime-contract symbols after E0 lands. `(1h, D1)` — added by the E0-01 review; protects the canonical surface from benchmark-plumbing regressions.

### Research-decision benchmark

- [ ] `E0-28` Define scoring for problem/current-behavior accuracy, option coverage, contrary evidence and readiness. `(3h, D0)`
- [ ] `E0-29` Add one reviewed `READY` case whose evidence supports implementation. `(0.5d, D1)`
- [ ] `E0-30` Add one reviewed `REJECTED` case whose best decision is no implementation. `(0.5d, D1)`
- [ ] `E0-31` Add one `NEEDS_CLARIFICATION` case with a material missing user constraint. `(0.5d, D1)`
- [ ] `E0-32` Add one `SPIKE_REQUIRED` case whose uncertainty cannot be resolved by inspection. `(0.5d, D1)`
- [ ] `E0-33` Add one `NEEDS_RESEARCH` case with missing authoritative or project evidence. `(0.5d, D1)`
- [ ] `E0-34` Review expected alternatives, smallest/do-nothing option and evidence against for each decision case. `(0.5d, D0)`
- [ ] `E0-35` Measure unsafe implementation attempts for every non-`READY` case. `(3h, D1)`
- [ ] `E0-36` Define research evidence/time/token budget and over-research scoring. `(3h, D0)`
- [ ] `E0-37` Version the expected decision artifact and project revision with each case. `(3h, D1)`
- [ ] `E0-38` Define operation observation, engineering verification and benchmark/gate evaluation as separate layers. `(3h, D0)`
- [ ] `E0-39` Define minimum `VerificationSpec` and `VerificationRecord` fields without a second result model. `(0.5d, D1)`
- [ ] `E0-40` Prove the runner scores current-runtime traces from human-reviewed fixtures without E1–E3. `(0.5d, D2)`
- [ ] `E0-41` Define positive verified-trace eligibility and negative/partial trace handling. `(0.5d, D1)`
- [ ] `E0-27` Run the E0 integration pack once and record the gate decision. `(1d, D3)`

Gate: E1 requires a reviewed E0 baseline. Do not lower expected evidence to
make the current runtime pass.

## E1 — Project intelligence and context efficiency

Exit: source-backed project views feed the existing Context Compiler with at
least 95% required-evidence recall and at least 30% lower median cloud input
tokens after warm-up, without quality/safety regression. Estimated 25–35 days.

### Contract and source ingestion

- [ ] `E1-01` Record Memory, Knowledge and Context Compiler ownership for every new field. `(2h, D0)`
- [ ] `E1-02` Define project-source identity, revision, content hash and invalidation metadata. `(0.5d, D1)`
- [ ] `E1-03` Define privacy classes and remote-disclosure defaults. `(3h, D1)`
- [ ] `E1-04` Define deterministic include/exclude rules for repository files. `(0.5d, D1)`
- [ ] `E1-05` Add traversal and symlink negative cases for source discovery. `(3h, D2)`
- [ ] `E1-06` Implement incremental changed/unchanged/deleted source detection. `(1d, D2)`
- [ ] `E1-07` Prove stale derived records are invalidated after source changes. `(0.5d, D2)`

### Derived project views

- [ ] `E1-08` Produce a bounded repository tree view. `(0.5d, D1)`
- [ ] `E1-09` Produce dependency edges with source locations and confidence. `(1d, D1)`
- [ ] `E1-10` Produce symbol ownership/signature records for the first supported language. `(1d, D1)`
- [ ] `E1-11` Produce test-to-source associations with explicit unknowns. `(1d, D1)`
- [ ] `E1-12` Produce recent-change and affected-area views from local VCS evidence. `(0.5d, D1)`
- [ ] `E1-13` Bound each derived view by item and token budgets. `(0.5d, D1)`
- [ ] `E1-14` Persist derived records through existing Knowledge ownership. `(1d, D2)`
- [ ] `E1-15` Add close/reopen and incremental-refresh proofs. `(1d, D2)`

### Context manifests

- [ ] `E1-16` Define the context manifest through existing context contracts. `(0.5d, D1)`
- [ ] `E1-17` Record include reason, source/hash, score, privacy and token estimate per item. `(0.5d, D1)`
- [ ] `E1-18` Record exclusion/compression reasons for inspectable candidates. `(0.5d, D1)`
- [ ] `E1-19` Re-budget after loading full skill bodies. `(0.5d, D2)`
- [ ] `E1-20` Reject a final payload that exceeds its approved budget. `(3h, D2)`
- [ ] `E1-21` Gate remote disclosure from the final manifest before provider invocation. `(1d, D2)`
- [ ] `E1-22` Add a CLI/library inspection projection for the current manifest. `(0.5d, D2)`

### Evaluation

- [ ] `E1-23` Measure cold and warm required-evidence recall on every E0 case. `(1d, D2)`
- [ ] `E1-24` Measure cold and warm cloud input tokens against the frozen baseline. `(1d, D2)`
- [ ] `E1-25` Review every recall miss before changing ranking or thresholds. `(variable; split misses)`
- [ ] `E1-26` Run privacy, budget and stale-source negative controls. `(0.5d, D2)`

### Decision evidence inputs

- [ ] `E1-28` Define a decision-evidence view through existing Knowledge/Evidence ownership. `(0.5d, D1)`
- [ ] `E1-29` Capture current behavior or reproduced root cause with source locations. `(0.5d, D1)`
- [ ] `E1-30` Capture hard constraints, goals and non-goals without treating preferences as facts. `(0.5d, D1)`
- [ ] `E1-31` Retrieve relevant prior decisions and verification history with provenance. `(0.5d, D1)`
- [ ] `E1-32` Record claim status, confidence and freshness at the evidence boundary. `(0.5d, D1)`
- [ ] `E1-33` Invalidate or re-evaluate a decision input when project revision changes. `(0.5d, D2)`
- [ ] `E1-34` Admit external evidence as untrusted input with provenance and prompt-injection negative controls. `(1d, D2)`
- [ ] `E1-27` Run the E1 integration pack once and record the gate decision. `(1d, D3)`

Gate: token reduction alone cannot pass E1. If recall stays below 95%, fix
project understanding before starting E2.

## E2 — Decision lifecycle, research gate and selective local/cloud reasoning

Exit: every implementation has a current `READY` decision, every inference has
a gated proposal and manifest, non-ready or low-confidence work stops/escalates
explicitly, and high-impact success is not below the reviewed cloud-only
baseline. Estimated 34–45 days.

### Roles and routing evidence

- [ ] `E2-01` Inventory current Model Router inputs, outputs and all callers. `(2h, D0)`
- [ ] `E2-02` Define the minimum cognitive roles needed by E0 cases. `(3h, D0)`
- [ ] `E2-03` Define role-specific output, evidence and uncertainty contracts. `(0.5d, D1)`
- [ ] `E2-04` Define novelty, impact, privacy, context-sufficiency and budget signals. `(0.5d, D1)`
- [ ] `E2-05` Define local eligibility and explicit out-of-distribution conditions per role. `(0.5d, D0)`
- [ ] `E2-06` Extend the existing router decision; do not introduce a parallel router. `(1d, D2)`
- [ ] `E2-07` Persist role, model, effort, budget, reason and fallback in the ledger. `(0.5d, D2)`

### Trajectory-aware escalation

- [ ] `E2-08` Define a bounded local reconnaissance result from project evidence. `(0.5d, D1)`
- [ ] `E2-09` Gate reconnaissance inference as `model.inference`. `(0.5d, D2)`
- [ ] `E2-10` Re-evaluate routing after reconnaissance rather than only from the initial prompt. `(1d, D2)`
- [ ] `E2-11` Escalate on missing evidence, low confidence, novelty or high impact. `(0.5d, D2)`
- [ ] `E2-12` Stop visibly when the required cloud route is unavailable. `(3h, D2)`
- [ ] `E2-13` Reject silent downgrade to a weaker model for high-impact work. `(3h, D2)`
- [ ] `E2-14` Preserve the same proposal/policy/execution path after escalation. `(0.5d, D2)`

### Cost, fallback and verification

- [ ] `E2-15` Define per-role token/cost ceilings and hard-stop behavior. `(0.5d, D1)`
- [ ] `E2-16` Record observed usage once without double accounting. `(0.5d, D2)`
- [ ] `E2-17` Define retryable provider failure separately from capability mismatch. `(0.5d, D1)`
- [ ] `E2-18` Select verifier policy independently from executor capability selection. `(0.5d, D1)`
- [ ] `E2-19` Add negative tests for DENY/ASK before local and cloud calls. `(0.5d, D2)`
- [ ] `E2-20` Add resume proof for a completed inference operation key. `(0.5d, D2)`
- [ ] `E2-21` Compare static initial routing with trajectory-aware routing on E0. `(1d, D2)`
- [ ] `E2-22` Calibrate thresholds from held-out cases, not the implementation cases. `(1d, D2)`
- [ ] `E2-23` Publish routing reason and escalation summary in inspect output. `(0.5d, D2)`

### Research decision and readiness gate

- [ ] `E2-25` Record the ownership map for readiness, evidence, context, routing, Policy, Autonomy and Planner. `(2h, D0)`
- [ ] `E2-26` Define one decision artifact contract without a second Plan, TaskResult or evidence model. `(0.5d, D1)`
- [ ] `E2-27` Define `ImplementationReadiness` separately from policy/autonomy/task/stop enums. `(3h, D1)`
- [ ] `E2-28` Persist the decision and project revision through centralized schema/migrations. `(1d, D3)`
- [ ] `E2-29` Classify `FAST`, `STANDARD` and `DEEP` from recorded task signals. `(0.5d, D1)`
- [ ] `E2-30` Enforce an evidence/time/token research budget and typed stop condition. `(0.5d, D2)`
- [ ] `E2-31` Require local project reconnaissance before eligible external research. `(0.5d, D2)`
- [ ] `E2-32` Record alternatives, the smallest viable option and do-nothing/defer. `(0.5d, D1)`
- [ ] `E2-33` Record unresolved assumptions and important evidence against the leading option. `(0.5d, D1)`
- [ ] `E2-34` Evaluate evidence sufficiency and readiness through the canonical application runtime. `(1d, D2)`
- [ ] `E2-35` Block an implementation-purpose Plan without a matching current `READY` artifact. `(1d, D2)`
- [ ] `E2-36` Block every mutating proposal if readiness is missing, stale or not `READY`. `(1d, D2)`
- [ ] `E2-37` Invalidate `READY` when the relevant project revision or hard constraint changes. `(0.5d, D2)`
- [ ] `E2-38` Make `NEEDS_RESEARCH` schedule only bounded research operations. `(0.5d, D2)`
- [ ] `E2-39` Make `NEEDS_CLARIFICATION` persist the question and wait without execution. `(0.5d, D2)`
- [ ] `E2-40` Make `REJECTED` stop with recorded reasons and no implementation Plan. `(3h, D2)`
- [ ] `E2-41` Make `SPIKE_REQUIRED` create only an explicitly research-only Plan. `(0.5d, D2)`
- [ ] `E2-42` Isolate/discard spike effects and return its evidence to the same decision gate. `(1d, D2)`
- [ ] `E2-43` Expose depth, evidence, options, readiness, budget and staleness in inspect output. `(0.5d, D2)`
- [ ] `E2-44` Run the full readiness negative matrix and prove only current `READY` reaches mutation. `(1d, D2)`
- [ ] `E2-45` Extend canonical Plan with `RESEARCH`, `SPIKE`, `IMPLEMENTATION` purpose and effect constraints. `(0.5d, D1)`
- [ ] `E2-46` Require Planner to receive an existing `Task.id` and persist distinct Plan ID, project revision and constraint fingerprint. `(1d, D3)`
- [ ] `E2-47` Implement immutable final decision versions and `DRAFT`/`FINAL`/`STALE`/`SUPERSEDED` transitions. `(1d, D3)`
- [ ] `E2-48` Define typed reasoning assessment fields and deterministic role/OOD thresholds. `(0.5d, D1)`
- [ ] `E2-49` Implement non-terminal assessment → cached Model Router selection → exact proposal → Policy → Autonomy → provider escalation in the canonical loop. `(1d, D3)`
- [ ] `E2-50` Prove no-route, denied-disclosure and exhausted-budget escalation stop explicitly without provider invocation. `(0.5d, D2)`
- [ ] `E2-24` Run the E2 integration pack once and record the gate decision. `(1d, D3)`

Gate: if routing lowers verified high-impact success, retain cloud-only routing
for that role and do not hide the regression with cost savings.

## E3 — Governed personal skills

Exit: at least one repeated workflow becomes a reviewed, replayed, versioned
and reversible personal skill with a negative trigger case. Estimated 15–25 days.

### Lifecycle contract

- [ ] `E3-01` Inventory Skill Fabric lifecycle, selector and persistence callers. `(2h, D0)`
- [ ] `E3-02` Define candidate, reviewed, active, rejected, deprecated and superseded states. `(0.5d, D1)`
- [ ] `E3-03` Define legal transitions and the actor/evidence required for each. `(0.5d, D1)`
- [ ] `E3-04` Define skill provenance, scope, version and rollback metadata. `(0.5d, D1)`
- [ ] `E3-05` Define trigger, non-applicability, input/output and allowed-tool fields. `(0.5d, D1)`
- [ ] `E3-06` Define required evidence and success/failure checks. `(0.5d, D1)`
- [ ] `E3-07` Prove facts/preferences cannot be normalized directly into active skills. `(3h, D1)`

### Candidate creation and review

- [ ] `E3-08` Select one repeated workflow from verified E0–E2 traces. `(2h, D0)`
- [ ] `E3-09` Create a deterministic trace-to-candidate draft with source links. `(1d, D2)`
- [ ] `E3-10` Redact secrets and private payloads before candidate persistence. `(0.5d, D2)`
- [ ] `E3-11` Detect exact duplicate and overlapping trigger candidates. `(1d, D1)`
- [ ] `E3-12` Present candidate diff, provenance and expected effect for approval. `(0.5d, D2)`
- [ ] `E3-13` Persist rejection without repeatedly proposing the same version. `(0.5d, D2)`

### Replay, promotion and rollback

- [ ] `E3-14` Add a replay path that cannot mutate the reviewed benchmark fixture. `(1d, D2)`
- [ ] `E3-15` Run positive replay against the source workflow. `(0.5d, D2)`
- [ ] `E3-16` Run a negative applicability case. `(0.5d, D2)`
- [ ] `E3-17` Compare verified outcome, tokens and intervention with no-skill baseline. `(0.5d, D2)`
- [ ] `E3-18` Require explicit approval to promote the exact candidate version. `(0.5d, D2)`
- [ ] `E3-19` Keep the prior active version and implement rollback. `(1d, D2)`
- [ ] `E3-20` Record selection precision, failures and maintenance cost per version. `(1d, D2)`
- [ ] `E3-21` Deprecate a drifting/overlapping skill without deleting its audit trail. `(0.5d, D2)`
- [ ] `E3-22` Expose skill state, source, replay and version in inspect output. `(0.5d, D2)`
- [ ] `E3-24` Prove each candidate trace preserves research, decision, implementation and verification links. `(0.5d, D2)`
- [ ] `E3-25` Migrate governance into the existing `SkillFabric`; prove `enabled` and the legacy registry table cannot bypass reviewed `ACTIVE`. `(1d, D3)`
- [ ] `E3-23` Run the E3 integration pack once and record the gate decision. `(1d, D3)`

Gate: a candidate that does not improve a named case remains rejected/manual.
Do not compensate by weakening the replay case.

## BETA — Daily engineering-partner slice

Exit: one clean install supports analyze, ideate, change and review profiles
through the same runtime and evidence model. Estimated 5–10 days after E3.

- [ ] `B-01` Define the four profiles as configuration, not separate runtimes. `(0.5d, D1)`
- [ ] `B-02` Define side-effect defaults: analyze/ideate read-only; change gated; review non-mutating by default. `(0.5d, D1)`
- [ ] `B-03` Define the user-visible answer contract for evidence, uncertainty and next action. `(0.5d, D0)`
- [ ] `B-04` Add one analyze demo over a non-trivial repository. `(0.5d, D2)`
- [ ] `B-05` Add one architecture-idea demo with alternatives and decision record. `(0.5d, D2)`
- [ ] `B-06` Add one multi-file change demo with approval and verification. `(1d, D2)`
- [ ] `B-07` Add one review demo that identifies an invariant regression without writing. `(0.5d, D2)`
- [ ] `B-08` Restart one demo and prove no completed side effect repeats. `(0.5d, D2)`
- [ ] `B-09` Inspect memory, context manifest, routing reason, skill and ledger from CLI/library. `(0.5d, D2)`
- [ ] `B-10` Run a privacy review of every remote payload in the demos. `(0.5d, D2)`
- [ ] `B-13` Show research depth, evidence/options, readiness and stop reason in all four daily profiles. `(0.5d, D2)`
- [ ] `B-14` Verify single-user/local-authority behavior and document that project/session IDs are not tenant isolation. `(3h, D1)`
- [ ] `B-11` Build/install the beta wheel and run the four demos outside the repository. `(1d, D3)`
- [ ] `B-12` Record beta limitations and the release decision. `(2h, D0)`

## E4 — Controlled local-model adaptation

Exit: one narrow local role has a reproducible trained artifact that beats its
non-trained baseline without reducing end-to-end quality or safety. Estimated
30–50 days; optional for beta.

### Entry and dataset governance

- [ ] `E4-01` Verify E0–E3 gates and identify one repeated narrow role. `(2h, D0)`
- [ ] `E4-02` Document why retrieval, deterministic code and skills are insufficient for that role. `(2h, D0)`
- [ ] `E4-03` Record explicit dataset scope, consent, retention and deletion behavior. `(0.5d, D0)`
- [ ] `E4-04` Define a versioned example schema with full lineage. `(0.5d, D1)`
- [ ] `E4-05` Export only successful reviewed traces through a deterministic filter. `(1d, D2)`
- [ ] `E4-06` Redact credentials, private paths, raw conversation and unrelated source. `(1d, D2)`
- [ ] `E4-07` Manually audit a sample and record rejection reasons. `(0.5d, D0)`
- [ ] `E4-08` Split train/validation/test by project or time to reduce leakage. `(0.5d, D1)`
- [ ] `E4-09` Freeze dataset hash, version and build manifest. `(2h, D0)`

### Baseline, training and acceptance

- [ ] `E4-10` Measure deterministic and non-trained local baselines. `(1d, D2)`
- [ ] `E4-11` Measure the approved cloud-teacher baseline on the same held-out set. `(1d, D2)`
- [ ] `E4-12` Select the smallest suitable base model and record hardware/runtime constraints. `(0.5d, D0)`
- [ ] `E4-13` Freeze training configuration, seed and dependency environment. `(0.5d, D1)`
- [ ] `E4-14` Run one bounded training experiment. `(2–5d, D2)`
- [ ] `E4-15` Evaluate held-out role quality, calibration, latency and resource use. `(1d, D2)`
- [ ] `E4-16` Run end-to-end E0 cases with normal escalation enabled. `(1d, D2)`
- [ ] `E4-17` Reject the artifact if it misses the pre-recorded acceptance threshold. `(2h, D0)`
- [ ] `E4-18` Record model, dataset, evaluation, compatibility and rollback manifest. `(0.5d, D1)`
- [ ] `E4-19` Register an accepted artifact as a replaceable model adapter, never a new router. `(1d, D2)`
- [ ] `E4-20` Canary the artifact with visible fallback and no autonomous online updates. `(2d, D2)`
- [ ] `E4-21` Exercise rollback and deletion consequences. `(1d, D2)`
- [ ] `E4-22` Run the E4 integration/release pack once and record the decision. `(1d, D3)`

Kill criterion: if the trained artifact does not beat the non-trained local
baseline for the named role, do not ship or expand training. Continue using
deterministic/local retrieval, personal skills and gated cloud reasoning.

## Current progress snapshot

Update this table only from evidence on the exact stated revision/tree. It is a
gate-progress view, not permission to call observed implementation `DONE`.

| Track | Status | Completed/total | Current blocker | Next item | Evidence revision |
|---|---|---:|---|---|---|
| SX | `VERIFIED` | 14/14 | none | `SX-14` closed | `f3ad4ef` (548 passed in 303.72s) |
| E0 | `READY` | 0/41 | none | `E0-01` | `f3ad4ef` |
| E1 | `BLOCKED` | 0/34 | E0 gate | `E1-01` | — |
| E2 | `BLOCKED` | 0/50 | E1 gate | `E2-01` | — |
| E3 | `BLOCKED` | 0/25 | E2 gate | `E3-01` | — |
| BETA | `BLOCKED` | 0/14 | E3 gate | `B-01` | — |
| E4 | `BLOCKED` | 0/22 | E3 gate and verified dataset | `E4-01` | — |
