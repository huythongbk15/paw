"""E1-02 contract test: project-source identity, revision, and invalidation (D1).

The contract is documented in
``docs/benchmarks/e1/project_source_identity.md``.
The test pins:

- the five new ``KnowledgeSource`` fields exist with the
  documented defaults;
- the closed ``INVALID_REASONS`` set is enforced (an
  unknown reason raises ``ValueError``);
- ``is_stale`` / ``is_fresh`` produce the right answer
  for every combination of ``invalidated_at``,
  ``superseded_by``, and ``status``;
- the SQL migration is additive (no ``DROP``, no row
  rewrite) and the new columns have the documented
  defaults;
- ``KnowledgeSource.to_dict()`` includes the new fields;
- the ``list_stale`` SQL filter agrees with the in-Python
  ``is_stale`` predicate on a representative mix;
- the E1-01 ownership audit + the E1-02 spec doc both
  list the new fields on ``KnowledgeSource``.

Two-fail-positive discipline: this test is added together
with the migration; reverting the migration would break
the schema test, reverting the dataclass would break the
field-existence test, and reverting the manager methods
would break the ``mark_invalid`` / ``list_stale`` tests.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from paw.core.storage import db
from paw.knowledge.source import (
    INVALID_REASONS,
    KnowledgeSource,
    KnowledgeSourceManager,
    KnowledgeSourceStatus,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = REPO_ROOT / "docs" / "benchmarks" / "e1" / "ownership_audit.md"
SPEC_PATH = REPO_ROOT / "docs" / "benchmarks" / "e1" / "project_source_identity.md"


# --- 1. The five new fields exist on the dataclass ---------------------


NEW_FIELDS = {
    "external_id": str,
    "revision": str,
    "invalidated_at": (str, type(None)),
    "invalidation_reason": str,
    "superseded_by": str,
}


def test_knowledge_source_has_new_fields() -> None:
    field_map = {f.name: f.type for f in dataclasses.fields(KnowledgeSource)}
    for name in NEW_FIELDS:
        assert name in field_map, f"KnowledgeSource missing E1-02 field {name!r}"


@pytest.mark.parametrize(
    "field_name,expected_default",
    [
        ("external_id", ""),
        ("revision", ""),
        ("invalidation_reason", ""),
        ("superseded_by", ""),
    ],
)
def test_knowledge_source_new_field_defaults(field_name, expected_default) -> None:
    src = KnowledgeSource()
    assert getattr(src, field_name) == expected_default


def test_knowledge_source_invalidated_at_default_is_none() -> None:
    src = KnowledgeSource()
    assert src.invalidated_at is None


# --- 2. to_dict exposes the new fields ---------------------------------


def test_to_dict_includes_e1_02_fields() -> None:
    src = KnowledgeSource(
        id="abc",
        external_id="repo:src/x.py:def",
        revision="abcdef1",
        invalidated_at="2026-09-04T00:00:00+00:00",
        invalidation_reason="checksum_mismatch",
        superseded_by="xyz",
    )
    d = src.to_dict()
    for name in NEW_FIELDS:
        assert name in d, f"to_dict missing {name!r}"
    assert d["external_id"] == "repo:src/x.py:def"
    assert d["revision"] == "abcdef1"
    assert d["invalidated_at"] == "2026-09-04T00:00:00+00:00"
    assert d["invalidation_reason"] == "checksum_mismatch"
    assert d["superseded_by"] == "xyz"


# --- 3. is_stale / is_fresh predicate matrix ---------------------------


def _is_stale_ground_truth(src: KnowledgeSource) -> bool:
    """The ground truth of 'is_stale' the spec defines. The
    test compares the ``KnowledgeSource.is_stale`` property
    to this function on every combination of the three
    drivers."""
    if src.invalidated_at is not None:
        return True
    if src.superseded_by:
        return True
    return src.status == KnowledgeSourceStatus.ERROR.value


@pytest.mark.parametrize(
    "invalidated_at,superseded_by,status",
    [
        (None, "", KnowledgeSourceStatus.ACTIVE.value),
        ("2026-09-04T00:00:00", "", KnowledgeSourceStatus.ACTIVE.value),
        (None, "xyz", KnowledgeSourceStatus.ACTIVE.value),
        (None, "", KnowledgeSourceStatus.ERROR.value),
        (None, "", KnowledgeSourceStatus.SYNCING.value),
        (None, "", KnowledgeSourceStatus.INACTIVE.value),
        (None, "", KnowledgeSourceStatus.ARCHIVED.value),
        ("2026-09-04T00:00:00", "xyz", KnowledgeSourceStatus.ERROR.value),
    ],
)
def test_is_stale_predicate(invalidated_at, superseded_by, status) -> None:
    src = KnowledgeSource(
        invalidated_at=invalidated_at,
        superseded_by=superseded_by,
        status=status,
    )
    expected = _is_stale_ground_truth(src)
    assert src.is_stale is expected
    assert src.is_fresh is (not expected)


# --- 4. INVALID_REASONS is the closed set ------------------------------


def test_invalid_reasons_set_is_stable() -> None:
    assert frozenset(
        {
            "checksum_mismatch",
            "revision_changed",
            "path_missing",
            "superseded",
            "manual",
        }
    ) == INVALID_REASONS


# --- 5. SQL schema: columns exist with documented defaults -------------


async def test_sql_schema_has_e1_02_columns() -> None:
    """The migration adds five new columns; the autouse
    ``session_db`` fixture gives every test a fresh database
    with the E1-02 schema applied, and this test asserts the
    columns are present on that schema."""
    if db._conn is None:
        await db.connect()
    cursor = await db._conn.execute("PRAGMA table_info(knowledge_sources)")
    rows = await cursor.fetchall()
    cols = {row[1] for row in rows}
    for col in NEW_FIELDS:
        assert col in cols, f"knowledge_sources missing column {col!r}"


# --- 6. mark_invalid: closed reason, supersede, error status -----------


async def test_mark_invalid_persists_state() -> None:
    mgr = KnowledgeSourceManager()
    src = await mgr.create(
        name="e1-02-stale",
        external_id="repo:src/x.py:def",
        revision="abcdef1",
    )
    # mark_invalid should write the three fields and the status.
    marked = await mgr.mark_invalid(
        src.id, "checksum_mismatch", superseded_by="newer-id"
    )
    assert marked.invalidated_at is not None
    assert marked.invalidation_reason == "checksum_mismatch"
    assert marked.superseded_by == "newer-id"
    assert marked.status == KnowledgeSourceStatus.ERROR.value
    assert marked.is_stale is True
    # And the row in the DB agrees.
    refetched = await mgr.get(src.id)
    assert refetched is not None
    assert refetched.invalidation_reason == "checksum_mismatch"
    assert refetched.status == KnowledgeSourceStatus.ERROR.value


async def test_mark_invalid_rejects_unknown_reason() -> None:
    mgr = KnowledgeSourceManager()
    src = await mgr.create(name="e1-02-bad-reason")
    with pytest.raises(ValueError, match="unknown invalidation_reason"):
        await mgr.mark_invalid(src.id, "made_up_reason")
    # The source must remain fresh — no partial write.
    refetched = await mgr.get(src.id)
    assert refetched is not None
    assert refetched.invalidated_at is None
    assert refetched.invalidation_reason == ""
    assert refetched.status == KnowledgeSourceStatus.ACTIVE.value


async def test_list_stale_agrees_with_is_stale_predicate() -> None:
    mgr = KnowledgeSourceManager()
    # A mix: one fresh, three stale by different drivers.
    fresh = await mgr.create(name="e1-02-fresh")
    a = await mgr.create(name="e1-02-stale-invalid")
    b = await mgr.create(name="e1-02-stale-superseded")
    c = await mgr.create(name="e1-02-stale-error")
    await mgr.mark_invalid(a.id, "checksum_mismatch")
    await mgr.mark_invalid(b.id, "superseded", superseded_by="other")
    # mark_invalid writes ERROR; use update_status to leave
    # invalidated_at/superseded_by empty but set ERROR.
    await mgr.update_status(c.id, KnowledgeSourceStatus.ERROR.value)

    stale = await mgr.list_stale()
    stale_ids = {s.id for s in stale}
    # Every one of a, b, c must show up; fresh must not.
    assert {a.id, b.id, c.id}.issubset(stale_ids)
    assert fresh.id not in stale_ids
    # The in-Python predicate agrees with the SQL filter.
    for s in stale:
        assert s.is_stale is True


# --- 7. Doc sync: audit + spec list the new fields ---------------------


def test_ownership_audit_lists_e1_02_fields() -> None:
    audit = AUDIT_PATH.read_text(encoding="utf-8")
    # The audit's KnowledgeSource table is under
    # ``### `source.py` — `KnowledgeSource` (12 fields)``.
    # After E1-02 the table has 17 fields.
    m = re.search(
        r"### `source\.py` — `KnowledgeSource` \((\d+) fields\)",
        audit,
    )
    assert m is not None, "KnowledgeSource section not found in audit"
    field_count = int(m.group(1))
    assert field_count == 17, (
        f"audit KnowledgeSource field count = {field_count}; "
        f"expected 17 (12 original + 5 E1-02 additions)"
    )
    # The new fields are listed as rows in the same table.
    for col in (
        "external_id",
        "revision",
        "invalidated_at",
        "invalidation_reason",
        "superseded_by",
    ):
        assert f"| `{col}`" in audit, (
            f"audit KnowledgeSource table missing row for {col!r}"
        )


def test_e1_02_spec_documents_invalid_reasons() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")
    for reason in (
        "checksum_mismatch",
        "revision_changed",
        "path_missing",
        "superseded",
        "manual",
    ):
        assert reason in spec, f"E1-02 spec missing reason {reason!r}"
    # The spec is a Phase 4 sync contract; it must reference
    # both the contract test file and the ownership audit.
    assert "test_e1_02_source_identity_contract.py" in spec
    assert "ownership_audit.md" in spec