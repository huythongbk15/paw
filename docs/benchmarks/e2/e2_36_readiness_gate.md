# E2-36: Block Every Mutating Proposal If Readiness Is Missing, Stale, or Not READY

## Contract

No mutating proposal may execute unless the current `ImplementationReadiness`
artifact is present, fresh, and explicitly `READY`. The check is a single
authority gate in `PawRuntime` before any step function or provider call.

## Readiness levels

| Level | Meaning | Mutating proposal allowed |
|-------|---------|---------------------------|
| `NEEDS_RESEARCH` | Local evidence insufficient | No |
| `NEEDS_CLARIFICATION` | Goal ambiguous | No |
| `SPIKE_REQUIRED` | Bounded exploration needed | No |
| `READY` | Preconditions met | Yes |
| `REJECTED` | Task should not proceed | No |

## Staleness rule

A readiness artifact is stale when:
- Its `revision` does not match the current project revision, OR
- Its `created_at` is older than a configurable freshness window, OR
- Any hard constraint it was evaluated against has changed.

## Runtime gate

```python
if proposed.is_mutating and not _is_ready(self.readiness):
    return ExecutionObservation(
        step_id=proposed.operation_id,
        action_id=proposed.operation_id,
        success=False,
        error=f"readiness_not_ready:{self.readiness.level}",
        resources_used=ResourceUsage(),
    )
```

## Boundary rule

* The gate applies only to mutating proposals; read-only proposals may proceed.
* The check is fail-closed: missing readiness → block.
* The gate is single authority: no other component may override it.

## Verification

* D2: invariant (gate exists) + runtime wiring + adversarial stale/missing + measurable export.
