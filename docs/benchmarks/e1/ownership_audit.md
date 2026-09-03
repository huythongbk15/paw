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

## Memory (`src/paw/core/memory.py`)

`MemoryStore` is the single owner. All memory record
fields live here:

| Field | Type | Owner | Notes |
|---|---|---|---|
| `id` | `str` | `MemoryStore` | UUID; immutable. |
| `project_id` | `str \| None` | `MemoryStore` | Scope identifier (not security tenant; see `docs/ARCHITECTURE.md` Tenancy boundary). |
| `task_id` | `str \| None` | `MemoryStore` | Back-reference; nullable. |
| `memory_type` | `MemoryType` (enum) | `MemoryStore` | `user_fact` / `project_decision` / `preference` / `error_pattern` / `context_hint`. |
| `content` | `str` | `MemoryStore` | The remembered text. |
| `summary` | `str` | `MemoryStore` | Reviewer-readable short label. |
| `confidence` | `float` | `MemoryStore` | `[0.0, 1.0]`; default 0.5. |
| `source` | `str` | `MemoryStore` | Origin tag (e.g. `user_input`, `cli_init`). |
| `created_at` | `datetime` | `MemoryStore` | UTC. |
| `access_count` | `int` | `MemoryStore` | Bumped on `get_by_*` / `search`. |
| `metadata` | `JSON` | `MemoryStore` | Free-form, but the contract is "no Memory field lives here"; metadata is for application-specific tags. |

The `AdvancedMemoryRetriever` (hybrid lexical + semantic
scoring) is the second concern: it reads Memory but does
not own fields. E1 may add a new scoring algorithm
without changing Memory.

## Knowledge (`src/paw/knowledge/`)

`KnowledgeIndex` is the single owner. Five modules
cooperate; each owns one row family:

| Module | Owns | Fields it may add |
|---|---|---|
| `source.py` | `KnowledgeSource` | `id`, `kind`, `uri`, `revision`, `created_at`, `metadata` |
| `chunk.py` | `KnowledgeChunk` | `id`, `source_id`, `content`, `span_start`, `span_end`, `metadata`, `created_at` |
| `evidence.py` | `KnowledgeEvidence` | `id`, `chunk_id`, `claim`, `confidence`, `metadata`, `created_at` |
| `citation.py` | `KnowledgeCitation` | `id`, `evidence_id`, `context`, `position`, `metadata`, `created_at` |
| `index.py` | `KnowledgeIndex` (the search layer) | adds no fields of its own; reads from the four above |
| `normalization.py` | the boundary function `normalize_knowledge_result` | the boundary itself is owned here; no new fields |

A new field is a contract change for **one** of the
five row modules plus the boundary (`normalization.py`).
The E1 reviewer must update the boundary in lock-step
or the contract breaks.

## Context Compiler (`src/paw/core/context_compiler.py`)

`ContextCompiler` is the single owner of the
`TaskContext` shape. The context compiler composes
candidates from Memory, Knowledge, Skills, the Ledger,
and the Session; it does not own their fields. The
compiler's own output fields are:

| Field on `TaskContext` (or its supporting types) | Owner | Notes |
|---|---|---|
| `task_id` | `ContextCompiler` | The Task whose context is being compiled. |
| `budget` | `ContextCompiler` | `ContextBudget` (max_tokens, max_fragments, max_sources, max_content_length, priority_weights). |
| `plan` | `ContextCompiler` | `ContextPlan` (sources list, priorities, flags). |
| `fragments` | `ContextCompiler` | The selected `ContextFragment` list. |
| `explain_mode` | `ContextCompiler` | Boolean toggle for debug output. |

The candidates the compiler *retrieves* (one per
Memory record, one per Knowledge chunk, etc.) carry the
owner module's fields; the compiler wraps them in
`ContextCandidate` with `relevance_score`, `reason`,
`token_estimate`, `priority`, `metadata`. Those wrapper
fields are the compiler's; the underlying fields are
the owner's.

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
