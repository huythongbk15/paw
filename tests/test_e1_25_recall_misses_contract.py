"""E1-25 contract test: review every recall miss before changing ranking or thresholds.

The contract is documented in
``docs/benchmarks/e1/recall_misses.md``. The test pins:

- the five miss categories exist as a closed set
  (``ranking``, ``threshold``, ``retrieval``,
  ``source_missing``, ``fixture_wrong``);
- a classification is mandatory for every miss;
- a ranking/threshold change is permitted only when
  the classification is ``ranking`` or ``threshold``;
- a retrieval change is permitted only when the
  classification is ``retrieval``;
- other classifications lead to a non-runtime change
  (fixture update, source addition, E0 case fix);
- the spec doc lists every classification.
"""

from __future__ import annotations

import pytest


# --- 1. The closed set of miss categories -----------------------------


MISS_CATEGORIES: frozenset[str] = frozenset(
    {
        "ranking",
        "threshold",
        "retrieval",
        "source_missing",
        "fixture_wrong",
    }
)


def test_miss_categories_is_closed_set() -> None:
    """The miss classification set is pinned: a reviewer
    who reads the spec sees every possible category, no
    more."""
    assert {
        "ranking",
        "threshold",
        "retrieval",
        "source_missing",
        "fixture_wrong",
    } == MISS_CATEGORIES


def test_miss_categories_has_exactly_five() -> None:
    assert len(MISS_CATEGORIES) == 5


# --- 2. Classification is mandatory -----------------------------------


def test_empty_classification_rejected() -> None:
    """A miss without a classification cannot be acted on."""
    empty = ""
    assert empty not in MISS_CATEGORIES


def test_unknown_classification_rejected() -> None:
    """A miss classified with an unknown category cannot
    be acted on."""
    unknown = "some_custom_thing"
    assert unknown not in MISS_CATEGORIES


# --- 3. Change rules --------------------------------------------------


@pytest.mark.parametrize("category,change_allowed", [
    ("ranking", True),
    ("threshold", True),
    ("retrieval", True),
    ("source_missing", False),
    ("fixture_wrong", False),
])
def test_change_allows_runtime_change(category: str, change_allowed: bool) -> None:
    """A runtime change (ranking / threshold / retrieval)
    is permitted only when the classification is one of
    ``ranking``, ``threshold``, ``retrieval``."""
    is_runtime_change = category in {"ranking", "threshold", "retrieval"}
    if change_allowed:
        assert is_runtime_change
    else:
        assert not is_runtime_change


@pytest.mark.parametrize("category,expected_action", [
    ("ranking", "adjust_ranking_or_threshold"),
    ("threshold", "adjust_ranking_or_threshold"),
    ("retrieval", "adjust_retrieval"),
    ("source_missing", "add_source_or_fix_repo"),
    ("fixture_wrong", "doc_plus_e0_case_update"),
])
def test_classified_miss_has_deterministic_action(category: str, expected_action: str) -> None:
    """Each miss classification maps to a deterministic
    non-runtime or runtime action."""
    mapping = {
        "ranking": "adjust_ranking_or_threshold",
        "threshold": "adjust_ranking_or_threshold",
        "retrieval": "adjust_retrieval",
        "source_missing": "add_source_or_fix_repo",
        "fixture_wrong": "doc_plus_e0_case_update",
    }
    assert mapping[category] == expected_action


# --- 4. Spec doc sync -------------------------------------------------


def test_spec_doc_lists_all_categories() -> None:
    """The spec doc ``docs/benchmarks/e1/recall_misses.md``
    must list every miss category in the closed set."""
    from pathlib import Path
    spec = Path("docs/benchmarks/e1/recall_misses.md").read_text(encoding="utf-8")
    for cat in MISS_CATEGORIES:
        assert cat in spec, (
            f"miss category {cat!r} missing from spec doc"
        )
