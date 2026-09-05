# E1-33 Invalidate or Re-Evaluate Decision Input When Project Revision Changes

This document is the **E1-33 deliverable**. It defines
the contract for `re_evaluate_on_revision`, the
function that flags a decision as `stale` when the
project revision it was pinned to no longer matches
HEAD.

## Why this contract exists

The E1-02 / E1-06 / E1-29 contracts pin a decision
(recommendation, observation, constraint) to a
project revision: the reviewer wrote "the budget
allocator is X" on commit `abc123`; the runtime
caches the decision + the revision. When the project
moves forward, the cached decision may be wrong.

The E1-33 contract is the *invalidation*: a function
that, given a `revision` and a list of `RecentChange`
records, returns a `ReEvaluationResult` whose
`stale` field is True when the revision no longer
matches HEAD. The caller (the E1-31 history view, a
future E2 readiness check) re-evaluates when `stale`
is True.

The contract is *narrow*: the function flags staleness
by comparing revisions; it does not re-derive the
decision. A future E2 item is the re-derivation.

## Canonical location

`re_evaluate_on_revision` is a new function in
`paw.knowledge.history` (the existing module that
owns `retrieve_prior_decisions`). The function is
pure: same input → same output.

## Signature

```python
async def re_evaluate_on_revision(
    *,
    pinned_revision: str,
    current_revision: str,
    recent_changes: Iterable[RecentChange],
) -> ReEvaluationResult:
    """Flag a decision as stale when ``pinned_revision``
    is no longer reachable from ``current_revision``.

    The heuristic: if ``pinned_revision`` does not
    appear in the recent-changes' ancestor chain
    within ``current_revision``, the decision is
    stale. A simple implementation: if
    ``pinned_revision != current_revision`` AND
    ``pinned_revision`` is not in the first N
    recent-changes' SHA list, the decision is stale.
    """
```

## `ReEvaluationResult` shape

```python
@dataclass(frozen=True)
class ReEvaluationResult:
    pinned_revision: str
    current_revision: str
    stale: bool
    reason: str
```

`reason` is a closed set: `"revision_match"`,
`"revision_mismatch"`, `"pinned_revision_not_found"`.

## Phase 4 sync contract

This document is the **source of truth** for E1-33.
The companion contract test
`tests/test_e1_33_revision_invalidation_contract.py`
enforces the cases above.