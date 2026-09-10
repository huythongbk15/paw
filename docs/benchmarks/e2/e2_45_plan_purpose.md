# E2-45: Extend Canonical Plan with RESEARCH, SPIKE, IMPLEMENTATION Purpose and Effect Constraints

## Contract

`Plan` gains a `purpose` field (closed enum) and `effect_constraints` (list of
allowed effect types). These fields are persisted alongside the plan.

## PlanPurpose enum

```python
class PlanPurpose(StrEnum):
    RESEARCH = "research"
    SPIKE = "spike"
    IMPLEMENTATION = "implementation"
```

## Effect constraints

`effect_constraints: list[str]` enumerates the effect types this plan may
produce. Examples: `"read"`, `"write"`, `"delete"`, `"network"`, `"model_inference"`.
An empty list means no constraints (fail-open for backward compatibility).

## Schema migration

Additive: `ALTER TABLE plans ADD COLUMN purpose TEXT DEFAULT 'implementation'`
and `ADD COLUMN effect_constraints TEXT DEFAULT '[]'`.

## Verification

* D2: invariant + runtime wiring + adversarial (invalid purpose rejected, empty constraints) + measurable export.

