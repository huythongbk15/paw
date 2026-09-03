# E0 Verification Layers Spec (E0-38)

This document is the **E0-38 deliverable**. It defines
the three distinct verification layers the benchmark
must keep separate, the artifact each layer produces,
and the rule that a layer is **never** allowed to read
the output of the layer above it.

## Why three layers

A benchmark that conflates "the executor returned
success" with "the engineering goal is correct" is
self-confirming. The E0 contract keeps the three
layers separate so a reviewer can tell, at any time,
which layer produced a given PASS/FAIL.

## Layer 1 — Operation observation

**Artifact**: `ExecutionObservation` (per executor
invocation).

**Question answered**: "Did one executor invocation
return successfully and what did it change?"

**Source**: `src/paw/core/models.py:ExecutionObservation`.

**Content**:

- `success` (bool)
- `result` (the executor's return value, normalized to
  a dict by the adapter)
- `error` (None on success; a typed error on failure)
- `resources_used` (tokens, latency, cost, human actions)

**Rules**:

- The observation is written by the executor adapter
  (e.g. `LocalFilesystemExecutor`), not by the runner.
- The observation is the only artifact that records
  "the executor returned success". The benchmark does
  **not** consult the observation to score the case;
  it consults the verification layer below.

## Layer 2 — Engineering verification

**Artifact**: `VerificationRecord` (per
`VerificationSpec` per case).

**Question answered**: "Did the predeclared acceptance
checks for the engineering goal pass?"

**Source**: a future
`paw.bench.VerificationSpec` / `paw.bench.VerificationRecord`
dataclass (added in a later E0 item; the present
contract reserves the names).

**Content**:

- `spec_id` / `spec_version` (the acceptance check's
  identity)
- `task_id` / `project_revision` (the artifact the
  check applies to)
- `check_kind` (file_contains, command_exit, ...)
- `expected_outcome` (what the spec required)
- `observed_outcome` (what the check actually saw)
- `result` (`PASS`, `FAIL`, `ERROR`, `SKIPPED`)
- `observed_output` / `artifacts` (the literal text the
  check produced; reviewer-readable)
- `verifier_identity` (who ran the check; the future
  runtime-driven runner's identity)
- `timestamps` (started_at, finished_at, duration_ms)
- `provenance` (the spec's path in the source tree)

**Rules**:

- A `VerificationRecord` is **not** the same as an
  `ExecutionObservation`. The observation records what
  the executor did; the verification record records
  whether the engineering goal was achieved.
- A `VerificationRecord` may consult the observation
  for context (e.g. "the executor produced this file,
  the spec says this file should contain this string"),
  but it never uses the observation's `success` field
  to determine its own `result`. The spec is the
  source of truth.
- A `VerificationRecord` with `result=SKIPPED` is
  **never** silently successful. A skipped check is
  reported as skipped, not as PASS.

## Layer 3 — Benchmark evaluation

**Artifact**: `RunSummary` / `RunAggregate` (per
case, per run, per pack).

**Question answered**: "Is the case a SUCCESS,
PARTIAL, FAILURE, or UNSAFE? Is the pack runnable?"

**Source**: `paw.bench.run_case` and
`paw.bench.runner.write_runs_jsonl` (the existing
E0-16 implementation).

**Content**:

- `case_id`, `outcome`, `passed_evidence`,
  `total_evidence`, `unsafe_preconditions`,
  `duration_ms`, `seed`
- Aggregate: `total_cases`, `success`, `partial`,
  `failure`, `unsafe`, `invalid`, `success_rate`,
  `unsafe_rate`

**Rules**:

- The benchmark evaluation reads from the
  `VerificationRecord`s (not the `ExecutionObservation`s
  directly). If a verification is missing or skipped,
  the case cannot be `SUCCESS`.
- The benchmark evaluation never reaches back into the
  observation to override a `FAIL`. The verification
  record is the source of truth.
- The benchmark evaluation applies the E0-04 outcome
  rules (SUCCESS / PARTIAL / FAILURE / UNSAFE) on top
  of the verification results.
- The benchmark evaluation applies the E0-06
  repeated-runs statistics (pass_rate, flakiness_score)
  on top of the per-run outcomes.
- The benchmark evaluation applies the E0-36 research
  budget check on top of the per-run resource usage.
- The benchmark evaluation applies the E0-35 unsafe
  attempt check on top of the per-run ledger and
  evidence.

## The arrow is one-way

```
Executor → ExecutionObservation
       → VerificationRecord
       → RunSummary / RunAggregate
```

The arrow points **down**. A layer may read the layer
above it for context, but it must not consult the
layer's PASS/FAIL to compute its own. A
`VerificationRecord` never inherits the observation's
`success`; a `RunSummary` never inherits the
verification's `PASS` without consulting the spec.

## Why a one-way arrow

The one-way arrow is what stops a benchmark from
self-confirming. The observation says "the executor
succeeded"; the verification says "the engineering
goal is met"; the benchmark says "the case is a
SUCCESS / PARTIAL / FAILURE / UNSAFE". Three
different questions, three different artifacts, three
different layers. The reviewer's eye can tell which
layer produced a given verdict because the verdict is
anchored to its layer's artifact, not to the layer
above.

## Phase 4 sync contract

This document is the **source of truth** for E0-38. A
future runner implementation must read it to wire the
three layers correctly. A change to the layer names,
the arrow direction, or the "consulted for context"
rule is a **breaking change** to the E0 contract.
