# E1-14 Persist Derived Records through Existing Knowledge Ownership

This document is the **E1-14 deliverable**. It defines
the contract for persisting the E1-09 / E1-10 / E1-11
derived views through the existing `Knowledge` ownership
boundary, plus the read-side helpers that surface the
persisted records back to a caller.

## Why this contract exists

The E1-09 dependency edges, the E1-10 symbol records,
and the E1-11 test associations are pure AST-derived
data. The runtime calls `extract_dependencies` /
`extract_symbols` / `associate_tests` on demand; the
result is in-memory. After a session close + reopen,
the runtime re-derives the views from the source files
on disk.

The E1-14 contract is a small step in the direction of
"the derived view is a first-class persisted record".
The contract reuses the existing `Knowledge` ownership
(no new table); the read-side helpers expose the
derived records through `KnowledgeIndex`. The E1-15
proof demonstrates that the records survive a session
close + reopen.

The contract is intentionally narrow: the E1-14
contract is about *round-trip persistence*, not
*content versioning*. The version (the source-revision
provenance) is the caller's responsibility; the
persisted record carries the `external_id` + `revision`
the caller supplied when it stored the record.

## Canonical location

The persistence helpers live in
`paw.knowledge.index.KnowledgeIndex` (the existing
module that owns the read-side API). The persisted
state is the existing `metadata` JSON column on the
`knowledge_sources` table (E1-02 field). The contract
adds three new methods on `KnowledgeIndex`:

- `save_derived_view(source_id, view_kind, view_data)`:
  persist a derived view (a dict) under the source's
  `metadata` JSON, keyed by `view_kind`.
- `load_derived_view(source_id, view_kind) -> dict`:
  load the persisted view; returns `{}` when no view
  has been stored yet.
- `list_derived_views(source_id) -> tuple[str, ...]`:
  list the `view_kind`s persisted for a source.

The `view_kind` is one of `"symbols"`, `"test_links"`,
`"dependency_edges"`, `"recent_changes"`, or
`"affected_areas"` (the E1-09 / E1-10 / E1-11 / E1-12
view names). The contract is open: a future E2 item
that adds a new view registers a new `view_kind` and
the round-trip works the same way.

## Phase 4 sync contract

This document is the **source of truth** for E1-14.
The companion contract test
`tests/test_e1_14_derived_persistence_contract.py`
enforces the round-trip + close/reopen invariants
that E1-15 builds on.