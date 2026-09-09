# E2-06: Router consumes E2-02/03/04/05 value contracts

**Date:** 2026-09-08
**Revision:** `2baebab`
**Gate:** E2 — Decision lifecycle, research gate and selective local/cloud reasoning
**Status:** IN PROGRESS (contract test written; implementation pending verification)

## Contract

`ModelRouter.route()` is the **sole** entry point for model selection. It must
accept and consume the E2 value contracts without introducing a parallel router,
changing `paw.core.__all__`, or adding a provider.

### Inputs

| Parameter | Type | Source | Default |
|---|---|---|---|
| `task_signals` | `TaskSignals | None` | E2-04 | `None` |

When `None`, `route()` behaves exactly as before (backward-compatible). When
supplied, the router uses the signals to evaluate local eligibility (E2-05)
and, when the role is out-of-distribution locally, demotes local candidates so
a non-local provider is preferred.

### Internal helper

`_observed_ood_conditions(signals, privacy_required) -> frozenset[OODCondition]`

Deterministic, fail-closed mapping from `TaskSignals` to the `OODCondition` set
that `evaluate_local_eligibility()` expects. Any `UNKNOWN` signal contributes
nothing — the caller cannot accidentally route a task that was never reconnoitred.

| Signal field | Condition added |
|---|---|
| `novelty == "novel"` | `OODCondition.NOVEL_TASK` |
| `impact == "high"` | `OODCondition.HIGH_IMPACT` |
| `privacy_required or privacy == "secret"` | `OODCondition.PRIVACY_BLOCKED` |
| `budget == "exhausted"` | `OODCondition.BUDGET_EXHAUSTED` |
| `uncertainty_score is not None and < 0.5` | `OODCondition.LOW_CONFIDENCE` |
| `context_sufficiency == "insufficient"` | `OODCondition.MISSING_EVIDENCE` |

### Behavior

1. `route()` computes `scored` exactly as before (Phase 15 availability filter).
2. If `task_signals` is `None`, skip the E2 block — identical behavior.
3. If `task_signals` is supplied:
   - Compute `observed = _observed_ood_conditions(...)`.
   - `eligibility = evaluate_local_eligibility(role, observed)`.
   - If `eligibility.eligible` is `False`, reorder `scored` so non-local
     candidates come first and local candidates last. Log
     `model_routed_ood_demote_local` with the matched conditions and rule.
   - If `eligibility.eligible` is `True`, log `model_routed_local_eligible`.
4. Continue with the existing real/local split and selection logic.

### Invariants

- `route()` signature gains one optional keyword parameter; all existing
  callers are unaffected (backward-compatible).
- `route_with_explain()` gains the same parameter for consistency.
- No new router, no `paw.core.__all__` change, no new provider.
- `evaluate_local_eligibility()` is fail-closed on unknown roles — the
  router does not bypass it.

### Negative controls

| Case | Expected |
|---|---|
| `task_signals=None` | Identical selection to pre-E2-06 behavior |
| Unknown role (not in `CANONICAL_ELIGIBILITY_RULES`) | `eligible=False`, `conditions=(UNKNOWN,)`, `matched_rule=None` |
| `TaskSignals()` (all defaults) | `observed` is empty; eligibility depends only on `privacy_required` |
| FAST role with `NO_MATCHING_CAPABILITY` | Demotes local; non-local preferred |
| REASONING role with `MISSING_EVIDENCE` | Demotes local; non-local preferred |
| FAST role with no OOD conditions | Local stays first; no demotion |
| `task_signals` with `uncertainty_score=0.0` | `LOW_CONFIDENCE` added |
| `task_signals` with `uncertainty_score=1.0` | No `LOW_CONFIDENCE` |
| `task_signals` with `uncertainty_score=None` | No `LOW_CONFIDENCE` (fail-closed) |

### Two-fail-positive discipline

Each negative case was written because the failure it asserts was reproduced
against a candidate that lacked the check. The `task_signals=None` backward-compat
case pins the pre-E2-06 behavior so a future refactor cannot silently change
the default path. The `NO_MATCHING_CAPABILITY` and `MISSING_EVIDENCE` cases
pin the demotion behavior so a future change cannot re-enable local routing
for out-of-distribution roles.