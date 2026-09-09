# E2-35: Stale Derived Records Invalidated After Source Changes

## Contract

When a source is invalidated or its checksum changes, all derived records
(chunks, evidence, citations) must be marked stale atomically. The runtime
must reject stale records during retrieval so they never reach the context
compiler.

## Boundary rule

* `KnowledgeSourceManager.invalidate_derived_rows` is the single authority for
  marking derived rows stale.
* After invalidation, `is_stale` on every affected `KnowledgeChunk`,
  `KnowledgeEvidence`, and `KnowledgeCitation` must be `True`.
* After re-ingest with a new checksum, `clear_derived_stale` restores fresh
  status.
* Stale records are filtered out by `ContextCompiler` candidates.

## Verification

* D2: adversarial tests prove stale cascade + runtime rejection + recovery.

