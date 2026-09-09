# E2-18: Select verifier policy independently from executor capability selection

## Contract

The verifier model (used to check the executor's output) is selected independently
from the executor model, using a **verifier policy** defined on
`ExecutionProfile.verifier_policy`:

| Policy | Behavior |
|--------|----------|
| `"none"` (default) | No verification step; return executor's selection unchanged |
| `"same"` | Reuse the executor's selected model |
| `"cheapest"` | Select the cheapest available local model supporting the executor's role |

### API

```python
profile = ExecutionProfile(verifier_policy="cheapest")
verifier = await router.select_verifier(selection, profile)
```

The verifier selection uses `_score_local_models` with `prefer_cheap=True`,
independent of the executor's `preferred_provider`, `task_signals`, or
reconnaissance state.

## Relationship to E2-17

E2-18 uses `ModelSelection.failure_kind` to surface verifier selection failures
(`"capability_mismatch"` if no local model is available).

## Verification

51 E2 + Phase 15/21 tests pass; ruff clean.
