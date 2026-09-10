# E2-38: Make NEEDS_RESEARCH Schedule Only Bounded Research Operations

## Contract

When `ImplementationReadiness` is `NEEDS_RESEARCH`, the runtime may execute
only proposals explicitly marked as research operations. All other mutating
proposals are blocked.

## Research proposal flag

`ProposedAction` gains `is_research: bool = False`. A proposal is a research
operation only when `is_research=True`.

## Gate behavior

```python
if proposed.is_mutating:
    if self.readiness == "NEEDS_RESEARCH" and not proposed.is_research:
        # Block: non-research mutating proposals are not allowed
        return ExecutionObservation(..., error="readiness_not_ready:NEEDS_RESEARCH")
    elif self.readiness == "NEEDS_RESEARCH" and proposed.is_research:
        # Allow: research proposals pass through to the research budget check
        pass
```

## Bounded research

Research proposals are still subject to the research budget check (E2-30).
Unbounded research (no budget) is a separate concern handled by the budget
check returning an immediate stop.

## Backward compatibility

* Default `is_research=False` preserves fail-closed behavior.
* Default `readiness="READY"` allows all proposals (no change to pre-E2-36 path).

## Verification

* D2: invariant + runtime wiring + adversarial (research bypass, non-research block) + measurable export.

