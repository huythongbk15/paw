# E2 Gate Ratification

**Date:** 2026-09-09
**Revision:** `76013fb`
**Gate:** E2 — Decision lifecycle, research gate and selective local/cloud reasoning
**Status:** RATIFIED

## Preconditions

| Condition | State |
|---|---|
| E1 `VERIFIED` | ✅ `2baebab` — recall=1.0, reduction=0.9847, `measurement_gate=PASS`, `evidence_state=VERIFIED` |
| E2-01 audit complete | ✅ `ba1a583` — `docs/benchmarks/e2/e2_01_audit.md` |
| E2-02 cognitive roles | ✅ 9 tests pass — `core/reasoning_contracts.py` |
| E2-03 role contracts | ✅ 8 tests pass — `core/reasoning_contracts.py` |
| E2-04 task signals | ✅ 18 tests pass — `core/reasoning_contracts.py` |
| E2-05 local eligibility | ✅ 17 tests pass — `core/reasoning_contracts.py` |
| E2-06 router extension | ✅ 17 tests pass — `core/model_router.py` — `76013fb` |
| E2-07 ledger persistence | ⏳ Next item |

## Ratification scope

The E2 gate is **RATIFIED**. Runtime consumption of E2-02..05 value
contracts is authorized.

### What is authorized

- `ModelRouter.route()` accepts `task_signals: TaskSignals | None`
  and demotes local candidates when the role is out-of-distribution
  (E2-05 eligibility via `evaluate_local_eligibility()`)
- `ContextCompiler` may use `TaskSignals` fields when building the manifest
- `AutonomyController` may use `RoleContract` disposition when deciding stop/escalate
- Any future E2 item may reference the `core/reasoning_contracts.py` value contracts

### What is NOT authorized (still pending E2 gate ratification)

- New provider integrations (Phase 11+ scope)
- Any change to `paw.core.__all__`
- MCP, browser automation, GUI/TUI, swarm

## Open risks

| Risk | Mitigation |
|---|---|
| `route()` signature change may break callers | All existing callers use defaults; `task_signals=None` is backward-compatible |
| E2-07 ledger persistence not yet done | Route decision not yet persisted in TaskLedger — pending |
| Value contracts are pre-gate drafts | Ratification is provisional until E2-07 proves runtime wiring end-to-end |

## Changelog since ratification

- `76013fb`: E2-06 — `ModelRouter.route()` now consumes `TaskSignals`,
  evaluates local eligibility, and demotes local candidates when OOD
  (17 contract tests, ruff clean)
- `2baebab`: E1-27 D3 gate VERIFIED on clean revision `649ded9`

## Next after E2-07

- E2-29: Escalation trigger (separate from E2-04 signals)
- E2-31: Embedding-aware routing
