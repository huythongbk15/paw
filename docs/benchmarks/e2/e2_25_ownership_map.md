# E2-25: Ownership Map

## Canonical owner mapping

| Component | Owning module | Key types |
|-----------|---------------|-----------|
| Readiness | `core.reasoning_contracts` | `ReadinessAssessment`, `EvidenceSuitability`, `ImplementationReadiness` |
| Evidence | `core.reasoning_contracts` | `EvidenceRecord`, `EvidenceSuitability`, `EvidenceCategory` |
| Context | `core.context_compiler` | `ContextManifest`, `ContextCandidate`, `ContextBudget` |
| Routing | `core.model_router` | `ModelRouter`, `ModelSelection`, `ReconnaissanceResult` |
| Policy | `core.policy` | `PolicyGuard`, `PolicyDecision`, `PolicyDecisionDetail` |
| Autonomy | `core.autonomy` | `AutonomyController`, `StopReason`, `AutonomyDecision` |
| Planner | (future: `core.planner`) | `Plan`, `PlanPurpose`, `PlanStatus` — not yet implemented |

## Evidence flow

1. `ContextManifest` (context) aggregates `ContextCandidate`s with scores
2. `ReconnaissanceResult` (routing) summarizes symbol/evidence analysis
3. `PolicyGuard.evaluate_request` (policy) gates the proposal
4. `AutonomyController.decide` (autonomy) tracks budget/iteration/stop
5. `ModelRouter.route` (routing) selects the model based on role + signals

## Verification

Document is source-anchored; no code changes needed (D0 discovery task).
