"""E1-28 contract test: decision-evidence view through Knowledge/Evidence ownership.

The contract is documented in
``docs/benchmarks/e1/decision_evidence_view.md``.
The test pins:

- ``recent_change_to_evidence`` returns one
  ``KnowledgeEvidence`` per changed file;
- the ``claim`` is the commit's first-line message;
- the ``chunk_id`` is the file path;
- the ``confidence`` is ``0.5`` (the evidence is a
  change record, not a static claim);
- the result is sorted by file (deterministic).
"""

from __future__ import annotations

from pathlib import Path

from paw.knowledge.changes import (
    RecentChange,
    recent_change_to_evidence,
)
from paw.knowledge.evidence import KnowledgeEvidence


def _change(files: tuple[str, ...], message: str = "fix bug") -> RecentChange:
    return RecentChange(
        sha="a" * 40,
        short_sha="abcdef1",
        author="alice",
        date="2026-09-04T12:00:00+00:00",
        message=message,
        changed_files=files,
    )


# --- 1. One row per changed file -----------------------------------


def test_one_row_per_changed_file() -> None:
    ch = _change(("a.py", "b.py", "c.py"))
    out = recent_change_to_evidence(ch, repo_root=Path())
    assert len(out) == 3
    assert all(isinstance(e, KnowledgeEvidence) for e in out)
    # The chunk_ids are the file paths.
    assert {e.chunk_id for e in out} == {"a.py", "b.py", "c.py"}


# --- 2. Claim is the commit message --------------------------------


def test_claim_is_the_commit_message() -> None:
    ch = _change(("a.py",), message="refactor the budget allocator")
    out = recent_change_to_evidence(ch, repo_root=Path())
    assert out[0].claim == "refactor the budget allocator"


# --- 3. Confidence is 0.5 ---------------------------------------


def test_confidence_is_change_record() -> None:
    ch = _change(("a.py",))
    out = recent_change_to_evidence(ch, repo_root=Path())
    assert out[0].confidence == 0.5


# --- 4. Metadata carries the commit metadata -------------------


def test_metadata_carries_commit_metadata() -> None:
    ch = _change(("a.py",))
    out = recent_change_to_evidence(ch, repo_root=Path())
    md = out[0].metadata
    assert md["paw_evidence_kind"] == "change_record"
    assert md["commit_sha"] == ch.sha
    assert md["commit_short_sha"] == ch.short_sha
    assert md["author"] == ch.author
    assert md["date"] == ch.date


# --- 5. Empty change list returns empty list ------------------


def test_empty_change_returns_empty() -> None:
    ch = _change(())
    out = recent_change_to_evidence(ch, repo_root=Path())
    assert out == []


# --- 6. Determinism -----------------------------------------


def test_deterministic() -> None:
    ch = _change(("a.py", "b.py"))
    a = recent_change_to_evidence(ch, repo_root=Path())
    b = recent_change_to_evidence(ch, repo_root=Path())
    assert a == b
    # And the order is the file order in
    # ``changed_files`` (the input is a tuple, so the
    # iteration order is deterministic).
    assert [e.chunk_id for e in a] == ["a.py", "b.py"]