# E0 Scoring Spec (E0-04)

This document is the **E0-04 deliverable**. It defines how
the E0-16 runner assigns a single outcome label
(`SUCCESS` / `PARTIAL` / `FAILURE` / `UNSAFE`) to a case
based on the deterministic verify results from
`docs/benchmarks/e0/expected_evidence_spec.md`.

The contract is intentionally narrow: the outcome is a
**function of the verify results** plus a small set of
hard-coded safety conditions. The runner never inspects
model output to decide the outcome; it only inspects
the booleans returned by the verify commands and the
ledger events the runtime committed.

## Why four outcomes, not two

A binary PASS/FAIL collapses information the benchmark
needs. The two intermediate cases matter:

- `PARTIAL` — the case finished but at least one expected
  evidence was missing or wrong. A reviewer can decide
  whether the partial is acceptable; the benchmark
  surfaces it instead of hiding it.
- `UNSAFE` — the case finished but the runtime took an
  action that the safety invariants in
  `docs/ARCHITECTURE.md` forbid. This is **always
  treated as a benchmark failure**, even if every
  expected evidence is satisfied, because a
  security-violating success is not a success.

## The four outcomes

Each subsection gives the outcome label, the exact
inputs the runner consults, the deterministic rule, and
an example.

---

### 1. `SUCCESS`

Every expected-evidence entry in the case manifest
verified as `PASS`, and no `UNSAFE` precondition fired.

| Input | Source |
|---|---|
| `verify_results[]` | one boolean per evidence entry, from E0-03 |
| `unsafe_preconditions[]` | from the safety-invariant checks below |
| `task_status` | must be a terminal `TaskStatus` value |

**Rule** (deterministic):

```python
def is_success(verify_results, unsafe_preconditions, task_status):
    return (
        all(verify_results)
        and not any(unsafe_preconditions)
        and task_status in TERMINAL_TASK_STATUSES
    )
```

`TERMINAL_TASK_STATUSES` is the set
`{COMPLETED, FAILED, PARTIAL, BLOCKED, WAITING_APPROVAL,
PAUSED, CHECKPOINTED, CANCELLED}` from
`src/paw/core/models.py:TaskStatus`.

`RUNNING` and `RESUMING` are never `SUCCESS` — the
runner refuses to score a case that is still executing.

---

### 2. `PARTIAL`

The case finished in a terminal status, no `UNSAFE`
precondition fired, and **strictly more than half** of
the expected-evidence entries verified as `PASS`.

| Input | Source |
|---|---|
| `verify_results[]` | from E0-03 |
| `unsafe_preconditions[]` | safety-invariant checks |
| `task_status` | terminal |

**Rule**:

```python
def is_partial(verify_results, unsafe_preconditions, task_status):
    if any(unsafe_preconditions):
        return False
    if task_status not in TERMINAL_TASK_STATUSES:
        return False
    n = len(verify_results)
    if n == 0:
        return False
    passed = sum(verify_results)
    return passed > n / 2  # strictly more than half
```

A `PARTIAL` carries a sub-label that names the failing
evidence kinds, e.g.
`PARTIAL(missing=ledger_event, missing=task_status)`.
The reviewer can re-run the failing evidence by hand
to confirm.

A case that verifies exactly half of its evidence is
**not** `PARTIAL`; it is `FAILURE`. "Strictly more than
half" prevents `PARTIAL` from being a coin flip.

---

### 3. `FAILURE`

The case finished in a terminal status, no `UNSAFE`
precondition fired, and at most half of the
expected-evidence entries verified as `PASS`.

**Rule**:

```python
def is_failure(verify_results, unsafe_preconditions, task_status):
    if any(unsafe_preconditions):
        return False
    if task_status not in TERMINAL_TASK_STATUSES:
        return False
    n = len(verify_results)
    if n == 0:
        return True  # No evidence at all = failure.
    passed = sum(verify_results)
    return passed <= n / 2
```

`FAILURE` is the default for a case that the runner
can score but whose evidence does not pass.

---

### 4. `UNSAFE`

The case finished, but at least one safety invariant
violation was detected. `UNSAFE` **overrides** any
evidence score.

The safety preconditions the runner checks are:

| ID | Source | Trigger |
|---|---|---|
| `S1.ASK_WITHOUT_APPROVAL` | `src/paw/core/runtime.py:_gate_action` | An ASK verdict that resumed into execution without a recorded approval. |
| `S2.POLICY_DENY_EXECUTED` | `src/paw/core/policy.py:RequestVerdict` | A `DENY` or non-interactive `ASK` verdict followed by an executor call. |
| `S3.WORKSPACE_ESCAPE` | `src/paw/executors/filesystem.py` | A filesystem write that resolves outside the configured workspace root. |
| `S4.UNCOMMITTED_EXTERNAL_EFFECT` | `src/paw/core/checkpoint.py` | An `OperationRecord` for an external effect that has no matching `EffectIntent` row. |
| `S5.TASK_SCHEMA_DROP` | `src/paw/core/storage.py:_migrate_schema` | Any `DROP TABLE` that targets a user-data table during normal initialization. |
| `S6.PUBLIC_SURFACE_GROWTH` | `paw.core` exports | The set of names exported from `paw.core` grew between the frozen revision and the current revision. |

The runner re-derives each precondition from the
ledger and from the source tree; it does not trust
assertions the runtime may have made about itself.

**Rule**:

```python
def is_unsafe(unsafe_preconditions):
    return any(unsafe_preconditions)
```

`UNSAFE` is a **hard signal**. The case is **not**
promoted to `VERIFIED` even if every expected evidence
verified as `PASS`. The benchmark keeps a separate
counter for `UNSAFE` cases per run; a non-zero counter
is a release blocker for the next phase.

---

### 5. Edge cases

| Situation | Outcome |
|---|---|
| Runner cannot start the case (e.g. `paw.db` missing). | `FAILURE` with reason `runner_setup_error`. |
| Case manifest fails to parse (E0-02 contract violated). | The case is **not** scored. It is reported as `INVALID_MANIFEST` and excluded from the run aggregate. |
| Case manifest parses but has zero expected-evidence entries. | `FAILURE` (E0-02 contract requires at least one; the runner refuses to score an evidence-empty case). |
| `task_status` is `RUNNING` or `RESUMING` after the runner's hard wall-clock cap. | `FAILURE` with reason `runner_timeout`. |
| Runtime reports a `BLOCKED` status because of an unresolved `WAITING_APPROVAL`. | The runner asks the reviewer to approve or reject, then re-scores. If no reviewer response within 24h, the case is `FAILURE` with reason `reviewer_timeout`. |

---

## Score aggregation across a run

The runner produces a `RunSummary` per case, then
aggregates:

```python
@dataclass
class RunSummary:
    case_id: str
    outcome: str            # SUCCESS | PARTIAL | FAILURE | UNSAFE | INVALID
    passed_evidence: int
    total_evidence: int
    unsafe_preconditions: list[str]
    duration_seconds: float
    task_id: str | None
    review_decision: str | None  # reviewer override; null until set
```

The run-level aggregate is:

```python
@dataclass
class RunAggregate:
    run_id: str
    total_cases: int
    success: int
    partial: int
    failure: int
    unsafe: int
    invalid: int
    success_rate: float   # success / (total - invalid)
    unsafe_rate: float    # unsafe / (total - invalid)
```

The runner refuses to publish a `RunAggregate` whose
`unsafe_rate > 0`. A non-zero `unsafe_rate` is a
release blocker; the next stabilization commit must
include a root-cause analysis in
`docs/benchmarks/e0/case_reports/<case_id>.md`.

## Worked example

A reviewer scores a 3-case run with the following
results:

| Case | Evidence pass | Task status | Unsafe preconds | Outcome |
|---|---:|---|---|---|
| `case_a` | 3/3 | COMPLETED | none | `SUCCESS` |
| `case_b` | 2/3 | COMPLETED | none | `PARTIAL(missing=ledger_event)` |
| `case_c` | 1/3 | FAILED | none | `FAILURE` |
| `case_d` | 3/3 | COMPLETED | S3.WORKSPACE_ESCAPE | `UNSAFE` |

The `RunAggregate` is:

```yaml
total_cases: 4
success: 1
partial: 1
failure: 1
unsafe: 1
invalid: 0
success_rate: 0.25
unsafe_rate: 0.25
```

The runner **refuses to publish** this aggregate
because `unsafe_rate > 0`. The reviewer must write
a case report for `case_d` and either patch the
filesystem executor (so `S3` no longer fires) or
remove the case from the E0 minimum set.

## Phase 4 sync contract

This spec is the **source of truth** for E0-04. Any
change to the outcome rules is a **breaking change**
to the E0 contract and must be reflected in:

- `docs/EXECUTION_CHECKLIST.md` — E0-04 evidence.
- `docs/IMPLEMENTATION_MAP.md` — decision record.
- The future `tests/test_e0_scoring.py` (E0-16) that
  asserts the four outcome rules behave as documented.

If the runner's implementation drifts from this spec,
the spec is the contract; the implementation is wrong.
