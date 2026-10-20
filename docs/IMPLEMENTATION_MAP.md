# PAW implementation map and stabilization audit

## Working tree capture — 2026-10-20

Base revision `9fb893e2017eceb01d80be4de7ee7a3744eb8ce5`. Capture commands:
`git status --short --untracked-files=all`, `git diff --stat HEAD`,
`git ls-files --others --exclude-standard`, `git rev-parse HEAD`.

Captured state: **68 paths** — 55 modified, 13 untracked; `+3672 / -697` net
over the tracked diff. This is the *entire* uncommitted working tree at the
start of the 2026-10-20 repair, spanning several prior sessions.

Classification — every path assigned to exactly one track owner:

| Track | Captured paths | Count |
|---|---:|---:|
| B-18 decision evidence | `src/paw/core/{storage,reasoning_contracts,planner,approval,policy}.py` + 5 test files | 10 |
| B-18 runtime admission | `src/paw/core/{runtime,runtime_persistence,checkpoint,repo_scanner}.py`, `src/paw/knowledge/checksum.py` + 16 test files | 21 |
| B-19/F06 fail-closed dispatch | `src/paw/core/model_executor.py` + 3 test files | 4 |
| B-18 CLI two-approval | `src/paw/application/chat.py`, `demos/demo_change.py` + 3 test files | 5 |
| Evidence repair (ledger/benchmark) | `src/paw/core/{models,ledger}.py`, `benchmarks/runtime/run_e2e.py` + 1 test file | 4 |
| Docs status sync | `README.md`, 10 `docs/*.md`, 10 `docs/vi/*.md` + 2 test files | 22 |
| Phase D recovery test repair | `tests/test_phase_d_recovery.py` | 1 |
| Preserved user change | `src/paw/knowledge/index.py` | 1 |
| Unrelated | `None identified` | 0 |

The `Unrelated` row is a contract: every diff hunk was examined and assigned.
The `Preserved user change` row is `src/paw/knowledge/index.py` — a retrieval
scoring change for short sparse files, carried unchanged from the user's
working tree and committed separately so it is never attributed to a PAW
track.

## Evidence-reliability repair — 2026-10-20, STANDARD / READY

Addresses the ledger/usage defects that made cost and token numbers
unusable, plus the documentation-status contradictions that prevented an
agent from continuing without re-deriving the state.

### Ledger usage accounting (code)

Two defects, both confirmed by reading the source and reproduced by the new
contract test:

1. **Wrong key.** `RuntimePersistence.commit_operation` serialized
   `ResourceUsage` with `model_dump()`, which emits only pydantic *fields*
   (`model_calls`, `tokens`, ...). `provider_calls` is a *method* on
   `ResourceUsage`, so it was absent from the STEP_EXECUTED payload.
   `TaskLedger.get_model_call_count` reads
   `resources_used["provider_calls"]` and therefore returned **0** for every
   runtime-written task, however many model calls actually happened.
   `assert_model_calls_monotonic` was vacuous for the same reason.

   Fix: `ResourceUsage.to_ledger_dict()` is now the single canonical
   serialization for usage written to the ledger (raw fields plus the
   receipt's `provider_calls` / `total_tokens` / `total_cost_usd`).
   `commit_operation` uses it. The ledger readers also tolerate a
   `resources_used` of `None`.

2. **Double-counted events.** `commit_operation` already writes one
   STEP_EXECUTED event, atomically with the `OperationRecord`. `_execute_unit`
   then wrote a *second* STEP_EXECUTED for the same operation, so every
   operation produced two events and a corrected reader would have counted
   each call twice.

   Fix: the second write is removed. `commit_operation` is the single
   authoritative STEP_EXECUTED writer. `StepProposed` still logs the
   *estimate*; STEP_EXECUTED logs the actual.

**Evidence.** `tests/test_ledger_usage_accounting_contract.py` (6 tests).
Fail-positive proven: restoring both defects fails 5 of 6 (the sixth is the
decision-invariant control). Focused regression sweep: 57 tests across
E2-34, Phase 19 runtime hardening/loop, E2-20 resume, external-effect
reconciliation, runtime atomicity and outcome task identity — all pass.
Broader sweep: 287 tests across E2-3x/E2-4x, ledger, phase-D recovery and
E1-2x — all pass. Ruff clean.

**Still open (not fixed here).** The final executor-side usage is still
derived from `estimated_cost`, not from a provider-issued receipt, so
per-provider token/cost measurement remains approximate. Router efficiency
and cloud savings must not be concluded from these numbers yet.

### Benchmark oracle attribution (benchmark)

`benchmarks/runtime/run_e2e.py` measured its oracle in a way that could not
distinguish "PAW performed the change" from "PAW refused and a direct file
write did it":

* the **baseline** oracle ran *after* the PAW writes, so "baseline" was
  really the post-write state;
* the script then did `git checkout -- .` and wrote both files **directly**
  with `write_text()`, so the "after" measurement described the direct write,
  not PAW's output;
* the program `return 0` unconditionally, so a failed oracle did not fail
  the benchmark.

Fix: the baseline oracle is measured on the pristine repository **before** any
write; the "after" oracle is measured on the files PAW actually produced (no
reset, no direct write); and the exit code now reflects an explicit verdict.
`FAIL` is returned when any file was not written by PAW, or when the oracle
gained new failures. `PASS` requires that PAW performed the change.

**Not yet closed.** `paw_write` in that harness proposes a
`FILESYSTEM_WRITE` action with no persisted implementation Plan, no
project-root binding and no reviewed decision, so under the current
admission contract the runtime refuses the write. The benchmark now reports
that honestly as `FAIL` instead of silently certifying a direct write. Wiring
the harness to a real reviewed Plan + binding is the remaining work; until
then this benchmark is a *negative control*, not a pass.

### Module size and responsibility split (observation, not a work item)

Current source sizes: `runtime.py` 2743, `model_router.py` 1413,
`skills.py` 1397, `storage.py` 1226, `context_compiler.py` 1186,
`application/chat.py` 1031.

Line count does not by itself prove a design is wrong, but it does show where
the coupling sits: `runtime.py` currently carries routing, reconnaissance,
admission, privacy, execution, recovery and usage accounting, and
`chat.py` additionally builds the decision/review flow. The next safe direction
is to extract responsibilities that already have proof, while keeping a single
orchestrator — **not** to introduce another "manager" layer and **not** to
rewrite the framework. The F04/F05 fixes in particular belong in the places
that own provider discovery and outbound payload, not in a new abstraction.

### B-19/F05: bind the outbound payload to the reviewed manifest — 2026-10-20, STANDARD / READY

**The defect.** The remote path asked only one question — *"may this manifest
go to this provider?"* — answered by `gate_remote_disclosure` over
`manifest.included`. The bytes actually sent were a different thing:
`action.metadata["messages"]`, an independent channel the manifest never
described. Three holes followed:

* a remote call with **no manifest** skipped the gate entirely
  (`if manifest is not None:`), so nothing authorized it;
* a manifest belonging to **another task** was accepted;
* content the disclosure decision **refused** could still reach the provider
  through the message list — the gate proved a property of the *manifest*,
  not of the *payload*.

**The fix.** `paw.core.privacy.bind_remote_payload` is the new canonical
binding. It refuses, in order: `manifest_missing` (fail closed — a remote
call with no manifest is not authorized by anything), `foreign_manifest`,
the per-candidate disclosure reasons reused from `gate_remote_disclosure`,
`payload_not_approved` (the payload carries text the disclosure refused, or
text from a SECRET/WORKSPACE record the compiler saw but did not include),
and `payload_oversized` (the payload exceeds the manifest's own budget). The
result carries the payload digest and the manifest digest so an audit record
names the exact bytes and the exact evidence that covered them. Both remote
paths in `_execute_action` now call it.

**A second defect found while doing this.** The runtime used the provider
*name* as the disclosure *kind*
(`PROVIDER_LOCAL if name == "ollama" else name`). For every real cloud
provider that produced a value outside `PROVIDER_KINDS`, so every remote call
refused as `unknown_provider_kind` and **the class table never actually
decided anything**. `provider_kind_for()` now owns the E1-03 mapping: an
on-box provider (`local`, `offline`, `vllm`, `ollama`) is `local`, a
charter-admitted cloud provider is `cloud_approved` (the admitted set is
**empty by default**, per the E1-03 contract that defers the cloud
baseline), and everything else is `cloud_unapproved`. `ModelManifest.local`
now reads the same canonical set so the two cannot drift.

**Evidence.** `tests/test_b19_f05_payload_binding_contract.py` (13 tests) and
`tests/test_b19_f05_provider_kind_contract.py` (16 tests).

*Fail-positive proven.* Restoring the old `if manifest is not None` gate
makes `test_remote_call_without_manifest_makes_zero_provider_calls` fail with
the remote provider actually called
(`{'model': 'remote-llama', 'messages': [...]}`). Disabling the binding
check fails `test_payload_carrying_refused_content_refuses` and
`test_excluded_secret_record_cannot_ride_the_payload`. Disabling the
mapper's local branch fails 6 of the provider-kind tests.

*Interaction.* `tests/test_model_dispatch_fail_closed.py` reached a remote
provider with no manifest. That is now refused before the provider is
reached — correctly — so the test was given a manifest bound to its task.
The test was about *dispatch* failure, not about disclosure; the gate is
upstream of it. 32 tests pass.

**Still open.** A secret that never entered the manifest (for example typed
into a chat turn) is not detected by the binding, because the binding can
only see what the compiler surfaced. Classifying raw user text is a chat
layer concern, not a manifest concern.

### B-19/F04: provider discovery is an explicit, Policy-admitted operation — 2026-10-20, STANDARD / READY

**The defect.** Two implicit provider-I/O sites existed:

* `ChatService.open()` called `initialize_all()`, so *starting a chat session*
  reached a provider with no operation authorized;
* `ModelRouter.route()` called `ensure_providers_ready()` and then
  `discover_models()`, so *choosing a model* reached a provider with no
  operation authorized.

The AGENTS.md contract already said what the right shape is: *"Model Router
selects only from admitted cached manifests"*. The implementation did not
match it.

**The fix.**

* `ModelRouter.route()` is now **cache-only**: it registers the local
  stand-ins and selects from the manifests already admitted. It no longer
  initializes or discovers a provider.
* `ModelRouter.discover_providers()` is the **explicit** discovery
  operation. It registers the local stand-ins first (so the cache always
  holds the fallback, whatever order admission happens in), initializes the
  providers and admits their models.
* `_available_provider_names()` no longer probes providers. A provider that
  has not been initialized reports `available is None`; its cached manifests
  stay usable, because admission was already a decision. A provider that was
  initialized and reports `available == False` is filtered out.
* `PawRuntime._admit_provider_discovery()` performs discovery only after
  Policy admits `Capability.NETWORK_HTTP` through the same single-authority
  gate. A denied discovery leaves the cache as it was and the run continues
  on the cached manifests.
* `ChatService.open()` no longer initializes providers.
  `ChatService.__init__` gained an optional `providers` registry so a caller
  (or a test) can supply its own providers.

**Evidence.** `tests/test_b19_f04_discovery_contract.py` (6 tests).

*Fail-positive proven.* Restoring the implicit discovery in `route()` and the
implicit initialization in `ChatService.open()` fails
`test_routing_performs_no_provider_io` and
`test_opening_a_chat_session_does_no_provider_io`.

*Interaction.* `tests/test_phase15_model_router_v2.py` relied on `route()`
discovering automatically; it now calls the explicit
`discover_providers()` first, and a new test pins that routing alone performs
zero discovery and zero initialization. 12 tests pass.

### Engineering workflow, proved end to end — 2026-10-20, STANDARD / READY

**The gap.** The runtime had every piece of the chain and none of the
chain. The compiled project context was summarised into a fragment count
and a token estimate, and the model never saw the retrieved sources. The
proposal's `model_result` was `{}`. `_build_messages()` was defined and
never called. There was no artifact for an engineering verification, and
no rule that said a change without one was not finished.

**The inference path (code).** `PawRuntime._model_payload()` builds the
outbound provider payload from the **manifest** - the reviewed, budgeted,
disclosure-checked view of the compiled context - rather than from the
conversation history or the bare goal. The manifest's included candidates
are the project content, and they are the same evidence the B-19/F05
payload binding is checked against, so what leaves the box is what the
evidence covers and the model reasons over what was actually retrieved.
A caller may still supply conversation messages (the chat REPL does);
those are kept and the reviewed context is added as its own block.

**The declared verification (code).** `VerificationRecord`
(`paw/core/models.py`) is an immutable artifact naming what was checked,
against which target, by which method, with what result and evidence. It
is recorded under its own ledger event, `VERIFICATION_RECORDED` - distinct
from `STEP_EXECUTED`, which is the executor's success observation, and
distinct from a gate verdict. `paw/application/workflow.py` owns the
verification port: PAW does not run shells (the charter does not authorize
shell execution), so the check is performed by a port the application
supplies, and PAW binds and records what it returns.

**The workflow (application).** `EngineeringWorkflow` composes the
existing primitives - Task, Decision, Plan, the policy gate, the shared
executable unit, the executors, the checkpoints, the ledger - into
research -> choose -> change -> declared verification. It adds no new
orchestration authority: every phase is a normal runtime task with its own
gate, ledger trail and checkpoint. The rule it exists to enforce is
**a change without a passing declared verification is not a completed
change**.

**Evidence.**

* `tests/test_engineering_workflow_contract.py` (6 tests) - the whole
  chain over a real temporary project with a real knowledge ingest, a
  real decision lifecycle, a real reviewed Plan, the real shared unit and
  the real filesystem executor. It proves: the research phase cites the
  sources it read; the choose phase cannot be skipped (the Planner refuses
  an implementation Plan without a reviewed FINAL READY decision); a
  denied approval changes nothing; a **failing** verification is recorded
  and the change is **not** completed; a **restart** after that failure
  does not repeat the completed change and a verification that then passes
  completes the chain; and the record is immutable and bound to the
  operation it verifies.
* `tests/test_inference_context_wiring_contract.py` (2 tests) - the
  compiled project content reaches the provider payload, and the payload's
  context is the manifest's included candidates.
* `demos/demo_engineering_workflow.py` - the chain as a runnable artifact:
  a failure, a restart, and a completed verification.

*Fail-positive proven.* Restoring the old payload (no manifest context)
fails both inference-wiring tests. Restoring "a change is completed when
it changed" fails `test_a_failing_verification_is_not_a_completed_change`.

**Still open.** The workflow proves the chain over a *simulated* change;
it does not yet run against a real project's own test suite, because PAW
does not run shells. The verification port is where a real CI or test
harness plugs in, and that integration is the next piece.

### Checkpoint operation counter (code)

`TaskCheckpoint` now carries `operations_completed`, persisted in a new
`task_checkpoints.operations_completed` column (additive migration,
`SCHEMA_VERSION` 7 → 8, no row rewrite, no DROP). `_create_checkpoint`
carries the counter; `CheckpointManager.get_latest()` delegates to
`CheckpointStore`; `TaskCheckpoint.status` is an alias for `task_status`.
A checkpoint that predates the column reports zero completed operations,
which is the honest value for that snapshot.

### Documentation status (docs)

The canonical set carried contradictory status claims. The resolution
separates two things that were both called "E1/E2 VERIFIED":

* a **gate** measured inside its own declared scope (E1-27 production
  measurement verified on clean revision `8d01d90`; E2 prerequisite
  contract ratified on the same revision), and
* a **track** qualification for release (E1 not established; E2/E3/BETA
  blocked on it).

`docs/README.md` (and `docs/vi/README.md`) now hold the **single** current
status table; the Roadmap files no longer restate a verdict and point there
instead. The English and Vietnamese Roadmaps previously gave *opposite*
verdicts for the same dated 2026-09-09 review and named different "current
tracks"; both now state the same thing. `docs/PROJECT_MAP.md` no longer
claims a blanket "VERIFIED on clean revision after all phases" and its
phantom READINESS CHECK stage is replaced by the real implementation-admission
contract. `docs/api.md` no longer claims routing happens only after the gate
(it happens during proposal — release blockers F04/F05). `docs/examples.md`
now describes the two-approval structured write.

**Evidence caveat recorded in the status table:** the E1-27 measurement
report `benchmarks/e1/e1_production_report.md` is *gitignored*, so that
`VERIFIED` verdict rests on recorded documentation rather than a tracked
artifact. Re-tracking it is a release prerequisite.

## B-18 runtime migration — 2026-10-07, DEEP / READY

Working-tree implementation replaces the four open callback xfails with actual
zero-callback assertions (pre-repair: 4 failures in 2.27s). Final focused packet:
154 passed in 129.30s across shared runtime/admission/recovery/CLI/stream/Plan/
legacy readiness migration and change-demo controls. Full Ruff/diff and locked
sync passed. Offline wheel byte parity covers 83 Python files; clean installed
outside-repo CLI proves separate review/effect approvals, real write, preserved
Task identity across processes, idle replay and dirty revision refusal.
First integrated candidate: 2260 passed, 3 skipped, 2 failed in 1013.06s.
The model-routing control incorrectly declared a write; the SQLite loop fixture
advertised write capabilities despite its observation-only callback. Both are
migrated to read-only controls without weakening production admission. A focused
run loaded one old assertion during editing (31 passed, 1 failed); the corrected
freeze was rerun: corrected files pass 13 tests in 20.83s. Final D3 command
`python -m pytest -q --disable-warnings --tb=short --show-capture=no`:
2262 passed, 3 skipped in 1264.19s, exit 0. Ruff/diff and 83-file wheel parity
were rechecked. B-18 bounded acceptance is satisfied; handoff/product remain
PARTIAL on this dirty tree, not clean-release VERIFIED.
Optional cookiecutter recovery fixtures remain skipped on this host;
their explicit fixture-human review migration is not an executed proof.
The change demo uses shared ChatService and explicit review=True/approve=True;
read-back is OBSERVED, not VERIFIED. No provider/web/training expansion.

The 2026-10-06 spike is resolved for the following bounded implementation,
not for product release. Existing filesystem reconciliation source/tests prove
an exact-intent, read-only path; shared callback probes reproduce four gaps.
Choose shared-unit admission over executor-only checks. Contrary: this breaks
raw READY fixtures and requires two explicit approvals in CLI write workflows.
Do not preserve an unsafe compatibility mode. Capability-declared project writes
require a persisted implementation Plan, reviewed immutable decision and trusted
root/filter/constraints; unscoped mutating callbacks also fail closed. Read/model
operations remain under Policy without pretending they are implementation.
Freshness read scope is included in the exact proposal before Policy evaluates
once; runtime's callback admission is task-local, not a caller-supplied flag.

Prepared recovery does not call the original callback, model, prepare or execute.
It invokes only the existing local filesystem read-only reconciliation method,
matching stored action fingerprint, original reviewed Plan binding, executor root
and durable intent. Original review may be historical during recovery; this never
admits a new write. Unsupported/ambiguous/changed recovery refuses. Completed
operation replay remains unchanged. Snapshot hashing still is not a writer lock.

Application selects separate decision-review and effect-approval steps over
combined approval: more user interaction, but no silent upgrade of ordinary ASK
to research review. Only structured local write intents get bounded FAST evidence;
unsupported mutating chat requests refuse rather than inventing implementation.
Same durable Task, version/Plan references and approval identity survive reopen.
Scope: Planner, runtime, Policy capability scope, RuntimePersistence metadata,
ChatService and focused caller migrations, existing stores only; no providers/web.
Budget/stop: negative controls first; reviewed callback/real-write positive,
stale/foreign/forged/private-call denial, Policy-read ordering, crash/reopen exact
reconciliation, ambiguous refusal and two-approval CLI/stream proof. Reassess
READY if an adapter cannot satisfy read-only recovery. Integrated D3 above.

Growth review: `_execute_unit` remains the orchestration owner; Planner owns
binding, Policy scoped admission, persistence commit, and the existing filesystem
adapter reconciliation. The private context-local receipt is async-task-bound.
Deleting executor-only readiness avoids a second gate; no new runtime/store.
Next B-19 F04/F05 is NEEDS_RESEARCH, not implemented: compare cache-only routing
plus explicit gated discovery with a discovery operation before selection.
Budget: one bounded call-site review and zero-call negatives before READY.
Neither option may initialize on ASK/DENY or duplicate Policy. Actual complete/
stream payload substitution and missing/foreign/stale/oversized evidence must
refuse before provider invocation. No HTTP promotion is claimed here.

## B-18 shared runtime admission — 2026-10-06, DEEP / SPIKE_REQUIRED

Source evidence: `_execute_unit` invokes `step_fn` after Policy/Autonomy but
without durable readiness validation. `_execute_action` alone checks caller
readiness strings and permits research/spike flags. ChatService constructs no
bound Plan or trusted freshness configuration. Prepared operations reach
executor reconciliation only later in `_execute_action`; LocalFilesystemExecutor
checks executor/operation/idempotency/request/content and does not repeat writes.
This means a generic freshness check can block proof of an already-applied write,
while simply exempting prepared operations can admit arbitrary callbacks.

Options: (1) add a freshness check before every callback (small, but breaks
prepared-effect recovery and existing CLI approval); (2) use one shared-unit
admission with a narrowly constrained read-only reconciliation branch and migrate
application review/approval together (preferred, not production READY yet).
Contrary evidence: the second option must preserve operation identity, exact
approval fingerprints and Policy-once order; no caller `isolated`, research,
`is_mutating=False`, prepared-status flag or raw READY string may authorize writes.
Completed-operation replay stays outside new-effect admission. Reconciliation
may prove only the durable exact intent, never fall back to executor execute or
an arbitrary callback. Bind its filesystem-read scope before Policy evaluation.

Owner/files: existing PawRuntime `_execute_unit`/`_gate_action`/`_execute_action`,
ChatService intake/approval/resume, ApprovalStore, Plan and local executor;
no new readiness manager or parallel approval store. Compare an explicit
decision-review-then-operation-approval workflow with combined approval before
choosing the application migration; ordinary ASK is not decision review.
Invariants: reviewed fresh implementation, gate-before-effect, exact approval,
prepared-effect idempotency, durable typed failure and common mode ownership.
Research budget/stop: local callback probes, installed CLI approval/reopen and
prepared-write reconciliation tests; no external provider or user data. Exit
SPIKE_REQUIRED only when an end-to-end proof covers reviewed positive execution,
unreviewed/stale/foreign/flag negatives with zero callback/provider/executor calls,
completed replay, exact read-only prepared recovery, ambiguous recovery refusal,
and Policy once before every freshness/reconciliation read. Then record READY
and implement/migrate callers; run D3 on the integrated frozen working tree.

`tests/test_runtime_readiness_admission_gap.py` is an explicit open acceptance
control. It isolates successful Policy/Autonomy admission, uses mock callbacks
and calls `pytest.xfail` only after confirming the unsafe callback succeeded;
unexpected errors still fail. Expected failures are debt, never PASS evidence.
Focused command: `.venv/bin/python -m pytest -q
tests/test_runtime_readiness_admission_gap.py tests/test_runtime_unit_pipeline.py
tests/test_productization_document_contract.py --disable-warnings --tb=short`:
3 passed, 4 xfailed in 5.12s. Full Ruff and `git diff --check` pass. Runtime
production is unchanged by this diagnostic packet; gate result is PARTIAL.
Integrated frozen-source check: `.venv/bin/python -m pytest -q
--disable-warnings --tb=short`: 2238 passed, 3 skipped, 4 xfailed in 1020.17s,
exit 0. Locked sync resolved 38/checked 37 packages. This supersedes the older
full-suite count for current v7 test evidence, not the open admission controls.
The four xfails are the explicit gaps above; B-18/product gate remains PARTIAL,
not VERIFIED or a clean-release result. No production source changed during
this run. Existing installed v7 scoped smoke still does not prove runtime admission.

## B-18 v7 scoped verification — 2026-10-06

Final focused command: `.venv/bin/python -m pytest -q
tests/test_readiness_freshness.py tests/test_plan_decision_binding.py
tests/test_planning_contract.py tests/test_e2_45_plan_purpose_contract.py
tests/test_e1_04_repo_filter_contract.py tests/test_e1_05_repo_scanner_contract.py
tests/test_e1_06_source_diff_contract.py tests/test_e1_08_bounded_tree_contract.py
--disable-warnings --tb=short`: 122 passed in 49.04s. Pre-repair controls:
freshness 6 failures in 2.72s; valid-fixture Plan admission 8 failures in 6.00s.
Planning callers 79 passed in 89.20s; affected CLI/executor/storage 60 passed
in 62.25s pre-final freshness-bound strengthening. Offline v7 wheel byte parity
covers all 83 Python files; installed outside-repo smoke proves unreviewed
refusal, explicit reviewed Plan and reopen. No runtime/web/full-current-D3 or
clean-revision claim follows from these scoped proofs. The current full-suite
result is recorded above; missing runtime admission keeps B-18 PARTIAL.

## B-18 reviewed Plan binding — 2026-10-06, STANDARD / READY

Planner currently persists implementation Plans without a decision. Compare
adding an optional unchecked version reference (smaller but still fake admission)
with default research decomposition and explicit implementation creation requiring
current FINAL READY, same durable Task/session, exact recorded human review and
fresh server-configured root/filter/hard constraints (selected). Contrary: old
callers now create research Plans; callers seeking implementation need an explicit
review workflow. Preserve old stored purpose/rows, marking unbound legacy Plans
non-authoritative rather than rewriting history. Scope: existing Planner,
ApprovalStore, DecisionVersion JSON encoding, centralized additive schema v7;
no new readiness manager or public root export. Snapshot review is separate from
execution ASK and does not consume/override exact side-effect approvals.
Policy evaluates planning filesystem-read scope before completeness/hash IO;
default runtime readiness is still a separate migration, not solved by Plan alone.
Budget/stop: defaults, missing/orphan/draft/stale/foreign/unreviewed/freshness/
constraints/Policy negatives and reviewed positive/reopen/private-save proof.
Only trusted application configuration supplies root/filter/constraints, not HTTP
request strings. Store version/revision/constraint reference on Plan; revalidate
current head and exact review inside the save transaction. Snapshot IO is not an
atomic external-writer lock. Runtime must recheck before effects in the next packet.

## B-18 freshness completeness — 2026-10-06, STANDARD / READY

Scanner deliberately caps paths and skips symlinks/read errors for context UI;
this cannot establish complete freshness evidence. Options: reuse its partial
output (rejected), create a second scanner (unnecessary ownership overlap), or
add strict opt-in completeness to the existing scanner and hash via the existing
checksum owner (selected). Contrary: strict mode will refuse large/deep/unreadable
projects that context browsing still supports; never silently raise its bounds.
Scope: repo_scanner.py, knowledge/checksum.py, focused tests, EN/VI canonical docs.
No gate, provider, schema, Plan or runtime default change in this prerequisite.
Acceptance: dirty edits/add/delete/root/filter changes alter revision; excluded
files do not; eligible symlink/permission/depth/file-count/entry-count/byte bounds
and detected concurrent input changes refuse instead of producing a digest.
Budget/stop: scanner/checksum callers and strict negatives; local fixtures only.
Snapshot is bounded evidence, not an atomic filesystem lock or review authority;
Policy admission must precede reads when it is wired into runtime/Planner.

## B-18 lifecycle repair — 2026-10-06, STANDARD / READY

Stored snapshots have no current-head/lifecycle. Compare timestamp selection
(small but caller-controlled/ambiguous) with CAS head and append-only versions
(selected). Contrary: additive schema v6 requires D3 at integration. Database
stays the sole owner; canonical DecisionVersionState owns states. Initial DRAFT;
DRAFT→DRAFT/FINAL; FINAL→STALE/SUPERSEDED; STALE→SUPERSEDED; SUPERSEDED terminal.
Exact retry is a no-op; expected-head conflicts insert nothing. Transitions need
an actor. This is lifecycle, not evidence adequacy/review/freshness authority.
Budget/stop: storage/schema, lifecycle regressions and EN/VI canonical docs;
reopen/rollback/CAS/orphan FINAL/terminal-state negatives. Runtime admission
defaults remain unchanged until Plan/freshness callers migrate together.
Freshness target: server-owned bounded relevant-input content snapshot and
canonical hard constraints, not HEAD alone. Agent writes invalidate remaining
unexecuted proposals unless a new reviewed decision admits them. Completed
operations replay durable results; prepared-effect reconciliation preserves the
original intent/idempotency. Full-workspace hashing is viable but creates
irrelevant-change churn; raw caller strings/flags cannot be authority. Input-set
completeness must be proven before production admission uses this target.

Lifecycle implementation uses immutable publication edges with a unique initial
edge and unique predecessor, retaining the full chain rather than overwriting a
head row. Only published leaves are current; legacy/unpublished FINAL is not
promoted during v5→v6 upgrade. Pre-repair: 6 tests failed in 2.80s. Final focused
command: `.venv/bin/python -m pytest -q tests/test_decision_version_lifecycle.py
tests/test_decision_version_storage.py tests/test_e2_28_decision_persistence.py
tests/test_e2_47_48_49_contract.py tests/test_storage_task_isolation.py
tests/test_runtime_atomicity.py tests/test_productization_document_contract.py
tests/test_project_lock.py --disable-warnings --tb=short`: 76 passed in 57.77s.
Full Ruff/diff and locked sync passed (38 resolved / 37 checked). Offline v6 wheel
build/install, 83-file byte parity and installed lifecycle/retry/reopen smoke
passed. Full current D3 remains pending at B-18 integration; historical D3/wheels
do not certify v6. Lifecycle subproof PASS, complete B-18/product PARTIAL. No
freshness check, Plan binding or shared-unit gate is implemented by this packet.
Growth review: canonical enum owns transitions and Database owns publication
constraints/transactions; no second manager/store or public root export added.

## Productization review — 2026-10-05 at `9fb893e`

### B-19/F06 dispatch repair decision — STANDARD / READY

B-18 audit confirms default READY, no application final-artifact creation and
no Planner artifact lookup; changing a constructor default alone is not a
durable readiness repair. Its production migration remains required. Within
the same pre-HTTP safety group, repair independently reproducible F06 first.
Problem: ModelExecutor silently dispatches missing remote routes to local echo;
runtime catches model failures and continues to a successful capability executor.
Options: reject invalid/missing/unavailable selected routes with a typed error
and convert model failures into unsuccessful observations (selected); explicitly
reroute and re-gate fallback (viable future behavior, but requires a new exact
proposal and cannot reuse prior approval); defer (leaves false success).
Contrary evidence: an old executor regression explicitly blesses remote→local
fallback; migrate it without removing positive explicit-local coverage.
Invariants: independent routing, exact proposal/Policy, truthful observations,
durable acknowledgement. Budget: executor/runtime callers and focused regressions
only; no provider/network research. Stop at complete/stream zero-call negatives,
explicit-local positive, actual registered dispatch and durable failed operation
after close/reopen. Files: model_executor.py, runtime.py, focused tests and EN/VI
map/checklist. No provider, dependency, schema or public root export expansion.
Core execution integration requires scheduled D3 before release certification.

F06 repair evidence on the current working tree: 8 negative controls failed /
2 explicit-local controls passed before repair; final focused command covering
`test_model_dispatch_fail_closed`, `test_phase19_model_executor`,
`test_phase11_ollama`, chat/intake/privacy, agent-loop/provenance/deterministic
routing, unit pipeline and atomicity: 100 passed in 107.05s. Full Ruff and locked
sync passed (38 resolved / 37 checked). Full D3 command `.venv/bin/python -m
pytest -q --disable-warnings --tb=short --maxfail=3`: 2182 passed, 3 skipped
in 1500.12s, exit 0. This is working-tree integration evidence, not a clean
revision release certificate.
ModelDispatchError carries stable refusal reasons; only an explicit local
manifest may use stand-in. Missing/mismatched manifests, no route, unavailable
providers, missing inference backends, provider exceptions/error envelopes stop
before capability execution. Empty routes no longer become an implicit local
selection. Failed observation/operation and public-loop Task survive reopen.
Provider exception payloads are not copied to observation/ledger by this path.
Remaining: failed/partial-stream usage receipts are incomplete; generic zero
usage is not evidence of no billed provider work. Discovery and approved actual
payload controls are separate unfinished B-19 subchanges. Handoff `PARTIAL`.

### B-18 immutable snapshot subchange — STANDARD / READY

Frozen DecisionVersion retains mutable caller payload and accepts invalid states.
Only contract tests construct it; no runtime/persistence consumer exists. Options:
deepcopy alone (still editable snapshot), or recursive JSON-shaped read-only
mapping/tuple snapshot (selected). Contrary evidence: generic JSON/dataclass
serializers cannot directly encode mapping proxies; future centralized persistence
must explicitly encode them. Reject unsupported objects, non-string keys, cycles
and non-finite numbers; normalize valid states to the canonical enum. Invariant:
immutable evidence, not FINAL lifecycle/freshness or mutation authority. Files:
reasoning_contracts.py and contract tests. Budget/stop: local callers plus nested
alias/mutation/state negatives; no schema/runtime changes. Acceptance: caller
edits cannot change nested evidence, snapshot edits fail, invalid shapes fail.
The preceding D3 belongs to F06; focused proof now, integrated D3 at B-18 admission.
Pre-repair regression: 6 failed, 11 passed (13.27s); nested caller edits changed
the decision and invalid payload/state inputs were accepted. Implementation now
recursively snapshots and validates evidence; no runtime admission was added.
Final focused proof: `.venv/bin/python -m pytest -q
tests/test_e2_47_48_49_contract.py tests/test_productization_document_contract.py
tests/test_project_lock.py --disable-warnings --tb=short`: 25 passed in 9.45s.
Full Ruff and `git diff --check` passed. Contract subproof `PASS`; B-18 and
product handoff remain `PARTIAL`. The installed F06 wheel predates this change.

### B-18 durable snapshot storage — STANDARD / READY (2026-10-06)

Problem: immutable DecisionVersion has no persistence path or reopen proof.
Choose normalized version rows inside the existing Database/schema owner over
embedding versions in generic metadata: the latter is smaller but cannot enforce
version identity/immutability or prevent legacy policy rows becoming snapshots.
Contrary evidence: adding a table/version and immutable triggers requires D3;
generic CRUD must remain compatible and table cleanup cannot delete evidence.
Scope: additive schema v5, typed save/load, explicit JSON conversion, immutable
version and bound parent rows; no new store, latest/head selection or authority.
Require an existing readiness parent, durable matching Task/session, nonempty
revision/constraints and canonical readiness payload matching its parent. Legacy
rows alone remain non-authoritative. Identical retries are idempotent; conflicting
version IDs fail. Save validation and insert share the task-owned transaction.
Invariant: durable immutable evidence and rollback before acknowledgement.
Acceptance: reopen equality, caller mutation isolation, duplicate conflict,
missing/foreign/unbound/policy-parent negatives, SQL update/delete refusal,
rollback and additive v4 upgrade preserving legacy rows. Budget: owner/callers
and these regressions; stop before lifecycle/freshness/admission integration.
Focused proof may establish the subchange, but D3/build/install must be scheduled
for the new schema; product remains PARTIAL until that integration gate passes.

Working-tree evidence: pre-change 9 tests failed (3.37s), missing save/load and
version table. Final focused command runs `test_decision_version_storage`,
`test_e2_28_decision_persistence`, `test_storage_task_isolation`,
`test_e2_47_48_49_contract`, `test_runtime_atomicity`, document contract and
project lock: 64 passed in 25.68s. Full Ruff/diff and locked sync passed
(38 resolved, 37 checked). Offline wheel build/install passed; all 83 Python
files match source bytes, and outside-repo installed v5/idempotency/reopen/
immutable-delete smoke passed. The old F06 D3 predates this schema; full current
D3 has not run. Snapshot subproof PASS, integrated B-18/product PARTIAL.
Growth review: Database is already large, but this bounded repository operation
and DDL remain with its existing centralized owner; no second store/manager or
root public export is added. Never bypass immutable triggers for retention or
cleanup; a future retention/lifecycle migration needs its own explicit decision.
Affected integration command covering storage helpers, skills migration/E3
migration, E2 inspect, chat CLI and product intake: 44 passed in 25.06s.
Final documentation contract/project-lock rerun: 7 passed in 2.58s; diff clean.

### B-18 migration handoff — DEEP / NEEDS_RESEARCH

Source findings: `ImplementationReadiness` values are lowercase enums while
runtime still compares uppercase free strings; its inference-readiness docstring
has been corrected to engineering implementation readiness. `DecisionVersion`
now deeply snapshots its JSON-shaped payload and has immutable save/load, but
now also has lifecycle publication/current-head selection. Freshness, evidence
adequacy/runtime admission remain missing; exact review is now required for
implementation Plan creation. `record_decision` is generic history, permitting empty
revision/constraints and non-durable Task IDs; those legacy rows are not mutation
authority. Planner now defaults to research decomposition and explicit
implementation requires reviewed/current/fresh decision binding, persisted on
Plan. Application
creates no final decision and passes no readiness artifact. Runtime trusts
`is_mutating`, `is_research`, purpose/isolated flags and optional freshness strings;
these flags alone do not establish bounded read-only research/spike containment.

Snapshot storage choice is now normalized rows under the existing centralized
Database owner; lifecycle/freshness integration still requires its own READY
decision. Do not add another readiness manager/store. A temporary
default change alone or synthesizing READY on approval is rejected. Contrary
evidence: existing negative tests pass for manually supplied strings; they do
not prove durable admission and some tests explicitly bless default READY.

Ordered subchanges: (1) ratify canonical version payload, lifecycle and server-
owned relevant-source/constraint freshness, including dirty source; (2) add
centralized persistence and immutable-version/reopen/rollback proofs, preserving
legacy rows as non-authoritative; (3) bind canonical Plan and application decision
creation to the same durable Task; (4) admit mutation in the shared executable-
unit owner before any supplied step_fn, routing/discovery or executor effect,
including resume; (5) migrate callers and tests without fabricated READY, prove
actual capabilities/effect containment cannot bypass via caller flags; then D3.
Tests must cover missing/draft/stale/superseded/foreign-Task/empty revision,
constraint changes, raw READY strings, approval without research, alternate
runtime modes and close/reopen. Acceptance is zero effect calls for all invalid
cases plus one reviewed exact-Task positive. Budget: local contract/caller/schema
review and bounded admission spike; stop until the storage/freshness choice is
READY. No new provider, training, tenant or research Task is authorized.

### Repair evidence (working tree; supersedes initial F01/F02 reproductions)

Shared `_prepare_turn` now rejects cancelled sessions, pending/approved actions
and empty/oversized input before either transport creates a task or runtime.
Streaming accumulation uses the existing `response` contract; the final reply
and persisted assistant message no longer fall back to mock output.
Database connection ownership is serialized per asyncio task. Same-task nested
transactions use savepoints; cancellation rolls back; reads and legacy helpers
cannot observe or commit another task's pending transaction.

Final focused regression: 47 passed in 52.71s, including multi-chunk reopen;
document contracts: 7 passed in 6.24s; full Ruff and `git diff --check` passed.
Integrated D3 working-tree proof: `.venv/bin/python -m pytest -q
--disable-warnings --tb=short` exited 0: 2150 passed, 3 skipped in 1173.83s.
Skipped cases are not evidence of live-provider or experimental capability.
This D3 predates the F06 dispatch repair; it does not certify the later code.
The final wheel built and installed offline into an isolated environment;
outside-repository CLI chat and streaming/cancel smoke passed with local stand-in.
All 83 packaged Python files match the current source bytes.
These are local boundary proofs, not cloud quality or a clean-revision release.
Product handoff remains `PARTIAL`. No web endpoint is implemented.

Next mandatory repairs are B-18/B-19: durable FINAL READY tied to Task/revision/
constraints (runtime currently defaults READY); cached-only routing with gated
provider discovery; bind disclosure approval to actual outbound messages and
reject missing-provider success fallbacks. The existing test approving default
READY must be replaced by a failing-closed acceptance test, not used as authority.
Disconnect/lifespan and cross-process ownership remain web-spike acceptance.

### B-16/B-17 implementation decision — STANDARD / READY

Accepted-stream regression additionally fails: `_execute_model` accumulates
tokens into `model_response`, while downstream `_execute_action` reads
`response`, replacing the durable assistant answer with mock output. STANDARD /
READY for normalizing the accumulated key to the existing completion contract.
Alternative: special-case the chat projection (rejected: preserves incompatible
executor contracts). Contrary evidence: visible live tokens looked correct;
only persisted/reloaded output exposes the loss. Acceptance: positive stream
returns the exact same model answer as send and multi-chunk accumulation persists.

Problem and reproduction: the new intake/isolation regressions reproduce stream
admission divergence and cross-task transaction loss on the unchanged source.
Constraints/invariants: ASK waits, durable acknowledgement, single runtime and
schema ownership; preserve user index work; no web endpoint or provider change.
Options: share intake/proposal preparation and task-owned connection lock with
nested savepoints (selected); use connection-per-operation (viable, but all
existing stores and transaction coordinators assume the shared connection);
defer and serialize only HTTP (cannot protect CLI/TUI/library writers).
Contrary evidence: serialization reduces read concurrency and a child task
awaited from inside its parent's transaction would deadlock; such concurrent
transaction composition is unsupported, callers must await owned writes in
the same task. Raw private connection access outside an owned transaction is
not a supported application API. Same-task nested failure uses a savepoint.
Budget/stop: owners, repository call sites and failing regressions only; stop
when plain/stream refusal parity, independent rollback, cancellation and
close/reopen pass. No external research required for these owned semantics.
Files: application/chat.py, core/storage.py and the two focused regression
modules. The large-file edits remove duplicated intake and isolate connection
ownership in the existing storage owner, not a new manager. Acceptance: focused
new negatives + existing chat/storage/atomicity tests, Ruff; integrated D3 is
required for storage atomicity before product certification.

Current tree includes the user's `knowledge/index.py` change, preserved.
[BETA audit](BETA_LIMITATIONS.md) records F01..F12, source owners, remedies,
parity and acceptance. Historical component PASS claims below do not certify
these boundaries. Decision: `DEEP / READY` for documentation/diagnostics;
production web is `SPIKE_REQUIRED` until B-15..B-19. The initial diagnostic
review changed no production code, provider, dependency or schema; repairs above
are subsequent working-tree changes.

Current reproductions with isolated temporary DBs:

- Cancel ChatService local; send returns `cancelled`, stream returns
  `completed`, session remains cancelled. F01 control `FAIL`.
- A transaction waits; independent B writes/exits successfully; A rolls back.
  B row is absent. F02 control `FAIL`. Use asyncio Events for exact ordering,
  existing policy_rules test rows, then close/reopen in the regression repair.
- `uv sync --locked --extra dev`: 38 resolved, 37 checked.
- `.venv/bin/python -m pytest -q tests/test_chat_cli_demo.py tests/test_runtime_atomicity.py tests/test_runtime_unit_pipeline.py`:
  13 passed in 24.65s; existing sequential paths only.
- `.venv/bin/python -m pytest --collect-only -q`: 2131 tests collected in
  11.14s. Collection is not test success or release evidence.

Handoff `PARTIAL`; execution-enabled concurrent web gate `FAIL` until repairs.
F03..F08 are source-inspected risks, not yet complete regression proofs.
No private DB inspection, live cloud calls or full-suite run in this audit.

This document records current source reality. It does not award completion
based on historical phase notes. Update it whenever ownership or runtime wiring
changes.

## Attrition repair and D3 readiness — 2026-09-29 (working tree on `957b588`)

Result: **PARTIAL**. A full-tree review at `957b588` found the working tree and
HEAD both ineligible for a D3 release check. Three repairs landed; the
clean-revision D3 itself has **not** run and no gate is promoted here.

Decisions: two `STANDARD`/records (attrition repair; deterministic-proposal
routing repair), each with a readiness result of `READY` for its own scope only.

### What was wrong (reproduced, not inferred)

1. **Working tree red.** `RuntimeOutcome.task_id` had been added as a required
   field; 12 of 19 construction sites did not pass it
   (`TypeError: missing 1 required positional argument: 'task_id'`). Attribution
   by stashing the change and re-running on clean HEAD: of 42 full-suite
   failures, **41 came from this change** and 1 pre-existed at HEAD.
2. **Suite uncollectable.** `tests/test_phase_d_recovery.py` imported
   `cookiecutter`/`jinja2` at module level while the module already carried a
   skip guard. The guard runs after the import, so a machine without those
   benchmark deps aborted the whole run: `2063 tests collected, 1 error`.
3. **Routing invariant violated at HEAD.** A structured `filesystem.write` action
   (`model_required=False`, capabilities `[filesystem.write]`) was still routed to
   `local-fast` and emitted a `MODEL_SELECTED` ledger event for a model that was
   never invoked — model routing standing in for capability routing.

### Root cause of (3)

E2-49 builds a `CanonicalProposal` naming a concrete model *before* the gates so
Policy evaluates the exact proposal. That pre-gate routing was unconditional, so
it also ran for deterministic operations. `CanonicalProposal.__post_init__`
rejects an empty `selected_model`, so the fix is **not** "route and pass an empty
name": the deterministic proposal now skips canonical wrapping and flows through
the same gates as a plain `ProposedAction`. `_execute_unit` already accepted both
types, and the branch reuses the existing invocation predicate
(`Capability.MODEL_INFERENCE in action.capabilities`, `runtime.py`) rather than
adding a second definition of "needs a model".

### Repairs

| Repair | Files | Proof |
|---|---|---|
| `task_id` defaulted and every runtime terminal path populated | `core/runtime.py` | `tests/test_outcome_task_identity.py` (9 pass); AST audit 12/12 `src/` call sites pass `task_id`; negative control: removing one path's `task_id` fails the test |
| benchmark deps guarded before import | `tests/test_phase_d_recovery.py` | full collection clean: `2074 items, 0 error`; module skips cleanly when deps are absent |
| deterministic proposal is not routed | `core/runtime.py` | `tests/test_deterministic_proposal_no_model.py` (2 pass) incl. a control asserting a model-backed proposal *is* still routed; negative control restores pre-fix behaviour → deterministic test fails, control still passes |
| E4 live test made opt-in | `tests/test_e4_provider_scaffolds.py` | skips by default with an explicit reason; run deliberately with `PAW_E4_LIVE_TESTS=1` |
| `ruff check .` green | `pyproject.toml`, `benchmarks/d1/tasks/run_d1.py` | dead imports removed, imports sorted, `timezone.utc`→`UTC`, ASCII dashes, `contextlib.suppress`/`Path.unlink`; `py_compile` OK |

### Known gaps left deliberately (not hidden)

- `benchmarks/d1/tasks/run_d1.py` captures D5/D13 state (`yaml_content`,
  `step1_done`, …) that it never asserts. F841 is suppressed for that path with
  the reason recorded in `pyproject.toml`; deleting the captures would delete the
  evidence, and adding assertions would change what the D1 benchmark measures.
- `TestE4LiveProvider.test_cloud_teacher_baseline_live` asserts
  `0.0 <= result.accuracy <= 1.0`, which cannot fail. Tightening it to the
  docstring's "accuracy > 0" needs a live run to confirm, so it is reported, not
  changed blind.
- `benchmarks/e1/fixtures_paw/*.py` are synthetic fixtures with keyword markers;
  they are data, and are intentionally not linted as production code.

## Real-world evaluation — 2026-09-29: the rehearsal exists, PAW did not produce it

Decision class: **DEEP**. Readiness: **READY for one bounded slice only**
(foreign-corpus context measurement). This does not authorize a second
benchmark tier, a new runner, or the row-5 end-to-end chain.

### Problem

Option 1 ("run PAW on real external codebases") appears to have prior work:
`/tmp/benchmark_repos/textdistance` (git `d6a68d6`, 54 py files) contains
`baseline_characterization.json`, `C4_ALTERNATIVES.md` (three options scored on
scope/risk/compat/rollback), `C_PROPOSAL_V1.md` (exact files, non-goals,
invariants, rollback), `C_REFACTOR_PROOF.md`, `BEHAVIORAL_INVARIANTS.md` and
`C_OBSERVATION.md` (`C_REFACTOR_VERDICT = PASS`, 187/187 characterization cases
identical, 400 tests pass). If that work was PAW-driven, Option 1 is already
partly done. The evidence says otherwise.

### Evidence that PAW did not produce it

- `~/.paw/paw.db`: 138 tasks, 139 with ledger events, and **zero** tasks whose
  goal mentions textdistance, refactor, token or cookiecutter. The recent tasks
  are chat smoke tests ("xin chào", "ok") and two arithmetic questions.
- `knowledge_sources` contains **only** PAW's own tree (`paw-source-repo` /
  `src/paw/**`). No external repository has ever been ingested.
- The artifacts are markdown plus JSON inside the *target* repository, together
  with a hand-written `characterize.py` that lives in that repo, not in
  `src/paw/bench/`.
- `textdistance` appears in the QwenPaw session `history.db` and nowhere in the
  PAW runtime database.

### What this means

The **methodology** is validated: that rehearsal is exactly the
research → options → decision → bounded change → proof loop the Charter
mandates, and it is a good model. What is **not** validated is PAW itself. PAW
has never run that loop, so the evaluation so far measured the method and not
the runtime. Option 1's real objective is therefore narrower than "more
benchmarks": make PAW produce the trace for a foreign repository, which is what
`ROADMAP.md` dependency row 5 (`PENDING`) already describes.

### Options considered

- **A — Make the D8–D13 recovery harness reproducible.** It is currently dead
  evidence: `cookiecutter`/`jinja2` are undeclared and the fixtures live in
  `/tmp`, so the module always skips. Restoring it needs a dependency decision
  and an in-repo fixture move. `NEEDS_RESEARCH`: cookiecutter is incidental to
  what is under test (PAW's recovery semantics, not a template engine), so the
  honest fix may be a stdlib harness rather than a new dependency, and that
  choice changes the dependency lock and therefore the D3 triggers.
- **B — Measure context/retrieval on a foreign corpus (selected).**
  `paw.bench.e1_production` already accepts arbitrary `--roots` and `--case-dir`,
  so the E1 claim ("≥95% required-evidence recall, ≥30% warm reduction") can be
  measured on a repository PAW has never seen, using reviewed cases. It reuses
  tracked machinery, adds no runner and no second result model, and is
  falsifiable against E1's own published thresholds.
- **C — Run row 5 end-to-end (research → decision → gated change → declared
  verification → inspect/restart) on a foreign repo, and compare PAW's trace to
  the textdistance rehearsal.** This is the real objective but it is the largest
  slice, it depends on the readiness gate being trustworthy, and B may invalidate
  its premise. Explicitly not authorized here.

### Contrary evidence and cost

E1 is already `VERIFIED` on `src/paw`, so a foreign corpus may legitimately
expose a retrieval gap — that is the measurement's value, not a reason to defer
it. A small case set is a weak proxy for real projects and must be reported as
such. Ollama is not running in this environment, so semantic re-ranking degrades
to the deterministic local provider; the report must state which embedding mode
produced the numbers rather than implying the E1 Ollama result. Slice B writes
reviewed cases, so it is authoring work, not just execution.

### Affected invariants

Evidence before implementation; one canonical `Task`; observation is not
verification; minimum cloud disclosure (this slice is local-only and sends
nothing remote); a changed project revision invalidates a decision.

### Acceptance for the authorized slice

Cases name the foreign repository and a fixed revision; the run reports
`min_recall` and `median_warm_reduction` with the embedding mode; the result is
compared against E1's own thresholds without lowering them; the report states
that fixture-level E0 evidence and this foreign-corpus measurement are different
tiers; and a failing case stays failing and visible rather than being reworded.

### Blocker found while preparing the slice (2026-09-29)

Seven reviewed cases were authored under `benchmarks/e1/cases_foreign/` for
`textdistance` at `d6a68d6`, and all 21 evidence strings were verified against
the corpus (including one deliberate negative control). The measurement itself
cannot run, because `paw.bench.e1_production` is a single-repository tool:

- `_resolve_under` rejects any root or case path outside `--repo-root`
  (`ValueError: path outside repository`), so a foreign corpus cannot be read
  in place;
- `_measurement_inputs` requires `<repo-root>/uv.lock` and `<repo-root>/src/paw`
  to exist; those only exist for PAW itself;
- `_review_fixtures` binds each fixture to a Git blob in the measured
  repository, so foreign fixtures cannot be reviewed against the foreign
  repository's own history.

Hashing `uv.lock` and `src/paw` is correct and must stay: those are the
compiler under measurement, and detecting mid-run changes to them is the point.
The two Git assumptions are what do not generalize.

Rejected workarounds, and why:

- **Vendor the corpus into PAW** (1.5 MB, 54 files). It would make the fixtures
  PAW blobs, so `project_revision: d6a68d6` could no longer be verified against
  the library's real history. It also adds third-party code PAW does not own.
- **Symlink `src/paw` into the foreign repo** so it can act as its own
  measurement host. It satisfies the tool's assumption while making the
  provenance claim untrue, which is exactly the false-evidence pattern the
  Charter forbids.

The honest fix is one parameter on the existing runner: an optional
`--corpus-root` that defaults to `--repo-root`, used for corpus discovery,
fixture resolution and fixture Git-blob binding, while `uv.lock` and `src/paw`
keep coming from the measurement host. That is not a second runner and not a
second result model. It is a change to verification machinery, so it is a
separate decision from the measurement itself and is not authorized by the slice
above.

### Result of the slice (2026-09-29): `min_recall = 0.0` on a foreign corpus

`--corpus-root` was added (authorized separately) and the measurement ran.
Against `textdistance` at `d6a68d6`, seven reviewed cases, local embedding:

| Metric | Foreign corpus | PAW's own source (E1-27) |
|---|---|---|
| `min_recall` | **0.00** | 1.00 |
| `median_warm_reduction` | 0.93 | 0.99 |
| `metric_gate` / `measurement_gate` | **FAIL** | PASS |
| corpus files / chunks | 14 files / 312 chunks | 71 files / 300+ chunks |

Per-case cold recall: token_based 0.50, edit_family 1.00, algorithm_families
0.25, public_api 0.25, counter_helpers 0.00, ngram_utils 0.00, and the negative
control 0.00 as designed. Compression is not the problem: warm reduction is
0.93, far above the 30% target. Required-evidence recall is.

**Root cause, and it is not a scoring defect.** `ContextPlan.max_knowledge_chunks`
defaults to `10` (`core/context_compiler.py:71`) and is passed straight through
as `idx.search_chunks(..., limit=plan.max_knowledge_chunks)`
(`core/context_compiler.py:446`). That is a hard cap on the candidate pool which
is **independent of `ContextBudget`**. Raising `max_fragments` from 30 to 400 and
`max_tokens` from 5000 to 60000 changed nothing: fragments included stayed at
~12 and `min_recall` stayed 0.00. The budget was never the binding constraint.

The failure is fragment-level, not file-level. For `counter_helpers` (recall
0.00) the compiler did include `textdistance/algorithms/base.py` at score 0.774,
rank 2 of 12 — the right file was retrieved, but the specific chunk holding
`def _get_counters(...)` was never a candidate. With 312 chunks and a 10-deep
pool, a query about n-gram utilities is unlikely to surface a particular private
helper.

### What this says about the E1 gate

E1 was ratified `VERIFIED` on `8d01d90` with `min_recall=1.00` measured on
`src/paw`. This measurement does not contradict that number, but it does
contradict the portability of the claim. On PAW's own corpus the answers
happened to fall inside a 10-chunk pool; the gate never varied
`max_knowledge_chunks`, so it never exercised the regime a foreign repository
creates. **"≥95% required-evidence recall" is currently demonstrated for one
corpus shape, not for foreign repositories.** E1's numeric threshold is not
weakened and the failing cases stay failing.

### Not authorized, and deliberately not done

`max_knowledge_chunks` was **not** raised to make the numbers pass. The roadmap
states the gate rule directly: "do not lower expected evidence to make the
current runtime pass", and the same applies symmetrically to raising a cap until
a benchmark clears. Changing the retrieval contract is a new decision with its
own options (widen the pool, raise the default, make the cap budget-derived, or
record that E1 is single-corpus and add a foreign-corpus gate with its own
threshold). It is recorded here as the next decision, not taken here.

The tool also reported `corpus_dirty=true` and `fixtures_fresh=false` on its own:
the rehearsal refactor in `textdistance` is uncommitted, so `base.py` and
`token_based.py` differ from `d6a68d6`. That is the provenance check working,
not a defect.

### Decision: budget is the only binding constraint (2026-09-29, `DEEP`/`READY`)

Selected over three alternatives: raise the constant default only (keeps a
constant that silently contradicts the budget contract); do nothing and declare
E1 single-corpus (leaves the measured gap unaddressed); narrow the chunker so
ten chunks suffice (re-scopes the benchmark instead of the system). The chosen
option derives the pool from `ContextBudget.max_fragments` with headroom for the
post-retrieval dedup and per-source ceiling, floored and ceilinged.

Cost evidence, checked before widening: `search_chunks` already scans and scores
up to `_MAX_LEXICAL_CANDIDATES` (5000) rows and embeds up to
`_MAX_HYBRID_CANDIDATES` (100) chunks **regardless of `limit`** — `limit` only
slices the final result. So a wider pool adds candidate construction and two
indexed lookups per candidate, not provider calls. `ContextPlan.max_knowledge_chunks`
became `None` (derive) and stays an explicit-int override for a caller that
deliberately wants a narrow pool.

### Result: real, partial, and the gate is still FAIL

| Case (cold) | pool=10 | derived pool |
|---|---|---|
| counter_helpers | 0.00 | **1.00** |
| token_based | 0.50 | **0.75** |
| edit_family | 1.00 | 1.00 |
| algorithm_families | 0.25 | 0.25 |
| public_api | 0.25 | 0.25 |
| ngram_utils | 0.00 | 0.00 |
| negative control | 0.00 | 0.00 |
| `median_warm_reduction` | 0.930 | 0.808 |

`min_recall` is still **0.00** and the measurement gate is still **FAIL**. The
fix delivered what the root-cause analysis predicted for the case it was derived
from, and did not clear the gate. Nothing was reworded or re-thresholded to make
it pass; the reduction drop from 0.930 to 0.808 is the honest cost of admitting
more candidates, and it stays far above the 0.30 target.

**A second, independent defect is now visible.** `ngram_utils` is no longer a
pool problem: `textdistance/utils.py` is admitted as a candidate at score 0.163
and dropped with `reason=max_fragments_exceeded`, ranked below roughly forty
algorithm chunks scoring 0.5-0.6. A 28-line file that is exactly the answer
loses to larger files whose chunks happen to share generic query words. That is
relevance-ranking precision, not pool depth, and it is a different decision
(touching ranking would re-open E1-27's own tuning).

**Caveat that bounds all of the above.** This run used `--embedding local`, the
deterministic hashed-bag-of-words provider, because no Ollama server is running
in this environment. E1-27's `min_recall=1.00` on `src/paw` was measured with
real `nomic-embed-text` embeddings. The two numbers are therefore **not
comparable on the ranking axis**: a large part of the residual ranking gap may be
an artifact of the weaker local provider, and that hypothesis cannot be tested
here without a local Ollama. Stating it otherwise would overstate what was
measured.

## Unblocked the cloud baseline — 2026-10-03

Decision class: `DEEP` (product authority). Readiness: `READY` for removing the
block only. This authorizes **no** spend, no new provider, and no new runtime
capability; it corrects documentation that was wrong.

### What the block actually said

Four places carried a charter-based block on cloud work:

- `ROADMAP.md` E0 row: "The cloud baseline remains deferred per the project charter."
- `ROADMAP.md` E4 row: "E4-10 cloud teacher baseline BLOCKED (out of scope per AGENTS.md)."
- `EXECUTION_CHECKLIST.md`: "E0-20/21 cloud baseline BLOCKED-BY-CHARTER", with
  E0-20 and E0-21 deferred "only if the charter is amended".

### Why the block was wrong

Read against `PRODUCT_CHARTER.md`, the charter does not forbid cloud:

- it assigns cloud an explicit reasoning role -- "cloud reasoning: architecture
  analysis, novel debugging, cross-module planning";
- it requires the user to be able to see "what project evidence was sent to a
  cloud model and what remained local";
- the benchmark **must** measure "cloud input/output tokens, cost and latency";
- the scope lock that bans "additional cloud/model providers" is explicitly
  bounded by "Until the exit gate in `ROADMAP.md` passes" -- it passed on
  `f3ad4ef`.

So the deferral was a misreading of "local-first, free-tier, zero vendor
lock-in" as a prohibition, when those are defaults and ownership constraints,
not a ban. Removing the block is a correction, not a charter amendment.

### What did not change

Local-first and zero vendor lock-in remain the defaults; a cloud response is
evidence, never approval; every remote call still passes Policy and the
disclosure gate; live provider calls stay opt-in and out of the default suite.
What is now permitted is *measuring* the cloud baseline (E0-20/21) and the cloud
teacher baseline (E4-10) -- the work the charter's own benchmark requirement
already implied.

### Still open

E0-20, E0-21 and E4-10 remain **unchecked**: unblocked is not done. Nothing here
has been run against a cloud provider.

## Verification follow-up — 2026-09-11 (`8d01d90` clean)

Result: **RATIFIED**. E1 gate is VERIFIED on clean revision `8d01d90`:
- E1-27 production measurement: `min_recall=1.0`, 12/12 samples at 100% recall
  with real Ollama embeddings (`nomic-embed-text:latest`), `fixtures_fresh=true`,
  `dirty=false`, `inputs_unchanged=true`.
- E2 entry gate: all prerequisites E2-25..28 + E2-45..47 implemented and tested
  (119 E2 contract tests pass). Cloud-baseline boundary explicitly resolved
  via `InferenceClassification` (E2-09) and `evaluate_local_eligibility` (E2-05).
- Offline qualification decision recorded in ROADMAP.md: local Ollama embeddings
  qualify; cloud token claim deferred to E2-21/E2-24.
- `tests/test_runtime_privacy_proof.py`: 7 end-to-end regression tests PASS.
- `tests/test_p1_router_filter_availability.py`: 9 contract tests PASS.
- Phase 21 bug fixes (4 regression tests in `test_phase21_bugfixes.py`) PASS.

Command evidence:

- `python -m pytest -q tests/test_e2_02_05_26_27_28_45_46_47*.py tests/test_planning_contract.py tests/test_e1_27_integration_pack_contract.py tests/test_e1_35_e2e_recall_contract.py tests/test_e1_36_adversarial_runtime.py`: 146 passed.
- `python -m ruff check src/paw/`: All checks passed.
- `git status --porcelain=v1`: empty (clean tree).
- E1-27 production measurement: PASS on clean revision.

## Phase-document review — 2026-09-09

Decision: **STANDARD / READY** for documentation repair only.
Problem: checklist/gate ratification promotes a measurement result to full E1,
while Roadmap blocks E2 and source already contains E2 runtime integration.
Evidence: `benchmarks/e1/real_measurement_local.json` explicitly limits scope
to measurement at `649ded9`; `docs/benchmarks/e1/integration_pack.md`
and `token_measurement.md` exclude full qualification and actual cloud savings.
At inspected `fd8a8c8`, E2-06..11 source is OBSERVED. Concurrent commits
subsequently advance E2 through `532bb38` (E2-18); those changes and new
uncommitted tests are preserved, not certified by this documentation review.

Options: (A) synchronize every document to the checklist's VERIFIED declaration;
(B) preserve measurement evidence, reopen unsupported overall acceptance and
make dependencies explicit (selected); (C) defer all documentation (leaves
conflicting execution instructions). Contrary evidence: clean source measurement
and later reported full-test results are meaningful progress, but neither alone
proves all Roadmap acceptance conditions on one revision.

Invariants: evidence before implementation, single ownership, exact proposal
before Policy/provider effects, and observation separate from verification.
Budget/stop: project documents, report scope, source/history only; no network,
runtime edits, full suite or new phase. Acceptance: EN/VI roadmap/checklist
distinguish item evidence from gate acceptance; E1 matrix names missing proof;
E2 preserves existing IDs with explicit readiness dependencies; D0 checks pass.
Scope changes or concurrent edits to the same paragraph require reassessment.

Documentation verification: contract-checks.sh reports CONTRACT PASSED;
`git diff --check` passes; `python -m pytest -q tests/test_project_lock.py`
reports 5 passed in 6.54s on the reviewed working tree. This is D0 evidence,
not D3; concurrent source commits prevent a clean-revision release claim.

Result: **PARTIAL** for project qualification; no new runtime verification.
Source presence is not entry authorization. Existing E2 changes need conformance
review, not deletion. Historical sections below retain their stated revision;
their “current”/“next” language must not override this review or the Roadmap.

## Historical audit records

### Verification follow-up — 2026-09-08 (`74b563e` + working tree)

Result: `PARTIAL`. The STANDARD/READY local-manifest repair below remains
applicable: its owning runtime branch is unchanged in HEAD. Model completion
now occurs once after the applicable disclosure check, including local
selections with a compiled manifest. The chat regression wraps the real model
executor and asserts one awaited completion. The status-lock assertion now
matches the canonical E1 row. Benchmark export lint repairs preserve members.

Current command evidence:

- `uv sync --locked --extra dev`: PASS (34 resolved, 33 checked).
- `python -m pytest -q tests/test_chat_cli_demo.py tests/test_runtime_privacy_proof.py tests/test_project_lock.py tests/test_e1_bl2_bench_exports_contract.py`:
  41 passed in 24.75s.
- `python -m ruff check .`: PASS.
- `uv build --wheel --out-dir /tmp/paw-d3-wheel-current`: PASS after preserving
  previous build staging outside the repository. Wheel archive bytes match all
  71 current Python source files. A separate venv installed that wheel and ran
  `python -m paw chat -m 'xin chào CLI' --provider local --json` outside the repo:
  completed, context compiled, response `[local-standin] xin chào CLI`.
- `python -m paw.bench.e1_production --output /tmp/paw-e1-review-74b563e-current.json --roots src/paw --case-dir benchmarks/e1/cases`:
  71 files / 836,732 bytes, recall 1.0, median reduction 0.9813659458820749,
  fresh fixtures, unchanged inputs/tree; PARTIAL/OBSERVED on dirty tree.

Earlier full-suite attempt: 1360 passed / 2 failed in 853.84s; the failures
were the local completion omission and old roadmap row assertion, both covered
by the current focused run. That attempt is not a passing D3 and cannot certify
the later E2-05 revision. The clean measurement at `7d0cc7e` passed with 71 files,
831,450 bytes and reduction 0.981077; it certifies that measurement only.

Remaining gate work: freeze the reviewed repair with current user changes
resolved, then rerun full D3 and representative measurement on that revision.
The workspace currently has unrelated AGENTS/PROFILE and bootstrap/state
changes; these were preserved. In particular, the uncommitted generic AGENTS
template no longer carries the tracked PAW rules and needs owner review before
freeze. No E2 activation is inferred from implementation checkboxes.

### Local manifest inference and status-lock repair — STANDARD / READY (2026-09-08)

Problem: D3 reproduces two failures on the clean E1 candidate. In
`PawRuntime._execute_action`, model completion is nested inside the non-local
privacy branch when a current manifest exists. A permitted local selection is
therefore never invoked; the capability executor still succeeds and its mock
output hides the missing model response. Separately, `test_project_lock` still
expects the retired `E1 measurement` roadmap row instead of the canonical `E1`
qualification row. The same D3 run finds two existing full-Ruff hygiene errors:
an unsorted `paw.bench.__all__` and an unnecessary generator in its export test.

Affected invariants: every provider side effect occurs after Policy and privacy
gates; a permitted selected model is executed exactly once; executor success is
not evidence that inference occurred; canonical documentation and its lock test
describe the same gate. Options considered: (A) change the chat expectation to
the mock-executor output (rejected because it blesses a skipped model call); (B)
omit the manifest for local chat (rejected because it removes the context and
privacy boundary); (C) apply disclosure checks only to non-local providers, then
invoke every admitted provider through one common completion path (selected).
Contrary evidence: task, checkpoint and executor records all complete normally,
so existing lifecycle evidence alone does not expose this inference omission.

Research budget and stop condition: current runtime, model executor, chat slice,
privacy contract and the two failing tests only; no external research or new
abstraction. Stop when local chat returns the deterministic local-model response,
remote refusal still makes zero provider calls, policy ordering remains covered,
and the documentation lock names the canonical row. Readiness: `READY`.

Implementation map: repair the call placement in `core/runtime.py`; keep
`ModelExecutor`, `CapabilityRouter` and privacy ownership unchanged. Normalize
the existing benchmark export list/test without changing its members, and
update the focused runtime regression plus canonical status lock. Acceptance:
the two reproduced failures, E1 disclosure tests, affected runtime ordering
tests and full Ruff pass before D3 is rerun.

### E1 qualification and E2 contract repair — DEEP / READY (2026-09-08)

Problem: E1 was promoted to `VERIFIED` from a clean report whose own
`corpus_roots` value is `benchmarks/e1/fixtures_paw`, although the Roadmap says
that report measured `src/paw`; the runner also states that its measurement gate
is separate from overall E1 qualification. E2-02/E2-03 then enlarged the locked
`paw.core` public surface and introduced two overlapping role registries. The
uncommitted E2-04 change additionally defines `PrivacyLevel` beside the canonical
`PrivacyClass`, defaults an unevaluated task to `FAST`, and implements E2-29
classification before E2-04's signal contract is closed.

Affected invariants: single contract, small public application surface,
quality-preserving optimization, evidence before implementation, and roadmap
gate ordering. Project evidence: `benchmarks/e1/e1_production_report.md` records
12 fixture files / 6,128 bytes and reduction 0.871; a current dirty-tree run over
`src/paw` records 70 files / 835,061 bytes, recall 1.0 and reduction 0.981, but is
`PARTIAL`/`OBSERVED` because the tree is dirty and at least one reviewed fixture
is stale. `tests/test_planning_contract.py` fails because `paw.core.__all__`
contains more than the eleven ratified symbols. `core/privacy.py` is already the
sole privacy-taxonomy owner.

Options considered: (A) accept the clean synthetic-fixture report and continue
E2 (rejected because it misstates the measured corpus and bypasses the entry
gate); (B) remove all E2 work until a new clean E1 freeze (safe but discards
useful contract work already committed); (C) restore E1/E2 status honesty,
quarantine E2 as pre-gate contract repair, keep only one immutable role-contract
registry, reuse `PrivacyClass`, define fail-closed task signals without routing
or depth decisions, and restore the eleven-symbol surface (selected). Contrary
evidence: the current real-source observation meets both numeric E1 thresholds,
so the remaining E1 problem is provenance/freeze and the wider quality/privacy
gate rather than retrieval performance. That is not enough to call E1
`VERIFIED`.

Research budget and stop condition: current source, contract tests, the two E1
corpora/reports and canonical documents only; external research cannot change a
PAW-owned status or ownership contract. Stop when the corpus mismatch, duplicate
contracts, unsafe defaults and public-surface regression have falsifiable tests.
Readiness: `READY` for this repair only. It does not authorize E2 router wiring,
classification, persistence, provider expansion or runtime behavior.

Implementation map: `core/reasoning_contracts.py` owns the bounded E2 role and
task-signal value contracts; `core/models.py` retains the historical `ModelRole`
enum and contains no second role registry; `core/privacy.py:PrivacyClass` remains
the privacy owner; `core/__init__.py` remains exactly eleven symbols. Tests cover
immutability, validation, fail-closed defaults, the minimum E2 role subset,
absence of a second privacy enum and the root public surface. Canonical EN/VI
documents must report E1 `PARTIAL`, E2 `BLOCKED`, and distinguish the synthetic
clean metric observation from the dirty real-source observation. Acceptance:
focused E1/E2/public/privacy tests and Ruff pass; document contracts and diff
hygiene pass; E1 remains `PARTIAL` until a current reviewed `src/paw` revision
passes the complete clean-revision gate.

### E1 real-project qualification repair — STANDARD / READY (2026-09-07)

Problem: the synthetic corpus passes E1-27, while the reviewed PAW-source cases
fail required-evidence recall; the production runner is ignored by Git and its
focused test cannot import it. The current tree also contains unfinished hybrid
retrieval/schema work labelled E2-31. E2 cannot use a synthetic PASS to bypass
the E1 entry gate.

Invariants: required evidence survives context reduction; benchmark evidence is
reproducible from tracked inputs; changed inputs cannot remain qualified; schema
has one versioned owner; E2 begins only after E1 acceptance on a representative
project corpus. Options: (A) select the synthetic PASS and defer real retrieval
(rejected: contradicts the product's code-analysis purpose); (B) enable semantic
retrieval and assume it fixes the gap (rejected without a controlled comparison);
(C) first make the runner canonical, reproduce the PAW-source miss, repair the
smallest deterministic retrieval defect, then retain hybrid persistence only if
it adds independently verified value (selected). Contrary evidence: a six-case
PAW corpus is still a small proxy for user projects, so passing it cannot prove
general production quality. Research budget: tracked source/tests, six reviewed
PAW cases and focused runtime/schema checks; stop at a falsifiable E1 gate result.

Implementation map: `paw.bench.e1_production` owns the tracked runner; the old
ignored scripts become compatibility-free local artifacts and are not evidence.
`KnowledgeIndex` owns knowledge retrieval; `ContextCompiler` consumes ranked
results; `storage.py` owns any retained schema change. Acceptance: the PAW-source
cases reach >=95% recall in cold and warm modes while median context reduction
remains >=30%; runner rejects dirty/mid-run changed evidence; remote-disclosure
runtime proofs pass; focused tests, Ruff and docs agree. This touches retrieval
and potentially schema, so integrated qualification requires D3 before E2.

### Measurement provenance repair — STANDARD / READY (2026-09-07) [EXECUTED 2026-09-07 08:24 UTC]

Problem: the new report pins a revision without the E1 runner, uses unexplained
4000/3000 baselines and recommends substituting skills for file evidence.
Invariant: source-bound evidence and quality-preserving optimization.
Options: restore the old script (small, but retains global DB/config ambiguity),
or add a standalone offline diagnostic runner with isolated per-case SQLite,
actual fixture ingestion, input hashes and machine-readable results (selected).
Contrary evidence: a full-fixture baseline is not a reviewed E0/cloud baseline;
the result must remain diagnostic, not E1 qualification. No embedding/provider
expansion, runtime changes or weakened recall. Budget: local code/test review
and one two-case run; stop after provenance and negative controls are proven.
Files: src/paw/bench/e1_production.py (tracked canonical runner), focused runner test, report and EN/VI map.
Acceptance: record HEAD plus dirty state and hashes, ingest actual case fixtures,
derive baseline with the compiler estimator, preserve errors and raw metrics,
never overwrite an existing report; no privacy/cache/quality claims from emptiness.

**Execution record (2026-09-07 09:52 UTC, HEAD = `208783c`):**

The runner was re-run a second time. Three further fixes shipped:

| # | Issue | Resolution evidence |
|---|-------|---------------------|
| 5 | Corpus too small: 2-case subset | Runner now uses the full 14-case E0 set by default; `--subset` opt-in for targeted runs. |
| 6 | False-negative reduction: file-only baseline counted the 24-token always-on skill overhead as extra cost | Runner now adds `_always_on_skill_overhead()` to the per-case baseline. New 4-test contract at `tests/test_e1_budget_compression.py` proves the budget filter drops 7 of 8 sources when the budget is tight (warm reduction > 0.30) and keeps all candidates when the budget is loose. The 30% gate is therefore not evaluable on the E0 fixture corpus (intentionally small) — it is calibrated for a realistic production corpus. |
| 7 | Recall/sample scope | 14 cases × 2 modes = 28 (case, mode) combinations; recall = 1.00 on every sample. |

Final results on 2026-09-07 09:52 UTC:
- Recall: 28/28 = 1.00 (every case, every mode). Gate `>= 0.95` PASS.
- Warm reduction: median = +0.000 (the budget never filters on the E0 corpus). Gate `>= 0.30` NOT MET.
- Qualification: `PARTIAL` (mechanism proven by 4-test contract; corpus too small for the gate).

Reproduction:
```
uv run python -m paw.bench.e1_production --output benchmarks/e1/measurement_20260907.json
# Optional: subset for a single case
uv run python -m paw.bench.e1_production --output /tmp/subset.json
```

The output path opens with `mode='x'`, so re-running on a non-empty target raises
`FileExistsError` and the prior report is never silently overwritten.

**Execution record (2026-09-07 10:30 UTC, HEAD = `30ed2ac`):** production-corpus runner added.

A new tracked production runner `paw.bench.e1_production`
(`src/paw/bench/e1_production.py`) ingests a real, reviewed production corpus
(default: `src/paw/`, or a synthetic 12-file corpus at `benchmarks/e1/fixtures_paw/`
with `UNIQUEKEYWORD_<MODULE>` markers). Python files are chunked by top-level
function/class definition (one `KnowledgeSource` per file, multiple `KnowledgeChunks`).
The baseline is the sum of every chunk's token estimate + the always-on skill overhead.

Three findings:

1. **Bug fix**: `ContextCandidate.__lt__` was inverted (returned `>` instead of `<`),
   making `sorted(reverse=True)` produce ASCENDING order. The budget filter dropped
   high-score candidates first. Fixed; pinned by `tests/test_context_compiler_sort.py`
   (3 tests).
2. **Synthetic corpus (12 small files, `max_tokens=1500`)**: E1-27 gate **PASSES** —
   recall 24/24 = 1.00, median warm reduction 0.812. Demonstrates the gate mechanics
   work end-to-end on a properly-sized corpus.
3. **PAW source corpus (69 files, `max_tokens=5000`)**: E1-27 gate **PASSES** —
   the `__lt__` fix closed the recall defect. recall = 1.00 on all 12 (case, mode)
   samples, median warm reduction 0.981. The compression mechanism works (reduction
   0.98); the target files are now correctly retained by the budget filter.

Reproduction:
```
# Synthetic corpus
uv run python -m paw.bench.e1_production \
  --output /tmp/e1_synthetic.json \
  --roots benchmarks/e1/fixtures_paw \
  --case-dir benchmarks/e1/cases_prod \
  --max-tokens 1500 --max-fragments 5 --max-sources 3

# PAW source (the representative gate)
uv run python -m paw.bench.e1_production \
  --output /tmp/e1_paw_source.json \
  --roots src/paw \
  --case-dir benchmarks/e1/cases \
  --max-tokens 5000 --max-fragments 30 --max-sources 10
```

Full evidence at `benchmarks/e1/e1_production_report.md`.

### Review 2026-09-07 at f625fcb

Follow-up decision: STANDARD / READY for measurement and freshness repair.
Invariants: explainable bounded context, evidence before acceptance, stale
decisions cannot authorize implementation. Source shows unbounded recall,
swallowed compiler/cache errors, self-baselines and clamped token regressions.
Select budget-preserving shared manifests, explicit positive baselines, signed
reduction and exact revision comparison. Alternative: keep diagnostic unlimited
recall and ancestry heuristics, but they cannot answer runtime quality/freshness.
Deferring is viable only while E1 stays PARTIAL. Trade-off: previously accepted
cases without retrievable file evidence/baselines now fail visibly; unrelated
commits conservatively invalidate decisions. No automatic corpus ingestion or
new runtime/schema owner. Budget: local owner/caller/test inspection, stop at
falsifiable regressions. Scope: bench recall/tokens/integration, knowledge history,
focused tests and EN/VI documentation. D2 measurement integration proof; full
release qualification remains separate. Acceptance: one manifest per case/mode,
cold then repeated warm calls, 95% recall and 30% median warm reduction, invalid
baselines/modes rejected, compiler failures propagated, changed revision stale.

Current handoff: `PARTIAL`. E1 qualification is reopened; later E2 work must
wait for reliable measurement. Historical completion counts below are not
current gate proof.

Source findings:
- `bench/integration.py` accepts an empty case directory as `VERIFIED`.
- Its token floor is 0%, whereas Roadmap requires 30% median warm reduction;
  it requests only cold measurements and does not enforce all privacy/quality
  acceptance conditions. Fixing empty input alone cannot qualify E1.
- `knowledge/history.py` treats a differing reachable revision as fresh;
  commit ancestry is not evidence that decision inputs are unchanged.
- README, Roadmap and checklist disagree on E1 completion. The Architecture
  document precedence also conflicts with docs/README source/test authority.

Decision: `STANDARD`, `READY` for empty-input repair. Options: return BLOCKED
with an inspectable report (selected), or raise an input exception (viable but
loses the existing report workflow); leaving success unchanged violates the
verification invariant. Keep the current result shape and nonempty behavior.
Acceptance: empty and missing directories cannot certify success; existing
nonempty scoring tests still pass. Budget: inspect runner, callers and tests,
stop after reproducing the false-positive. Owner/files: bench/integration.py,
its focused regression test, benchmark contract and synchronized audit docs.
This is a D1 repair without schema or runtime-loop changes.

| Item | Observed value |
|---|---|
| Revision | `f21a508` on `main` + Core Stabilization working tree |
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

Capture date: 2026-09-02. Base revision: `f21a508`.
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

### Active decision record: E1-01 ownership audit (reopened 2026-09-04)

Decision class: STANDARD (was FAST for the original audit, reopened because the
original audit listed phantom `MemoryRecord.source`, missing
`keywords`/`updated_at`/`last_accessed`, and phantom `KnowledgeSource.kind`/
`uri`/`revision` — the contract test makes it STANDARD). Readiness: READY for
the regenerated audit + contract test.

- **Problem:** the original E1-01 audit (`f909f65`) listed field sets that did
  not match the actual dataclasses (`MemoryRecord` had a phantom `source` and
  was missing `keywords`/`updated_at`/`last_accessed`; `KnowledgeSource` had
  phantom `kind`/`uri`/`revision` and was missing the real `name`/`type`/
  `path`/`status`/`chunk_count`/`last_sync`/`checksum`/`updated_at`; the
  ContextCompiler section listed only 5 `TaskContext` fields and missed
  `ContextBudget`, `ContextPlan`, and the compiler-instance fields).
- **Constraints:** one canonical owner per concept (Architecture Safety
  invariant #1); the audit is read-only (no new field, no migration, no
  runtime code path); the audit must be regenerated from source on every change
  that adds a field to one of the owned dataclasses.
- **Evidence (regenerated):**
  - `src/paw/core/memory.py` `MemoryRecord` — 13 persistent fields
    (`id`, `project_id`, `task_id`, `memory_type`, `content`, `summary`,
    `keywords`, `metadata`, `confidence`, `created_at`, `updated_at`,
    `last_accessed`, `access_count`); 13 SQL columns on `memory_records`
    (`keywords` is JSON-encoded).
  - `src/paw/knowledge/source.py` `KnowledgeSource` — 12 fields (`id`,
    `name`, `type`, `path`, `metadata`, `status`, `chunk_count`,
    `last_sync`, `checksum`, `created_at`, `updated_at`).
  - `src/paw/knowledge/chunk.py` `KnowledgeChunk` — 7 fields.
  - `src/paw/knowledge/evidence.py` `KnowledgeEvidence` — 6 fields.
  - `src/paw/knowledge/citation.py` `KnowledgeCitation` — 7 fields.
  - `src/paw/core/context.py` `TaskContext` — 8 fields; `ContextBudget` —
    8 fields.
- **Option A — selected:** regenerate `docs/benchmarks/e1/ownership_audit.md`
  from source (every field on every owned dataclass, plus the transient
  `KnowledgeSearchResult`/`ContextCandidate`/`ContextPlan`/`ContextCompiler`
  fields the original audit dropped). Pin the audit with a contract test
  `tests/test_e1_ownership_audit_contract.py` (16 D1 tests) that asserts
  every audit row is a real dataclass field and every dataclass field
  appears in the audit.
- **Option B — rejected:** regenerate the audit from source without a
  contract test. A reviewer could re-introduce the regression (phantom
  fields, missing fields) in the next E1 change; the audit would silently
  drift and the bug would only surface on a manual diff.
- **Option C — rejected:** replace the audit with a runtime import that
  introspects the dataclasses. The Architecture forbids ownership being a
  runtime check; the audit must be human-readable prose plus a test that
  pins it.
- **Two-fail-positive proven:** swapping the regenerated audit with the
  original `f909f65` audit causes the contract test to fail 16/16
  (every owned dataclass trips the "audit missing field" or
  "audit lists phantom field" assertion). The test is doing its job; the
  audit was wrong.
- **Phase 4 sync contract:** the audit is the source of truth for E1
  ownership; the contract test pins the audit to the actual dataclass
  fields. A later E1 item that adds a new field must update both the audit
  table and the test expectation in the same change, or the test fails.
  If the new field lives in a module that is not listed, the change is
  introducing a new owner and the change is wrong.

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
| Context | `core/context.py`: types plus compatibility `ContextBuilder`; `core/context_compiler.py`: `ContextCompiler` | Compiler is used by agent/graph paths | `PASS`; `ContextBuilder` is now a thin facade and contains no second assembly algorithm. `ContextManifest` included/excluded truth fixed: `_allocate_budget` now sets `metadata['included']=False` for excluded candidates, preventing manifest corruption where candidates excluded by `max_fragments_exceeded` appeared in neither list. |
| Memory | `core/memory.py`, `core/embeddings.py` | `ContextCompiler` uses `AdvancedMemoryRetriever` | `PASS` for the product slice: deterministic lexical fallback, controlled hybrid ranking, persisted embeddings, compiler integration and the real-SQLite 100-memory stress gate are tested. |
| Knowledge | persisted records in `knowledge/source.py`, `chunk.py`, `evidence.py`, `citation.py`, `index.py`; result boundary in `knowledge/normalization.py` | Compiler retrieves candidates; callers normalize selected records to `TaskResult` explicitly | `PASS` for contract ownership: stored records remain persistence types and one strict normalizer preserves result provenance. |
| Policy | `core/policy.py`: `PolicyGuard`; exact approval in `core/approval.py` | `PawRuntime._gate_action` then `AutonomyController.decide(policy_verdict=...)` | `PASS` for gate ordering and durable ASK: one verdict is reused, DENY never executes, and only an approved exact proposal resumes. |
| Privacy | `core/privacy.py`: `PrivacyClass`, `gate_remote_disclosure`, `RemoteDisclosureRefused` | Runtime-side helper; context compiler and policy gate consult it | `PASS` for E1-03 privacy classes; E1-21 hard gate now raises `RemoteDisclosureRefused` to stop execution instead of silently skipping model invocation. |
| Autonomy | `core/autonomy.py`; detectors in `core/detectors.py`; profiles in `core/execution_profile.py`; beta profiles in `core/beta_profiles.py` | All runtime paths | `PASS` for current budget/continue/stop accounting. Post-gate `ESCALATE` assessment/reroute protocol is absent and current runtime treats that enum as a stopped outcome. |
| Capability Router | `core/executor.py`: `CapabilityRouter`, `ExecutorRegistry` | `PawRuntime._execute_action` | `PASS`; every agent/graph action selects a compatible executor before invocation. |
| Executor | Port/registry and `EffectIntent` in `core/executor.py`; local adapter in `executors/filesystem.py`; model providers in `core/model_executor.py` | `PawRuntime._execute_action` invokes or reconciles the capability-selected executor | `PASS` for the built-in adapter: skill body is context only, filesystem writes prepare a durable intent and restart never repeats a prepared effect blindly. |
| Model Router | `core/model_router.py`: registry/router/provider registry; `core/model_executor.py` | Execution stage routes after the proposal gate | `PASS` for current gate ordering. `ModelRouter.score_model_for_task()` added as the canonical scoring entry point. **P1 Router fix (2026-09-07)**: `_filter_for_availability` local-fallback branch now (a) filters by `m.supports_role(role)` so wrong-role models do not leak; (b) re-scores via the canonical entry point; (c) sorts by score descending so registration order does not affect the final selection; (d) returns `[]` when no local model supports the role. 9 new contract tests in `tests/test_p1_router_filter_availability.py` pin every property. Post-gate escalation needs a side-effect-free cached selection path; live initialization/discovery cannot hide before the new proposal gate. |
| E2 reasoning contracts | `core/reasoning_contracts.py`; historical routing vocabulary remains `core/models.py:ModelRole`; privacy remains `core/privacy.py:PrivacyClass` | Not wired into router/runtime while E1 is `PARTIAL` | Pre-gate contract repair only. One immutable registry covers the minimum FAST/REASONING/CODING/TOOLS role outputs; `TaskSignals` records fail-closed novelty/impact/privacy/context/budget inputs. It deliberately does not classify research depth, select a route or authorize escalation. |
| E2 local eligibility + OOD | `core/reasoning_contracts.py` | Not wired into router/runtime while E1 is `PARTIAL` | Pre-gate contract repair only. One closed `OODCondition` enum (9 values) and one immutable `EligibilityRule` per cognitive role define when a role is not eligible for local execution. `FAST` and `TOOLS` are bounded; `REASONING` and `CODING` are strict. `evaluate_local_eligibility()` is deterministic and fail-closed for unknown roles. It does not select a model, authorize escalation or invoke a provider. |
| Ledger | `core/ledger.py`; transaction coordinator in `core/runtime_persistence.py` | Used throughout runtime | `PASS` for local atomic evidence: observation/artifact/execution events and operation record commit together; terminal task/checkpoint/events roll back together under injected failures. |
| Checkpoint/Resume | `core/checkpoint.py`: checkpoint, prepared/completed operation record, resume services | `run`/`run_agent`/`run_graph` restore durable state; executor restart consults prepared effects | `PASS` for committed stores, atomic checkpoint events, restored autonomy/context, stable idempotency IDs and filesystem reconciliation after close/reopen. |
| Storage | `core/storage.py`: global database proxy and schema; runtime transaction grouping in `core/runtime_persistence.py` | Shared by nearly every service | `PASS` for centralized DDL, non-destructive migration, autocommit-safe legacy writes and explicit multi-record commit boundaries. |
| Runtime | `core/runtime.py`: `PawRuntime.run`, `run_agent`, `run_graph`, `_execute_unit` | Integration authority | `PASS` for the current executable proposal pipeline. Remote-disclosure gate is HARD: `RemoteDisclosureRefusedError` exception stops the loop. **Runtime privacy proof (2026-09-07)**: `_execute_unit` now persists `OperationRecord` with `status="failed"` (and reason metadata) when the hard gate fires, so reopen/resume does NOT retry the refused operation (previously: early return without op-record = silent resume = provider re-call). 7 end-to-end regression tests in `tests/test_runtime_privacy_proof.py` prove: zero provider calls + zero executor calls when SECRET+remote, terminal non-success, OperationRecord persisted as 'failed', WORKSPACE class blocks remote, INTERNAL class allowed, stale manifest blocks remote. Post-gate decision admission, non-terminal escalation and engineering `VerificationRecord` derivation are absent. |
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
| E2 cognitive roles and signals | `core/reasoning_contracts.py`; `ModelRole` remains in `core/models.py`; `PrivacyClass` remains in `core/privacy.py` | One `RoleContract` registry; task signals reference the canonical privacy enum. No `PrivacyLevel`, duplicate role-definition registry, depth classifier or escalation decision is present. |

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
4. Remote-disclosure gate is HARD: when `gate_remote_disclosure` refuses,
   `RemoteDisclosureRefused` exception propagates from `_execute_action`
   through `_execute_unit` to stop the loop. Previously it silently set
   `model_result={}` which allowed execution to continue with remote
   SECRET/WORKSPACE context — a critical privacy violation.

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

The F0 (SX + E0) work is closed. Core Stabilization is `VERIFIED` on the
frozen revision `f3ad4ef`, and E0 has a verified deterministic
fixture-validation baseline. The current repair target is E1 qualification:
the `c28d679` clean report measured the small synthetic fixture corpus, while
the current representative `src/paw` observation is numerically green but
dirty and stale against reviewed fixture revisions. E2 remains blocked. The
isolated E2 role/signal contracts are retained as pre-gate drafts only; the
next executable E2 item is not authorized until E1 is frozen `VERIFIED`.

### E1 backlog items from the F0 review (added 2026-09-03)

These three items were identified while reviewing the F0 surface but did
not block the E0 gate. They are recorded here so the E1 reviewer picks
them up before the first E1 deliverable. They are also tracked as
`E1-BL1`, `E1-BL2`, `E1-BL3` in `docs/EXECUTION_CHECKLIST.md`.

- **`E1-BL1` — broaden the contract check status-vocabulary rule**
  (2h, D0). Today
  `skills/bootstrap-canonical-docs/scripts/contract-checks.sh` only flags
  `DONE` / `TODO` / `FIXME` / `XXX` / `WIP` when they appear inside an
  item-shaped clause (`(\d+[hd],\s*D[0-9])`). A roadmap line like
  `already DONE` slipped through during the F0 review. The fix is a
  broader regex that flags any of the six forbidden tokens used as a
  status word anywhere in the canonical docs.
- **`E1-BL2` — tighten `paw.bench` wildcard exports** (1h, D0). The
  current `paw/bench/__init__.py` re-exports stdlib symbols (`Any`,
  `ClassVar`, `StrEnum`, `dataclass`, `field`) and the `runner` /
  `verification` submodules. Architecture says "module-level helper
  proliferation and broad wildcard exports are not part of the
  architectural contract". The fix narrows `__all__` to the twelve
  benchmark-contract symbols and removes the stdlib re-exports;
  submodules stay importable via their explicit path.
- **`E1-BL3` — refresh the agent memory file `PROFILE.md`** (30m, D0).
  The memory file still records the Phase 10/19/20 narrative from the
  early sessions and does not mention the E0-23a `paw.core` surface,
  the E0-27 gate verdict, or the new `bootstrap-canonical-docs` /
  `doc-driven-stabilization` skills. The fix records the post-F0 state
  so the next session reads an accurate memory.

The ordered acceptance plan is in `ROADMAP.md`.
## E1 measurement repair — 2026-09-07

Implementation is PARTIAL at the project level. Focused regression checks cover
budget-preserving source-bound recall, signed token reduction, explicit baselines,
shared cold/warm manifests and exact revision freshness. The measurement gate
returns PASS/PARTIAL/FAIL/BLOCKED, never a full-E1 VERIFIED declaration.
See benchmarks/e1/{recall_measurement,token_measurement,integration_pack,revision_invalidation}.md.

Verification: 59 focused tests passed (measurement regressions, E1-23/24/27/33/35
and project lock). This is dirty-tree evidence, not a clean-revision exit gate.
Remaining: reviewed corpus/baseline provenance, controlled cold/warm dataset run,
privacy and engineering-quality acceptance, and clean-revision evidence.
