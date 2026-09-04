# E1-02 Project-Source Identity, Revision, Content Hash and Invalidation Metadata

This document is the **E1-02 deliverable**. It defines the
project-source identity, revision, content-hash and
invalidation contract that backs every byte of remote
project context the runtime consumes.

## Why this contract exists

The E1 roadmap acceptance criteria (ROADMAP.md) require
that:

- every byte of remote project context is attributable
  to an approved context manifest;
- a decision can identify which project evidence
  supports or contradicts it and detect when a changed
  project revision makes the decision stale.

The `KnowledgeSource` row (`src/paw/knowledge/source.py`)
is the single owner of every project source the runtime
reads from. A decision that cites evidence from
`KnowledgeChunk.content` therefore inherits its
freshness from the source that chunk came from; if the
source is stale, the decision is stale. The contract
below is the typed surface that makes that detection
mechanical.

## Existing fields that already cover the contract

| Concept | Field | Notes |
|---|---|---|
| **identity** | `id` | UUID for the row. The row-level identity used by SQL and the manager. Distinct from the *project* identity below. |
| **content hash** | `checksum` | Content hash for invalidation; the existing field is the right home for the hash. |

Two of the four required concepts (`identity` and
`content hash`) are already present. The remaining two
(`revision` and `invalidation metadata`) are introduced
by E1-02.

## New fields E1-02 adds

The owner remains `KnowledgeSource` (per the E1-01
ownership audit). The fields are:

| Field | Type | Default | Notes |
|---|---|---|---|
| `external_id` | `str` | `""` | Caller-supplied stable project identity (e.g. `"repo:src/paw/core/memory.py:abc123"`). Lets the runtime re-discover the same logical source across runs even when the row UUID changes. Empty when the source is not yet registered against a project revision. |
| `revision` | `str` | `""` | The project revision the source was last synchronized against (e.g. a git commit SHA, a `pyproject.toml` version, a feed item GUID). Distinct from `id` (the row UUID) and from `path` (the source location). Empty when the source is not pinned to a revision. |
| `invalidated_at` | `str \| None` | `None` | UTC ISO-8601 timestamp the source was marked invalid. `None` while the source is still valid. |
| `invalidation_reason` | `str` | `""` | Why the source is invalid. One of the stable codes below. Empty while the source is still valid. |
| `superseded_by` | `str` | `""` | The `id` of the `KnowledgeSource` row that replaced this one. Empty when the source has not been superseded. Lets a query follow the chain of superseded sources to the current head. |

### Stable `invalidation_reason` codes

The reason is a stable string; downstream code and
tests assert on the literal. New codes are added by
editing this list and updating the contract test
together.

| Code | Meaning |
|---|---|
| `""` | Source is valid. (Sentinel; the absence of a reason means the source is fresh.) |
| `checksum_mismatch` | The current `checksum` of the source content differs from the last-recorded `checksum`; the source was edited since the last sync. |
| `revision_changed` | The project revision the source was pinned to is no longer current; the source needs a re-sync. |
| `path_missing` | The source path no longer exists on disk. |
| `superseded` | The source was replaced by a newer one; `superseded_by` is the new source's `id`. |
| `manual` | A reviewer explicitly invalidated the source. |

The codes are intentionally narrow. The contract test
asserts the closed set; adding a new code is a
change-control surface.

## Computed properties

Two read-only helpers make the contract queryable
without leaking persistence details:

- `KnowledgeSource.is_stale` → `True` iff
  `invalidated_at` is set, `superseded_by` is non-empty,
  or `status == KnowledgeSourceStatus.ERROR.value`.
  This is the *minimal* "is the decision still
  trustworthy" predicate the E1 acceptance target asks
  for.
- `KnowledgeSource.is_fresh` → the inverse of
  `is_stale`.

These properties are derived; they are not stored and
do not require schema changes.

## Manager methods (knowledge boundary)

`KnowledgeSourceManager` gains two methods that exercise
the new contract. They are the *only* way a caller
should mark a source invalid; ad-hoc UPDATE statements
against the table bypass the contract.

- `async def mark_invalid(source_id, reason: str,
  superseded_by: str = "") -> KnowledgeSource` —
  atomically sets `invalidated_at` (now), `invalidation_reason`
  and optionally `superseded_by`, and returns the
  updated source. Validates the reason against the
  closed set above; raises `ValueError` on an unknown
  reason.
- `async def list_stale() -> list[KnowledgeSource]` —
  returns every source for which `is_stale` is `True`.
  A reviewer can run this against the runtime to detect
  which project evidence has gone stale.

The current `update_status` method is unchanged; it
remains the canonical owner of the `status` field. The
new `mark_invalid` is intentionally distinct: it
captures *why* the source went invalid, not just that
it is inactive.

## SQL migration (additive only)

The five new columns are added by an idempotent
`ALTER TABLE` block in `src/paw/core/storage.py`'s
`_migrate_schema`. The pattern follows the existing
`skills` migration (storage.py lines 467-488):

```sql
ALTER TABLE knowledge_sources ADD COLUMN external_id TEXT NOT NULL DEFAULT '';
ALTER TABLE knowledge_sources ADD COLUMN revision TEXT NOT NULL DEFAULT '';
ALTER TABLE knowledge_sources ADD COLUMN invalidated_at TEXT;
ALTER TABLE knowledge_sources ADD COLUMN invalidation_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE knowledge_sources ADD COLUMN superseded_by TEXT NOT NULL DEFAULT '';
```

The migration is guarded by `PRAGMA table_info` (the
same pattern `_migrate_schema` uses for `skills`): the
runner checks whether each column already exists and
only runs the `ALTER TABLE` if it does not. The
`CREATE TABLE IF NOT EXISTS knowledge_sources`
statement is updated to declare the columns so a fresh
database gets them without a migration step.

The migration does **not** rewrite existing rows; new
columns are `NOT NULL DEFAULT ''` or nullable, so the
existing `KnowledgeSource` rows load with the new
fields at their default values.

## Boundary exposure (E0-40)

The E0-40 runtime-driven runner is the consumer of
this contract. The boundary that exposes the new
fields is the existing `KnowledgeSource.to_dict()`
method: every field is included in the dict, and the
contract test asserts that. The runtime-driven runner
will read `is_stale` and `revision` from the dict to
decide whether a context manifest is still trustworthy.

## Phase 4 sync contract

This document is the **source of truth** for E1-02.
The companion contract test
`tests/test_e1_02_source_identity_contract.py`
enforces:

- the five new fields exist on `KnowledgeSource`;
- the field defaults match this spec;
- the closed `invalidation_reason` set is enforced
  (an unknown reason raises);
- `is_stale` / `is_fresh` produce the right answer for
  every combination of `invalidated_at`,
  `invalidation_reason`, `superseded_by`, and `status`;
- the SQL migration is additive (no `DROP`, no row
  rewrite);
- `KnowledgeSource.to_dict()` includes the new fields.

A later E1 item that adds another field to
`KnowledgeSource` must update the E1-01 ownership
audit table (`docs/benchmarks/e1/ownership_audit.md`),
this spec, and the contract test
(`tests/test_e1_02_source_identity_contract.py`) in the
same change.