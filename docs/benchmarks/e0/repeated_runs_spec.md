# E0 Repeated-Runs Spec (E0-06)

This document is the **E0-06 deliverable**. It defines how
the E0-16 runner summarizes the result of running the
**same case** multiple times, and how non-determinism
(model temperature, network jitter, GC pauses) is reported
without being conflated with the case's intrinsic
variance.

The contract is intentionally narrow: the runner never
averages PASS/FAIL into a single number; it produces a
**per-run outcome table** plus three summary statistics
that are honest about uncertainty. A reviewer who reads
the output can answer "does this case reliably pass?" or
"is the result flaky?" without re-running the suite.

## Why not "average PASS/FAIL"

A binary outcome (`SUCCESS` / `FAILURE` / `UNSAFE`) is
not a continuous variable. Averaging it produces a
"score" that has no clear meaning — `0.7` is not
"70% correct"; it could mean "the case passes 7 of 10
times", "the case passes every time but the runner is
flaky", or "the case is broken in 3 different ways that
all happen on the same task". The E0-06 contract
forbids this collapse.

Instead, the runner reports a **per-run outcome table**
plus three summary statistics:

- `pass_rate` — fraction of runs whose outcome is
  `SUCCESS` (excluding `UNSAFE`).
- `unsafe_rate` — fraction of runs whose outcome is
  `UNSAFE`. (Re-stated from E0-04 because repeated
  runs amplify safety variance.)
- `flakiness_score` — fraction of runs whose outcome
  class differs from the modal outcome. A case that
  sometimes passes and sometimes fails is flaky
  regardless of the pass rate.

The three numbers are independent. A case can have
`pass_rate = 1.0` and `flakiness_score = 0` (always
passes) or `pass_rate = 0.5` and `flakiness_score = 0.4`
(passes half the time, fails the other half — flaky).

## Why a per-case repetition count

A single run cannot tell the reviewer whether a `PARTIAL`
is a stable 2-of-3 evidence pass or a flaky 1-or-3
swing. The contract requires:

- A **minimum of 3 runs** per case before a `pass_rate`
  is published.
- A **default of 5 runs** per case.
- A **maximum of 20 runs** per case (the cap is
  configurable via env var `PAW_BENCH_REPEAT_MAX`).

The default of 5 is chosen because it gives a
per-case `pass_rate` with a confidence interval narrow
enough to be useful (~±10% for a true rate of 50%)
while keeping the total benchmark cost under 5× the
single-run cost. A reviewer can lower the count for
expensive cases via the env var.

## The per-run output

The runner writes one row per (case, run_index) to
`benchmarks/e0/runs/<run_id>/<case_id>.runs.jsonl`:

```json
{"run_index": 1, "outcome": "SUCCESS", "passed_evidence": 3, "total_evidence": 3,
 "unsafe_preconditions": [], "duration_ms": 5012, "cost_usd": 0.005,
 "human_interventions": 0, "seed": "..."}
{"run_index": 2, "outcome": "FAILURE", "passed_evidence": 1, "total_evidence": 3,
 "unsafe_preconditions": [], "duration_ms": 4820, "cost_usd": 0.004,
 "human_interventions": 0, "seed": "..."}
...
```

The `seed` field records the random seed (or model
temperature, or a hash of the network jitter window)
the runner used for that run. Two runs with the same
`seed` must be byte-identical except for the timestamp;
this is the contract for deterministic reproduction.

## The summary statistics

The runner produces a `RepeatedRunSummary` per case:

```python
@dataclass
class RepeatedRunSummary:
    case_id: str
    runs: int
    outcomes: dict[str, int]      # {"SUCCESS": 4, "FAILURE": 1}
    pass_rate: float             # SUCCESS / (runs - UNSAFE)
    unsafe_rate: float          # UNSAFE / runs
    flakiness_score: float      # runs-with-non-modal-outcome / runs
    mean_latency_ms: float      # arithmetic mean of duration_ms
    stdev_latency_ms: float     # population stdev of duration_ms
    mean_cost_usd: float
    stdev_cost_usd: float
    mean_human_interventions: float
    seeds: list[str]            # every seed the runner used
```

`mean_*` and `stdev_*` are honest: they are arithmetic
mean and population stdev across the runs. The runner
never uses a weighted mean or a rolling average; a
reviewer who wants a different statistic re-derives it
from the `runs.jsonl` file.

### Pass-rate and unsafe-rate definitions

```python
def pass_rate(outcomes):
    n = sum(outcomes.values())
    if n == 0:
        return None
    unsafe = outcomes.get("UNSAFE", 0)
    if n - unsafe == 0:
        return None  # No safe runs to compare.
    return outcomes.get("SUCCESS", 0) / (n - unsafe)

def unsafe_rate(outcomes):
    n = sum(outcomes.values())
    if n == 0:
        return None
    return outcomes.get("UNSAFE", 0) / n
```

The `pass_rate` excludes `UNSAFE` runs because
`UNSAFE` is a release-blocker signal (E0-04), not a
"the case failed" signal. A case that always goes
`UNSAFE` has `pass_rate = None`, which the reviewer
reads as "this case has a safety defect, not a quality
defect".

### Flakiness score

```python
def flakiness_score(outcomes):
    n = sum(outcomes.values())
    if n <= 1:
        return 0.0
    # Modal outcome: the most frequent one.
    modal = max(outcomes, key=outcomes.get)
    non_modal = n - outcomes[modal]
    return non_modal / n
```

A `flakiness_score > 0` means "this case sometimes
behaves differently from its modal outcome". The
reviewer reads `0.4` as "4 of 10 runs disagree with the
majority"; whether that is acceptable depends on the
case, but the signal is honest.

The runner **flags** a case with `flakiness_score > 0.2`
as `FLAKY` in the run-level aggregate. A flaky case is
not promoted to `VERIFIED` until the reviewer writes a
`case_reports/<case_id>.md` explaining the cause.

## Non-determinism attribution

A reviewer who sees `latency_total = 12000ms` on one
run and `18000ms` on the next wants to know whether the
variance is in the runtime (slow query) or in the
network (slow API). The contract requires the runner
to record three latency decomposition per run:

```json
{"name": "latency.runtime", "value_ms": 11200, "unit": "ms"}
{"name": "latency.network", "value_ms": 700, "unit": "ms"}
{"name": "latency.human_wait", "value_ms": 100, "unit": "ms"}
```

The sum is `latency.total` from E0-05. A run with high
`latency.network` variance is different from a run
with high `latency.runtime` variance; the reviewer can
tell at a glance.

The runner never attributes variance to the **model**.
If the model is the source of variance, that is a
known model property (temperature, sampling) and the
runner reports it under `latency.runtime` together with
the `seed` field.

## Worked example

A reviewer asks the runner to repeat `case_a` 5 times:

| Run | Outcome | Passed | Latency (ms) | Cost (USD) | Human | Seed |
|---|---|---:|---:|---:|---:|---|
| 1 | SUCCESS | 3/3 | 5012 | 0.005 | 0 | s1 |
| 2 | SUCCESS | 3/3 | 4980 | 0.005 | 0 | s2 |
| 3 | FAILURE | 1/3 | 4920 | 0.004 | 0 | s3 |
| 4 | SUCCESS | 3/3 | 5050 | 0.005 | 0 | s4 |
| 5 | SUCCESS | 3/3 | 5030 | 0.005 | 0 | s5 |

The `RepeatedRunSummary` is:

```yaml
case_id: case_a
runs: 5
outcomes: {SUCCESS: 4, FAILURE: 1}
pass_rate: 0.8
unsafe_rate: 0.0
flakiness_score: 0.2   # 1 of 5 runs disagrees with the modal SUCCESS
mean_latency_ms: 4998.4
stdev_latency_ms: 47.0
mean_cost_usd: 0.0048
stdev_cost_usd: 0.0004
mean_human_interventions: 0
seeds: [s1, s2, s3, s4, s5]
```

The runner flags this case as `FLAKY` (`flakiness_score
= 0.2 > 0.2 == 0.2`? actually equal; the threshold is
strict `> 0.2`). Wait, the score is exactly 0.2, so the
case is not flagged. A reviewer can re-run with more
seeds to see if the case is reliably flaky or
seed-sensitive.

## Phase 4 sync contract

This spec is the **source of truth** for E0-06. Any
change to the summary statistics, the per-run schema,
or the flakiness flag is a **breaking change** to the
E0 contract and must be reflected in:

- `docs/EXECUTION_CHECKLIST.md` — E0-06 evidence.
- `docs/IMPLEMENTATION_MAP.md` — decision record.
- The future `tests/test_e0_repeated_runs.py` (E0-16)
  that asserts the per-run schema and the summary
  functions behave as documented.

If the runner's implementation drifts from this spec,
the spec is the contract; the implementation is wrong.
