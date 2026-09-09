# E2-32: Per-Role Token/Cost Ceiling and Overflow Rejection

## Contract

Every model role has a typed ceiling for tokens and estimated cost. The
runtime must reject any inference attempt that would exceed the ceiling
*before* the provider call occurs.

| Role | Token ceiling | Cost ceiling | Unit |
|------|---------------|--------------|------|
| `FAST` | 2 048 | 0.01 | tokens / USD |
| `BALANCED` | 8 192 | 0.05 | tokens / USD |
| `DEEP` | 32 768 | 0.20 | tokens / USD |
| `LOCAL` | 16 384 | 0.00 | tokens / USD |

## Typed ceiling record

```python
@dataclass(frozen=True)
class RoleCeiling:
    role: ModelRole
    max_tokens: int
    max_cost_usd: float
```

## Fail-closed rule

* Unknown roles map to `LOCAL` ceilings.
* Overflow on either dimension rejects the inference with a typed stop
  reason (`TOKEN_LIMIT` / `COST_LIMIT`).
* Ceilings are checked from the `ProposedAction.estimated_cost` and the
  runtime's current token count before routing.

## Verification

* D2: invariant (stable ceilings) + runtime wiring + adversarial overflow +
  measurable export.
