# E1-32 Record Claim Status, Confidence and Freshness at the Evidence Boundary

This document is the **E1-32 deliverable**. It defines
the claim-status, confidence, and freshness fields the
runtime records on every `KnowledgeEvidence` row at
the boundary.

## Why this contract exists

The roadmap E2 acceptance target says: "represent
claim status, confidence and freshness without promoting
model summaries or external material to fact". E1-03
gave the runtime a privacy class; E1-32 gives the
runtime a *truth* class. Every evidence row carries
three fields a reviewer inspects:

- **status** — `unverified` / `verified` / `disputed` /
  `stale`. A `verified` evidence is one a human (or a
  test) has confirmed; `unverified` is the default.
- **confidence** — the runtime's belief the evidence is
  correct (the E1-09 / E1-10 / E1-11 functions already
  use this; the contract pins the field).
- **freshness** — the timestamp the evidence was last
  verified (a reviewer who sees a stale evidence can
  decide to re-verify).

## Canonical location

`paw/knowledge/evidence` gains two new fields on the
`KnowledgeEvidence` dataclass: `status` (default
`"unverified"`) and `freshness` (default `None`,
ISO-8601 timestamp when set). The existing `confidence`
field is unchanged.

## Closed set of status codes

```python
EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {"unverified", "verified", "disputed", "stale"}
)
```

The closed set is the change-control surface; a new
status code requires updating the contract test.

## Phase 4 sync contract

This document is the **source of truth** for E1-32.
The companion contract test
`tests/test_e1_32_claim_status_contract.py`
enforces the cases above.