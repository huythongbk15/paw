# E0 Measurement Spec (E0-05)

This document is the **E0-05 deliverable**. It defines
how the E0-16 runner records and reports four
quantitative measurements per case:

- **Tokens** — model input + output tokens consumed.
- **Latency** — wall-clock time from case start to
  terminal status.
- **Cost** — USD-equivalent spend attributable to the
  case.
- **Human intervention** — the number of distinct
  reviewer actions required during the case (approvals,
  clarifications, overrides).

The contract is intentionally narrow: every measurement
is anchored to a single source of truth (a SQLite column,
a ledger event, or a CLI field) so a reviewer can re-derive
the number from the same artifact. No measurement is
estimated, averaged without bounds, or computed by the
model itself.

## Why four measurements

A benchmark that reports only PASS/FAIL collapses the
information an engineering manager needs to choose
between two correct runtimes. The four measurements are
the smallest set that supports a "faster / cheaper /
less human" comparison without leaking internal cost
details or non-deterministic averages.

## The four measurements

Each subsection names the measurement, the source of
truth, the unit, the bounds the runner must enforce, and
the JSONL row the runner writes to
`benchmarks/e0/runs/<run_id>/<case_id>.measurements.jsonl`.

---

### 1. Tokens

The artifact is the sum of model input tokens and model
output tokens consumed during the case. The runner reads
from `task_events` where the runtime committed the
`STEP_EXECUTED` payload; the payload carries
`resources_used.model_tokens` from
`src/paw/core/models.py:ResourceUsage`.

| Field | Value |
|---|---|
| Unit | integer tokens |
| Source | `task_events.payload` for events with `event_type = STEP_EXECUTED` |
| Aggregation | sum across all `STEP_EXECUTED` events for the case's `task_id` |
| Bounds | The runner refuses to publish if a single `STEP_EXECUTED` payload reports a non-integer or negative `model_tokens`. |

**JSONL row** (one line per case):

```json
{"name": "tokens.input", "value": 1234, "unit": "tokens"}
{"name": "tokens.output", "value": 567, "unit": "tokens"}
{"name": "tokens.total", "value": 1801, "unit": "tokens"}
```

The runner reports input and output separately so a
reviewer can tell whether a high total is dominated by
context (input) or generation (output).

---

### 2. Latency

The artifact is the wall-clock interval between the case
start and the case terminal status. The runner reads
the first `task_event` (case start) and the
`TASK_COMPLETED` event (case end) for the case's
`task_id`.

| Field | Value |
|---|---|
| Unit | milliseconds |
| Source | `task_events.created_at` of the first and last events |
| Aggregation | `last.created_at - first.created_at` in milliseconds |
| Bounds | The runner refuses to publish a negative latency; a zero latency is reported as `0` with reason `same_tick`. |

**JSONL row**:

```json
{"name": "latency.total", "value": 12450, "unit": "ms"}
{"name": "latency.runtime_only", "value": 11200, "unit": "ms",
 "note": "excludes human review wait time"}
```

`latency.total` includes human review wait time;
`latency.runtime_only` subtracts intervals where the
task was `WAITING_APPROVAL` so reviewers can see how much
of the wall-clock was waiting for a human.

---

### 3. Cost

The artifact is the USD-equivalent spend the runtime
incurred for the case. The runner reads the
`cost_usd` field of the `STEP_EXECUTED` payload (added
in Phase 19 / `src/paw/core/models.py:ResourceUsage`).
The runtime computes the per-call cost from the model's
published price list; the runner never recomputes the
price.

| Field | Value |
|---|---|
| Unit | USD, 6 decimal places |
| Source | `task_events.payload.cost_usd` for `event_type = STEP_EXECUTED` |
| Aggregation | sum across all `STEP_EXECUTED` events for the case's `task_id` |
| Bounds | The runner refuses to publish if a `cost_usd` is non-numeric, negative, or larger than `cost_max_usd_per_case` (default `10.0`). A case that exceeds the cap is recorded as `FAILURE(cost_cap_exceeded)` and the runner stops the case immediately. |

**JSONL row**:

```json
{"name": "cost.total_usd", "value": 0.012345, "unit": "USD"}
```

A reviewer can re-derive this from the ledger plus the
price list; the runner does not ship a price list of its
own.

---

### 4. Human intervention

The artifact is the number of distinct reviewer actions
the case required. The runner counts events from three
sources:

- `POLICY_GATE_EVALUATED` with verdict `ask` that
  resumed into execution (i.e. an approval was used).
- `approval` lifecycle events emitted by
  `src/paw/core/approval.py` (one per approval request
  plus one per approval grant).
- `CHAT_REPLY` events with `interactive = true` (a
  reviewer typed a clarification that the runtime
  consumed).

| Field | Value |
|---|---|
| Unit | integer actions |
| Source | ledger event count, deduplicated by `approval_id` / `interaction_id` |
| Aggregation | distinct actions across the case's `task_id` |
| Bounds | The runner refuses to publish a `human_intervention` whose total exceeds `human_max_interventions_per_case` (default `3`). A case that exceeds the cap is recorded as `PARTIAL(human_cap_exceeded)`. |

**JSONL row**:

```json
{"name": "human.approvals", "value": 1, "unit": "actions"}
{"name": "human.clarifications", "value": 0, "unit": "actions"}
{"name": "human.overrides", "value": 0, "unit": "actions"}
{"name": "human.total", "value": 1, "unit": "actions"}
```

The breakdown lets a reviewer see whether the human
load was approvals (governance friction) or
clarifications (intent ambiguity).

---

## Aggregation across a run

The runner appends the per-case measurements to
`<case_id>.measurements.jsonl`, then a `RunSummary`
carries the four totals:

```yaml
run_id: <run_id>
cases: 4
tokens_total: 7821
tokens_per_case_avg: 1955.25
latency_total_ms: 48930
cost_total_usd: 0.045678
human_interventions_total: 5
```

A reviewer who only reads `RunSummary` can still answer
"did this run cost more than the last?" without
diving into per-case files.

## Bounds and caps

| Cap | Default | Configured via |
|---|---|---|
| `cost_max_usd_per_case` | `10.0` | env var `PAW_BENCH_COST_MAX_USD_PER_CASE` |
| `human_max_interventions_per_case` | `3` | env var `PAW_BENCH_HUMAN_MAX_ACTIONS` |
| `latency_max_ms_per_case` | `600000` (10 min) | env var `PAW_BENCH_LATENCY_MAX_MS` |

A case that hits any cap is recorded with the cap name
in the `failure_reason` field; the runner stops the
case immediately and refuses to publish the run if the
cap was hit more than once across the run.

## Worked example

A reviewer scores a 3-case run with the following
per-case measurements:

| Case | Tokens (in/out) | Latency (ms) | Cost (USD) | Human |
|---|---|---:|---:|---:|
| `case_a` | 1000 / 200 | 5000 | 0.005 | 0 |
| `case_b` | 1500 / 300 | 12000 | 0.012 | 1 |
| `case_c` | 800 / 100 | 3000 | 0.003 | 0 |

The `RunSummary` is:

```yaml
run_id: 2026-09-03T10-00-00Z
cases: 3
tokens_total: 3900
tokens_per_case_avg: 1300
latency_total_ms: 20000
cost_total_usd: 0.020
human_interventions_total: 1
```

A reviewer comparing this to the last run answers
"the new runtime spent `0.020 USD` for `3` cases
versus `0.025 USD` for the same cases last week —
**20% cheaper**, **same human load**".

## Phase 4 sync contract

This spec is the **source of truth** for E0-05. Any
change to a measurement's source, unit, or bound is a
**breaking change** to the E0 contract and must be
reflected in:

- `docs/EXECUTION_CHECKLIST.md` — E0-05 evidence.
- `docs/IMPLEMENTATION_MAP.md` — decision record.
- The future `tests/test_e0_measurements.py` (E0-16) that
  asserts each measurement reads from the documented
  source.

If the runner's implementation drifts from this spec,
the spec is the contract; the implementation is wrong.
