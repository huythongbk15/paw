# E1-01 Ownership Audit

This document is the **E1-01 deliverable**. It records
which module owns every existing field in Memory,
Knowledge, and the Context Compiler, so the E1 reviewer
knows which module to add a new field to without
creating a second owner.

The rule from
[`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) is "one
canonical type and implementation per owned concept"
(Safety invariant #1). E1 inherits this rule; the
audit below is the source of truth for which module
implements which concept.

This audit is **regenerated from source** whenever a
new field lands in one of the modules below. The
companion contract test
[`tests/test_e1_ownership_audit_contract.py`](../../tests/test_e1_ownership_audit_contract.py)
pins the audit tables to the actual dataclass fields;
if the audit drifts from the source, the test fails
and the audit is the artifact that must be updated.

## Memory (`src/paw/core/memory.py`)

`MemoryStore` is the single owner. The `MemoryRecord`
dataclass declares 16 fields; the SQL table
`memory_records` declares the same 14 persistent
columns (the dataclass adds `keywords` and
`last_accessed` which are JSON/nullable on the SQL
side and do not need a dedicated column):

| Field | Type | Owner | Notes |
|---|---|---|---|
| `id` | `str` | `MemoryStore` | UUID; immutable. |
| `project_id` | `str \| None` | `MemoryStore` | Scope identifier (not security tenant; see `docs/ARCHITECTURE.md` Tenancy boundary). |
| `task_id` | `str \| None` | `MemoryStore` | Back-reference; nullable. |
| `memory_type` | `MemoryType` (enum) | `MemoryStore` | `user_fact` / `project_decision` / `preference` / `error_pattern` / `context_hint`. |
| `content` | `str` | `MemoryStore` | The remembered text. |
| `summary` | `str` | `MemoryStore` | Reviewer-readable short label. |
| `keywords` | `list[str]` | `MemoryStore` | Persisted as a JSON string in the `keywords` SQL column. |
| `metadata` | `JSON` | `MemoryStore` | Free-form, but the contract is "no Memory field lives here"; metadata is for application-specific tags. |
| `confidence` | `float` | `MemoryStore` | `[0.0, 1.0]`; default 0.5. |
| `created_at` | `datetime` | `MemoryStore` | UTC. |
| `updated_at` | `datetime` | `MemoryStore` | UTC; bumped by `MemoryRecord.touch()`. |
| `last_accessed` | `datetime \| None` | `MemoryStore` | Nullable; bumped on `get_by_*` / `search`. |
| `access_count` | `int` | `MemoryStore` | Bumped on `get_by_*` / `search`. |

The `AdvancedMemoryRetriever` (hybrid lexical + semantic
scoring) is the second concern: it reads Memory but does
not own fields. E1 may add a new scoring algorithm
without changing Memory.

## Knowledge (`src/paw/knowledge/`)

`KnowledgeIndex` is the single owner. Four row modules
plus the boundary module cooperate; each owns one row
family:

### `source.py` — `KnowledgeSource` (12 fields)

| Field | Type | Owner | Notes |
|---|---|---|---|
| `id` | `str` | `KnowledgeSource` | UUID; immutable. |
| `name` | `str` | `KnowledgeSource` | Human-readable label. |
| `type` | `KnowledgeSourceType` (enum) | `KnowledgeSource` | `file` / `url` / `database` / `api` / `manual` / `feed` / `inbox`. |
| `path` | `str` | `KnowledgeSource` | Local path or URI; default empty for non-file sources. |
| `metadata` | `JSON` | `KnowledgeSource` | Source-specific tags; "no Knowledge field lives in metadata" rule. |
| `status` | `KnowledgeSourceStatus` (enum) | `KnowledgeSource` | `active` / `inactive` / `syncing` / `error` / `archived`. |
| `chunk_count` | `int` | `KnowledgeSource` | Cached count of chunks; maintained by `KnowledgeSourceManager`. |
| `last_sync` | `datetime \| None` | `KnowledgeSource` | Nullable. |
| `checksum` | `str` | `KnowledgeSource` | Content hash for invalidation. |
| `created_at` | `datetime` | `KnowledgeSource` | UTC. |
| `updated_at` | `datetime` | `KnowledgeSource` | UTC. |

### `chunk.py` — `KnowledgeChunk` (7 fields)

| Field | Type | Owner | Notes |
|---|---|---|---|
| `id` | `str` | `KnowledgeChunk` | UUID. |
| `source_id` | `str` | `KnowledgeChunk` | FK to `knowledge_sources.id`. |
| `content` | `str` | `KnowledgeChunk` | The chunk text. |
| `span_start` | `int` | `KnowledgeChunk` | Byte offset into source. |
| `span_end` | `int` | `KnowledgeChunk` | Byte offset into source. |
| `metadata` | `JSON` | `KnowledgeChunk` | Chunk-specific tags. |
| `created_at` | `datetime` | `KnowledgeChunk` | UTC. |

### `evidence.py` — `KnowledgeEvidence` (6 fields)

| Field | Type | Owner | Notes |
|---|---|---|---|
| `id` | `str` | `KnowledgeEvidence` | UUID. |
| `chunk_id` | `str` | `KnowledgeEvidence` | FK to `knowledge_chunks.id`. |
| `claim` | `str` | `KnowledgeEvidence` | The claim text. |
| `confidence` | `float` | `KnowledgeEvidence` | `[0.0, 1.0]`; default 0.5. |
| `metadata` | `JSON` | `KnowledgeEvidence` | Evidence-specific tags. |
| `created_at` | `datetime` | `KnowledgeEvidence` | UTC. |

### `citation.py` — `KnowledgeCitation` (7 fields)

| Field | Type | Owner | Notes |
|---|---|---|---|
| `id` | `str` | `KnowledgeCitation` | UUID. |
| `task_id` | `str` | `KnowledgeCitation` | FK to the citing task. |
| `evidence_id` | `str` | `KnowledgeCitation` | FK to `knowledge_evidence.id`. |
| `context` | `str` | `KnowledgeCitation` | Optional surrounding context. |
| `position` | `int` | `KnowledgeCitation` | Ordering within the citation list. |
| `metadata` | `JSON` | `KnowledgeCitation` | Citation-specific tags. |
| `created_at` | `datetime` | `KnowledgeCitation` | UTC. |

### `index.py` and `normalization.py` — no owned fields

`KnowledgeIndex` adds no fields of its own; it reads
from the four row modules above. `KnowledgeSearchResult`
is a transient search-layer result type (5 fields:
`chunk_id`, `content`, `source_id`, `score`,
`evidence_count`, `citations`, `metadata`) and is not
persisted. `normalize_knowledge_result` is the boundary
function — it owns the boundary itself, not a row
family.

A new field is a contract change for **one** of the
four row modules plus the boundary (`normalization.py`).
The E1 reviewer must update the boundary in lock-step
or the contract breaks.

## Context Compiler (`src/paw/core/context_compiler.py`)

### `TaskContext` (`src/paw/core/context.py`)

The `TaskContext` dataclass is the compiler's output
container; it owns these fields:

| Field on `TaskContext` | Type | Owner | Notes |
|---|---|---|---|
| `task_id` | `str` | `TaskContext` | The Task whose context is being compiled. |
| `fragments` | `list[ContextFragment]` | `TaskContext` | The selected fragment list (ordered by `relevance_score` desc). |
| `summary` | `str` | `TaskContext` | Reviewer-readable summary of sources. |
| `token_count` | `int` | `TaskContext` | Sum of fragment tokens (word/3 heuristic). |
| `budget` | `ContextBudget` | `TaskContext` | The budget that bounded the selection. |
| `exceeded` | `bool` | `TaskContext` | `True` if a candidate was dropped because of budget. |
| `explain_mode` | `bool` | `TaskContext` | Boolean toggle for debug output. |
| `created_at` | `datetime` | `TaskContext` | UTC. |

### `ContextBudget` (`src/paw/core/context.py`)

The `ContextBudget` dataclass owns the budget constraints:

| Field | Type | Owner | Notes |
|---|---|---|---|
| `max_tokens` | `int` | `ContextBudget` | Token budget (default 12000). |
| `max_fragments` | `int` | `ContextBudget` | Fragment count ceiling (default 50). |
| `max_sources` | `int` | `ContextBudget` | Distinct source ceiling (default 10). |
| `max_content_length` | `int` | `ContextBudget` | Character length ceiling per fragment (default 50000). |
| `dedup_threshold` | `float` | `ContextBudget` | Similarity threshold for cross-source dedup (default 0.85). |
| `dedup_enabled` | `bool` | `ContextBudget` | Whether to apply dedup (default True). |
| `priority_weights` | `dict[str, float]` | `ContextBudget` | Per-source priority weights. |
| `token_estimator` | `TokenEstimator` | `ContextBudget` | Pluggable token estimator. |

### `ContextPlan` and `ContextCompiler` (`src/paw/core/context_compiler.py`)

`ContextPlan` owns the *plan* fields
(`task_id`, `query`, `token_budget`, `sources`,
`priorities`, `include_*` flags, `selected_skills`,
`skill_categories`, `max_skills`, `knowledge_query`,
`max_knowledge_chunks`, `repo_paths`, `created_at`).
`ContextCompiler` owns the *compiler instance* fields
(`budget`, `embedding_provider`, `auto_attach_embeddings`,
`_embedding_resolved`, `_token_estimator`,
`_memory_retriever`).

The compiler wraps retrieved items in `ContextCandidate`
with `relevance_score`, `reason`, `token_estimate`,
`priority`, `metadata`. Those wrapper fields are the
compiler's; the underlying fields (MemoryRecord,
KnowledgeChunk, etc.) are the owner's.

## New fields E1 may add

For each candidate new field, the E1 reviewer must
name:

1. The owner module (one of the rows above).
2. The column added (or the JSON path, for `metadata`).
3. The migration that adds the column to existing rows
   (no `CREATE TABLE` outside `src/paw/core/storage.py`).
4. The boundary that exposes the field to the runner
   (`paw.bench.run_case` or the future runtime-driven
   runner).
5. A test that pins the field's contract.

The E1-04 spec ("deterministic include/exclude rules for
repository files") is the first place E1 is likely to
add a field. The natural owner is the source module
(`source.py`); the natural field is `include_patterns`
or `exclude_patterns` (a `list[str]` per source). A
column-add migration must land with the field.

## Phase 4 sync contract

This document is the **source of truth** for E1-01. A
later E1 item that adds a new field must update this
table in the same change; if the new field lives in a
module that is not listed above, the change is
introducing a new owner and the change is wrong.

The companion contract test
`test_e1_ownership_audit_contract.py` enforces that
every dataclass field listed in this audit is still
present on the corresponding dataclass; a missing
field fails the test and the audit must be regenerated
from source before the next E1 item lands.