# E2 entry-gate review

**Date:** 2026-09-11  
**Source reviewed:** `8d01d90` (clean)  
**E1 gate:** `VERIFIED` on `8d01d90` with real Ollama embeddings (`nomic-embed-text:latest`), min_recall=1.00, 12/12 samples at 100% recall.  
**Result:** **RATIFIED** for acceptance.

## Resolution of prior BLOCKED conditions

The prior review (2026-09-09, `fd8a8c8`) was BLOCKED for acceptance. Three
blocking conditions are now resolved:

### 1. E1 acceptance matrix closed

- **E1 measurement gate: PASS/VERIFIED** on clean revision `8d01d90`.
  - `paw.bench.e1_production` runner records input hashes before AND after run,
    validates fixture Git blobs against reviewed revisions (`fixtures_fresh=true`),
    checks tree state (`dirty=false`) and revision stability.
  - `test_dirty_tree_cannot_self_certify_a_pass` proves a dirty tree cannot
    self-certify.
  - 12/12 measurement samples (6 cases × cold/warm) at recall 1.00.
  - Report: `benchmarks/e1/e1_production_report.md` (see "Production re-run" section).

### 2. Prerequisites E2-25..28 and E2-45..47 complete

| Item | Status | Evidence |
|------|--------|----------|
| E2-25 Ownership Map | ✅ DONE | `e2_25_ownership_map.md`, source-anchored to `core.reasoning_contracts` |
| E2-26 Decision artifact | ✅ DONE | `DecisionVersion` + `DecisionVersionState` (E2-47) — single decision model, no second plan |
| E2-27 ImplementationReadiness | ✅ DONE | `ImplementationReadiness` StrEnum in `reasoning_contracts.py`, separate from policy/autonomy/task/stop enums |
| E2-28 Persistence | ✅ DONE | `decision_records` table + `Database.record_decision()`/`get_decision()`/`get_decisions_by_task()` with project_revision + constraint_fingerprint |
| E2-45 Plan purpose | ✅ DONE | `PlanPurpose` (RESEARCH/SPIKE/IMPLEMENTATION) + effect_constraints |
| E2-46 Effect constraints | ✅ DONE | `_gate_action` enforces `effect_constraints` before step_fn |
| E2-47 Immutable versions | ✅ DONE | `DecisionVersion` frozen dataclass with DRAFT/FINAL/STALE/SUPERSEDED transitions |

**Tests:** 119 E2 contract tests pass (`test_e2_02_05_26_27_28_45_46_47*.py`).

### 3. Cloud-baseline boundary explicitly resolved

The boundary between local baseline and cloud/model inference is defined by:

- **`InferenceClassification` (E2-09):** `model.inference` vs `local.compute` — single
  authority, fail-closed. If reconnaissance finds no/insufficient evidence, the
  step requires `MODEL_INFERENCE`; otherwise `LOCAL_COMPUTE`.
- **`evaluate_local_eligibility` (E2-05):** deterministic, fail-closed eligibility
  rules per role based on observed out-of-distribution conditions.
- **`LocalModelExecutor` (Phase 11):** the always-available local baseline, no
  network, no cost, never raises on provider unavailability.
- **`ProviderRegistry` (Phase 15):** distinguishes local providers (always
  available) from cloud providers (gated by E1-03 privacy gate).
- **`gate_remote_disclosure` (E1-03):** maps `ollama` → `local` provider_kind,
  ensuring local-first classification.

The distinction is **estimates vs. usage**: token estimates are advisory
(E2-32/E2-33 resource receipt); the local baseline is the floor; cloud is
escalation-gated. There is no silent fallback from cloud to local for
high-impact work (E2-13).

## What is ratified

E2 contracts in `paw.core.reasoning_contracts` are now the **single source of
truth** for:
- Role contracts (E2-02/03)
- Task signals (E2-04)
- Local eligibility (E2-05)
- Inference classification (E2-09)
- Research-depth classification (E2-29)
- Escalation decision (E2-11)
- Decision lifecycle (E2-47)
- Canonical proposal (E2-49)

`paw.core.__all__` remains the 11-symbol runtime surface. E2 contracts are
module-level expert APIs and do not widen the package root.

## What is NOT ratified

- No provider expansion, public export, browser/MCP/swarm or training work.
- No routing beyond `ModelRouter.route()` (E2-06).
- E2 contracts are consumed by the runtime only after the single authority
  gate: Proposal → Policy → Autonomy → Provider (E2-49).

## Re-entry evidence

| Check | Command | Result |
|-------|---------|--------|
| E2 contracts | `python -m pytest tests/test_e2_02_05_26_27_28_45_46_47*.py -q` | 119 passed |
| E1-27 measurement | `python -m paw.bench.e1_production --output /tmp/...json --embedding ollama` | PASS/gate=PASS |
| ruff | `ruff check src/paw/` | All checks passed |
| Clean tree | `git status --porcelain=v1` | empty |

Vietnamese: `../../vi/benchmarks/e2/gate_ratification.md`.
