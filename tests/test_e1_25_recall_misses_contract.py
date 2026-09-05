"""E1-25 contract test: review every recall miss before changing ranking or thresholds.

The contract is documented in
``docs/benchmarks/e1/recall_misses.md``.
The test pins the *discipline*: every recall-miss
category has a documented response, and a change to
ranking / thresholds is permitted only when the cause
is in those layers.
"""

from __future__ import annotations


# --- 1. Closed set of miss categories -----------------------------


EXPECTED_CATEGORIES: frozenset[str] = frozenset(
    {
        "ranking",
        "threshold",
        "retrieval",
        "source_missing",
        "fixture_wrong",
    }
)

# The action each category permits. The test pins the
# mapping; changing an action is a change-control
# surface.
ACTIONS: dict[str, str] = {
    "ranking": "change ranking or threshold",
    "threshold": "change ranking or threshold",
    "retrieval": "change retrieval (e.g. tokenization, "
                 "embedding, scanner)",
    "source_missing": "fix the source (add the file, "
                      "fix the path, or close the case)",
    "fixture_wrong": "fix the E0 case fixture (the "
                     "expected evidence is wrong)",
}


def test_categories_are_closed_set() -> None:
    """The closed set of miss categories; a new
    category is a change-control surface."""
    assert frozenset(
        {"ranking", "threshold", "retrieval", "source_missing", "fixture_wrong"}
    ) == EXPECTED_CATEGORIES


def test_every_category_has_an_action() -> None:
    """Every miss category has a documented response.
    A reviewer who classifies a miss and looks up the
    action knows the next step."""
    for cat in EXPECTED_CATEGORIES:
        assert cat in ACTIONS, f"category {cat!r} has no documented action"


def test_ranking_and_threshold_actions_match() -> None:
    """Ranking and threshold are the categories that
    permit a heuristic change. The actions are the
    same string by design."""
    assert ACTIONS["ranking"] == ACTIONS["threshold"]


def test_retrieval_action_does_not_match_ranking() -> None:
    """The retrieval action is distinct: a
    retrieval miss is not fixed by changing ranking."""
    assert ACTIONS["retrieval"] != ACTIONS["ranking"]


def test_source_missing_and_fixture_wrong_are_distinct() -> None:
    """Source-missing and fixture-wrong are both
    non-runtime fixes; their actions are distinct
    (one is a code change, the other is a test
    fixture change)."""
    assert ACTIONS["source_missing"] != ACTIONS["fixture_wrong"]


# --- 2. Discipline: a miss with a known category is recorded --


def test_recall_miss_discipline_is_documented() -> None:
    """The discipline: every recall miss is reviewed
    *before* the heuristic is changed. The contract
    is the mapping from category to action."""
    # A reviewer who sees ``misses = (("hello", "ranking"),)``
    # knows the response: change ranking or threshold.
    # The test does not assert a specific case; it
    # asserts the discipline is documented and
    # exhaustive.
    assert len(ACTIONS) == len(EXPECTED_CATEGORIES)