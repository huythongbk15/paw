"""PAW Core — budget-bound view utility (E1-13).

``bound_by_budget`` is a *pure* utility that clips a
list of items to a token + item budget. The function
is the single source of truth for "fit a derived list
into a manifest": a caller who has a list of E1-10
symbols, E1-11 test associations, E1-12 affected
areas, or any other items with a `token_estimate`
attribute, calls this function to get the
budget-conformant prefix.

The function is pure: same input -> same output, in
the same order. The caller is responsible for sorting
the input in the order the budget should respect; the
function does not impose a priority order.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def _get_token(item: object, attr: str) -> int:
    """Read the item's token estimate. A missing /
    non-int attribute is treated as 0 (the function
    never raises; the budget utility is permissive so
    a caller can pass a heterogeneous list)."""
    value = getattr(item, attr, 0)
    if not isinstance(value, int):
        return 0
    return max(0, value)


def bound_by_budget[T](
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
    if token_budget <= 0 or item_budget == 0:
        return ([], list(items))
    kept: list[T] = []
    dropped: list[T] = []
    running_tokens = 0
    running_items = 0
    for item in items:
        item_tokens = _get_token(item, token_attr)
        if (
            running_tokens + item_tokens > token_budget
            or (item_budget is not None and running_items + 1 > item_budget)
        ):
            dropped.append(item)
            continue
        kept.append(item)
        running_tokens += item_tokens
        running_items += 1
    return kept, dropped


__all__ = ["bound_by_budget"]
