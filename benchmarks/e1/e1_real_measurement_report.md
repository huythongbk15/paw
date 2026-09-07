# E1 Real Measurement Decision Report

**Date**: 2026-09-07
**Revision**: f3ad4ef
**Corpus**: `benchmarks/e0/cases/` (2 representative cases)
**Source**: `/home/huythong/.hybridagent/workspaces/default/src`
**Configuration**: `ContextCompiler` (lexical-only, `auto_attach_embeddings=False`, `ContextBudget(max_tokens=8000)`)

---

## 1. Measurement Results

### Recall (E1-23)

| Case | Mode | Recall | Recalled | Total | Missed |
|------|------|--------|----------|-------|--------|
| architecture_decision_cache | cold | 0.00 | 0 | 2 | file_contains:fixture.txt:value |
| architecture_decision_cache | warm | 0.00 | 0 | 2 | file_contains:fixture.txt:value |
| cross_module_change_constant | cold | 0.00 | 0 | 2 | file_contains:fixture.txt:value |
| cross_module_change_constant | warm | 0.00 | 0 | 2 | file_contains:fixture.txt:value |

### Tokens (E1-24)

| Case | Mode | Baseline | Measured | Reduction |
|------|------|----------|----------|-----------|
| architecture_decision_cache | cold | 4000 | 24 | 0.99 |
| architecture_decision_cache | warm | 4000 | 24 | 0.99 |
| cross_module_change_constant | cold | 3000 | 24 | 0.99 |
| cross_module_change_constant | warm | 3000 | 24 | 0.99 |

### Recall Misses (E1-25)

All misses classified as **retrieval** — the candidate was not in the retrieved set.
None classified as ranking/threshold because no candidates were retrieved at all.

---

## 2. Root Cause Analysis

**The ContextCompiler returns skill content, not knowledge source content.**

When compiling a manifest, the `ContextCompiler` returns 2 items:
- `# Echo Skill` — content: "Echoes back input."
- `# Datetime Skill` — content: "Returns current datetime."

These are **default skills** from the `SkillFabric`. Their properties:
- `reference=None` — no file path reference
- `external_id=""` — empty
- `relevance_score=0.0` — flat, not from retrieval
- `privacy_class=None` — not set

The recall measurement checks `manifest.included` for `external_id` or `reference` matching evidence targets like `benchmarks/e0/fixtures/architecture_decision.txt`. Since skills have neither field, recall is always 0.00.

**This is not a bug — it is the expected behavior of a system with:**
1. No embedding provider (Ollama not available in test environment)
2. Empty knowledge base (no `KnowledgeSource` records for PAW source files)
3. Empty memory store (no `MemoryRecord` records)
4. `auto_attach_embeddings=False` (lexical-only retrieval)

The lexical-only retrieval cannot find relevant files because the `KnowledgeSourceManager` has no records indexed by the lexical matcher.

---

## 3. Gate Decision (E1-27)

**Gate: FAIL**

| Criterion | Threshold | Actual | Result |
|-----------|-----------|--------|--------|
| Recall (any sample) | >= 0.95 | 0.00 | FAIL |
| Recall regression | >= 0.5 | 0.00 | FAIL |
| Warm token reduction | >= 0.30 | 0.99 | PASS |
| Cold/warm recall | >= 0.95 | 0.00 | FAIL |

The **token reduction** is artificially high (0.99) because the measured context is empty (24 tokens), not because the system is efficient. A 99% reduction with 0% recall means the system is **selecting nothing**.

---

## 4. Privacy and Freshness Audit

- **Context items**: 2 (both are skill metadata, not source files)
- **Stale items**: 0 (no source files in context)
- **Gate to cloud_unapproved**: allowed (no SECRET items to block)
- **Privacy risk**: LOW — but only because the context is empty, not because the gate works correctly

**Critical finding**: The privacy gate works correctly in principle (stale sources would be blocked), but it has nothing to gate because the system retrieves no source files. The privacy gap is masked by the retrieval gap.

---

## 5. What's Missing (Path to E1 PASS)

### Required changes for measurement gate PASS:

| Priority | Item | Effort | Description |
|----------|------|--------|-------------|
| **P0** | Knowledge source ingestion | 1h | Populate `KnowledgeSourceManager` with PAW source files |
| **P0** | Embedding provider | 1h | Start Ollama or use `LocalEmbeddingProvider` for semantic retrieval |
| **P1** | Recall fix | 1h | `measure_recall` must handle skills as valid evidence targets |
| **P1** | Baseline tokens | 1h | Review and set baseline from actual compiler output |
| **P2** | Cold/warm cache isolation | 2h | Prove warm compilation reuses cached results |
| **P2** | Answer quality assessment | 3h | Evaluate if retrieved context answers the query correctly |

### The gap is NOT in the code — it's in the setup:

1. **No knowledge base**: The `KnowledgeSourceManager` was empty. Need to ingest PAW source files.
2. **No embeddings**: Ollama is not running. The lexical-only retrieval is insufficient.
3. **Recall checks skills, not sources**: `measure_recall` looks for `external_id`/`reference`, but the compiler returns skills with `reference=None`.

---

## 6. Decision

**E1 Measurement Gate: FAIL**

**Reason**: The system does not retrieve relevant source files. Recall is 0.00 because the knowledge base is empty and the lexical-only retrieval cannot find PAW source files.

**This measurement is valid and useful.** It proves:
1. The E1-27 measurement gate works correctly (it correctly identifies FAIL)
2. The `measure_recall` function correctly detects missing content
3. The privacy gate works in principle but has nothing to gate
4. The system needs embeddings and a populated knowledge base to function

**Recommendation**: 
1. Start Ollama (or enable `LocalEmbeddingProvider`) 
2. Ingest PAW source files into `KnowledgeSourceManager`
3. Re-run measurement to get real recall numbers
4. Set reviewed baseline tokens from the first successful run
5. Then E1 measurement gate can be evaluated fairly

**This report should NOT be confused with a previous run's results.** It was generated from a clean state with revision f3ad4ef, no cached embeddings, and an empty knowledge base.

---

*Generated by `run_e1_measurement.py` — revision f3ad4ef, 2026-09-07*
