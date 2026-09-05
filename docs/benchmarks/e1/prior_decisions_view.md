# E1-31 Retrieve Relevant Prior Decisions and Verification History with Provenance

This document is the **E1-31 deliverable**. It defines
the contract for `retrieve_prior_decisions`, the
function that surfaces the prior decisions + verification
history a reviewer can cite when reasoning about a new
change.

## Why this contract exists

The roadmap E2 acceptance target says: "expose project
revision, current behavior, constraints, relevant
decisions and verification history as source-backed
inputs to the research decision". E1-09 / E1-10 / E1-11
/ E1-12 give the runtime the *raw* views; E1-28 gives
the join. E1-31 is the *retrieval*: a function that,
given a query (a symbol name, a file path, a recent
change), returns the prior decisions + verification
history that match the query, with provenance the
reviewer can cite.

The contract is *narrow*: the retrieval is keyword +
symbol-name match, not an LLM-based semantic search. The
heuristic is the E1-11 + E1-12 join; a future E2 item
can add semantic retrieval on top.

## Canonical location

`retrieve_prior_decisions` is a new function in
`paw.knowledge.history` (a new module). The function
is pure: same input → same output, in the same order.
The caller passes a query + a list of recent changes
+ a list of test associations; the function returns
the matches with provenance.

## Signature

```python
def retrieve_prior_decisions(
    query: str,
    *,
    recent_changes: Iterable[RecentChange],
    test_links: Iterable[TestLink],
    max_count: int = 20,
) -> list[PriorDecision]:
    """Surface the prior decisions + verification
    history that match ``query``.

    The heuristic is keyword + symbol-name match:
    the query is matched against the commit message
    (recent_changes) and the test's qualified name
    (test_links). A match is added to the result; the
    result is sorted by date (most-recent first) and
    capped at ``max_count``.
    """
```

## `PriorDecision` shape

```python
@dataclass(frozen=True)
class PriorDecision:
    """One prior decision the runtime surfaces for
    review.

    ``provenance`` is the source the decision came
    from: ``"recent_change"`` for a matched commit,
    ``"test_link"`` for a matched test association.
    """
    kind: str
    date: str
    description: str
    provenance: str
    commit_sha: str = ""
    test_qualified_name: str = ""
    source_qualified_name: str = ""
```

## Phase 4 sync contract

This document is the **source of truth** for E1-31.
The companion contract test
`tests/test_e1_31_prior_decisions_contract.py`
enforces the cases above.