# E1-17: Record Include Reason, Source/Hash, Score, Privacy, Token Estimate Per Item

This document is the **E1-17 deliverable**.

## Contract

Every candidate that the runtime **includes** in a `ContextManifest.included`
tuple must carry a per-item record with five observable attributes:

| Field              | Source on `ContextCandidate`       | Required? |
|--------------------|------------------------------------|-----------|
| Include reason     | `reason` (non-empty string)        | Yes       |
| Source / hash      | `source_hash` (SHA-256)            | Yes when the source data is available; defaults to `""` |
| Score              | `relevance_score` (float 0.0–1.0)  | Yes       |
| Privacy class      | `privacy_class` (PrivacyClass enum) | Yes when available; defaults to `None` (treated as `INTERNAL` by the E1-03 gate) |
| Token estimate     | `token_estimate` (int)             | Yes       |

## Why this contract exists

The E1-16 context manifest introduces `ContextCandidate` with the
`source_hash`, `external_id`, `revision`, and `privacy_class` fields
(the "E1-17 per-item record"). The E1-17 contract is the **wiring**:
these fields must be populated — not merely declared — wherever
source-level data is available at retrieval time. A reviewer who
inspects a manifest must be able to trace every included item back
to its source revision and privacy class.

## Implementation

- **Knowledge candidates** (`_retrieve_knowledge_candidates`): the
  runtime fetches the owning `KnowledgeSource` from its
  `source_id` and copies `checksum` → `source_hash`,
  `external_id`, `revision`, and `privacy_class`.
- **Memory candidates** (`_retrieve_memory_candidates`): the
  runtime copies `privacy_class` from the `MemoryRecord`.
- **Skill / ledger / session / repository candidates**: these
  sources do not carry revision identity; the E1-17 fields
  default to `""` / `None`.

The contract test in `tests/test_e1_17_inclusion_contract.py`
pins: (1) every included candidate has a non-empty `reason`;
(2) knowledge candidates carry a non-empty `source_hash` when
the source is available; (3) `relevance_score` is in `[0, 1]`;
(4) `token_estimate` is a non-negative integer; (5) the privacy
class is set on knowledge + memory candidates.

## Phase 4 sync contract

This document is the **source of truth** for E1-17.
