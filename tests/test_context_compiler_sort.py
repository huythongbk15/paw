"""Regression test for the ContextCandidate.__lt__ sort order fix.

The runtime used ``sorted(candidates, reverse=True)`` to put the
highest-score candidate first. But ``ContextCandidate.__lt__`` was
inverted: it returned ``self > other`` instead of ``self < other``,
which made ``sorted(reverse=True)`` produce ASCENDING order. The
budget filter (``_allocate_budget``) then processed the lowest-score
candidates first and dropped the highest-score ones, breaking recall
on production-scale corpora.

This test pins the correct sort order.
"""

from __future__ import annotations

from paw.core.context_compiler import ContextCandidate


def _cand(score: float, priority: float = 0.1) -> ContextCandidate:
    return ContextCandidate(
        source="knowledge",
        source_id=f"src-{score}",
        content=f"content for score {score}",
        reason="test",
        relevance_score=score,
        token_estimate=100,
        priority=priority,
    )


def test_default_sort_ascending() -> None:
    """sorted(candidates) with the fixed __lt__ puts the LOWEST first
    (default Python ascending order)."""
    candidates = [_cand(0.9), _cand(0.5), _cand(0.7)]
    sorted_cands = sorted(candidates)
    assert [c.relevance_score for c in sorted_cands] == [0.5, 0.7, 0.9]


def test_reverse_sort_descending() -> None:
    """sorted(candidates, reverse=True) with the fixed __lt__ puts the
    HIGHEST first. This is the order _rank_candidates relies on."""
    candidates = [_cand(0.9), _cand(0.5), _cand(0.7)]
    sorted_cands = sorted(candidates, reverse=True)
    assert [c.relevance_score for c in sorted_cands] == [0.9, 0.7, 0.5]


def test_rank_key_matches_inverse_lt() -> None:
    """The __lt__ comparator must match ``relevance * priority`` in the
    correct direction (lower rank = "less than" higher rank)."""
    high = _cand(0.9, priority=0.5)  # rank 0.45
    low = _cand(0.5, priority=0.5)   # rank 0.25
    assert high > low  # numeric comparison of relevance
    # The __lt__ should return True when self < other (i.e. low < high)
    assert (low < high) is True
    assert (high < low) is False
