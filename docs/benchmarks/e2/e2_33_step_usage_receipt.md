# E2-33: Exact Cost/Usage Receipt per Step

## Contract

Every executed step produces an exact cost/usage receipt. The receipt is
logged to the ``TaskLedger`` as part of the ``STEP_EXECUTED`` event and is
computable from the final ``ExecutionObservation`` without re-running the
step.

```python
class ResourceUsage(BaseModel):
    model_calls: int = 0
    tool_calls: int = 0
    tokens: int = 0
    wall_time_ms: int = 0
    network_bytes: int = 0
    destructive_ops: int = 0

    def provider_calls(self) -> int:
        return self.model_calls

    def total_tokens(self) -> int:
        return self.tokens

    def to_receipt(self) -> dict[str, Any]:
        return {
            "provider_calls": self.provider_calls(),
            "total_tokens": self.total_tokens(),
            "total_cost_usd": self.total_cost(),
            "wall_time_ms": self.wall_time_ms,
            "tool_calls": self.tool_calls,
            "network_bytes": self.network_bytes,
            "destructive_ops": self.destructive_ops,
        }
```

## Boundary rule

* The receipt is derived from the *final* ``ExecutionObservation``, not from
  intermediate estimates.
* ``provider_calls`` is synonymous with ``model_calls`` for receipt purposes.
* ``total_tokens`` is the cumulative token count for the step.

## Verification

* D2: invariant (method exists) + runtime wiring + adversarial receipt
  tampering + measurable export.
