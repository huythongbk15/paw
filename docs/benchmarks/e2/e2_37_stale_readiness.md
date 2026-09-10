# E2-37: Invalidate READY When the Relevant Project Revision or Hard Constraint Changes

## Contract

A `READY` readiness artifact is valid only for the project revision and
constraint fingerprint it was evaluated against. `PawRuntime` detects staleness
and blocks mutating proposals when either changes.

## Detection rule

1. `PawRuntime.__init__` accepts `readiness_revision: str = ""` and
   `readiness_constraints: str = ""`.
2. If `readiness == "READY"` and either:
   * `readiness_revision` is non-empty and differs from the current project
     revision, OR
   * `readiness_constraints` is non-empty and differs from the current
     constraint fingerprint,
   then the readiness is stale and the gate returns
   `ExecutionObservation(success=False, error="readiness_stale")`.
3. The check is applied before any local research, model inference, or step
   function call.

## Backward compatibility

* Empty `readiness_revision` or `readiness_constraints` means "no staleness
  check" (pre-E2-37 behavior).
* Default `readiness="READY"` with empty revision/constraints allows execution.

## Verification

* D2: invariant + runtime wiring + adversarial (revision mismatch, constraint
  mismatch) + measurable export.

