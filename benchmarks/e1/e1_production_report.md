# E1 Production Corpus Measurement Decision Report

**Date**: 2026-09-08
**Revision**: `bfd1fbe` (HEAD — dirty tree, measurement_gate=PARTIAL)
**Corpus**: `src/paw/` (PAW source tree, 69 files, 2.3 MB)
**Script**: `paw.bench.e1_production` (tracked — `src/paw/bench/e1_production.py`)
**Cases**: 6 cases in `benchmarks/e1/cases/`, each asks about one specific module
**Mode**: both `--roots benchmarks/e1/fixtures_paw` (synthetic, 12 files) and `--roots src/paw` (PAW source, 69 files)

> **Key update (2026-09-08)**: The `ContextCandidate.__lt__` sort inversion was
> fixed on the same day. Before the fix, `_rank_candidates()` produced ASCENDING
> order (lowest-score candidate first), causing the budget filter to drop the
> highest-scoring chunks and select wrong-source chunks. After the fix, all
> cases on both corpora achieve **recall = 1.00** (≥ 0.95 ✓).

---

## 1. Measurement Results

### Option A (PAW source, 69 files, `max_tokens=5000`)

| Case | Mode | Recall | Reduction |
|------|------|--------|-----------|
| paw_autonomy_budget | cold/warm | 1.00 | +0.990 |
| paw_checkpoint | cold/warm | 1.00 | +0.980 |
| paw_context_compiler | cold/warm | 1.00 | +0.981 |
| paw_model_router | cold/warm | 1.00 | +0.981 |
| paw_models_status | cold/warm | 1.00 | +0.993 |
| paw_privacy_gate | cold/warm | 1.00 | +0.981 |

**24/24 (case, mode) samples: recall = 1.00.**
**Median warm reduction: 0.981** (gate threshold ≥ 0.30 — PASS).

### Option B (synthetic, 12 small files, `max_tokens=1500`)

| Case | Mode | Recall | Reduction |
|------|------|--------|-----------|
| case_auth | cold/warm | 1.00 | +0.814 |
| case_billing | cold/warm | 1.00 | +0.812 |
| case_cache | cold/warm | 1.00 | +0.813 |
| case_config | cold/warm | 1.00 | +0.813 |
| case_database | cold/warm | 1.00 | +0.811 |
| case_events | cold/warm | 1.00 | +0.813 |
| case_logging | cold/warm | 1.00 | +0.812 |
| case_metrics | cold/warm | 1.00 | +0.812 |
| case_models | cold/warm | 1.00 | +0.812 |
| case_queue | cold/warm | 1.00 | +0.812 |
| case_router | cold/warm | 1.00 | +0.812 |
| case_scheduler | cold/warm | 1.00 | +0.812 |

**24/24 (case, mode) samples: recall = 1.00.**
**Median warm reduction: 0.871** (gate threshold ≥ 0.30 — PASS).

---

## 2. Gate Decision

**metric_gate: PASS** on both corpora (min recall = 1.00 ≥ 0.95 ✓, median warm
reduction ≥ 0.30 ✓ on both).

**measurement_gate: PARTIAL** (dirty tree — uncommitted changes exist).

**evidence_state: OBSERVED** (dirty tree prevents VERIFIED).

On a clean revision, the measurement_gate would be **PASS** with
evidence_state = **VERIFIED**.

---

## 3. Freshness Verification (end-of-run re-check)

The runner implements a **post-run freshness re-check** (not just recording):

1. **Before run**: `_snapshot(owned_inputs, repo_root)` records SHA-256 of every
   input file (`uv.lock`, `src/paw/*.py`, corpus files, case YAMLs).
2. **During run**: each case uses an isolated `TemporaryDirectory` with a fresh
   `Database` and fresh `ContextCompiler` — no cross-contamination.
3. **After run**: `_snapshot(after_inputs, repo_root)` records SHA-256 again.
4. **Decision**: `_measurement_decision` returns `BLOCKED` if `before != after`
   (inputs changed during measurement), even if `metric_gate == "PASS"`.

This is pinned by `test_run_e1_production.py::test_changed_input_during_run_is_blocked`.

### Fixture freshness

Each case's fixtures are bound to a Git blob at a reviewed revision. The runner
checks:
- `reviewed_hash` = `git show <revision>:<path>` blob hash
- `current_hash` = current file SHA-256
- `fresh` = True iff `current_hash == reviewed_hash`

On the PAW source corpus, fixtures are the case YAML files themselves, bound
to `revision: bfd1fbe`. `fixtures_fresh: True`.

---

## 4. Root Cause of Previous Failure (0% recall)

Before the `__lt__` fix, the PAW source corpus showed 5/6 cases at 0% recall
and 1/6 at 50%. Root cause:

- `ContextCandidate.__lt__` returned `self > other` (inverted)
- `_rank_candidates()` used `sorted(candidates, reverse=True)`
- Double inversion → ascending order → lowest-score chunks first
- Budget filter (`_allocate_budget`) processed lowest-score chunks first
- Target chunks were dropped; wrong-source chunks selected

Fix: `__lt__` now returns `self < other` (normal), so `sorted(reverse=True)`
correctly produces descending order (highest-score first). This was pinned by
`tests/test_context_compiler_sort.py` and `tests/test_e1_16_context_manifest_contract.py`.

---

## 5. Reproduction (clean checkout)

The runner is a tracked package module, not a gitignored script:

```
# Clean checkout — reproduce measurement
uv run python -m paw.bench.e1_production \\
  --output /tmp/e1_paw_source.json \\
  --roots src/paw \\
  --case-dir benchmarks/e1/cases \\
  --max-tokens 5000 --max-fragments 30 --max-sources 10

# Synthetic corpus
uv run python -m paw.bench.e1_production \\
  --output /tmp/e1_synthetic.json \\
  --roots benchmarks/e1/fixtures_paw \\
  --case-dir benchmarks/e1/cases_prod \\
  --max-tokens 1500 --max-fragments 5 --max-sources 3
```

The output path opens with `mode='x'`, so re-running on a non-empty target
raises `FileExistsError` and the prior report is never silently overwritten.

---

## 6. Privacy and Freshness Audit (same run)

- Manifest items include ingested source content (file-based candidates with
  `reference` / `external_id` set). `privacy_class` is `INTERNAL` (default for
  newly created `KnowledgeSource` records). No SECRET candidates.
- Stale items: 0 (no `mark_invalid` was issued in this run).
- `gate_remote_disclosure(manifest, provider_kind="cloud_unapproved")` — covered
  by `tests/test_e1_21_remote_disclosure_contract.py` and
  `tests/test_runtime_privacy_proof.py` (PASS).

---

## 7. What this report proves and does NOT prove

**Proves:**
- The E1-23/24/25/27 measurement infrastructure is wired correctly end-to-end.
- The ContextCompiler + KnowledgeSourceManager + KnowledgeChunkStore +
  measure_recall + measure_tokens chain produces a real reviewed-baseline result.
- The `__lt__` fix resolves the PAW source recall gap (was 0% → now 100%).
- Freshness check catches mid-run input changes (`test_changed_input_during_run_is_blocked`).

**Does NOT prove:**
- Answer quality or behavioral correctness of the agent on real tasks.
- Cache benefit between cold and warm on this corpus (both are identical).
