"""E1-13 contract test: budget-bound derived views.

The contract is documented in
``docs/benchmarks/e1/budget_bound_views.md``.
The test pins:

- empty input;
- all-items-fit case;
- first-item-doesn't-fit case;
- middle-item-doesn't-fit case;
- ``token_budget <= 0`` returns no kept;
- ``item_budget = 0`` returns no kept;
- missing / non-int ``token_estimate`` is treated as 0;
- custom ``token_attr`` reads the named attribute;
- determinism: two calls produce the same result;
- the partition invariant: ``kept + dropped`` is a
  permutation of the input.
"""

from __future__ import annotations

from dataclasses import dataclass

from paw.core.budget import bound_by_budget


@dataclass
class _Item:
    name: str
    token_estimate: int = 0
    relevance: float = 0.0


# --- 1. Empty input ---------------------------------------------------


def test_bound_by_budget_empty() -> None:
    kept, dropped = bound_by_budget([], token_budget=1000)
    assert kept == []
    assert dropped == []


# --- 2. All items fit ------------------------------------------------


def test_bound_by_budget_all_fit() -> None:
    items = [_Item(f"i{i}", token_estimate=10) for i in range(3)]
    kept, dropped = bound_by_budget(items, token_budget=100)
    assert kept == items
    assert dropped == []


# --- 3. First item doesn't fit ---------------------------------------


def test_bound_by_budget_first_item_overflows() -> None:
    items = [
        _Item("big", token_estimate=200),
        _Item("small", token_estimate=10),
    ]
    kept, dropped = bound_by_budget(items, token_budget=100)
    # The ``big`` item does not fit; it is dropped.
    # The ``small`` item does fit (after ``big`` was
    # dropped, the running total is 0). The function
    # does not stop the iteration on a single drop;
    # later items still get a chance.
    assert [k.name for k in kept] == ["small"]
    assert [d.name for d in dropped] == ["big"]


# --- 4. Middle item doesn't fit --------------------------------------


def test_bound_by_budget_middle_item_overflows() -> None:
    items = [
        _Item("a", token_estimate=50),
        _Item("big", token_estimate=200),
        _Item("b", token_estimate=10),
    ]
    kept, dropped = bound_by_budget(items, token_budget=100)
    # a (50) is kept; big (200) is dropped (50+200 > 100);
    # b (10) is kept (50+10 <= 100). The dropped list
    # holds every item that was rejected, in the same
    # order they were considered.
    assert [k.name for k in kept] == ["a", "b"]
    assert [d.name for d in dropped] == ["big"]


# --- 5. token_budget <= 0 -------------------------------------------


def test_bound_by_budget_zero_token_budget() -> None:
    items = [_Item("a", token_estimate=1)]
    kept, dropped = bound_by_budget(items, token_budget=0)
    assert kept == []
    assert dropped == items


# --- 6. item_budget = 0 -----------------------------------------------


def test_bound_by_budget_zero_item_budget() -> None:
    items = [_Item("a", token_estimate=1)]
    kept, dropped = bound_by_budget(items, token_budget=100, item_budget=0)
    assert kept == []
    assert dropped == items


# --- 7. Item budget cap ---------------------------------------------


def test_bound_by_budget_item_budget_cap() -> None:
    items = [_Item(f"i{i}", token_estimate=1) for i in range(5)]
    kept, dropped = bound_by_budget(items, token_budget=100, item_budget=3)
    assert len(kept) == 3
    assert len(dropped) == 2


# --- 8. Missing token_estimate treated as 0 -------------------------


def test_bound_by_budget_missing_token_attr() -> None:
    @dataclass
    class NoTokens:
        name: str

    items = [NoTokens(f"i{i}") for i in range(3)]
    kept, dropped = bound_by_budget(items, token_budget=100)
    # All three fit because token_estimate defaults to 0.
    assert kept == items
    assert dropped == []


def test_bound_by_budget_non_int_token_attr() -> None:
    @dataclass
    class BadTokens:
        name: str
        token_estimate: str = "nope"  # type: ignore[assignment]

    items = [BadTokens("a"), BadTokens("b")]
    kept, dropped = bound_by_budget(items, token_budget=100)
    # Non-int treated as 0 -> both fit.
    assert kept == items
    assert dropped == []


# --- 9. Custom token_attr --------------------------------------------


def test_bound_by_budget_custom_token_attr() -> None:
    @dataclass
    class CustomToken:
        name: str
        weight: int = 0

    items = [
        CustomToken("a", weight=50),
        CustomToken("b", weight=80),
        CustomToken("c", weight=10),
    ]
    kept, dropped = bound_by_budget(
        items, token_budget=100, token_attr="weight",
    )
    # a (50) fits; b (50+80=130) is dropped; c (50+10=60)
    # fits. The function does not stop on a single drop.
    assert [k.name for k in kept] == ["a", "c"]
    assert [d.name for d in dropped] == ["b"]


# --- 10. Partition invariant ----------------------------------------


def test_bound_by_budget_partition_invariant() -> None:
    items = [_Item(f"i{i}", token_estimate=i + 1) for i in range(10)]
    kept, dropped = bound_by_budget(items, token_budget=20)
    # ``kept + dropped`` is a permutation of ``items``:
    # same elements, same relative order.
    assert kept + dropped == items


# --- 11. Determinism ------------------------------------------------


def test_bound_by_budget_deterministic() -> None:
    items = [_Item(f"i{i}", token_estimate=i + 1) for i in range(8)]
    a = bound_by_budget(items, token_budget=15)
    b = bound_by_budget(items, token_budget=15)
    assert a == b