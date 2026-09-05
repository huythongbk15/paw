# E1-28 Decision-Evidence View through Existing Knowledge/Evidence Ownership

This document is the **E1-28 deliverable**. It defines
the contract for the `recent_change_to_evidence` function
that turns a `RecentChange` (E1-12) into a list of
`KnowledgeEvidence` rows the runtime can attach to a
context manifest.

## Why this contract exists

The roadmap E2 acceptance target says: "a decision can
identify which project evidence supports or contradicts
it". The E1-09 / E1-10 / E1-11 / E1-12 contracts give
the runtime the *raw* evidence: dependency edges,
symbol records, test associations, recent changes. The
E1-28 contract is the *join*: it surfaces the recent
change as a `KnowledgeEvidence` row a reviewer can
read in the existing `Knowledge/Evidence` shape.

The contract is *narrow*: the E1-28 contract is the
join, not the analysis. The E2 contract (out of scope
for E1) is the analysis that decides *which* evidence
supports or contradicts a decision.

## Canonical location

`recent_change_to_evidence` is a new function in
`paw.knowledge.changes` (the existing module that owns
`RecentChange`). The function is pure: it takes a
`RecentChange` and a `repo_root` and returns a list of
`KnowledgeEvidence` rows (one per changed file, with
the commit's metadata as the claim's text).

## Signature

```python
def recent_change_to_evidence(
    change: RecentChange,
    *,
    repo_root: Path,
) -> list[KnowledgeEvidence]:
    """Turn a ``RecentChange`` into a list of
    ``KnowledgeEvidence`` rows.

    The function is pure: same input -> same output,
    in the same order. Each row's ``claim`` is the
    commit's first-line message; the ``chunk_id`` is
    the file path (the chunk the evidence is about);
    the ``confidence`` is ``0.5`` (the evidence is
    a *change record*, not a static claim).
    """
```

The function does not write to the database; the caller
is responsible for persisting the rows if desired.

## Phase 4 sync contract

This document is the **source of truth** for E1-28.
The companion contract test
`tests/test_e1_28_decision_evidence_contract.py`
enforces the cases above.