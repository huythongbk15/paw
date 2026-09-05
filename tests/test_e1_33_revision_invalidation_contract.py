"""E1-33 contract test: invalidate or re-evaluate decision on revision change.

The contract is documented in
``docs/benchmarks/e1/revision_invalidation.md``.
The test pins:

- the closed set of reason codes
  (``revision_match``, ``revision_mismatch``,
  ``pinned_revision_not_found``);
- the happy path: matching revisions are not stale;
- the revision-mismatch path: when the pinned
  revision does not appear in the recent-changes
  SHA list, the decision is stale;
- the pinned-revision-not-found path: when the
  pinned revision *does* appear in the recent-changes
  SHA list, the decision is reachable and not
  stale;
- empty inputs are handled as a revision
  mismatch (stale);
- determinism: two calls produce the same result.
"""

from __future__ import annotations

import pytest

from paw.knowledge.changes import RecentChange
from paw.knowledge.history import (
    ReEvaluationResult,
    re_evaluate_on_revision,
)


def _ch(sha: str, date: str = "2026-09-01T00:00:00+00:00") -> RecentChange:
    return RecentChange(
        sha=sha, short_sha=sha[:7], author="alice",
        date=date, message="m", changed_files=(),
    )


# --- 1. Result shape -------------------------------------


def test_re_evaluation_result_shape() -> None:
    r = ReEvaluationResult(
        pinned_revision="abc", current_revision="def", stale=True, reason="revision_mismatch",
    )
    assert r.pinned_revision == "abc"
    assert r.current_revision == "def"
    assert r.stale is True
    assert r.reason == "revision_mismatch"


# --- 2. Happy path: matching revisions ------------------


async def test_matching_revisions_not_stale() -> None:
    r = await re_evaluate_on_revision(
        pinned_revision="abc", current_revision="abc", recent_changes=[],
    )
    assert r.stale is False
    assert r.reason == "revision_match"


# --- 3. Revision mismatch + pinned not in SHAs -> stale -


async def test_revision_mismatch_when_pinned_not_in_changes() -> None:
    r = await re_evaluate_on_revision(
        pinned_revision="pinned",
        current_revision="head",
        recent_changes=[_ch("head")],
    )
    assert r.stale is True
    assert r.reason == "revision_mismatch"


# --- 4. Revision mismatch + pinned in SHAs -> not stale -


async def test_pinned_revision_still_reachable() -> None:
    """When ``pinned_revision`` is in the recent-changes
    SHA list, the decision is reachable and not
    stale (the pinned revision is in the chain)."""
    r = await re_evaluate_on_revision(
        pinned_revision="pinned",
        current_revision="head",
        recent_changes=[_ch("pinned"), _ch("intermediate"), _ch("head")],
    )
    assert r.stale is False
    assert r.reason == "pinned_revision_not_found"


# --- 5. Empty inputs: stale ----------------------------


async def test_empty_pinned_revision_is_stale() -> None:
    r = await re_evaluate_on_revision(
        pinned_revision="", current_revision="head", recent_changes=[],
    )
    assert r.stale is True


async def test_empty_current_revision_is_stale() -> None:
    r = await re_evaluate_on_revision(
        pinned_revision="abc", current_revision="", recent_changes=[],
    )
    assert r.stale is True


# --- 6. Determinism ---------------------------------


async def test_deterministic() -> None:
    a = await re_evaluate_on_revision(
        pinned_revision="pinned", current_revision="head",
        recent_changes=[_ch("pinned"), _ch("head")],
    )
    b = await re_evaluate_on_revision(
        pinned_revision="pinned", current_revision="head",
        recent_changes=[_ch("pinned"), _ch("head")],
    )
    assert a == b


# --- 7. Frozen + hashable ----------------------------


def test_re_evaluation_result_is_frozen() -> None:
    import dataclasses

    r = ReEvaluationResult(
        pinned_revision="a", current_revision="b",
        stale=True, reason="revision_mismatch",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.stale = False  # type: ignore[misc]