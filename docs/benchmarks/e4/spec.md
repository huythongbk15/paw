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

**BLOCKED (E4-11..14):** Provider scaffolds implemented (contract defined,
NotImplementedError enforced) but training/teaching measurement cannot run
until a cloud provider adapter is available outside the core per AGENTS.md
scope lock. 17 tests pass (`test_e4_provider_scaffolds.py`) proving
contracts exist + are blocked.

**Implementation:**
- `CloudTeacherBaselineResult` — dataclass with cost tracking
- `TrainingConfig` — config with `config_hash()`
- `TrainingArtifact` — versioned artifact with `artifact_hash()`
- `TrainingEvaluation` — comparison metrics
- `measure_cloud_teacher_baseline()` → NotImplementedError
- `train_dataset()` → NotImplementedError
- `register_training_artifact()` → NotImplementedError
- `evaluate_training_artifact()` → NotImplementedError
- `should_accept_artifact()` → pure logic (acceptance gate, no provider)

## Implementation

**Module:** `src/paw/core/dataset.py` (299 lines)

**Key components:**

| Component | Type | Fields/Methods |
|-----------|------|----------------|
| `DatasetExample` | `@dataclass` | `trace_id`, `skill_name`, `skill_version`, `input_prompt`, `target_completion`, `source_files`, `capabilities`, `cost_estimate`, `created_at`, `redacted=True` |
| `DatasetSplit` | `@dataclass` | `name`, `examples` |
| `DatasetManifest` | `@dataclass` | `dataset_id`, `version`, `description`, `created_at`, `content_hash`, `example_count`, `splits`, `consent_statement`, `retention_days`, `deletion_policy`, `source_trace_ids`, `base_model`, `environment`, `excluded_trace_ids` |
| `LocalBaselineResult` | class | `model_name`, `accuracy`, `mean_latency_ms`, `total_tokens`, `examples_evaluated` |

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
- **Total: 18 tests, all PASS**

## Design principles

- **Dataset-only, no training:** This module manages dataset structure only.
  Training/experimentation (E4-11+) lives in a separate module and requires
  a provider adapter.
- **Verified-trace gate:** Only `is_success=True` traces can be exported.
  There is no path to export failed or unreviewed activity.
- **Redaction-first:** Secrets and private paths are redacted at export time
  using E3-10's `redact_payload()`. All examples have `redacted=True`.
- **Reproducibility:** Dataset hash + `environment` field (Python version, OS)
  enable reproducible baseline verification.
- **Zero vendor lock-in:** `measure_local_baseline` uses existing PAW runtime
  infrastructure (`_execute_unit`, `LocalModelExecutor`). No provider SDK deps.
- **Graceful degradation:** If no runtime is available, `measure_local_baseline`
  returns `accuracy=0.0` (measurement framework operational, just no model).

## Acceptance

- [x] Dataset can only be built from successful reviewed traces (E4-05 raises `ValueError`)
- [x] All examples are redacted before storage (E4-06, `redacted=True`)
- [x] Dataset hash is reproducible and frozen (E4-09 content_hash stable)
- [x] Local baseline measurement works without training (E4-10, 4 tests pass)
- [x] Cloud teacher baseline is documented as blocked (out of scope per AGENTS.md)
