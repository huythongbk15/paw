# E2-43: Expose Depth, Evidence, Options, Readiness, Budget and Staleness in Inspect Output

## Contract

`PawRuntime` exposes a read-only `inspect_state()` method that returns a
diagnostic snapshot of the current runtime decision state. The snapshot
includes depth, evidence, options, readiness, budget, and staleness.

## Inspect output schema

```python
{
    "depth": "FAST" | "STANDARD" | "DEEP",
    "evidence": {
        "novelty": float,
        "impact": float,
        "privacy": str,
        "context_sufficiency": float,
        "budget": str,
    },
    "options": {
        "preferred_model": str | None,
        "fallback_chain": list[str],
        "selected_role": str,
    },
    "readiness": {
        "level": str,  # ImplementationReadiness value
        "revision": str,
        "constraints": str,
        "is_stale": bool,
    },
    "budget": {
        "model_calls": int,
        "tool_calls": int,
        "total_tokens": int,
        "wall_time_seconds": float,
    },
    "staleness": {
        "revision_mismatch": bool,
        "constraint_mismatch": bool,
    },
}
```

## Behavior

* `inspect_state()` is read-only; it does not modify runtime state.
* Missing fields return `None` or empty collections.
* The output is deterministic for the same runtime state.

## Verification

* D2: invariant + runtime wiring + adversarial (missing fields, default values) + measurable export.

