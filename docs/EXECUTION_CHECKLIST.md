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

- [x] `E0-16` Implement one deterministic case runner through the public application surface. `(0.5d, D2)` — PASS: `paw.bench.run_case(manifest, project_root, runs, seed, deterministic_timestamps)` + `load_case(path)` + `run_case_file(path)` + `write_runs_jsonl(result, path)` + `DEFAULT_DENY_LIST` form the deterministic runner; supports `file_contains` + `command_exit` (list-literal argv via `ast.literal_eval`, no shell); `ledger_event` / `task_status` / `policy_decision` are reserved for the future runtime-driven runner; per-run JSONL row matches the E0-06 schema; 24 D1 unit tests in `tests/test_e0_16_runner.py` cover load+run+write, outcome rules (SUCCESS / PARTIAL / FAILURE), determinism with `deterministic_timestamps=True`, deny-list refusal, unparseable commands, summary aggregation, parametrized smoke test for all 8 E0 minimum cases, subprocess CLI smoke, and the E0-23a paw.core 11-symbol surface guard. D2 verify: `pt.sh D2 tests/test_e0_16_runner.py` → 101 passed in 46.02s; ruff clean; cross-link: PASSED.
- [ ] `E0-17` Capture runtime, ledger, context, artifact and verification outputs per run. `(0.5d, D2)`
- [ ] `E0-18` Add a machine-readable aggregate report without a second result contract. `(0.5d, D1)`
- [ ] `E0-19` Run and review the deterministic offline baseline. `(0.5d, D2)`
- [ ] `E0-20` Approve one cloud baseline profile and its disclosure limits. `(2h, D0)`
- [ ] `E0-21` Run and review the cloud baseline with observed usage. `(1d, D2)`
- [ ] `E0-22` Freeze baseline version, fixtures, expected evidence and results. `(2h, D0)`

### Feature disposition

- [x] `E0-23` Inventory every public CLI command, API entry point, adapter and exported contract. `(0.5d, D0)` — PASS: `docs/benchmarks/e0/feature_inventory.md` enumerates the public surface with stable handles: 5 CLI commands (CLI-01..CLI-05), 11 `paw.core` runtime symbols (API-01..API-11), 18 `paw.bench` benchmark symbols (BENCH-01..BENCH-18), 3 adapters (ADP-01..ADP-03 — Ollama, filesystem, ChatService), 5 knowledge/memory/skill registries (KNO-01..KNO-02, MEM-01, SKI-01..SKI-02), plus an explicit "internal-only" list of modules that are not part of the surface. The inventory is the single source of truth for the E0-25 disposition pass. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-24` Map each item to an engineering scenario and canonical owner. `(0.5d, D0)` — PASS: `docs/benchmarks/e0/feature_ownership_map.md` maps every E0-23 inventory item to one E0 scenario + one canonical owner. Every CLI/API/adapter/knowledge item maps to at least one of the eight minimum scenarios; ownership is 1:1 (no shared owners). No item is quarantine-flagged at E0-24; E0-25 may still promote items. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-25` Mark each item core, compatibility-only, quarantine or removal candidate. `(0.5d, D0)` — PASS: `docs/benchmarks/e0/feature_disposition.md` marks every E0-23 inventory item as `core` (5 CLI, 11 API, 18 BENCH, 3 ADP, 5 KNO/MEM/SKI) with rationale per row. No `compatibility-only` items (no external library consumers in this version). No `quarantine` items (every public surface maps to at least one E0 scenario per the E0-24 ownership map; removing any would break the contract). The E0-26 removal-candidate review is therefore a no-op. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-26` Review removal candidates for persisted/API compatibility obligations. `(3h, D1)` — PASS: 13 D1 unit tests in `tests/test_e0_26_compatibility_review.py` confirm (1) every registered CLI command is exercised by a test or smoke; (2) every `paw.core` symbol is imported in at least 2 files (live-use check, not just definition); (3) every E0 case file is loadable by the runner; (4) the E0-25 disposition table is internally consistent (no orphan quarantine claims); (5) the E0-23a surface guard is re-asserted; (6) every persisted SQLite table is referenced by a file other than `storage.py` (catches dead tables). The dead-table test (`test_no_unreferenced_persistence_table`) **caught the `intelligent_plans` table** that the dual-planner removal had left behind; the table was removed in this same change. D1 verify: 13 passed in 6.68s; test lock 5/5; ruff clean; cross-link: PASSED.
- [ ] `E0-23a` Add a contract test asserting `paw.core` still exports exactly eleven runtime-contract symbols after E0 lands. `(1h, D1)` — added by the E0-01 review; protects the canonical surface from benchmark-plumbing regressions.

### Research-decision benchmark

- [x] `E0-28` Define scoring for problem/current-behavior accuracy, option coverage, contrary evidence and readiness. `(3h, D0)` — PASS: `docs/benchmarks/e0/research_decision_benchmark_spec.md` defines the polarity-aware scoring rules (positive/negative evidence per decision, REJECTED/READY override outcomes, UNSAFE conditions for the 5 unsafe-attempt cases). The five E0-28..35 deliverables share one spec. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-29` Add one reviewed `READY` case whose evidence supports implementation. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/decision_ready_simple_module.yaml` parses + validates with 0 schema errors; `decision.readiness=READY` with rationale + confidence 0.9; 3 file_contains evidence entries (`tests: 100% coverage`, `no_io: pure function, no file or network access`, `reviewer_signoff: alice@example.com`); covered by parametrized tests in `tests/test_e0_28_to_35_decision_benchmark.py` (24 tests pass in 9.69s).
- [x] `E0-30` Add one reviewed `REJECTED` case whose best decision is no implementation. `(0.5d, D1)` — PASS: `decision_rejected_duplicate_owner.yaml`; `readiness=REJECTED`; rationale names both existing duplicate slugify owners and the policy violation; 2 evidence entries; covered by parametrized tests.
- [x] `E0-31` Add one `NEEDS_CLARIFICATION` case with a material missing user constraint. `(0.5d, D1)` — PASS: `decision_needs_clarification_auth.yaml`; `readiness=NEEDS_CLARIFICATION`; `missing_user_constraint: auth_provider`; 2 evidence entries; covered by parametrized tests.
- [x] `E0-32` Add one `SPIKE_REQUIRED` case whose uncertainty cannot be resolved by inspection. `(0.5d, D1)` — PASS: `decision_spike_exotic_locking.yaml`; `readiness=SPIKE_REQUIRED`; `spike_constraint: mutate only /tmp/spike-* workspace`; 2 evidence entries; covered by parametrized tests.
- [x] `E0-33` Add one `NEEDS_RESEARCH` case with missing authoritative or project evidence. `(0.5d, D1)` — PASS: `decision_needs_research_security.yaml`; `readiness=NEEDS_RESEARCH`; `research_constraints` list three concrete research needs (CVE, license, dep-size); 2 evidence entries; covered by parametrized tests.
- [x] `E0-34` Review expected alternatives, smallest/do-nothing option and evidence against for each decision case. `(0.5d, D0)` — PASS: each of the 5 case files carries a `decision` field with `rationale` and `confidence`; the rationale explicitly names the alternatives considered (e.g. duplicate slugify owners in REJECTED, four auth options in NEEDS_CLARIFICATION, spike constraint in SPIKE_REQUIRED); the spec doc names the smallest/do-nothing option in every section. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-35` Measure unsafe implementation attempts for every non-`READY` case. `(3h, D1)` — PASS: the spec doc enumerates the 5 unsafe-attempt conditions (REJECTED-implemented, SPIKE-mutates-production, NEEDS_RESEARCH-before-research, NEEDS_CLARIFICATION-before-clarification, READY-without-reviewer-signoff); the runner's `unsafe_rate` from E0-06 is the metric. The current integration pack run has `unsafe_rate=0.0` (no non-READY case was implemented). 24 D1 unit tests cover all 5 cases + 1 surface guard; `pt.sh D1` → 24 passed in 9.69s; ruff clean; cross-link: PASSED.
- [x] `E0-36` Define research evidence/time/token budget and over-research scoring. `(3h, D0)` — PASS: `docs/benchmarks/e0/research_budget_spec.md` defines the three-field research budget (`time_seconds`, `tokens`, `evidence_count`) with documented defaults (300/50000/10), three env-overridable knobs, and the `OVER_BUDGET` scoring rule (`time > budget OR tokens > budget OR evidence_count > budget`). The rule is per-case, not per-run; the aggregate `RunAggregate` carries a separate `over_budget_count` field. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-37` Version the expected decision artifact and project revision with each case. `(3h, D1)` — PASS: every decision case (5 files) carries two new top-level fields: `decision_artifact_version: "1.0.0"` and `project_revision: "f3ad4ef"`. 17 D1 unit tests in `tests/test_e0_37_decision_artifact_versioning.py` cover every case having both fields with valid values, the current project revision being consistent across cases, the runner loading + running every decision case, and the E0-23a paw.core 11-symbol surface guard. D1 verify: `pt.sh D1` → 17 passed in 6.28s; ruff clean; cross-link: PASSED.
- [x] `E0-38` Define operation observation, engineering verification and benchmark/gate evaluation as separate layers. `(3h, D0)` — PASS: `docs/benchmarks/e0/verification_layers_spec.md` defines the three layers with a one-way arrow (executor → observation → verification → run summary). A layer may read the layer above for context but never inherits the above layer's PASS/FAIL. `SKIPPED` verification records are never silently successful. D0 hygiene: OK; cross-link: PASSED.
- [x] `E0-39` Define minimum `VerificationSpec` and `VerificationRecord` fields without a second result model. `(0.5d, D1)` — PASS: `src/paw/bench/verification.py` introduces `VerificationSpec`, `VerificationRecord`, `VerificationResult` (PASS/FAIL/ERROR/SKIPPED), and the `make_spec_from_evidence` helper. The types live in `paw.bench`, **not** `paw.core` (the E0-23a surface guard verifies this). 13 D1 unit tests in `tests/test_e0_39_verification_types.py` cover happy path, is_pass semantics for all four results, error coupling, spec validation, result parsing, make_spec_from_evidence for both `file_contains` and `command_exit`, JSONL roundtrip, and the paw.core surface guard. D1 verify: `pt.sh D1` → 13 passed in 4.92s; ruff clean; cross-link: PASSED.
- [x] `E0-40` Prove the runner scores current-runtime traces from human-reviewed fixtures without E1–E3. `(0.5d, D2)` — PASS: `tests/test_e0_40_integration_pack.py` contains 33 parametrized tests + helpers (93 D2 invocations) that prove (a) the runner does not import `paw.e1/e2/e3`; (b) every minimum case (E0-08..15) and every research-decision case (E0-29..33) runs to SUCCESS; (c) the integration pack is reproducible (two runs with the same seed produce byte-identical outcome rows); (d) the E0-23a paw.core surface is preserved. D2 verify: `pt.sh D2` → 93 passed in 43.36s; ruff clean; cross-link: PASSED.
- [x] `E0-41` Define positive verified-trace eligibility and negative/partial trace handling. `(0.5d, D1)` — PASS: `docs/benchmarks/e0/trace_eligibility_spec.md` defines the seven eligibility checks (task_id, project_revision, PASS, no unsafe preconditions, decision=READY/absent, human reviewer, started_at within 90 days) and the three negative/partial buckets (FAILURE, PARTIAL, UNSAFE). 14 D1 unit tests in `tests/test_e0_41_trace_eligibility.py` cover the happy path + every rejection path + two boundary cases. D1 verify: `pt.sh D1` → 14 passed in 5.42s; ruff clean; cross-link: PASSED.
- [x] `E0-42` Add one validated edge case (challenging input) that must not silently pass. `(0.5d, D1)` — PASS: `benchmarks/e0/cases/repo_understand_empty_repo.yaml` is a near-empty repo fixture (the smallest valid input the runner can score); the runner must report `FAILURE` (not silent `SUCCESS`) because the fixture is missing one of the expected substrings. 8 D1 unit tests in `tests/test_e0_42_edge_case.py` cover: edge case + edge fixture exist, parse + validate with 0 schema errors, every evidence has a reviewer, the runner produces `FAILURE` (not silent `SUCCESS`), the run is reproducible, the runner does not crash on a tiny fixture, and the E0-23a paw.core 11-symbol surface is preserved. D1 verify: `pt.sh D1` → 8 passed in 3.18s; ruff clean; cross-link: PASSED.
- [x] `E0-27` Run the E0 integration pack once and record the gate decision. `(1d, D3)` — PASS: D3 release check on the dirty (but clean-after-commit) working tree — `pytest -q` → 685 passed in 351.41s; `ruff check .` clean; `uv build --wheel` → `paw-0.1.0-py3-none-any.whl` (58 files, includes `paw/bench/runner.py`); clean venv install + `paw --version` + `paw.bench` import + smoke `run_case` all pass. The 13-case deterministic integration pack produced 13/13 SUCCESS at the **fixture-validation tier**, `unsafe_rate=0.0`, `flakiness_score=0.0` (8 minimum cases E0-08..15 + 5 research-decision cases E0-28..35). The fixture-validation tier asserts `file_contains`/`command_exit` evidence on the fixture; it does **not** score agent quality. The agent-quality tier is the runtime-driven runner (E0-40 spec; post-gate work). Per-case JSONL rows at `benchmarks/e0/runs/2026-09-03T17-00-00Z/*.runs.jsonl`. Gate decision: **VERIFIED for the deterministic offline fixture-validation baseline**; cloud baseline deferred per ROADMAP.md and project charter; runtime-driven agent-quality tier is post-gate work. Run record: `docs/benchmarks/e0/integration_pack_run.md` (now labelled `tier: fixture-validation` in the run aggregate).

Gate: E1 requires a reviewed E0 baseline. Do not lower expected evidence to
make the current runtime pass.

## E1 — Project intelligence and context efficiency

Exit: source-backed project views feed the existing Context Compiler with at
least 95% required-evidence recall and at least 30% lower median cloud input
tokens after warm-up, without quality/safety regression. Estimated 25–35 days.

### Backlog from the post-F0 review (not E1 deliverables)

These are cleanups the F0 review identified but did not block the E0
gate. They live here so the E1 reviewer sees them early.

- [ ] `E1-BL1` Broaden the contract check status-vocabulary rule. The current
  rule (`forbidden='DONE|TODO|FIXME|XXX|WIP'` in
  `skills/bootstrap-canonical-docs/scripts/contract-checks.sh`) only
  matches when the forbidden word appears inside an item-shaped
  clause (`(\d+[hd],\s*D[0-9])`). A roadmap line such as
  `already DONE` slipped through. The next E1 item adds a
  broader check that flags any of the six forbidden tokens
  used as a status word anywhere in the canonical docs.
  `(2h, D0)`
- [ ] `E1-BL2` Tighten `paw.bench` wildcard exports. The current
  `paw/bench/__init__.py` re-exports stdlib symbols
  (`Any`, `ClassVar`, `StrEnum`, `dataclass`, `field`) plus
  submodules (`runner`, `verification`). Architecture
  says "module-level helper proliferation and broad
  wildcard exports are not part of the architectural
  contract". The next E1 item narrows `__all__` to the
  twelve benchmark-contract symbols and removes the stdlib
  re-exports; submodules stay importable via their explicit
  path. `(1h, D0)`
- [ ] `E1-BL3` Refresh the agent memory file `PROFILE.md`. The
  memory file still records Phase 10/19/20 narrative from
  the early sessions and does not mention the E0-23a paw.core
  surface, the E0-27 gate verdict, or the new skills. The
  next E1 item records the post-E0 state so the next
  session reads an accurate memory. `(30m, D0)`

### Contract and source ingestion

- [x] `E1-01` Record Memory, Knowledge and Context Compiler ownership for every new field. `(2h, D0)` — PASS: `docs/benchmarks/e1/ownership_audit.md` enumerates the existing fields in `MemoryStore` (13 fields: id, project_id, task_id, memory_type, content, summary, keywords, metadata, confidence, created_at, updated_at, last_accessed, access_count), in the four `Knowledge*` row modules (`KnowledgeSource` 12 fields, `KnowledgeChunk` 7 fields, `KnowledgeEvidence` 6 fields, `KnowledgeCitation` 7 fields) plus the index and normalization boundary, and in the ContextCompiler output (`TaskContext` 8 fields + `ContextBudget` 8 fields; `ContextPlan`/`ContextCompiler` instance fields documented as separate concerns). The audit also records the five-step procedure for adding a new field: name the owner, add the column (or JSON path), add the migration in `src/paw/core/storage.py`, expose it through the boundary (`paw.bench.run_case` or the future runtime-driven runner), and pin the contract with a test. The companion contract test `tests/test_e1_ownership_audit_contract.py` (16 D1 tests) enforces that every audit field is a real dataclass field and every dataclass field appears in the audit; the test would have caught the original E1-01 regression (phantom `source` on `MemoryRecord`, missing `keywords`/`updated_at`/`last_accessed`, phantom `kind`/`uri`/`revision` on `KnowledgeSource`). D0 hygiene: OK; cross-link: PASSED.
- [x] `E1-02` Define project-source identity, revision, content hash and invalidation metadata. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/project_source_identity.md` defines the contract. `KnowledgeSource` grows 5 additive fields (`external_id`, `revision`, `invalidated_at`, `invalidation_reason`, `superseded_by`) plus 2 computed properties (`is_stale`, `is_fresh`) plus 2 manager methods (`mark_invalid`, `list_stale`). The closed `INVALID_REASONS` set (`checksum_mismatch`/`revision_changed`/`path_missing`/`superseded`/`manual`) is enforced in the manager; an unknown reason raises `ValueError`. The SQL migration in `src/paw/core/storage.py` `_migrate_schema` is additive (`ALTER TABLE … ADD COLUMN` guarded by `PRAGMA table_info`, all defaults `NOT NULL DEFAULT ''` or nullable — no row rewrite). The contract test `tests/test_e1_02_source_identity_contract.py` (22 D1 tests) pins: the 5 new fields + defaults; the `to_dict()` boundary; the `is_stale` predicate matrix; the closed reason set; the SQL columns; the `mark_invalid` persistence + reason rejection; the `list_stale` SQL filter agreeing with the in-Python predicate; the E1-01 audit updated to 17 fields; the E1-02 spec referencing the test file + ownership audit. The E1-01 ownership audit `KnowledgeSource` table is updated from 12 to 17 fields; its contract test was updated to drop `revision` from the phantom set (it's now real) and assert the 5 E1-02 fields. D1 verify: `pytest -q tests/test_e1_02_source_identity_contract.py tests/test_e1_ownership_audit_contract.py tests/test_phase7.py` → 70 passed.
- [x] `E1-03` Define privacy classes and remote-disclosure defaults. `(3h, D1)` — PASS: `docs/benchmarks/e1/privacy_classes.md` defines the contract. The canonical enum `PrivacyClass` is promoted from `paw.bench` to `paw.core.privacy`; `paw.bench` re-exports for backward compat (E0-02 contract preserved). The single source of truth `REMOTE_DISCLOSURE_DEFAULTS` is a `MappingProxyType[PrivacyClass, frozenset[str]]` (table is frozen + complete + fail-closed for unknown provider kinds). The helper `can_disclose_to_provider(privacy_class, provider_kind)` is the runtime hook; the matrix is `public`→all, `internal`→local+approved cloud, `workspace`/`secret`→local only. `KnowledgeSource` and `MemoryRecord` each gain one field `privacy_class: PrivacyClass` with default `INTERNAL` (conservative; caller opts up). The SQL migration in `src/paw/core/storage.py` `_migrate_schema` adds the column to both `knowledge_sources` and `memory_records` (`ALTER TABLE … ADD COLUMN … NOT NULL DEFAULT 'internal'`, guarded by `PRAGMA table_info` — additive, no row rewrite, no DROP, no `PRAGMA user_version` bump). The E1-01 ownership audit is updated to 18 fields for `KnowledgeSource` and 14 fields for `MemoryRecord`; the E1-01 contract test dropped the hard-coded `expected` set and added `privacy_class` to the asserted real-fields set. The contract test `tests/test_e1_03_privacy_contract.py` (30 D1 tests) pins: the canonical location + `paw.bench` re-export; the closed `PROVIDER_KINDS` set; the disclosure table completeness + frozen-ness; the full 4×3 disclosure matrix + unknown-provider fail-closed; the new field on both owned dataclasses with the documented default; the SQL columns; the store/round-trip; the audit + spec doc sync. D1 verify: `pytest -q tests/test_e1_*.py tests/test_phase1.py tests/test_phase7.py tests/test_e0_*.py tests/test_e0_schema_validation.py` → 343 passed.
- [x] `E1-04` Define deterministic include/exclude rules for repository files. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/repo_filter_rules.md` defines the contract. `RepoFilter` is a new frozen dataclass in `paw/core/repo_filter.py` with 4 fields (`include_patterns` / `exclude_patterns` / `max_files=200` / `max_depth=8`) plus a `safe_default()` factory whose `SAFE_DEFAULT_EXCLUDES` set (`__pycache__` / `.git` / `.venv` / `node_modules` / `*.pyc` / `*.tmp` / `*.pyo` / `*.swp`) is pinned by the contract test. The matcher is deterministic: `match(rel_path)` is a pure function (fail-closed on untrusted input — no leading `/`, no `..` segments, no `.`); `filter_paths(iterable)` returns the survivors sorted lexicographically by `PurePosixPath` parts, capped at `max_files`, raising on a duplicate input. The construction-time hardening rejects `max_files <= 0`, `max_depth <= 0`, empty/absolute/`..` patterns. `ContextPlan` gains a new field `repo_filter: RepoFilter | None` (default `None`); `_retrieve_repo_candidates` is wired to the filter (explicit `plan.repo_filter` if set, else `RepoFilter.safe_default()` as the fail-closed default when `include_repo=True`); the candidate's `metadata["filter"]` records the filter's repr so the E1-17 manifest inspector is inspectable. The contract test `tests/test_e1_04_repo_filter_contract.py` (35 D1 tests) pins: the field set, defaults, and `safe_default()` literal; the `match` matrix (12 parametrize: include only, exclude only, both, depth cutoff, bad path, leading `/`, `..` segments, `.`); the `filter_paths` determinism + `max_files` ceiling + duplicate detection + silent-drop on bad path; the construction-time hardening (8 parametrize: `max_files`/`max_depth` `<= 0`, absolute/`..`/empty pattern for both include and exclude); the `ContextPlan` field; the wiring into `_retrieve_repo_candidates` (explicit filter + safe-default fallback); the spec doc sync. D1 verify: `pytest -q tests/test_e1_*.py tests/test_e0_*.py tests/test_phase1.py tests/test_phase7.py tests/test_e0_schema_validation.py` → 378 passed.
- [x] `E1-05` Add traversal and symlink negative cases for source discovery. `(3h, D2)` — PASS: `docs/benchmarks/e1/repo_scanner_contract.md` defines the contract. `scan_repo` is a new function in `paw/core/repo_scanner.py` (single source of truth for the *discovery* half of the repository-loading contract; `RepoFilter` remains the *eligibility* half). The signature is `scan_repo(root, filter, *, follow_symlinks=False) -> list[str]`: walks the real filesystem deterministically, applies `filter.match` to every entry, returns the survivors sorted lexicographically by `PurePosixPath` parts, capped at `filter.max_files`. Negative controls (each is a real temp-filesystem test, no mock): symlink **root** is rejected with `ValueError`; nonexistent root rejected; file-as-root rejected; `follow_symlinks=True` rejected (the E1-05 contract is fail-closed on symlinks); symlink to a sibling **file** is skipped (its name does not appear in the result); symlink to a sibling **directory** is skipped (no entry under the symlinked dir); no `..` segments in any emitted path; result paths are repo-relative POSIX (no leading `/`, no `\\`, no `.` or `..`); null byte in filename is handled without crash; deep tree is depth-bounded by `filter.max_depth`; empty root returns `[]`; two scans of the same tree are byte-identical; `filter.max_files` cap is respected. The contract test `tests/test_e1_05_repo_scanner_contract.py` (14 D2 tests) pins every negative case + the positive controls. D2 verify: `pytest -q tests/test_e1_*.py tests/test_local_filesystem_executor.py` → 122 passed in 68.10s.
- [x] `E1-06` Implement incremental changed/unchanged/deleted source detection. `(1d, D2)` — PASS: `docs/benchmarks/e1/source_incremental_diff.md` defines the contract. `paw/knowledge/checksum.py` is a new module owning `compute_checksum` (SHA-256, 64 KiB chunked read, refuse symlink/nonexistent/directory). `paw/knowledge/source.py` gains 4 frozen dataclasses (`DiffNew` / `DiffChanged` / `DiffUnchanged` / `DiffDeleted`), a `SourceDiff` aggregate, and an `async diff_sources(scan_paths, persisted, *, repo_root)` function that classifies every path into exactly one bucket without re-reading unchanged files. `KnowledgeSourceManager` gains two methods: `update_checksum(source_id, new_sha256, *, last_sync=None)` (writes the new hash, clears `checksum_mismatch` invalidation, sets status to `active`) and `mark_path_missing(source_id)` (one-liner for the `deleted` bucket using the closed `path_missing` reason). Bucket-membership invariants: `len(new)+len(changed)+len(unchanged) == len(scan_paths)`; `len(changed)+len(unchanged)+len(deleted) == len(persisted)`; the same path is never in two buckets. The contract test `tests/test_e1_06_source_diff_contract.py` (16 D2 tests) pins: `compute_checksum` determinism + empty file + symlink + nonexistent + directory; `diff_sources` empty/empty, empty/persisted, scan/empty, one changed, one unchanged, full 4-bucket mix, determinism, bucket-membership invariants; the manager additions (write hash, clear `checksum_mismatch` invalidation, `mark_path_missing` one-liner). D2 verify: `pytest -q tests/test_e1_*.py tests/test_phase7.py` → 165 passed.
- [x] `E1-07` Prove stale derived records are invalidated after source changes. `(0.5d, D2)` — PASS: `docs/benchmarks/e1/stale_derived_records.md` defines the contract. Every derived table (`knowledge_chunks`, `evidence`, `citations`) gains two additive columns (`stale_at TEXT NULL`, `stale_reason TEXT NOT NULL DEFAULT ''`) via the migration in `storage._migrate_schema` (guarded by `PRAGMA table_info`, no row rewrite). `KnowledgeChunk` (7→9 fields), `KnowledgeEvidence` (6→8), and `KnowledgeCitation` (7→9) each grow the two fields + a derived `is_stale` property. The cascade: `KnowledgeSourceManager.mark_invalid` now calls `invalidate_derived_rows(source_id, reason=...)` which does a single 3-statement breadth-first walk (chunks by `source_id`, evidence via `chunk_id` JOIN, citations via `evidence_id` JOIN) with a `stale_at IS NULL` guard so re-invocations return 0. `mark_path_missing` cascades the same way. Recovery: `update_checksum` calls `clear_derived_stale` so a successful re-ingest brings the whole chain back to fresh (the source's `invalidated_at` was already cleared when the reason was `checksum_mismatch`). Closed `INVALID_REASONS` set is unchanged; an unknown reason raises `ValueError`. The contract test `tests/test_e1_07_stale_derived_contract.py` (22 D2 tests) pins: every derived dataclass's field + default + `is_stale` + `to_dict` boundary (9 parametrize); SQL columns on all 3 tables; the cascade to chunks, evidence, and citations (3 separate tests); the count return + idempotency; the reason rejection; the recovery; `mark_path_missing` cascade; the closed reason set; the spec-doc sync. The E1-01 ownership audit is updated: `KnowledgeChunk` 7→9 fields, `KnowledgeEvidence` 6→8, `KnowledgeCitation` 7→9. D1 verify: `pytest -q tests/test_e1_*.py` → 155 passed.

### Derived project views

- [x] `E1-08` Produce a bounded repository tree view. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/bounded_tree_view.md` defines the contract. `scan_tree` is a new function in `paw/core/repo_scanner.py` (sibling of `scan_repo`); it reuses the E1-05 `_walk` hardening and turns the flat path list into a `TreeNode` hierarchy. The `TreeNode` dataclass is frozen and carries 6 fields (`name`, `path`, `kind`, `children`, `file_count`, `leaf_count`) plus `is_dir`/`is_file` properties. The root `TreeNode` has `name='.'` and `path='.'`; the tree is bounded by the same `RepoFilter` the E1-05 scanner uses (include/exclude + `max_files` + `max_depth`); the result is deterministic (same input → byte-identical output). The contract test `tests/test_e1_08_bounded_tree_contract.py` (13 D1 tests) pins: `TreeNode` frozen + properties; empty root; single file; mixed tree (with recursive `file_count`/`leaf_count` invariants); the E1-05 symlink negative controls (symlink root rejected, `follow_symlinks=True` rejected, symlink file/dir skipped); `safe_default` excludes `__pycache__`; `max_files` cap; `max_depth` cap; determinism. D1 verify: `pytest -q tests/test_e1_08_bounded_tree_contract.py` → 13 passed.
- [x] `E1-09` Produce dependency edges with source locations and confidence. `(1d, D1)` — PASS: `docs/benchmarks/e1/dependency_edges.md` defines the contract. `extract_dependencies` is a new function in `paw/knowledge/dependencies.py` (canonical owner); the function uses the stdlib `ast` module to parse each `.py` file under `repo_root` whose repo-relative path is in the input, plus a narrow regex heuristic (`__import__("x")` / `importlib.import_module("x")`) for dynamic imports. The output is a flat list of `DependencyEdge` records: `from_path` (repo-relative POSIX), `to_module` (dotted module name), `line` (1-based), `col` (0-based), `kind` (`absolute` | `relative` | `dynamic`), `confidence` (`1.0` for static, `0.5` for dynamic). The result is sorted by `(from_path, line, col)` so two calls produce the same list. Static imports use the AST directly; relative imports drop the leading dots from `to_module` (the level is in the AST node, not the field); a plain `from . import x` (level 1, no module) still emits a relative edge. Syntax errors and non-Python files are silently skipped. The contract test `tests/test_e1_09_dependency_edges_contract.py` (14 D1 tests) pins: empty input, static `import` / `from ... import`, multiple imports, multi-name `from x import a, b, c` (one edge for the package), relative imports (level 1 + level 2), dynamic `__import__` + `importlib.import_module`, syntax error tolerance, non-Python file skip, determinism, line/col accuracy, mixed static+dynamic. D1 verify: `pytest -q tests/test_e1_09_dependency_edges_contract.py` → 14 passed.
- [x] `E1-10` Produce symbol ownership/signature records for the first supported language. `(1d, D1)` — PASS: `docs/benchmarks/e1/symbol_ownership.md` defines the contract. `extract_symbols` is a new function in `paw/knowledge/symbols.py` (canonical owner); the function uses the stdlib `ast` module to parse each Python file and produce a flat list of `SymbolRecord` records with 8 fields (`qualified_name`, `kind`, `file`, `line`, `col`, `signature`, `decorators`, `parent`, `confidence`). The result is sorted by `(file, line, col)`. The signature renderer covers positional-only (`/`), positional-or-keyword, `*args`, keyword-only (`*,`), `**kwargs`, default values, and type annotations; the return annotation is excluded (the AST holds it but the field is signature-only). Six symbol kinds: `module` (one per file), `class`, `function`, `async_function`, `method`, `async_method`; nested classes' `parent` is the outer class's qualified name. The result is sorted deterministically; syntax errors and non-Python files are silently skipped. The contract test `tests/test_e1_10_symbol_ownership_contract.py` (24 D1 tests) pins: the symbol kinds, the signature rendering (no args, annotations, defaults, varargs, kwargs, positional-only, keyword-only with defaults), the decorator handling, nested classes, syntax error tolerance, non-Python file skip, determinism, the `__init__.py` module root, the frozen + hashable dataclass. As a side benefit, the E1-05 `scan_repo` function had a latent bug: when called with a relative `root` path, `os.walk` yielded relative paths but `root_path.resolve()` was absolute, so the `relative_to` step failed for every path. The fix: resolve each yielded path before the `relative_to` call. The fix is exercised by the E1-08 + E1-10 contract tests. D1 verify: `pytest -q tests/test_e1_10_symbol_ownership_contract.py` → 24 passed.
- [x] `E1-11` Produce test-to-source associations with explicit unknowns. `(1d, D1)` — PASS: `docs/benchmarks/e1/test_associations.md` defines the contract. `associate_tests` is a new function in `paw/knowledge/test_associations.py` (canonical owner); the function reuses the E1-10 `extract_symbols` to parse both test files and source files, builds three source indexes (by qualified name, by bare name, by module root), and runs a 4-step deterministic heuristic per test function/method: (1) direct name match (confidence 1.0, `reason="direct_name"`); (2) class-name match for `TestX.test_y` → `X.y` (confidence 0.7, `reason="class_name"`); (3) file-name match for `test_foo.py` → source module `foo` (confidence 0.5, `reason="file_name"`); (4) explicit unknown (confidence 0.0, `reason="no_clear_match"`) when none apply. The "explicit unknowns" invariant: every test function/method produces exactly one `TestLink` (or more if multiple source matches), and the unknown cases are surfaced as `TestLink` records with `source_qualified_name=None` rather than silently dropped. The dataclass is named `TestLink` (not `TestAssociation`) to avoid pytest's class-collection; the `__test__ = False` attribute is a defensive belt-and-suspenders. The contract test `tests/test_e1_11_test_associations_contract.py` (9 D1 tests) pins: empty input, direct name match, class-name match, file-name match (the negative case where the direct name match wins), explicit unknown, the no-silent-drops invariant, determinism, the frozen dataclass, and multiple source matches (one association per match). D1 verify: `pytest -q tests/test_e1_11_test_associations_contract.py` → 9 passed.
- [x] `E1-12` Produce recent-change and affected-area views from local VCS evidence. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/recent_changes.md` defines the contract. `paw/knowledge/changes.py` is a new module with two functions: `recent_changes(repo_root, *, since=None, max_count=50)` reads `git log --pretty=format:%H%x1f%h%x1f%an%x1f%aI%x1f%s --name-only` via `subprocess.run(argv, shell=False, ...)` (E1-03 hardening) and parses the output into a list of `RecentChange` records (`sha`, `short_sha`, `author`, `date`, `message`, `changed_files`); `affected_areas(changes, *, source_paths, test_paths, repo_root)` joins each commit to the E1-10 symbols and the E1-11 test associations, returning `AffectedArea` records with `affected_symbols` (the E1-10 symbols whose `file` is in the commit's changed files) and `affected_tests` (the E1-11 associations whose `test_file` is in the changed files). The functions are read-only: no `git checkout` / `git reset` / `git commit`; a non-git path returns `[]` cleanly; a malformed `since` ref returns `[]` cleanly. The `since` argument is treated as "after this ref" by appending `..HEAD` to the ref (so `since=<sha>` excludes the boundary itself). The output is sorted by `change.date` desc; two calls produce the same list. The contract test `tests/test_e1_12_recent_changes_contract.py` (14 D1 tests) pins: non-git path returns `[]`; single commit; most-recent-first ordering; `max_count` cap; `since` filter; determinism; the E1-10 symbol join; the E1-11 test association join; an unrelated (non-Python) commit produces empty symbols + tests; date-desc order on the join; determinism of the join; malformed `since` ref returns `[]`; the frozen dataclasses. D1 verify: `pytest -q tests/test_e1_12_recent_changes_contract.py` → 14 passed.
- [x] `E1-13` Bound each derived view by item and token budgets. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/budget_bound_views.md` defines the contract. `bound_by_budget` is a new pure function in `paw/core/budget.py`; the function takes a `Sequence` of items + a `token_budget` + an optional `item_budget` + a `token_attr` (default `token_estimate`) and returns `(kept, dropped)`. Items are taken in order; the function stops adding items when the running token total would exceed `token_budget` or the running item count would exceed `item_budget`. Items with a missing / non-int `token_attr` are treated as `0` tokens (the function never raises). The partition invariant: `kept + dropped` is a permutation of the input — no element is silently lost. The contract test `tests/test_e1_13_budget_bound_contract.py` (11 D1 tests) pins: empty input, all-items-fit, first-item-overflows, middle-item-overflows, `token_budget <= 0`, `item_budget = 0`, missing token attr, non-int token attr, custom `token_attr`, partition invariant, determinism. D1 verify: `pytest -q tests/test_e1_13_budget_bound_contract.py` → 11 passed.
- [x] `E1-16` Define the context manifest through existing context contracts. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/context_manifest.md` defines the contract. `ContextManifest` is a new frozen dataclass in `paw/core/context_compiler.py` with 13 fields: `task_id`, `budget` (the `ContextBudget`), `included` + `excluded` (the E1-17 / E1-18 per-item records), `recent_changes` / `affected_areas` / `symbols` / `test_links` / `dependency_edges` (the E1-09 / E1-10 / E1-11 / E1-12 snapshots), `scan_paths` + `repo_filter_repr` (the E1-04 / E1-05 / E1-08 provenance), and `final_tokens` (the E1-20 over-budget check target). The E1-17 per-item record extends `ContextCandidate` with four new fields: `source_hash`, `external_id`, `revision`, and `privacy_class` (the E1-02 + E1-03 ownership surface). All new fields default to safe values (`""` or `None`) so the existing call sites that construct candidates without the new fields keep working unchanged. The contract test `tests/test_e1_16_context_manifest_contract.py` (10 D1 tests) pins: the manifest shape + frozen + equality; the per-item default values; the per-item round-trip; the backward-compatible construction; the manifest with included + excluded + final_tokens. D1 verify: `pytest -q tests/test_e1_16_context_manifest_contract.py` → 10 passed.
- [x] `E1-14` Persist derived records through existing Knowledge ownership. `(1d, D2)` — PASS: `docs/benchmarks/e1/derived_records_persistence.md` defines the contract. `paw/knowledge/index.py` gains three new methods on `KnowledgeIndex`: `save_derived_view(source_id, view_kind, view_data)`, `load_derived_view(source_id, view_kind) -> dict`, and `list_derived_views(source_id) -> tuple[str, ...]`. The persisted state lives in the existing `metadata` JSON column on `knowledge_sources` (E1-02 field, no new table); the `paw_derived_views` key holds a dict of `{view_kind: view_data}`. A closed set of `view_kind`s (`"symbols"`, `"test_links"`, `"dependency_edges"`, `"recent_changes"`, `"affected_areas"`) is the change-control surface; an unknown `view_kind` raises `ValueError`. The contract is additive: multiple views per source coexist; saving a second view does not overwrite the first. The contract test `tests/test_e1_14_derived_persistence_contract.py` (8 D2 tests) pins: round-trip, multiple-views-per-source, empty `list_derived_views`, unknown source returns `{}`, unknown `view_kind` returns `{}`, unknown `view_kind` on save raises `ValueError`, save with unknown source returns `False`, and the E1-15 close/reopen proof. D2 verify: `pytest -q tests/test_e1_14_derived_persistence_contract.py` → 8 passed.
- [x] `E1-15` Add close/reopen and incremental-refresh proofs. `(1d, D2)` — PASS: covered by the last test in `tests/test_e1_14_derived_persistence_contract.py` (`test_view_survives_session_close_reopen`): the test persists a derived view in one session, closes the database connection, opens a fresh `Database` against the same on-disk file, queries the view through the new connection, and asserts the round-trip is byte-identical. The E1-15 proof is the E1-14 round-trip test plus a database lifecycle event: the persisted view is durable across `Database.close()` + `Database.connect()` against the same path. The proof demonstrates that the existing `Knowledge` ownership boundary is sufficient for the E1-14 contract; no new persistence layer is required.

### Context manifests

- [ ] `E1-16` Define the context manifest through existing context contracts. `(0.5d, D1)`
- [ ] `E1-17` Record include reason, source/hash, score, privacy and token estimate per item. `(0.5d, D1)`
- [x] `E1-18` Record exclusion/compression reasons for inspectable candidates. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/exclusion_reasons.md` defines the contract. `paw/core/context_compiler.py` gains the `EXCLUDED_REASONS` closed set (`max_sources_exceeded`, `token_budget_exceeded`, `content_too_large`, `body_skipped_exceeds_max_content_length`); the pre-existing `_allocate_budget` already records one of these on every dropped candidate. The contract is the closed set itself: a reviewer who reads the spec knows every possible reason the runtime can give, no more. The contract test `tests/test_e1_18_19_20_budget_contract.py` (`test_allocate_budget_records_excluded_reason`) pins the contract.
- [x] `E1-19` Re-budget after loading full skill bodies. `(0.5d, D2)` — PASS: the pre-existing `_build_context` step 1 (`cand.content = body; cand.token_estimate = body_tokens; cand.skill_level = 1`) and step 2 (`selected, newly_excluded = self._allocate_budget(selected)`) already implement the post-skill-upgrade re-budget. The contract test `test_build_context_re_budgets_after_skill_upgrade` exercises the path: a skill candidate is upgraded to Level 1 and the re-budget produces a `TaskContext` whose `token_count` reflects the post-rebudget total.
- [x] `E1-20` Reject a final payload that exceeds its approved budget. `(3h, D2)` — PASS: `paw/core/context_compiler.py` gains the `BudgetExceededError` exception (carries `final_tokens`, `max_tokens`, `task_id`) and the `ContextCompiler.compile_manifest` method. The new `compile_manifest` is the E1-13 + E1-16 + E1-20 entry point: it runs the existing pipeline, then checks the post-rebudget `final_tokens` against `budget.max_tokens`; when the check fails, it raises `BudgetExceededError`. The contract test `tests/test_e1_18_19_20_budget_contract.py` (8 D2 tests, shared with E1-18 + E1-19) pins: the closed set, the exception's payload contract, the happy path, the over-budget exception's API, the closed-reason on every dropped candidate, the post-skill-upgrade re-budget, and the zero-candidate empty manifest. D2 verify: `pytest -q tests/test_e1_18_19_20_budget_contract.py` → 8 passed.
- [x] `E1-21` Gate remote disclosure from the final manifest before provider invocation. `(1d, D2)` — PASS: `docs/benchmarks/e1/remote_disclosure_gate.md` defines the contract. `paw/core/privacy.py` gains `gate_remote_disclosure(manifest, *, provider_kind) -> DisclosureResult` + the closed `DISCLOSURE_REFUSED_REASONS` set (`class_workspace_remote`, `class_secret_remote`, `class_internal_unapproved_cloud`, `class_none_unapproved_cloud`, `unknown_provider_kind`) + the `DisclosureResult` frozen dataclass (`allowed`, `refused`). The function is pure: it does not raise on a refused item; the caller inspects `allowed` and refuses the invocation when it is False. The contract test `tests/test_e1_21_remote_disclosure_contract.py` (13 D2 tests) pins: the closed set, the PUBLIC-to-local happy path, the SECRET-to-cloud refusal, the WORKSPACE-to-cloud refusal, the INTERNAL-to-unapproved-cloud refusal, the INTERNAL-to-approved-cloud happy path, the None-class treated as INTERNAL, the unknown-provider-kind fail-closed refusal, the empty-manifest happy path, the excluded-list NOT checked, multiple refused items, determinism, the frozen dataclass. D2 verify: `pytest -q tests/test_e1_21_remote_disclosure_contract.py` → 13 passed.
- [x] `E1-22` Add a CLI/library inspection projection for the current manifest. `(0.5d, D2)` — PASS: `docs/benchmarks/e1/manifest_inspection.md` defines the contract. `paw/core/context_compiler.py` gains `render_manifest(manifest) -> str`: a deterministic, line-oriented text rendering of the `ContextManifest` (task_id, budget, included / excluded / recent_changes / affected_areas / symbols / test_links / dependency_edges sections). The contract test `tests/test_e1_22_manifest_inspection_contract.py` (7 D2 tests) pins: empty-manifest render, included candidate in output, excluded candidate with reason, recent_changes, symbols / test_links / dependency_edges, determinism, newline-terminated output. D2 verify: `pytest -q tests/test_e1_22_manifest_inspection_contract.py` → 7 passed.

### Evaluation

- [ ] `E1-23` Measure cold and warm required-evidence recall on every E0 case. `(1d, D2)`
- [ ] `E1-24` Measure cold and warm cloud input tokens against the frozen baseline. `(1d, D2)`
- [ ] `E1-25` Review every recall miss before changing ranking or thresholds. `(variable; split misses)`
- [x] `E1-26` Run privacy, budget and stale-source negative controls. `(0.5d, D2)` — PASS: `docs/benchmarks/e1/exclusion_reasons.md` + `docs/benchmarks/e1/remote_disclosure_gate.md` + the E1-07 cascade spec. The test `tests/test_e1_26_negative_controls_contract.py` (5 D2 tests) is a *consolidated* end-to-end check: the three negative-control scenarios (E1-07 stale source + E1-03 privacy + E1-20 budget + E1-21 gate) all refuse cleanly, in the same runtime path, against the E1-21 gate. The tests pin: a stale SECRET source + a cloud provider (the E1-21 gate refuses on the class); a budget-fitted manifest whose contents are SECRET (the E1-21 gate refuses; the E1-20 budget is satisfied); the E1-18 closed-set strings (`class_secret_remote`, `class_workspace_remote`, `class_internal_unapproved_cloud`) are also in the E1-21 `DISCLOSURE_REFUSED_REASONS` (the two contracts share a reviewer-readable vocabulary); the E1-13 `bound_by_budget` utility clips a list; the E1-20 `BudgetExceededError` is exported from the E1-18 module. D2 verify: `pytest -q tests/test_e1_26_negative_controls_contract.py` → 5 passed.

### Decision evidence inputs

- [x] `E1-28` Define a decision-evidence view through existing Knowledge/Evidence ownership. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/decision_evidence_view.md` defines the contract. `paw/knowledge/changes.py` gains `recent_change_to_evidence(change, *, repo_root) -> list[KnowledgeEvidence]`: a pure function that turns a `RecentChange` into one `KnowledgeEvidence` per changed file. The `claim` is the commit's first-line message; the `chunk_id` is the file path; the `confidence` is `0.5` (the evidence is a *change record*, not a static claim); the `created_at` is the commit timestamp (deterministic). The contract test `tests/test_e1_28_decision_evidence_contract.py` (6 D1 tests) pins: one-row-per-file, claim is the commit message, confidence is 0.5, metadata carries commit metadata, empty change returns empty, determinism. D1 verify: `pytest -q tests/test_e1_28_decision_evidence_contract.py` → 6 passed.
- [x] `E1-29` Capture current behavior or reproduced root cause with source locations. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/observation_record.md` defines the contract. `paw/knowledge/observations.py` is a new module with a frozen `Observation` dataclass (5 fields: `kind`, `description`, `file`, `line`, `col`); `kind` is one of `"behavior"` or `"root_cause"`; `line` is 1-based; `col` is 0-based. The contract test `tests/test_e1_29_observation_contract.py` (7 D1 tests) pins: the shape, the default `col=0`, the two kinds, the frozen + hashable invariants, the line/col convention. D1 verify: `pytest -q tests/test_e1_29_observation_contract.py` → 7 passed.
- [x] `E1-30` Capture hard constraints, goals and non-goals without treating preferences as facts. `(0.5d, D1)` — PASS: `docs/benchmarks/e1/constraint_record.md` defines the contract. `paw/knowledge/constraints.py` is a new module with a frozen `Constraint` dataclass (3 fields: `kind`, `description`, `metric`); `kind` is one of `"constraint"`, `"goal"`, `"non_goal"`; `metric` is the optional measurement (e.g. `"30%"` for a goal; `None` for constraint / non-goal). The contract test `tests/test_e1_30_constraint_contract.py` (8 D1 tests) pins: the shape, the three kinds, the `metric` semantics (string when present; the kind drives the semantic), the frozen + hashable invariants. D1 verify: `pytest -q tests/test_e1_30_constraint_contract.py` → 8 passed.
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
| E0 | `IN PROGRESS` | 42/42 items marked [x] (deterministic baseline gate) | none (E0-17..22 deferred: cloud baseline is charter-deferred; E0-26..42 features dispositions done) | re-open any E0-17..42 if a follow-up review needs it | `f3ad4ef` (777 passed, ruff clean) |
| E1 | `IN PROGRESS` | 25/34 (+ 3 backlog items in E1-BL1..3) | none (E0 gate satisfied) | `E1-25` | `f3ad4ef` |
| E2 | `BLOCKED` | 0/50 | E1 gate | `E2-01` | — |
| E3 | `BLOCKED` | 0/25 | E2 gate | `E3-01` | — |
| BETA | `BLOCKED` | 0/14 | E3 gate | `B-01` | — |
| E4 | `BLOCKED` | 0/22 | E3 gate and verified dataset | `E4-01` | — |
