"""E1-32 contract test: claim status, confidence, freshness at the evidence boundary.

The contract is documented in
``docs/benchmarks/e1/claim_status_record.md``.
The test pins:

- the closed set ``EVIDENCE_STATUSES``;
- the default ``status="unverified"`` + ``freshness=None``;
- the ``to_dict`` exposure;
- the ``from_row`` round-trip preserves the new fields;
- back-compat: existing call sites without the new
  fields still work (the E1-32 fields are additive).
"""

from __future__ import annotations

from paw.knowledge.evidence import EVIDENCE_STATUSES, KnowledgeEvidence


# --- 1. Closed set of status codes -------------------------


def test_evidence_statuses_is_closed_set() -> None:
    assert frozenset(
        {"unverified", "verified", "disputed", "stale"}
    ) == EVIDENCE_STATUSES


# --- 2. Default values ---------------------------------


def test_default_status_is_unverified() -> None:
    e = KnowledgeEvidence(id="x", chunk_id="y", claim="z")
    assert e.status == "unverified"


def test_default_freshness_is_none() -> None:
    e = KnowledgeEvidence(id="x", chunk_id="y", claim="z")
    assert e.freshness is None


# --- 3. Custom values round-trip ---------------------


def test_custom_status_and_freshness() -> None:
    e = KnowledgeEvidence(
        id="x", chunk_id="y", claim="z",
        status="verified",
        freshness="2026-09-01T00:00:00+00:00",
    )
    assert e.status == "verified"
    assert e.freshness == "2026-09-01T00:00:00+00:00"


# --- 4. to_dict exposure -----------------------------


def test_to_dict_includes_status_and_freshness() -> None:
    e = KnowledgeEvidence(
        id="x", chunk_id="y", claim="z",
        status="verified",
        freshness="2026-09-01T00:00:00+00:00",
    )
    d = e.to_dict()
    assert d["status"] == "verified"
    assert d["freshness"] == "2026-09-01T00:00:00+00:00"


# --- 5. from_row round-trip --------------------------


def test_from_row_round_trip() -> None:
    row = {
        "id": "x",
        "chunk_id": "y",
        "claim": "z",
        "confidence": 0.7,
        "metadata": "{}",
        "created_at": "2026-09-01T00:00:00+00:00",
        "stale_at": None,
        "stale_reason": "",
        "status": "verified",
        "freshness": "2026-09-01T00:00:00+00:00",
    }
    e = KnowledgeEvidence.from_row(row)
    assert e.status == "verified"
    assert e.freshness == "2026-09-01T00:00:00+00:00"


def test_from_row_missing_new_fields_uses_defaults() -> None:
    """A pre-E1-32 row that lacks the new columns
    loads with the safe defaults (``unverified``,
    ``None``)."""
    row = {
        "id": "x",
        "chunk_id": "y",
        "claim": "z",
        "confidence": 0.5,
        "metadata": "{}",
        "created_at": "2026-09-01T00:00:00+00:00",
        "stale_at": None,
        "stale_reason": "",
    }
    e = KnowledgeEvidence.from_row(row)
    assert e.status == "unverified"
    assert e.freshness is None


# --- 6. Back-compat: existing call sites still work --


def test_existing_construction_still_works() -> None:
    """The pre-E1-32 call sites construct
    ``KnowledgeEvidence(id=..., chunk_id=..., claim=...)``
    with positional args. The E1-32 additions are
    additive: those calls keep working."""
    e = KnowledgeEvidence("a", "b", "c")  # type: ignore[misc]
    assert e.id == "a"
    assert e.chunk_id == "b"
    assert e.claim == "c"
    assert e.status == "unverified"
    assert e.freshness is None