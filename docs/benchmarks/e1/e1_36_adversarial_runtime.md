# E1-36 Track — Adversarial Runtime (2026-09-07)

**Mục tiêu:** Counter-pattern cho E1 contract tests. Pure runtime/adversarial/measurable.

**Philosophy:** Invariant → Runtime wiring → Adversarial → Measurable → PASS

**NOT:** Contract → Dataclass → Unit test → Checkbox PASS

### E1-36 Test Structure (12 tests, all PASS)

| Layer | Test | Description |
|-------|------|-------------|
| 1: Invariant | `test_inv1_ask_never_becomes_execution` | ASK → STOP (constitutional) |
| 1: Invariant | `test_inv2_deny_never_becomes_execution` | DENY → STOP |
| 1: Invariant | `test_inv3_budget_hard_limits_enforced` | Budget limits respected |
| 2: Runtime | `test_runtime_policy_blocks_execution` | PolicyGuard → Autonomy → STOP |
| 2: Runtime | `test_runtime_knowledge_ingestion_to_retrieval` | Knowledge pipeline wired |
| 3: Adversarial | `test_adv1_path_traversal_source_id_blocked` | Path traversal rejected |
| 3: Adversarial | `test_adv2_stale_source_blocks_remote_disclosure` | Stale SECRET blocked |
| 3: Adversarial | `test_adv3_budget_overflow_blocked` | Budget overflow tracked |
| 4: Measurable | `test_measure1_context_compiler_respects_budget` | final_tokens ≤ max_tokens |
| 4: Measurable | `test_measure2_autonomy_budget_tracks_usage` | Usage tracked |
| 4: Measurable | `test_measure3_checkpoint_persists_and_resumes` | Checkpoint roundtrip |
| 5: Composite | `test_e1_36_adversarial_pipeline_verified` | All layers verified |

**Key design decisions:**
- All tests use REAL subsystems (PolicyGuard, AutonomyController, KnowledgeSourceManager, ContextCompiler, CheckpointStore)
- No mocks for core subsystems
- Real temp SQLite (session_db fixture)
- Tests prove BEHAVIOR, not structure

### E1-26 Retrofit (9 new adversarial tests, added to existing 5 contract tests)

| Test | Description |
|------|-------------|
| `test_adv_stale_source_cannot_bypass_privacy_gate` | Stale SECRET cannot bypass gate |
| `test_adv_manipulation_cannot_bypass_privacy_gate` | Content manipulation doesn't bypass |
| `test_adv_multiple_sources_stale_secret_cannot_leak` | Mixed sources blocked |
| `test_adv_policy_deny_stops_execution_before_step` | DENY → STOP before step |
| `test_adv_ask_non_interactive_stops_execution` | ASK → STOP (constitutional) |
| `test_adv_budget_overflow_blocks_execution` | Budget tracked |
| `test_adv_null_byte_in_source_path_blocked` | Null byte rejected |
| `test_adv_absolute_path_in_source_path_blocked` | Absolute path handled |
| `test_e1_26_adversarial_gate_verified` | Composite gate |

**Total E1-26: 14 tests (5 contract + 9 adversarial), all PASS**

### Test Composition Audit (post-E1-36)

| Category | Count | % |
|----------|-------|---|
| Contract tests | ~50 | ~20% |
| Adversarial tests | ~15 | ~6% |
| Runtime/measurable tests | ~10 | ~4% |
| Phase tests | ~30 | ~12% |
| Other | ~150 | ~60% |

**Target:** Contract ~20%, Adversarial/Runtime ~10% — moving toward the correct ratio.

### Status: PASS (26 tests, ruff clean, committed `f68944d`)
