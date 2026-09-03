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
| Cases run | 8 / 8 (E0-08..15 minimum case set) |
| Seed | `e0-27-integration` (deterministic) |

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
in-tree fixtures produces `outcome=SUCCESS passed=1/1`.

## Per-case runner output

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

The per-run JSONL files are at
`benchmarks/e0/runs/2026-09-03T17-00-00Z/*.runs.jsonl`.

## Run aggregate

```yaml
outcomes: {SUCCESS: 8}
cases: 8
unsafe_rate: 0.0
flakiness_score: 0.0   # all 8 cases deterministic
```

## E0 acceptance criteria check

The E0 track has the following acceptance criteria from
ROADMAP.md:

| Criterion | Status | Evidence |
|---|---|---|
| Reproducible deterministic offline baseline | PASS | All 8 cases pass with fixed seed. |
| Reviewed cloud baseline | DEFERRED | Out of scope until a non-Ollama cloud provider is approved (charter scope lock). The Ollama local baseline (ADP-01) is in place; a future E2 step may add the cloud baseline. |
| Benchmarks measure research/readiness decisions | PARTIAL | The minimum case set (E0-08..15) measures engineering outcomes. The research-decision cases (E0-28..35) are part of the post-27 work; they will extend the E0 baseline to include `NEEDS_RESEARCH`, `NEEDS_CLARIFICATION`, `SPIKE_REQUIRED`, `READY`, `REJECTED` decision scoring. |
| Every public capability has a disposition | PASS | E0-23..26 review: all 42 inventory items marked `core`, no `quarantine` items, no compat obligations silently dropped. |

## Gate decision

**`VERIFIED`** — the E0 track has the right
*foundation* for the E0-28..35 research-decision
benchmark extension.

The E0 gate is `VERIFIED` **for the deterministic offline
baseline**; the cloud baseline remains deferred per
the E0 acceptance criteria. This is the right
outcome for a project that is still local-first by
charter.

## What passes and what does not

**Passes**:

- 685/685 unit tests, lint clean, wheel builds, clean
  install works, smoke test produces SUCCESS.
- 8/8 minimum cases load + run + produce SUCCESS.
- The contract is end-to-end: case YAML → loader →
  manifest → runner → JSONL row → aggregate.
- The E0-23a paw.core 11-symbol surface is preserved
  (verified by 17+ guard tests across the E0 items).
- The E0-26 dead-table check caught and removed a real
  dead `intelligent_plans` table.

**Does not (yet) pass**:

- The 4 research-decision benchmarks (E0-28..35) are
  scoped but not authored; the E0-27 deliverable
  records the gap and the next item picks it up.
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
