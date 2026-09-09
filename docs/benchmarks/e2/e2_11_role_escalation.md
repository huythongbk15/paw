# E2-11: Escalate role on missing evidence, low confidence, novelty or high impact

## Contract

The `ModelRouter` must **escalate the role** (fast/tools → reasoning) on the
**initial** routing decision when `task_signals` (E2-04) indicate conditions
that warrant a stronger model. This complements E2-10 (trajectory-aware
re-evaluation) which escalates after reconnaissance has been gathered.

### Escalation triggers (OOD upscaling conditions)

| OODCondition | When | Effect |
|---|---|---|
| `NOVEL_TASK` | `signals.novelty == NOVEL` | escalate fast→reasoning |
| `HIGH_IMPACT` | `signals.impact == HIGH` | escalate fast→reasoning |
| `LOW_CONFIDENCE` | `uncertainty_score < 0.5` | escalate fast→reasoning |
| `MISSING_EVIDENCE` | `context_sufficiency == INSUFFICIENT` | escalate fast→reasoning |

### Boundary rules

1. Escalation only fires when `task_signals is not None` — explicit opt-in.
2. Escalation only applies to `fast` and `tools` roles → upgrade to `reasoning`.
3. `reasoning` role is NOT escalated further (already the strongest tier).
4. `UNKNOWN` signals (the deliberate default) do NOT trigger escalation —
   fail-closed (no accidental escalation from un-reconnoitred tasks).
5. The escalation is logged as `model_routed_ood_escalation` with the
   task_id, prev_role, new_role, and triggering conditions.

### API

Both `route()` and `route_with_explain()` accept `task_signals` and apply
the escalation before model scoring:

```python
selection = await router.route(
    task_id="t1", goal="...", role="fast",
    task_signals=TaskSignals(novelty=NoveltyLevel.NOVEL, ...),
)
# role escalated to "reasoning" before scoring
```

### Relationship to E2-05/E2-06

- E2-05 (`evaluate_local_eligibility`) decides whether local models are
  *eligible* for a role (demotion path — local goes last).
- E2-10 (`re_evaluate_routing`) re-routes after reconnaissance.
- E2-11 escalates the role *before* scoring so a stronger model is
  considered from the start.

These three compose into a single coherent routing decision:
`role escalation (E2-11)` → `model scoring` → `local eligibility demotion (E2-05)` →
`provider availability filtering (Phase 15)` → `selection`.

## Verification

- E2-06: 106 tests continue to pass (E2-11 escalation only fires on
  non-default task_signals).
- E2-07: 35 tests continue to pass (ledger provenance preserved).
- Full suite: 1469 passed, 0 failed. Ruff clean.
