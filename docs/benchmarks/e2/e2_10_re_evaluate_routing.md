# E2-10: Re-evaluate routing after reconnaissance

## Contract

The `ModelRouter` must re-evaluate the model selection **after** reconnaissance
is available, rather than routing blindly from the initial prompt.

A `ReconnaissanceResult` (E2-08) gathers bounded local evidence from the
project — symbol counts, recent git changes, test associations, and knowledge
sources. `classify_inference` (E2-09) gates whether that evidence is sufficient
to satisfy the task with local compute.

### Boundary rule (single authority — `classify_inference`)

| Reconnaissance state | classify_inference | Re-evaluation action |
|---|---|---|
| Empty (symbol_count=0, confidence=0.0) | `model.inference` | Escalate role (fast→reasoning) if OOD signals present; otherwise keep prev |
| Non-empty, confidence ≥ 0.25, privacy ≤ WORKSPACE | `local.compute` | Downgrade cloud→local (pick local model supporting the role) |
| Non-empty, confidence ≥ 0.25, privacy = SECRET | `local.compute` | Do NOT downgrade (SECRET must not downgrade to local for privacy safety) |
| confidence < 0.25 | `model.inference` | Escalate role (fast→reasoning) if OOD signals present |

### OOD signal derivation

When `classify_inference` returns `model.inference`, the router derives OOD
conditions from the reconnaissance:

- `MISSING_EVIDENCE` — symbol_count == 0 AND recent_change_count == 0
- `LOW_CONFIDENCE` — evidence_confidence < 0.25
- `NOVEL_TASK` — recent_change_count > 0

If OOD conditions are present and the role is `fast` or `tools`, escalate to
`reasoning`.

### API

```python
async def ModelRouter.re_evaluate_routing(
    task_id: str,
    prev_selection: ModelSelection,
    reconnaissance: ReconnaissanceResult,
) -> ModelSelection
```

- Returns the updated `ModelSelection` (downgraded, escalated, or unchanged).
- Idempotent: calling with the same recon result on the already-downgraded
  selection produces the same local model selection.
- The previous selection is preserved in `fallback_chain`.

### Runtime wiring

`PawRuntime._execute_action` calls `re_evaluate_routing()` after the initial
`route()`. The ledger records `MODEL_RESELECTED` when the re-evaluation changes
the selection.

`PawRuntime._gather_reconnaissance(task_id, task_goal)` gathers real evidence:
- E1-10 `extract_symbols` — symbol_count, symbol_kinds
- E1-12 `recent_changes` — recent_change_count, recent_changed_files
- E1-11 `associate_tests` — test_association_count
- E1-02/03 `KnowledgeSourceManager.list` — knowledge_source_count

On any error, returns an empty `ReconnaissanceResult` (never raises).

## Verification

17 tests in `tests/test_e2_10_re_evaluate_routing.py`:

- **Invariant (4):** downgrade path, escalate path, empty-recon → model.inference, no-local-fallback keeps prev
- **Runtime (4):** `_gather_reconnaissance` exists, passes recon to `route()`, re-evaluation after route, method exists
- **Adversarial (4):** SECRET blocks downgrade, NaN rejected by dataclass, zero evidence no downgrade, fallback chain preserves prev
- **Measurable (5):** downgrade changes selection, initial vs re-evaluated differ, no-evidence escalates, idempotency, persistence to ledger
