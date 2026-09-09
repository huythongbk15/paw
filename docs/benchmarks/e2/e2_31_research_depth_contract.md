# E2-31: Typed Research Depth Enum with Escalate/Ask/Stop Mapping

## Contract

Research depth is a typed classification of how much local reasoning the
canonical loop should apply before any model inference call. Each depth has
an explicit, fail-closed action mapping.

| Depth | Meaning | Default action | Fail-closed fallback |
|-------|---------|----------------|----------------------|
| `FAST` | Routine, low-impact, sufficient context, no uncertainty | `continue` | `stop` |
| `STANDARD` | Moderate novelty/impact or partial context | `ask` | `stop` |
| `DEEP` | High novelty/impact, insufficient context, high uncertainty | `continue` | `stop` |

## Typed mapping

```python
RESEARCH_DEPTH_ACTIONS: Mapping[DecisionLevel, str] = MappingProxyType({
    DecisionLevel.FAST: "continue",
    DecisionLevel.STANDARD: "ask",
    DecisionLevel.DEEP: "continue",
})
```

## Boundary rule

* Unknown or future `DecisionLevel` values map to `"stop"` (fail-closed).
* The action string is consumed by the autonomy/runtime layer; it is not
  itself an autonomy decision.
* `classify_research_depth` (E2-29) remains the single source of truth for
  the depth classification; E2-31 only adds the explicit action mapping.

## Verification

* D2: enum stability + mapping correctness + adversarial unknown depth +
  measurable export.
