# E1-13 Budget-Bound Derived Views

This document is the **E1-13 deliverable**. It defines
the `bound_by_budget` utility that the runtime uses to
produce the prefix of a derived list that fits a token
+ item budget. The function is a *pure* utility: it
takes a list of items (any type with a `token_estimate`
and a `priority` + `relevance_score`) and a budget, and
returns the prefix that fits, sorted by the same
deterministic key the caller uses.

## Why this contract exists

The E1-09 dependency edges, the E1-10 symbol records,
the E1-11 test associations, and the E1-12 affected
areas are all lists the runtime consumes to build a
context manifest. Each list can grow unboundedly;
without a bound, a project with 10,000 symbols would
push the manifest over its token budget. The E1-13
utility is the *single* function the runtime uses to
clip a derived list to a budget.

The utility is pure: same input → same output, in the
same order. The sort key is the caller's choice; the
utility does not impose a priority order (the caller
passes a pre-sorted list). What the utility *does* do
is respect the budget: stop adding items when either
the token total or the item count would exceed the
budget, and record the excluded items in the returned
"dropped" list with a reason.

## Canonical location

`bound_by_budget` is a new function in
`paw.core.budget` (a new module). The function is a
pure utility: it does not import the runtime, the
database, or the policy gate. It takes Python
primitives; the caller is any consumer that has a list
of items with `token_estimate` and an integer `item`
budget.

## Signature

```python
def bound_by_budget(
    items: Sequence[T],
    *,
    token_budget: int,
    item_budget: int | None = None,
    token_attr: str = "token_estimate",
) -> tuple[list[T], list[T]]:
    """Return ``(kept, dropped)``: the prefix of
    ``items`` that fits the budget, and the items that
    did not fit.

    Items are taken in order. The function stops when
    adding the next item would push the running token
    total over ``token_budget`` or the running item
    count over ``item_budget``.

    The function is pure: it does not mutate ``items``.
    The result ``kept + dropped`` equals ``items`` (same
    elements, same order); no element is silently lost.
    """
```

The two budget dimensions — tokens and items — are
independent. A caller who wants a 12 000-token limit
and a 50-item limit passes `token_budget=12000,
item_budget=50`; the function stops on whichever bound
is hit first.

## Negative cases

| Case | Expected result |
|---|---|
| Empty input | `([], [])`. |
| All items fit | `kept = items`, `dropped = []`. |
| First item does not fit | `kept = []`, `dropped = items`. |
| Middle item does not fit | `kept = items[:i]`, `dropped = items[i:]`. |
| `token_budget <= 0` | `([], items)` (no item can fit). |
| `item_budget = 0` | `([], items)`. |
| Item's `token_attr` is missing or non-int | The item is silently treated as `token_estimate=0` (the function does not raise). |
| Custom `token_attr` | The function reads the attribute named `token_attr` instead of the default `token_estimate`. |
| Determinism | Two calls produce the same result. |

## Phase 4 sync contract

This document is the **source of truth** for E1-13.
The companion contract test
`tests/test_e1_13_budget_bound_contract.py`
enforces the cases above.