"""E1-16 + E1-17 contract test: context manifest + per-item record.

The contract is documented in
``docs/benchmarks/e1/context_manifest.md``.
The test pins:

- the ``ContextManifest`` shape (13 fields, frozen,
  hashable);
- the per-item fields on ``ContextCandidate``
  (``source_hash``, ``external_id``, ``revision``,
  ``privacy_class``) for E1-17;
- the default values (backward-compatible: the
  pre-existing 9 fields still work);
- the frozen + hashable invariants.
"""

from __future__ import annotations

import dataclasses

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCandidate, ContextManifest
from paw.core.privacy import PrivacyClass


# --- 1. ContextManifest shape -----------------------------------------


def test_context_manifest_is_frozen() -> None:
    m = ContextManifest(task_id="t1", budget=ContextBudget())
    assert dataclasses.asdict(m)["task_id"] == "t1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.task_id = "t2"  # type: ignore[misc]
    # Equality compares every field.
    n = ContextManifest(task_id="t1", budget=ContextBudget())
    assert m == n


def test_context_manifest_defaults() -> None:
    m = ContextManifest(task_id="t", budget=ContextBudget())
    assert m.included == ()
    assert m.excluded == ()
    assert m.recent_changes == ()
    assert m.affected_areas == ()
    assert m.symbols == ()
    assert m.test_links == ()
    assert m.dependency_edges == ()
    assert m.scan_paths == ()
    assert m.repo_filter_repr == ""
    assert m.final_tokens == 0


# --- 2. E1-17: per-item record fields on ContextCandidate ----------


def test_candidate_default_source_hash_is_empty() -> None:
    c = ContextCandidate(source="memory", source_id="m1", content="")
    assert c.source_hash == ""
    assert c.external_id == ""
    assert c.revision == ""
    assert c.privacy_class is None
    # The E1-17 fields default to safe values; the
    # E1-03 privacy gate treats ``None`` as INTERNAL.


def test_candidate_e1_17_fields_round_trip() -> None:
    """A candidate with the E1-17 fields set produces a
    `to_dict` (via ``dataclasses.asdict``) that
    includes them, so a reviewer who inspects the
    manifest sees the per-item record."""
    c = ContextCandidate(
        source="knowledge",
        source_id="KnowledgeSource:src/foo.py",
        content="",
        source_hash="abc123",
        external_id="repo:src/foo.py:def456",
        revision="def456",
        privacy_class=PrivacyClass.INTERNAL,
    )
    d = dataclasses.asdict(c)
    assert d["source_hash"] == "abc123"
    assert d["external_id"] == "repo:src/foo.py:def456"
    assert d["revision"] == "def456"
    assert d["privacy_class"] is PrivacyClass.INTERNAL


def test_candidate_backward_compatible() -> None:
    """The 9 pre-E1-17 fields still work as before:
    callers that construct a candidate without the
    E1-17 fields get the documented defaults."""
    c = ContextCandidate(source="memory", source_id="m1", content="hi")
    assert c.source == "memory"
    assert c.source_id == "m1"
    assert c.content == "hi"
    assert c.token_estimate == 0
    assert c.priority == 1.0
    # The new fields default sensibly.
    assert c.source_hash == ""
    assert c.external_id == ""
    assert c.revision == ""
    assert c.privacy_class is None


def test_candidate_e1_17_fields_default_to_empty() -> None:
    """The E1-17 fields default to safe values: the
    ``ContextCandidate`` dataclass is intentionally
    mutable (the runtime mutates ``content`` and
    ``skill_level`` during re-budgeting), so the
    ``frozen`` invariant does not apply. The E1-17
    contract is: a candidate without the new fields
    produced by the pre-E1-17 code path still passes
    through the manifest with the documented defaults."""
    c = ContextCandidate(source="memory", source_id="m1", content="")
    assert c.source_hash == ""
    assert c.external_id == ""
    assert c.revision == ""
    assert c.privacy_class is None
    # And the candidate is mutable (the existing
    # ``_build_context`` reassigns ``content``,
    # ``skill_level``, ``token_estimate``).
    c.content = "updated"
    assert c.content == "updated"


def test_candidate_sorting_still_works() -> None:
    """The pre-existing ``__lt__`` (relevance * priority)
    is unchanged by the E1-17 addition."""
    a = ContextCandidate(source="x", source_id="a", content="", relevance_score=0.9, priority=1.0)
    b = ContextCandidate(source="x", source_id="b", content="", relevance_score=0.5, priority=1.0)
    assert a < b  # higher relevance * priority first


# --- 3. Manifest carries included + excluded per E1-17 + E1-18 -----


def test_manifest_with_included_and_excluded() -> None:
    a = ContextCandidate(
        source="memory", source_id="m1", content="", reason="high_score",
        relevance_score=0.9, token_estimate=100,
    )
    b = ContextCandidate(
        source="memory", source_id="m2", content="", reason="low_score",
        relevance_score=0.1, token_estimate=50,
    )
    b.metadata["excluded_reason"] = "token_budget_exceeded"
    m = ContextManifest(
        task_id="t",
        budget=ContextBudget(max_tokens=120),
        included=(a,),
        excluded=(b,),
        final_tokens=100,
    )
    assert len(m.included) == 1
    assert m.included[0].source_id == "m1"
    assert m.included[0].reason == "high_score"
    assert len(m.excluded) == 1
    assert m.excluded[0].metadata["excluded_reason"] == "token_budget_exceeded"
    assert m.final_tokens == 100


# --- 4. Manifest final_tokens is the post-rebudget total ---------


def test_manifest_final_tokens_reflects_post_rebudget_total() -> None:
    """The ``final_tokens`` field is the runtime's
    bookkeeping for the E1-20 over-budget check: when
    the re-budgeting brings the payload back under
    the limit, ``final_tokens <= budget.max_tokens``;
    when the E1-20 over-budget check fails, the runtime
    raises ``BudgetExceededError`` and does not build
    the manifest (this contract test covers the
    success path; the failure path is in the E1-20
    test)."""
    m = ContextManifest(
        task_id="t",
        budget=ContextBudget(max_tokens=1000),
        final_tokens=750,
    )
    assert m.final_tokens == 750
    assert m.final_tokens <= m.budget.max_tokens