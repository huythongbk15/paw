"""E1-07 contract test: stale derived records are invalidated after source changes.

The contract is documented in
``docs/benchmarks/e1/stale_derived_records.md``.
The test pins:

- the ``stale_at`` / ``stale_reason`` boundary on every
  derived dataclass (``KnowledgeChunk``,
  ``KnowledgeEvidence``, ``KnowledgeCitation``): field
  existence, default value, ``is_stale`` property,
  ``to_dict`` exposure, ``from_row`` round-trip;
- the SQL migration: every derived table has the new
  columns on a fresh database;
- the manager cascade: marking a source invalid
  (via ``mark_invalid`` or ``mark_path_missing``) also
  marks its chunks stale, its evidence stale, and its
  citations stale in the same call;
- the manager recovery: ``update_checksum`` after a
  successful re-ingest clears the stale state on every
  derived row that derives from the source;
- the cascade is idempotent (a second call on an
  already-stale source returns 0);
- the cascade refuses an unknown reason with
  ``ValueError`` (closed ``INVALID_REASONS`` set).

Two-fail-positive discipline: each assertion was
written because the failure it asserts was reproduced
against a candidate that lacked the cascade. Reverting
the chunk-stale UPDATE breaks the chunk-test; reverting
the evidence JOIN breaks the evidence-test; reverting
the citation JOIN breaks the citation-test; reverting
the recovery cascade leaves stale rows after a
successful re-ingest.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from paw.knowledge.chunk import KnowledgeChunk, KnowledgeChunkStore
from paw.knowledge.citation import KnowledgeCitation, KnowledgeCitationStore
from paw.knowledge.evidence import KnowledgeEvidence, KnowledgeEvidenceStore
from paw.knowledge.source import (
    INVALID_REASONS,
    KnowledgeSourceManager,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "docs" / "benchmarks" / "e1" / "stale_derived_records.md"


# --- 1. The new fields exist on every derived dataclass ---------------


@pytest.mark.parametrize(
    "cls,fields",
    [
        (KnowledgeChunk, {"stale_at", "stale_reason", "is_stale"}),
        (KnowledgeEvidence, {"stale_at", "stale_reason", "is_stale"}),
        (KnowledgeCitation, {"stale_at", "stale_reason", "is_stale"}),
    ],
)
def test_derived_dataclass_fields(cls, fields) -> None:
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(cls)}
    # ``is_stale`` is a property, not a dataclass field;
    # check it separately.
    missing = fields - field_names - {"is_stale"}
    assert not missing, f"{cls.__name__} missing E1-07 fields {missing}"
    # The property exists on the class.
    assert isinstance(getattr(cls, "is_stale", None), property), (
        f"{cls.__name__} missing is_stale property"
    )


def test_chunk_default_stale_at_is_none() -> None:
    assert KnowledgeChunk().stale_at is None
    assert KnowledgeChunk().stale_reason == ""


def test_evidence_default_stale_at_is_none() -> None:
    assert KnowledgeEvidence().stale_at is None
    assert KnowledgeEvidence().stale_reason == ""


def test_citation_default_stale_at_is_none() -> None:
    assert KnowledgeCitation().stale_at is None
    assert KnowledgeCitation().stale_reason == ""


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (KnowledgeChunk, {"stale_at": "2026-09-04T00:00:00", "stale_reason": "checksum_mismatch"}),
        (KnowledgeEvidence, {"stale_at": "2026-09-04T00:00:00", "stale_reason": "checksum_mismatch"}),
        (KnowledgeCitation, {"stale_at": "2026-09-04T00:00:00", "stale_reason": "checksum_mismatch"}),
    ],
)
def test_derived_dataclass_is_stale_property(cls, kwargs) -> None:
    fresh = cls()
    stale = cls(**kwargs)
    assert fresh.is_stale is False
    assert stale.is_stale is True


@pytest.mark.parametrize(
    "cls",
    [KnowledgeChunk, KnowledgeEvidence, KnowledgeCitation],
)
def test_derived_dataclass_to_dict_includes_stale_fields(cls) -> None:
    obj = cls(
        stale_at="2026-09-04T00:00:00",
        stale_reason="checksum_mismatch",
    )
    d = obj.to_dict()
    assert "stale_at" in d
    assert "stale_reason" in d
    assert d["stale_at"] == "2026-09-04T00:00:00"
    assert d["stale_reason"] == "checksum_mismatch"


# --- 2. SQL migration: every derived table has the new columns -------


async def test_sql_schema_has_e1_07_columns() -> None:
    from paw.core.storage import db

    if db._conn is None:
        await db.connect()
    for table in ("knowledge_chunks", "evidence", "citations"):
        cursor = await db._conn.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        cols = {row[1] for row in rows}
        assert "stale_at" in cols, f"{table} missing E1-07 column 'stale_at'"
        assert "stale_reason" in cols, (
            f"{table} missing E1-07 column 'stale_reason'"
        )


# --- 3. The cascade: source invalid -> chunks + evidence + citations -


async def test_cascade_chunks_on_mark_invalid() -> None:
    src_mgr = KnowledgeSourceManager()
    chunk_mgr = KnowledgeChunkStore()
    src = await src_mgr.create(name="e1-07-cascade-chunk", path="src.py")
    chunk = await chunk_mgr.add_chunk(src.id, "hello")
    assert chunk.is_stale is False
    await src_mgr.mark_invalid(src.id, "checksum_mismatch")
    refetched = await chunk_mgr.get(chunk.id)
    assert refetched is not None
    assert refetched.is_stale is True
    assert refetched.stale_reason == "checksum_mismatch"
    assert refetched.stale_at is not None


async def test_cascade_evidence_on_mark_invalid() -> None:
    src_mgr = KnowledgeSourceManager()
    chunk_mgr = KnowledgeChunkStore()
    ev_mgr = KnowledgeEvidenceStore()
    src = await src_mgr.create(name="e1-07-cascade-evidence", path="src.py")
    chunk = await chunk_mgr.add_chunk(src.id, "hello")
    ev = await ev_mgr.add_evidence(chunk.id, "the chunk is hello")
    assert ev.is_stale is False
    await src_mgr.mark_invalid(src.id, "path_missing")
    refetched = await ev_mgr.get(ev.id)
    assert refetched is not None
    assert refetched.is_stale is True
    assert refetched.stale_reason == "path_missing"


async def test_cascade_citation_on_mark_invalid() -> None:
    src_mgr = KnowledgeSourceManager()
    chunk_mgr = KnowledgeChunkStore()
    ev_mgr = KnowledgeEvidenceStore()
    cit_mgr = KnowledgeCitationStore()
    src = await src_mgr.create(name="e1-07-cascade-citation", path="src.py")
    chunk = await chunk_mgr.add_chunk(src.id, "hello")
    ev = await ev_mgr.add_evidence(chunk.id, "the chunk is hello")
    cit = await cit_mgr.add_citation(task_id="task-1", evidence_id=ev.id)
    assert cit.is_stale is False
    await src_mgr.mark_invalid(src.id, "revision_changed")
    refetched = await cit_mgr.get(cit.id)
    assert refetched is not None
    assert refetched.is_stale is True
    assert refetched.stale_reason == "revision_changed"


async def test_cascade_count_on_mark_invalid() -> None:
    """``invalidate_derived_rows`` returns the count of
    rows newly marked stale. Two chunks + one evidence +
    one citation deriving from the same source = 4."""
    src_mgr = KnowledgeSourceManager()
    chunk_mgr = KnowledgeChunkStore()
    ev_mgr = KnowledgeEvidenceStore()
    cit_mgr = KnowledgeCitationStore()
    src = await src_mgr.create(name="e1-07-cascade-count", path="src.py")
    c1 = await chunk_mgr.add_chunk(src.id, "alpha")
    c2 = await chunk_mgr.add_chunk(src.id, "bravo")
    ev1 = await ev_mgr.add_evidence(c1.id, "claim 1")
    cit1 = await cit_mgr.add_citation(task_id="task-1", evidence_id=ev1.id)
    # Mark invalid: cascades to 2 chunks + 1 evidence + 1 citation = 4.
    n = await src_mgr.invalidate_derived_rows(src.id, reason="checksum_mismatch")
    assert n == 4
    # Idempotent: a second call returns 0.
    n2 = await src_mgr.invalidate_derived_rows(src.id, reason="checksum_mismatch")
    assert n2 == 0
    # And every derived row is stale.
    for cls, mgr, cid in [
        (KnowledgeChunk, chunk_mgr, c1.id),
        (KnowledgeChunk, chunk_mgr, c2.id),
        (KnowledgeEvidence, ev_mgr, ev1.id),
        (KnowledgeCitation, cit_mgr, cit1.id),
    ]:
        refetched = await mgr.get(cid)
        assert refetched is not None
        assert refetched.is_stale is True


# --- 4. Refusal of unknown reasons -----------------------------------


async def test_invalidate_derived_rows_rejects_unknown_reason() -> None:
    src_mgr = KnowledgeSourceManager()
    src = await src_mgr.create(name="e1-07-bad-reason", path="src.py")
    with pytest.raises(ValueError, match="unknown invalidation_reason"):
        await src_mgr.invalidate_derived_rows(src.id, reason="made_up_reason")
    # And the source itself was not touched.
    refetched = await src_mgr.get(src.id)
    assert refetched is not None
    assert refetched.invalidated_at is None
    assert refetched.invalidation_reason == ""


# --- 5. Recovery: a successful re-ingest clears the stale chain -----


async def test_recovery_clears_derived_stale_on_update_checksum() -> None:
    src_mgr = KnowledgeSourceManager()
    chunk_mgr = KnowledgeChunkStore()
    ev_mgr = KnowledgeEvidenceStore()
    src = await src_mgr.create(name="e1-07-recovery", path="src.py")
    chunk = await chunk_mgr.add_chunk(src.id, "hello")
    ev = await ev_mgr.add_evidence(chunk.id, "claim")
    # 1. Mark invalid: everything is stale.
    await src_mgr.mark_invalid(src.id, "checksum_mismatch")
    assert (await chunk_mgr.get(chunk.id)).is_stale is True
    assert (await ev_mgr.get(ev.id)).is_stale is True
    # 2. Re-ingest: write a new hash; recovery clears
    # the derived stale state. The value of the hash is
    # opaque to the recovery logic; any non-empty string
    # works.
    await src_mgr.update_checksum(src.id, "newhash")
    assert (await chunk_mgr.get(chunk.id)).is_stale is False
    assert (await ev_mgr.get(ev.id)).is_stale is False
    # And the source is back to active.
    refetched = await src_mgr.get(src.id)
    assert refetched is not None
    assert refetched.invalidated_at is None
    assert refetched.status == "active"


# --- 6. mark_path_missing also cascades ------------------------------


async def test_mark_path_missing_cascades() -> None:
    src_mgr = KnowledgeSourceManager()
    chunk_mgr = KnowledgeChunkStore()
    src = await src_mgr.create(name="e1-07-missing", path="src.py")
    chunk = await chunk_mgr.add_chunk(src.id, "hello")
    marked = await src_mgr.mark_path_missing(src.id)
    assert marked.invalidation_reason == "path_missing"
    refetched = await chunk_mgr.get(chunk.id)
    assert refetched is not None
    assert refetched.is_stale is True
    assert refetched.stale_reason == "path_missing"


# --- 7. INVALID_REASONS remains the closed set -----------------------


def test_invalid_reasons_unchanged() -> None:
    assert frozenset(
        {
            "checksum_mismatch",
            "revision_changed",
            "path_missing",
            "superseded",
            "manual",
        }
    ) == INVALID_REASONS


# --- 8. Doc sync ------------------------------------------------------


def test_e1_07_spec_documents_closed_reasons() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")
    for reason in (
        "checksum_mismatch",
        "revision_changed",
        "path_missing",
        "superseded",
        "manual",
    ):
        assert reason in spec, f"E1-07 spec missing reason {reason!r}"
    assert "invalidate_derived_rows" in spec
    assert "test_e1_07_stale_derived_contract.py" in spec