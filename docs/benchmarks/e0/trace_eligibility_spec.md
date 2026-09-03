# E0 Trace Eligibility Spec (E0-41)

This document is the **E0-41 deliverable**. It defines
when a trace (the per-case record produced by the
deterministic or runtime-driven runner) is **eligible**
to be promoted to a downstream consumer (skill
promotion, dataset ingestion, model adaptation), and
how negative / partial traces are handled.

## Positive eligibility (E0-41)

A trace is **eligible** when **every** of the following
holds:

1. The case's `task_id` matches the trace's `task_id`.
2. The case's `project_revision` matches the trace's
   `project_revision` (no stale fixtures).
3. Every required `VerificationRecord` in the trace is
   `PASS` (no `FAIL`, `ERROR`, or `SKIPPED`).
4. The trace's `unsafe_preconditions` list is empty.
5. The case's `decision.readiness` is `READY` (or
   absent, for the engineering-outcome cases that do
   not declare a decision).
6. A human reviewer signed the trace (the
   `verifier_identity` field on at least one
   `VerificationRecord` is a non-empty email-style
   string).
7. The trace's `started_at` is within the last 90 days
   (stale traces are not eligible; a reviewer can
   re-verify by re-running the case).

If **any** of the seven checks fails, the trace is
**not eligible**, and the runner records the
ineligibility reason in the per-trace `RunSummary`
under the `ineligibility_reasons` field.

## Negative / partial handling

A trace that is not eligible falls into one of three
buckets:

- **`FAILURE`**: the trace has at least one failing
  `VerificationRecord`. The runner keeps the trace for
  the diagnostic value; downstream consumers must
  filter it out.
- **`PARTIAL`**: the trace has at least one passing and
  at least one failing `VerificationRecord`. The
  runner keeps the trace but tags it `partial=true` so
  downstream consumers can decide what to do.
- **`UNSAFE`**: the trace has at least one
  `unsafe_preconditions` entry. The runner refuses to
  export the trace; the case is recorded as
  `UNSAFE` and the `RunAggregate` reports
  `unsafe_rate > 0`, which is a release-blocker.

The E0-04 outcome rules apply; this document does not
change them. The new piece is the `ineligibility_reasons`
field on the per-trace `RunSummary` (added by the
future runtime-driven runner; the deterministic runner
does not yet emit it).

## Worked example

A reviewer who has re-run `E0-08` today and finds:

- `task_id` matches
- `project_revision` matches (`f3ad4ef`)
- 3/3 `VerificationRecord`s are `PASS`
- `unsafe_preconditions` is empty
- `decision` field is absent (the case is an
  engineering-outcome case, not a research-decision
  case)
- `verifier_identity` is `alice@example.com` on every
  record
- `started_at` is today

marks the trace `eligible`. A reviewer who finds any
of:

- `verifier_identity` is `paw.bench.deterministic_runner`
  (the deterministic runner wrote it; no human signed
  off) → **not eligible**, reason
  `no_human_reviewer`.
- `unsafe_preconditions` is non-empty (the case
  triggered an unsafe-attempt condition) → **not
  eligible**, reason `unsafe_preconditions_present`.
- `started_at` is more than 90 days old → **not
  eligible**, reason `trace_too_old`.

marks the trace `not eligible` with a clear reason.
Downstream consumers (skill promotion, dataset
ingestion) MUST filter ineligible traces; the runner
exposes `ineligibility_reasons` so the filter is
auditable.

## Phase 4 sync contract

This document is the **source of truth** for E0-41. A
future runner implementation reads it to compute
`ineligibility_reasons`; a change to the seven checks
or the three buckets is a **breaking change** to the E0
contract and must be reflected here, in the future
`RunSummary` dataclass, and in the E0-27 integration
pack run record.
