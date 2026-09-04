# E1-07 Stale Derived Records: Source-Change Invalidation

This document is the **E1-07 deliverable**. It defines
the contract that proves every derived record (chunk,
evidence, citation) is invalidated when its source
becomes stale — so a context query against a stale
source cannot return false evidence.

## Why this contract exists

The E1-02 / E1-06 contract lets the runtime mark a
`KnowledgeSource` invalid with a closed reason
(`checksum_mismatch`, `path_missing`, `revision_changed`,
`superseded`, `manual`). The `KnowledgeChunk`,
`KnowledgeEvidence`, and `KnowledgeCitation` tables
are *derived* from the source: a chunk is a slice of
the source content, an evidence is a claim about a
chunk, a citation is a reference from a task to an
evidence.

If a source is marked invalid but its chunks / evidence
/ citations are not, a future `KnowledgeIndex.search_chunks`
call would happily return stale evidence that no longer
reflects the on-disk content. That breaks the E1
acceptance target "a decision can detect when a
changed project revision makes the decision stale".

The contract below is the eager-recursion
invalidation: marking a source invalid also marks
its derived rows stale in the same atomic call.

## Canonical location

The contract is implemented in
`paw/knowledge/source.py` (the existing module that
owns `KnowledgeSource` and `KnowledgeSourceManager`).
A new manager method
`KnowledgeSourceManager.invalidate_derived_rows(source_id)`
does the recursion; a small set of helper queries on
`KnowledgeChunkStore`, `KnowledgeEvidenceStore`, and
`KnowledgeCitationStore` does the actual marking.

## Schema additions

Three new columns, one on each derived table. The
columns are additive (`TEXT NULL`); existing rows load
with `stale_at = NULL` and are considered fresh.

```sql
ALTER TABLE knowledge_chunks ADD COLUMN stale_at TEXT;
ALTER TABLE knowledge_chunks ADD COLUMN stale_reason TEXT NOT NULL DEFAULT '';

ALTER TABLE evidence ADD COLUMN stale_at TEXT;
ALTER TABLE evidence ADD COLUMN stale_reason TEXT NOT NULL DEFAULT '';

ALTER TABLE citations ADD COLUMN stale_at TEXT;
ALTER TABLE citations ADD COLUMN stale_reason TEXT NOT NULL DEFAULT '';
```

The two columns mirror the E1-02 source-invalidation
contract at the derived-row level: a row is fresh iff
`stale_at IS NULL`; a row is stale iff `stale_at IS
NOT NULL`. The `stale_reason` is one of the same
`INVALID_REASONS` codes the source uses; the recursion
passes the source's reason down so a reviewer can
trace "this evidence is stale because its source had a
checksum mismatch".

`KnowledgeChunk.to_dict` / `KnowledgeEvidence.to_dict`
/ `KnowledgeCitation.to_dict` include the new fields.
The contract test pins the boundary.

## Manager method

```python
async def invalidate_derived_rows(
    self,
    source_id: str,
    *,
    reason: str,
) -> int:
    """Mark every chunk / evidence / citation that
    derives from ``source_id`` as stale.

    The function recursively walks the
    chunk→evidence→citation chain in a single SQLite
    transaction. The recursion is breadth-first and
    iterates over the rows that need to change; the
    function never reads a row that is already stale
    (the recursion is a no-op for those).

    The return value is the number of rows newly
    marked stale (i.e. the count of rows whose
    ``stale_at`` was NULL before this call). A
    re-invocation on the same source returns 0.

    The function refuses an unknown reason with
    ``ValueError``; the closed reason set is the same
    E1-02 ``INVALID_REASONS`` set the source
    invalidation uses.
    """
```

The new method is called by `mark_invalid` and
`mark_path_missing` automatically: every time a source
is marked invalid, its derived rows are too. The
contract test pins the auto-cascade behavior; a
reviewer who marks a source invalid can be sure the
derived rows are stale.

## Boundary exposure (E1-26 + E1-08 + E1-17)

The cascade is consumed by:

- the E1-26 negative-control test (the "stale source
  produces no context" guarantee);
- the E1-08 bounded tree view (which must skip stale
  chunks);
- the E1-17 manifest inspector (which must show the
  stale reason for every included chunk).

The boundary is the `invalidate_derived_rows` method
itself; a reviewer who calls it on a known source can
be sure the derived rows are stale in the same
transaction.

## Phase 4 sync contract

This document is the **source of truth** for E1-07.
The companion contract test
`tests/test_e1_07_stale_derived_contract.py` enforces
the cascade (chunk + evidence + citation), the
`stale_at` boundary on every derived dataclass, the
`to_dict` exposure, and the manager-method auto-cascade.

A later E1 item that adds another derived row type
(e.g. `KnowledgeSummary`) must update both the schema
and the cascade in the same change.