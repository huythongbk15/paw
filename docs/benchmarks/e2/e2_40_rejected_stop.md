# E2-40: Make REJECTED Stop with Recorded Reasons and No Implementation Plan

## Contract

When `ImplementationReadiness` is `REJECTED`, the runtime must stop all
mutating proposals, record the rejection reasons, and return a non-success
observation. No implementation plan is created or executed.

## Rejection reasons

`ProposedAction` gains `rejection_reasons: list[str] = Field(default_factory=list)`.
When readiness is `REJECTED`, the runtime logs the reasons to the ledger and
includes them in the returned observation.

## Gate behavior

```python
if proposed.is_mutating:
    if self.readiness == "REJECTED":
        reasons = proposed.rejection_reasons or ["no_reasons_provided"]
        await log_autonomy_gate_evaluated(
            task_id, proposed.operation_id,
            "REJECTED", ";".join(reasons),
        )
        return ExecutionObservation(
            step_id=proposed.operation_id,
            action_id=proposed.operation_id,
            success=False,
            error=f"rejected:{';'.join(reasons)}",
            resources_used=ResourceUsage(),
        )
```

## No implementation plan

The gate returns before any proposer, planner, or model call, ensuring no
implementation plan is generated for a rejected task.

## Backward compatibility

* Empty `rejection_reasons` yields `rejected:no_reasons_provided`.
* Default `readiness="READY"` bypasses the gate.

## Verification

* D2: invariant + runtime wiring + adversarial (empty reasons, non-mutating bypass) + measurable export.

