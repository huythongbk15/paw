# E0 Research Budget Spec (E0-36)

This document is the **E0-36 deliverable**. It defines the
research budget (time / token / evidence) and the
over-research scoring rule for the research-decision
benchmark.

## Why a budget

A `NEEDS_RESEARCH` case is one where authoritative
evidence is missing. The runner must schedule bounded
research operations and refuse to enter implementation
until the evidence is collected. A budget is required
because **research is unbounded by nature** — without
a budget, a research case can absorb the entire run
budget and starve the other cases.

The budget is per-case, not per-run. A case that exceeds
its budget is recorded as `OVER_BUDGET`; a case that
finishes under budget is recorded as `WITHIN_BUDGET`.
Both are valid outcomes for a `NEEDS_RESEARCH` case.

## Three budget fields

Every case manifest may declare a `research_budget`
block. The block is optional; if absent, the runner
applies the defaults below.

| Field | Default | Env override | Unit |
|---|---|---|---|
| `time_seconds` | `300` (5 min) | `PAW_BENCH_RESEARCH_TIME_SECONDS` | wall-clock seconds |
| `tokens` | `50000` | `PAW_BENCH_RESEARCH_TOKENS` | model tokens (input + output) |
| `evidence_count` | `10` | `PAW_BENCH_RESEARCH_EVIDENCE_COUNT` | distinct evidence items |

The defaults are the documented budget for a single
`NEEDS_RESEARCH` case; the E0-27 integration pack run
configured the same defaults and produced `unsafe_rate=0`.

## Worked example

```yaml
schema_version: "1.0.0"
case_id: decision_needs_research_security
research_budget:
  time_seconds: 600
  tokens: 100000
  evidence_count: 20
decision:
  readiness: NEEDS_RESEARCH
  rationale: |
    The CVE database has not been queried, the
    license has not been reviewed, and the
    dependency-size budget has not been checked.
  confidence: 0.0
```

## Over-research scoring

A case is `OVER_BUDGET` if **any one** of the three
budget fields is exceeded:

```python
def is_over_budget(case_result, budget):
    return (
        case_result.time_seconds > budget.time_seconds
        or case_result.tokens > budget.tokens
        or case_result.evidence_count > budget.evidence_count
    )
```

`OVER_BUDGET` is **not** a failure outcome by itself;
it is a per-case metric. The aggregate `RunAggregate`
carries a separate `over_budget_count` field so a
reviewer can see how many cases ran over budget.

A reviewer who wants to relax the budget updates the
case's `research_budget` block (not the env override);
a reviewer who wants to tighten the default updates
`docs/benchmarks/e0/expected_evidence_spec.md` (the
canonical source for the defaults).

## Why three fields, not one

A single field (e.g. "10 minutes") is not enough because
research can be slow in two unrelated ways: it can
spend wall-clock time talking to a slow source, or it
can spend tokens making many small calls. A time-only
budget starves token-heavy research; a token-only budget
starves slow-network research. The three-field budget
matches the three sources of cost the runner observes
(time, tokens, evidence count) and lets a reviewer set
each independently.

## Phase 4 sync contract

This document is the **source of truth** for E0-36. A
future runtime-driven runner reads it to implement the
budget enforcement; a change to the field names,
default values, or `OVER_BUDGET` rule is a **breaking
change** to the E0 contract and must be reflected here,
in the case files that declare a `research_budget`
block, and in the E0-27 integration pack run record.
