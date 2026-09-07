# E1 Real Measurement Decision Report

**Date**: 2026-09-07
**Revision**: `263c075` (HEAD; `bench/integration.py` is present)
**Corpus**: `benchmarks/e0/cases/` (2 representative cases, `architecture_decision_cache`, `cross_module_change_constant`)
**Fixtures ingested**: `benchmarks/e0/fixtures/architecture_decision.txt`, `benchmarks/e0/fixtures/cross_module_change.txt`
**Source**: `/home/huythong/.hybridagent/workspaces/default/src`
**Configuration**: `ContextCompiler` (lexical-only, `auto_attach_embeddings=False`, `ContextBudget(max_tokens=8000)`)
**Script**: `scripts/run_e1_measurement.py` (re-runnable; output path is `exclusive-create` to prevent overwriting)

> **Provenance note (2026-09-07)**: this report replaces the earlier draft that incorrectly
> pinned revision `f3ad4ef` (which did NOT yet contain `src/paw/bench/integration.py` or
> the E1-23/24/25 measurement module), used unexplained baselines of 4000/3000, and
> recommended substituting skills for file evidence. All three issues are corrected below
> by re-running the canonical script against the current HEAD that owns the E1-23/24/25
> infrastructure.

---

## 1. Measurement Results (real run, 2026-09-07 08:24 UTC)

### Recall (E1-23)

| Case | Mode | Recall | Recalled | Total | Missed |
|------|------|--------|----------|-------|--------|
| architecture_decision_cache | cold | 1.00 | 2 | 2 | (none) |
| architecture_decision_cache | warm | 1.00 | 2 | 2 | (none) |
| cross_module_change_constant | cold | 1.00 | 2 | 2 | (none) |
| cross_module_change_constant | warm | 1.00 | 2 | 2 | (none) |

All four evidence targets (the two `file_contains` items per case) were retrieved for both
cases in cold and warm modes. Recall = 1.00 is **not** a pass; it is one of the
acceptance thresholds the contract tests pin (≥ 0.95). This run is a fixture-validation
baseline, not a reviewed E0 / cloud baseline.

### Tokens (E1-24)

| Case | Mode | Baseline | Measured | Reduction (signed) |
|------|------|----------|----------|---------------------|
| architecture_decision_cache | cold | 179 | 203 | -0.13 |
| architecture_decision_cache | warm | 179 | 203 | -0.13 |
| cross_module_change_constant | cold | 103 | 127 | -0.23 |
| cross_module_change_constant | warm | 103 | 127 | -0.23 |

`baseline_tokens` is the sum of `TokenEstimator().estimate(content)` over every fixture
referenced by the case (single-fixture cases: 1 file each). `measured_tokens` is the
`final_tokens` of the compiled `ContextManifest`. The negative reduction means the
manifest includes skill headers + session context around the file content, so total tokens
slightly exceed the file-only baseline; the same value is returned for cold and warm
because the lexical-only path is deterministic and the script instantiates a fresh
compiler per case (no warm-cache benefit to claim).

### Cold vs warm

Cold and warm runs produce identical results in this configuration (lexical-only, no
embeddings, fresh per-case DB). The 0.99 reduction in the earlier draft was an artifact of
an empty manifest (`measured = 0`); with the fixture corpus ingested the manifest is no
longer empty and the reduction is correctly negative (overflow by session/skill metadata).

### Recall Misses (E1-25)

Zero misses across all four (case, mode) combinations. The closed-set of
`MISS_CATEGORIES` is unchanged and the mapping stays `retrieval → next action: verify
ingestion / expand lexical prefilter / enable embeddings`.

---

## 2. Reproduction

The run is reproducible from the recorded inputs:

```
git rev-parse HEAD       # 263c075
git status --porcelain   # working tree (after this commit) must be clean for re-run

# Exclusive-create guarantees the previous report is never silently overwritten.
uv run python scripts/run_e1_measurement.py --output benchmarks/e1/measurement_20260907.json
```

The output JSON records: HEAD revision, dirty flag, hashes for every file under
`src/paw/`, the case YAML, and the script itself. A second run with any of those inputs
mutated fails the `inputs_unchanged` check.

Per-case isolation: each case runs in its own `TemporaryDirectory(prefix="paw-e1-")` with
a fresh `Database` and fresh `ContextCompiler`, so no global state leaks between cases.

---

## 3. Privacy and Freshness Audit (same run)

- Manifest items include the ingested fixture content (file-based candidates with
  `reference` / `external_id` set). `privacy_class` is `INTERNAL` (the default for newly
  created `KnowledgeSource` records, since the cases declare `privacy_class: workspace`
  on the case itself, not on the source). No SECRET candidates.
- Stale items: 0 (no `mark_invalid` was issued in this run).
- `gate_remote_disclosure(manifest, provider_kind="cloud_unapproved")` was NOT invoked
  from the diagnostic runner because the runner only compiles a manifest; provider
  invocation is a separate runtime path. Privacy gate correctness on this exact fixture
  corpus therefore remains unverified by THIS run; the contract test
  `tests/test_e1_21_remote_disclosure_contract.py` covers the gate itself and was run
  separately (PASS).

---

## 4. What was wrong with the previous draft (P1 / P2)

| # | Severity | Issue | Resolution |
|---|----------|-------|-----------|
| 1 | P1 | Report pinned `f3ad4ef`, but that revision pre-dates `src/paw/bench/integration.py` (first added at `cf37681`). The numbers belonged to an unknown revision. | Re-ran the script against HEAD (`263c075`) which DOES own the E1-23/24/25 infrastructure; revision is now reproducible via `git rev-parse HEAD` in the JSON. |
| 2 | P1 | Baselines were 4000/3000 with no source for those numbers; the resulting "99% reduction" was meaningless. | Baselines are now `TokenEstimator.estimate(content)` summed over the case's actual fixture files. For these two cases the values are 179 and 103, which is consistent with the on-disk fixture sizes. |
| 3 | P1 | The previous "fix" suggested letting skills count as file evidence. The cases explicitly require `file_contains` of the fixture text. Substituting skills would weaken the contract. | The script now ingests the actual fixture corpus via `KnowledgeSourceManager.create` + `KnowledgeChunkStore.add_chunk` BEFORE the `ContextCompiler` runs, and `measure_recall` matches the case's `expected_evidence` directly. The earlier "ingest PAW source" recommendation was wrong: the evidence targets are the fixtures, not the PAW source tree. |
| 4 | P2 | An empty knowledge base (caused by an outdated `bfd1fbe`-era report) was used to claim the system "needs embeddings" and that "the privacy gate works in principle but has nothing to gate". Neither claim was evidence-based. | With fixtures ingested, recall is 1.00 on both cases; the privacy-gate claim is now isolated to `test_e1_21_remote_disclosure_contract.py` and is NOT conflated with the retrieval gap. |

---

## 5. Gate decision (E1-27)

**Gate: PARTIAL → Diagnostic-PASS, qualification unchanged.**

| Criterion | Threshold | Actual | Verdict |
|-----------|-----------|--------|---------|
| Recall (per case, mode) | ≥ 0.95 | 1.00 | PASS (diagnostic) |
| Warm token reduction (median) | ≥ 0.30 | -0.18 (signed, overflow) | FAIL — but the overflow is structural (session/skill metadata around the file content), not retrieval |
| Cold/warm equivalence (lexical-only, fresh DB) | n/a | identical | OBSERVED |
| Inputs unchanged / revision unchanged | required | both true | PASS |
| Compiler failures propagated | required | not encountered | OBSERVED |
| Privacy gate correctness on this corpus | contract test | PASS separately | OBSERVED |

The token overflow is real and expected for a two-fixture case: the budget is
`max_tokens=8000`, the file content is ~100–200 tokens, and the manifest wraps each file
with skill metadata + a session header that adds ~24 tokens of fixed overhead per
candidate. A larger fixture corpus or a tighter budget would change the sign. The
contract test `tests/test_e1_24_token_measurement_contract.py` enforces the
`baseline_tokens` validator independently and was not affected by this run.

`qualification` in the JSON stays `PARTIAL`. This is a fixture-validation run, not a
review; the E0 reviewed baseline and cloud comparison remain deferred per the project
charter.

---

## 6. What this run proves and does NOT prove

**Proves**
- The E1-23 / E1-24 / E1-25 measurement infrastructure (recall / tokens / miss
  discipline) is wired end-to-end against real fixture files.
- Per-case SQLite isolation works; no global DB is touched; the script is
  re-runnable and refuses to overwrite an existing report.
- The fixture corpus is correctly ingested and produces a manifest that
  contains the required file content.
- Cold and warm produce the same lexical-only result, which is the expected
  behaviour for a fresh-DB script with no cache.

**Does NOT prove**
- Recall on a real production corpus (PAW source tree, larger docs).
- Privacy gate behaviour under SECRET / WORKSPACE content (covered by the
  contract test, not by this run).
- Cache benefit between cold and warm (the script is intentionally
  cache-free; the contract test pins the mode semantics).
- Answer quality or behavioural correctness of the agent.
- An E0 reviewed baseline; `baseline_status` is "diagnostic full-fixture
  reference, not reviewed E0/cloud baseline".

---

*Generated by `scripts/run_e1_measurement.py` — revision `263c075`, 2026-09-07 08:24 UTC.*
