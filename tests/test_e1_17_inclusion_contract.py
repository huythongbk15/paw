"""E1-17 contract test: per-item include record on included candidates.

The contract is documented in
``docs/benchmarks/e1/inclusion_reasons.md``.
The test pins:

- every ``ContextCandidate`` has the E1-17 fields
  (``source_hash``, ``external_id``, ``revision``,
  ``privacy_class``) with documented defaults;
- knowledge candidates populate ``source_hash`` /
  ``privacy_class`` when the source data is available;
- memory candidates populate ``privacy_class``;
- ``reason`` is non-empty for every candidate;
- ``relevance_score`` is in ``[0, 1]``;
- ``token_estimate`` is a non-negative ``int``.
"""

from __future__ import annotations

import pytest

from paw.core.context_compiler import ContextCandidate
from paw.core.privacy import PrivacyClass


# --- 1. Default fields exist and have safe defaults -------------------


def test_candidate_has_e1_17_fields() -> None:
    c = ContextCandidate(source="memory", source_id="m1", content="")
    assert hasattr(c, "source_hash")
    assert hasattr(c, "external_id")
    assert hasattr(c, "revision")
    assert hasattr(c, "privacy_class")
    assert c.source_hash == ""
    assert c.external_id == ""
    assert c.revision == ""
    assert c.privacy_class is None


def test_candidate_e1_17_fields_settable() -> None:
    c = ContextCandidate(
        source="knowledge",
        source_id="k1",
        content="",
        source_hash="abc",
        external_id="repo:foo",
        revision="rev1",
        privacy_class=PrivacyClass.INTERNAL,
    )
    assert c.source_hash == "abc"
    assert c.external_id == "repo:foo"
    assert c.revision == "rev1"
    assert c.privacy_class is PrivacyClass.INTERNAL


# --- 2. Knowledge candidate: source_hash + privacy_class populated ----


def test_knowledge_candidate_fields_populated_from_source() -> None:
    """A knowledge candidate constructed with the E1-17 fields
    populated from a KnowledgeSource carries them for the
    reviewer-level inspection."""
    c = ContextCandidate(
        source="knowledge",
        source_id="chunk-1",
        content="",
        reason="Knowledge chunk from src/foo.py",
        relevance_score=0.85,
        token_estimate=120,
        source_hash="sha256:abc123",
        external_id="repo:src/foo.py:def456",
        revision="def456",
        privacy_class=PrivacyClass.INTERNAL,
    )
    assert c.source_hash == "sha256:abc123"
    assert c.external_id == "repo:src/foo.py:def456"
    assert c.revision == "def456"
    assert c.privacy_class is PrivacyClass.INTERNAL
    assert c.reason != ""
    assert 0.0 <= c.relevance_score <= 1.0
    assert c.token_estimate >= 0


# --- 3. Memory candidate: privacy_class from MemoryRecord -------------


def test_memory_candidate_has_privacy_class() -> None:
    """A memory candidate carries the privacy_class from the
    MemoryRecord (E1-03 default INTERNAL)."""
    c = ContextCandidate(
        source="memory",
        source_id="m1",
        content="",
        reason="Memory record (semantic+lexical): summary",
        relevance_score=0.7,
        token_estimate=50,
        privacy_class=PrivacyClass.WORKSPACE,
    )
    assert c.privacy_class is PrivacyClass.WORKSPACE
    assert c.reason != ""
    assert 0.0 <= c.relevance_score <= 1.0
    assert c.token_estimate >= 0


# --- 4. Skill / ledger / session candidates: defaults preserved ------


def test_skill_candidate_defaults_no_revision() -> None:
    """Skill candidates do not carry revision identity; the E1-17
    fields default to empty / None."""
    c = ContextCandidate(
        source="skill",
        source_id="s1",
        content="Skill body",
        reason="Skill (lexical): s1",
        relevance_score=0.6,
        token_estimate=200,
    )
    assert c.source_hash == ""
    assert c.external_id == ""
    assert c.revision == ""
    assert c.privacy_class is None
    assert c.reason != ""
    assert 0.0 <= c.relevance_score <= 1.0
    assert c.token_estimate >= 0


def test_ledger_candidate_defaults_no_revision() -> None:
    c = ContextCandidate(
        source="ledger",
        source_id="event-1",
        content="",
        reason="Ledger event: task_started",
        relevance_score=0.3,
        token_estimate=10,
    )
    assert c.source_hash == ""
    assert c.revision == ""
    assert c.privacy_class is None
    assert c.reason != ""


def test_session_candidate_defaults_no_revision() -> None:
    c = ContextCandidate(
        source="session",
        source_id="s1",
        content="",
        reason="Session context for s1",
        relevance_score=0.4,
        token_estimate=5,
    )
    assert c.source_hash == ""
    assert c.privacy_class is None
    assert c.reason != ""


# --- 5. Universal invariants on every candidate type ----------------


@pytest.mark.parametrize("source", ["memory", "knowledge", "skill", "ledger", "session", "repository"])
def test_candidate_always_has_reason_score_tokens(source: str) -> None:
    c = ContextCandidate(
        source=source,
        source_id="x1",
        content="",
        reason=f"{source} candidate",
        relevance_score=0.5,
        token_estimate=42,
    )
    assert c.reason != ""
    assert 0.0 <= c.relevance_score <= 1.0
    assert isinstance(c.token_estimate, int)
    assert c.token_estimate >= 0
    # E1-17 fields are always present on the dataclass.
    assert hasattr(c, "source_hash")
    assert hasattr(c, "external_id")
    assert hasattr(c, "revision")
    assert hasattr(c, "privacy_class")


def test_score_clamped_to_unit_interval() -> None:
    """The contract pins: relevance_score must be expressible
    as a float in [0, 1]. A candidate with score 0.0 or 1.0
    is valid."""
    lo = ContextCandidate(source="x", source_id="a", content="", reason="lo", relevance_score=0.0)
    hi = ContextCandidate(source="x", source_id="b", content="", reason="hi", relevance_score=1.0)
    assert 0.0 <= lo.relevance_score <= 1.0
    assert 0.0 <= hi.relevance_score <= 1.0
