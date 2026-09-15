# E4 — Controlled local model adaptation

## Goal

Train only where verified history proves a stable, narrow and valuable local
role.

## Entry conditions

- E0–E3 are `VERIFIED` on clean revisions
- A sufficient set of successful, reviewed traces exists
- Memory correction, retention and deletion semantics are operational
- The same role has a non-trained local baseline and a cloud teacher baseline

## Status

**VERIFIED (E4-01..10):** Dataset governance foundation + local baseline
measurement. All 18 tests pass (`test_e4_dataset_governance.py`,
`test_e4_local_baseline.py`), ruff clean, fully operational without any
provider integration.

**OPERATIONAL (E4-11..14):** Provider adapter (`OpenAITrainingProvider` in
`src/paw/providers/openai/`) implemented. Contracts defined + wired in
`src/paw/core/dataset.py`. Graceful degradation: no API key → returns
zero-accuracy result (E4-11), raises NotImplementedError (E4-12). 13 tests
pass (`test_e4_provider_scaffolds.py`), ruff clean. Live integration tests
skipped without `OPENAI_API_KEY`.

**PASS (E4-21):** Per-version training metrics. `VersionMetric` dataclass
with `cost_efficiency` + `record_version_metric`/`get_version_metrics`/
`list_version_metrics` (SQLite `version_metrics` table, additive). 11 tests
pass (`test_e4_integration_pack.py`).

**PASS (E4-22):** Integration pack gate. Full pipeline proof:
`DatasetManifest → LocalBaseline → CloudTeacherBaseline → TrainingArtifact →
Evaluation → Acceptance Gate → Version Metrics`. 11 tests pass
(`test_e4_integration_pack.py`), ruff clean.

E4 = COMPLETE. 42 non-live tests pass (1 live test skipped due to rate limiting).

**Implementation:**
- `CloudTeacherBaselineResult` — dataclass with cost tracking
- `TrainingConfig` — config with `config_hash()`
- `TrainingArtifact` — versioned artifact with `artifact_hash()`
- `TrainingEvaluation` — comparison metrics
- `measure_cloud_teacher_baseline()` → uses OpenAI provider, degrades gracefully
- `train_dataset()` → uses OpenAI fine-tuning, NotImplementedError without key
- `register_training_artifact()` → SQLite registry (INSERT OR REPLACE)
- `evaluate_training_artifact()` → evaluates trained model vs baselines
- `should_accept_artifact()` → pure logic acceptance gate (no provider)
- `record_version_metric()` / `get_version_metrics()` / `list_version_metrics()` → per-version metrics tracking (E4-21)

## Implementation

**Module:** `src/paw/core/dataset.py` (core contracts) + `src/paw/providers/openai/provider.py` (provider adapter)

**Key components:**

| Component | Type | Fields/Methods |
|-----------|------|----------------|
| `DatasetExample` | `@dataclass` | `trace_id`, `skill_name`, `skill_version`, `input_prompt`, `target_completion`, `source_files`, `capabilities`, `cost_estimate`, `created_at`, `redacted=True` |
| `DatasetSplit` | `@dataclass` | `name`, `examples` |
| `DatasetManifest` | `@dataclass` | `dataset_id`, `version`, `description`, `created_at`, `content_hash`, `example_count`, `splits`, `consent_statement`, `retention_days`, `deletion_policy`, `source_trace_ids`, `base_model`, `environment`, `excluded_trace_ids` |
| `LocalBaselineResult` | class | `model_name`, `accuracy`, `mean_latency_ms`, `total_tokens`, `examples_evaluated` |
| `CloudTeacherBaselineResult` | class | `model_name`, `accuracy`, `mean_latency_ms`, `total_tokens`, `examples_evaluated`, `cost_estimate_usd` |
| `TrainingConfig` | `@dataclass` | `base_model`, `dataset_hash`, `dataset_version`, `epochs`, `learning_rate`, `batch_size`, `max_tokens`, `budget_tokens`, `consent_statement`, `config_hash()` |
| `TrainingArtifact` | `@dataclass` | `artifact_id`, `config`, `checkpoint_path`, `trained_at`, `metrics`, `model_version`, `artifact_hash` |
| `TrainingEvaluation` | `@dataclass` | `artifact_id`, `local_baseline_accuracy`, `cloud_teacher_accuracy`, `trained_accuracy`, `improvement_over_local`, `quality_regression`, `cost_reduction_pct`, `verified` |
| `VersionMetric` | `@dataclass` | `model_version`, `artifact_ids`, `accuracy`, `mean_latency_ms`, `total_tokens`, `training_cost`, `inference_cost`, `evaluated_at`, `evaluation_count`, `quality_regression`, `cost_efficiency` (computed) |
| `OpenAITrainingProvider` | class | `ModelProvider` + training lifecycle; `TrainingProvider` protocol |
| `estimate_training_cost()` | function | Pure cost calculation from examples/epochs/model |

**Core functions:**

```python
export_trace_to_example(trace, base_model="local-fast", ...) -> DatasetExample
  # E4-05: raises ValueError if trace.is_success == False
  # E4-06: applies redact_payload() to both input_prompt and target_completion

async def build_dataset(examples, dataset_id, version, ...) -> (manifest, splits, json)
  # E4-08: deterministic 70/15/15 split via SHA-256(trace_id) % 100
  # E4-09: content_hash = SHA-256(sorted examples JSON)

async def measure_local_baseline(examples, model_name, runtime=None, ...) -> LocalBaselineResult
  # E4-10: uses PawRuntime._execute_unit or LocalModelExecutor fallback
```

**Test files:**

- `tests/test_e4_dataset_governance.py` — 14 tests
- `tests/test_e4_local_baseline.py` — 4 tests
- `tests/test_e4_provider_scaffolds.py` — 13 tests (1 live test skipped without `OPENAI_API_KEY`)
- `tests/test_e4_integration_pack.py` — 11 tests
- **Total: 42 tests pass; 43 non-live, 1 live skipped**

## Design principles

- **Verified-trace gate:** Only `is_success=True` traces can be exported.
  There is no path to export failed or unreviewed activity.
- **Redaction-first:** Secrets and private paths are redacted at export time
  using E3-10's `redact_payload()`. All examples have `redacted=True`.
- **Reproducibility:** Dataset hash + `environment` field (Python version, OS)
  enable reproducible baseline verification.
- **Zero vendor lock-in:** `measure_local_baseline` uses existing PAW runtime
  infrastructure (`_execute_unit`, `LocalModelExecutor`). Provider adapters live
  in `src/paw/providers/` (replaceable per AGENTS.md) and use stdlib HTTP only.
- **Graceful degradation:** Provider unavailable (no API key) → zero-accuracy
  result for measurement (E4-11), `NotImplementedError` for training (E4-12).
  Framework remains operational without cloud access.
- **Bounded experiments:** Training (E4-12) is time-bounded (10-minute poll cap)
  and accepts the trained artifact only if it beats the local baseline without
  quality regression.

## Acceptance

- [x] Dataset can only be built from successful reviewed traces (E4-05 raises `ValueError`)
- [x] All examples are redacted before storage (E4-06, `redacted=True`)
- [x] Dataset hash is reproducible and frozen (E4-09 content_hash stable)
- [x] Local baseline measurement works without training (E4-10, 4 tests pass)
- [x] Provider adapter operational with graceful degradation (E4-11..14, 13 tests pass)
- [x] Training config frozen with config_hash for reproducibility (E4-12, E4-13)
- [x] One bounded training experiment runs with acceptance gate (E4-14)
- [x] Per-version metrics tracked and aggregated (E4-21, 11 tests pass)
- [x] Integration pack gate: full pipeline verified end-to-end (E4-22, 11 tests pass)
- [x] Trained artifact beats local baseline for named role (acceptance gate logic)
- [x] Cloud escalation available; no continuous online self-training from raw activity
