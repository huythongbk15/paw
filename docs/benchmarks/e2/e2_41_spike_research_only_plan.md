# E2-41: Make SPIKE_REQUIRED Create Only an Explicitly Research-Only Plan

## Contract

When `ImplementationReadiness` is `SPIKE_REQUIRED`, the runtime may accept
only proposals explicitly marked as research-only. No implementation plan is
created or executed.

## Research-only flag

`ProposedAction` gains `plan_purpose: str = "implementation"`. Valid values
are `"research"`, `"spike"`, and `"implementation"`. When readiness is
`SPIKE_REQUIRED`, only `"research"` and `"spike"` are allowed.

## Gate behavior

```python
if proposed.is_mutating:
    if self.readiness == "SPIKE_REQUIRED" and proposed.plan_purpose not in ("research", "spike"):
        return ExecutionObservation(..., error="readiness_not_ready:SPIKE_REQUIRED")
```

## Bounded spike

Research/spike proposals are still subject to the research budget check (E2-30).
Unbounded research is a separate concern handled by the budget check.

## Backward compatibility

* Default `plan_purpose="implementation"` preserves fail-closed behavior.
* Default `readiness="READY"` bypasses the gate.

## Verification

* D2: invariant + runtime wiring + adversarial (implementation blocked, research allowed) + measurable export.

