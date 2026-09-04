# E0 Integration Pack Run (E0-27)

This document is the **E0-27 deliverable**. It records the
D3 release-check evidence and the gate decision for the
E0 track.

## Run identifier

| Field | Value |
|---|---|
| Run ID | `2026-09-03T17-00-00Z` |
| Revision | (the frozen revision on `main` at run time) |
| Branch | `main` |
| Operator | `doc-driven-stabilization` skill |
| Cases run | 13 / 13 (8 minimum cases E0-08..15 + 5 research-decision cases E0-28..35, the latter two via list-literal `command_exit` evidence) |
| Seed | `e0-27-integration` (deterministic) |

## What this run does and does not measure

The deterministic runner in `src/paw/bench/runner.py` is
the **fixture-validation** tier of the benchmark. It
asserts that the case manifest, the fixture, and the
expected-evidence verify command agree on the artifact
the runtime is supposed to produce. It does **not**
score agent quality: no runtime loop runs in this pack,
no model output is sampled, no prompt is evaluated.

The agent-quality tier is the **runtime-driven runner**
that lives in `paw.bench.run_case` (E0-40 roadmap; the
contract is specified in
`docs/benchmarks/e0/expected_evidence_spec.md` but the
runtime-driven implementation is post-gate work). The
fixture-validation tier proves the *contract*; the
runtime-driven tier proves the *agent*.

Concretely:

- `outcome=SUCCESS` in this pack means
  `file_contains`/`command_exit` evidence passed on the
  fixture. It does not mean the agent solved the case.
- The 13/13 SUCCESS line below is **fixture-validation
  evidence**, not an agent-quality gate. A reviewer who
  treats it as an agent-quality claim is over-reading
  the run.
- The agent-quality gate is `RunSummary.outcomes` from
  the runtime-driven runner. That runner does not exist
  yet; the E0-40 spec is the contract that closes it.

## D3 evidence

### Full test suite

```
.venv/bin/python -m pytest -q
685 passed in 351.41s (0:05:51)
```

### Lint

```
.venv/bin/python -m ruff check src/paw/ tests/
All checks passed!
```

### Wheel build

```
uv build --wheel
Successfully built dist/paw-0.1.0-py3-none-any.whl
```

### Clean install

```
uv pip install --python /tmp/paw-test-install/bin/python \
    dist/paw-0.1.0-py3-none-any.whl
/tmp/paw-test-install/bin/paw --version
PAW version 0.1.0
```

### Smoke test

The wheel exposes `paw.bench` with all 18 benchmark
symbols; importing and running a case against the
in-tree fixtures produces `outcome=SUCCESS passed=1/1`
(fixture validation only — see the section above).

## Per-case runner output (fixture validation)

| Case | Outcome | Evidence | Duration (ms) |
|---|---|---|---:|
| `architecture_decision_cache` | SUCCESS | 2/2 | <50 |
| `cross_module_change_constant` | SUCCESS | 2/2 | <50 |
| `defect_localization_simple_math` | SUCCESS | 2/2 | <50 |
| `insufficient_context_empty_goal` | SUCCESS | 1/1 | <50 |
| `interrupted_recovery_midway` | SUCCESS | 2/2 | <50 |
| `privacy_negative_secret_marker` | SUCCESS | 1/1 | <50 |
| `refactor_rename_function` | SUCCESS | 2/2 | <50 |
| `repo_understand_small_repo` | SUCCESS | 3/3 | <50 |
| `decision_needs_clarification_auth` | SUCCESS | n/n | <50 |
| `decision_needs_research_security` | SUCCESS | n/n | <50 |
| `decision_ready_simple_module` | SUCCESS | n/n | <50 |
| `decision_rejected_duplicate_owner` | SUCCESS | n/n | <50 |
| `decision_spike_exotic_locking` | SUCCESS | n/n | <50 |

The per-run JSONL files are at
`benchmarks/e0/runs/2026-09-03T17-00-00Z/*.runs.jsonl`.
Each row records the verify command's exit code and a
seed; no model output is captured at this tier.

## Run aggregate

```yaml
outcomes: {SUCCESS: 13}
cases: 13
unsafe_rate: 0.0
flakiness_score: 0.0   # all 13 cases deterministic
tier: fixture-validation   # NOT agent-quality
```

## E0 acceptance criteria check

The E0 track has the following acceptance criteria from
ROADMAP.md:

| Criterion | Status | Evidence |
|---|---|---|
| Reproducible deterministic offline baseline | PASS | All 13 cases pass with fixed seed (fixture validation). |
| Reviewed cloud baseline | DEFERRED | Out of scope until a non-Ollama cloud provider is approved (charter scope lock). The Ollama local baseline (ADP-01) is in place; a future E2 step may add the cloud baseline. |
| Benchmarks measure research/readiness decisions | PARTIAL | The minimum case set (E0-08..15) measures engineering outcomes. The research-decision cases (E0-28..35) measure `NEEDS_RESEARCH`, `NEEDS_CLARIFICATION`, `SPIKE_REQUIRED`, `READY`, `REJECTED` decision scoring via the same fixture-validation tier; the runtime-driven scoring tier is post-gate work. |
| Every public capability has a disposition | PASS | E0-23..26 review: all 42 inventory items marked `core`, no `quarantine` items, no compat obligations silently dropped. |

## Gate decision

**`VERIFIED`** — the E0 track has the right
*foundation* for the E0-28..35 research-decision
benchmark extension.

The E0 gate is `VERIFIED` **for the deterministic offline
fixture-validation baseline**; the cloud baseline
remains deferred per the E0 acceptance criteria and the
runtime-driven agent-quality baseline is post-gate
work per E0-40. This is the right outcome for a project
that is still local-first by charter and that has not
yet built the runtime-driven runner.

## What passes and what does not

**Passes**:

- 685/685 unit tests, lint clean, wheel builds, clean
  install works, smoke test produces SUCCESS.
- 13/13 cases load + run + produce SUCCESS at the
  fixture-validation tier.
- The contract is end-to-end: case YAML → loader →
  manifest → runner → JSONL row → aggregate.
- The E0-23a paw.core 11-symbol surface is preserved
  (verified by 17+ guard tests across the E0 items).
- The E0-26 dead-table check caught and removed a real
  dead `intelligent_plans` table.
- The E1 reopen added an ownership contract test
  (`tests/test_e1_ownership_audit_contract.py`,
  16 tests) that pins the E1-01 audit to the actual
  dataclass fields.

**Does not (yet) pass**:

- The runtime-driven agent-quality tier does not exist;
  the 13/13 SUCCESS line is fixture-validation, not an
  agent-quality gate. The agent-quality tier is the
  E0-40 deliverable.
- The cloud baseline is deferred per the E0 acceptance
  criteria and the project charter.
- The `ledger_event`, `task_status`, `policy_decision`
  evidence kinds are reserved for the runtime-driven
  runner; the deterministic runner scores them as
  FAIL with a clear diagnostic.

## Phase 4 sync contract

This document is the **source of truth** for the E0-27
gate decision. A future E0 milestone (e.g. E0-40) may
re-run the integration pack and update the run ID +
result table; the criteria checklist and the gate
decision section are the change-control surface.

The tier label in the run aggregate is the
change-control surface for the
fixture-validation-vs-agent-quality distinction: a
reviewer who wants to claim 13/13 SUCCESS as an
agent-quality gate must first land the runtime-driven
runner that the label refers to.
