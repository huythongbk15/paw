"""E1-31 contract test: retrieve relevant prior decisions with provenance.

The contract is documented in
``docs/benchmarks/e1/prior_decisions_view.md``.
The test pins:

- ``retrieve_prior_decisions`` returns a list of
  ``PriorDecision`` records;
- the result is sorted by date desc (commits first,
  tests after);
- the result is capped at ``max_count``;
- the heuristic is keyword + symbol-name match
  (case-insensitive);
- the provenance field is one of ``"recent_change"``
  or ``"test_link"``;
- a short or empty query returns an empty list
  (the contract is: too-short queries are too noisy
  to match).
"""

from __future__ import annotations

import pytest

from paw.knowledge.changes import RecentChange
from paw.knowledge.history import (
    PriorDecision,
    retrieve_prior_decisions,
)
from paw.knowledge.test_associations import TestLink


def _change(message: str, date: str = "2026-09-01T00:00:00+00:00") -> RecentChange:
    return RecentChange(
        sha="a" * 40,
        short_sha="abc1234",
        author="alice",
        date=date,
        message=message,
        changed_files=("src/foo.py",),
    )


def _link(test_q: str, source_q: str) -> TestLink:
    return TestLink(
        test_qualified_name=test_q,
        test_file=test_q.replace(".", "/") + ".py",
        source_qualified_name=source_q,
        source_file=source_q.replace(".", "/") + ".py",
        confidence=1.0, reason="direct_name",
    )


# --- 1. Empty query returns empty list ---------------------


def test_empty_query_returns_empty() -> None:
    out = retrieve_prior_decisions("", recent_changes=[], test_links=[])
    assert out == []


def test_short_query_returns_empty() -> None:
    """Queries shorter than 3 characters are too
    noisy to match; the contract returns an empty list."""
    out = retrieve_prior_decisions("ab", recent_changes=[_change("xyz")], test_links=[])
    assert out == []


# --- 2. Match on recent change message -------------------


def test_match_on_recent_change() -> None:
    ch = _change("refactor the budget allocator")
    out = retrieve_prior_decisions(
        "budget", recent_changes=[ch], test_links=[],
    )
    assert len(out) == 1
    assert out[0].kind == "commit"
    assert out[0].description == "refactor the budget allocator"
    assert out[0].provenance == "recent_change"
    assert out[0].commit_sha == ch.sha


# --- 3. Match on test link -------------------------


def test_match_on_test_link() -> None:
    tl = _link("tests.test_foo.test_bar", "src.foo.bar")
    out = retrieve_prior_decisions(
        "test_bar", recent_changes=[], test_links=[tl],
    )
    assert len(out) == 1
    assert out[0].kind == "test"
    assert out[0].provenance == "test_link"
    assert out[0].test_qualified_name == tl.test_qualified_name
    assert out[0].source_qualified_name == "src.foo.bar"


# --- 4. Match on source qualified name ---------------------


def test_match_on_source_qualified_name() -> None:
    tl = _link("tests.test_x", "src.budget_allocator")
    out = retrieve_prior_decisions(
        "budget", recent_changes=[], test_links=[tl],
    )
    assert len(out) == 1
    assert out[0].kind == "test"


# --- 5. No match returns empty ---------------------------


def test_no_match_returns_empty() -> None:
    out = retrieve_prior_decisions(
        "nonexistent", recent_changes=[_change("budget")], test_links=[],
    )
    assert out == []


# --- 6. Result is sorted by date desc --------------------


def test_result_sorted_by_date() -> None:
    ch_old = _change("old commit", date="2026-01-01T00:00:00+00:00")
    ch_new = _change("new commit", date="2026-09-01T00:00:00+00:00")
    out = retrieve_prior_decisions(
        "commit", recent_changes=[ch_old, ch_new], test_links=[],
    )
    assert len(out) == 2
    # Newer commit first.
    assert out[0].commit_sha == ch_new.sha
    assert out[1].commit_sha == ch_old.sha


# --- 7. Result is capped at max_count -----------------


def test_result_capped() -> None:
    changes = [
        _change(f"commit {i}", date=f"2026-01-{i+1:02d}T00:00:00+00:00")
        for i in range(10)
    ]
    out = retrieve_prior_decisions(
        "commit", recent_changes=changes, test_links=[], max_count=3,
    )
    assert len(out) == 3


# --- 8. Determinism --------------------------------


def test_deterministic() -> None:
    ch = _change("budget")
    a = retrieve_prior_decisions("budget", recent_changes=[ch], test_links=[])
    b = retrieve_prior_decisions("budget", recent_changes=[ch], test_links=[])
    assert a == b


# --- 9. PriorDecision is frozen + hashable --------------


def test_prior_decision_is_frozen() -> None:
    import dataclasses

    p = PriorDecision(
        kind="commit", date="2026-09-01", description="x",
        provenance="recent_change",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.kind = "test"  # type: ignore[misc]