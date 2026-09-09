# E2-34: Persistent Counter and Monotonicity Check for Model Calls

## Contract

The model-call count per task must be derivable from the append-only
``TaskLedger`` and must be monotonically non-decreasing across
``STEP_EXECUTED`` events. Any observed decrease is a hard invariant
violation.

## Derivation rule

```python
@staticmethod
async def get_model_call_count(task_id: ID) -> int:
    events = await TaskLedger.get_events_by_type(task_id, TaskEventType.STEP_EXECUTED)
    return sum(
        (e.payload or {}).get("resources_used", {}).get("provider_calls", 0)
        for e in events
    )
```

## Monotonicity check

```python
@staticmethod
async def assert_model_calls_monotonic(task_id: ID) -> None:
    events = await TaskLedger.get_events_by_type(task_id, TaskEventType.STEP_EXECUTED)
    cumulative = 0
    for event in events:
        provider_calls = (event.payload or {}).get("resources_used", {}).get("provider_calls", 0)
        cumulative += provider_calls
        recorded = (event.payload or {}).get("model_call_count")
        if recorded is not None and recorded < cumulative:
            raise RuntimeError(f"model_call_count decreased for {task_id}")
```

## Boundary rule

* The check is derived from ``STEP_EXECUTED`` events only; other event types
  are ignored.
* Missing or non-integer ``provider_calls`` values are treated as ``0``.
* A task with no ``STEP_EXECUTED`` events has a count of ``0``.

## Verification

* D2: invariant (helper exists) + runtime wiring + adversarial tampering +
  measurable export.
