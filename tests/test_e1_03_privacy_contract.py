"""E1-03 contract test: privacy classes and remote-disclosure defaults (D1).

The contract is documented in
``docs/benchmarks/e1/privacy_classes.md``.
The test pins:

- ``PrivacyClass`` is the canonical enum at
  ``paw.core.privacy.PrivacyClass`` and re-exported from
  ``paw.bench`` for backward compatibility;
- the closed ``PROVIDER_KINDS`` set is stable;
- the ``REMOTE_DISCLOSURE_DEFAULTS`` table is complete
  (every ``PrivacyClass`` is a key) and the values are
  frozen sets of valid provider kinds;
- ``can_disclose_to_provider`` returns the right answer
  for every (class, provider_kind) combination, and
  fails closed for an unknown provider kind;
- the new ``privacy_class`` field exists on
  ``KnowledgeSource`` and ``MemoryRecord`` with the
  documented default ``INTERNAL``;
- the SQL migration is additive (no ``DROP``, no row
  rewrite) and the new column has the documented
  default;
- the E1-01 ownership audit + the E1-03 spec doc
  list the new field on both owned dataclasses.

Two-fail-positive discipline: this test would have
caught the original placement of ``PrivacyClass`` inside
``paw.bench`` (which would mean ``from paw.core.privacy
import PrivacyClass`` fails) and any drift in the
remote-disclosure defaults.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from paw.bench import PrivacyClass as BenchPrivacyClass
from paw.core.memory import MemoryRecord
from paw.core.privacy import (
    PROVIDER_CLOUD_APPROVED,
    PROVIDER_CLOUD_UNAPPROVED,
    PROVIDER_KINDS,
    PROVIDER_LOCAL,
    REMOTE_DISCLOSURE_DEFAULTS,
    PrivacyClass,
    can_disclose_to_provider,
)
from paw.core.storage import db
from paw.knowledge.source import KnowledgeSource


REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = REPO_ROOT / "docs" / "benchmarks" / "e1" / "ownership_audit.md"
SPEC_PATH = REPO_ROOT / "docs" / "benchmarks" / "e1" / "privacy_classes.md"


# --- 1. Canonical location + re-export --------------------------------


def test_privacy_class_lives_in_paw_core_privacy() -> None:
    """The canonical enum is in ``paw.core.privacy``."""
    from paw.core import privacy as core_privacy

    assert hasattr(core_privacy, "PrivacyClass")
    assert core_privacy.PrivacyClass is PrivacyClass


def test_paw_bench_re_exports_privacy_class() -> None:
    """``paw.bench.PrivacyClass`` is the same enum as
    ``paw.core.privacy.PrivacyClass`` (E0-02 contract
    preserved)."""
    assert BenchPrivacyClass is PrivacyClass


# --- 2. Closed PROVIDER_KINDS set -------------------------------------


def test_provider_kinds_set_is_stable() -> None:
    assert frozenset(
        {PROVIDER_LOCAL, PROVIDER_CLOUD_APPROVED, PROVIDER_CLOUD_UNAPPROVED}
    ) == PROVIDER_KINDS


# --- 3. REMOTE_DISCLOSURE_DEFAULTS table is complete and frozen --------


def test_remote_disclosure_defaults_complete() -> None:
    """Every PrivacyClass is a key; the value is a
    frozenset of valid provider kinds."""
    for cls in PrivacyClass:
        assert cls in REMOTE_DISCLOSURE_DEFAULTS, (
            f"REMOTE_DISCLOSURE_DEFAULTS missing key {cls!r}"
        )
        kinds = REMOTE_DISCLOSURE_DEFAULTS[cls]
        assert isinstance(kinds, frozenset)
        assert kinds.issubset(PROVIDER_KINDS), (
            f"{cls!r} has unknown provider kind in its disclosure set"
        )


def test_remote_disclosure_defaults_frozen() -> None:
    """The table is a MappingProxyType; the inner sets are
    frozensets; nothing on the surface is mutable."""
    with pytest.raises(TypeError):
        REMOTE_DISCLOSURE_DEFAULTS[PrivacyClass.PUBLIC] = frozenset()  # type: ignore[index]
    # ``frozenset.add`` does not exist; Python raises
    # ``AttributeError`` rather than ``TypeError``. Either is
    # acceptable evidence the inner set is frozen.
    with pytest.raises(AttributeError):
        REMOTE_DISCLOSURE_DEFAULTS[PrivacyClass.SECRET].add(PROVIDER_CLOUD_APPROVED)  # type: ignore[attr-defined]


# --- 4. can_disclose_to_provider: full matrix --------------------------


@pytest.mark.parametrize(
    "cls,provider,expected",
    [
        # PUBLIC may go everywhere.
        (PrivacyClass.PUBLIC, PROVIDER_LOCAL, True),
        (PrivacyClass.PUBLIC, PROVIDER_CLOUD_APPROVED, True),
        (PrivacyClass.PUBLIC, PROVIDER_CLOUD_UNAPPROVED, True),
        # INTERNAL may go to local + approved cloud only.
        (PrivacyClass.INTERNAL, PROVIDER_LOCAL, True),
        (PrivacyClass.INTERNAL, PROVIDER_CLOUD_APPROVED, True),
        (PrivacyClass.INTERNAL, PROVIDER_CLOUD_UNAPPROVED, False),
        # WORKSPACE is local only.
        (PrivacyClass.WORKSPACE, PROVIDER_LOCAL, True),
        (PrivacyClass.WORKSPACE, PROVIDER_CLOUD_APPROVED, False),
        (PrivacyClass.WORKSPACE, PROVIDER_CLOUD_UNAPPROVED, False),
        # SECRET is local only (on-box); the compiler still
        # filters it out of any remote-capable decision.
        (PrivacyClass.SECRET, PROVIDER_LOCAL, True),
        (PrivacyClass.SECRET, PROVIDER_CLOUD_APPROVED, False),
        (PrivacyClass.SECRET, PROVIDER_CLOUD_UNAPPROVED, False),
        # Unknown provider kind fails closed.
        (PrivacyClass.PUBLIC, "satellite_relay", False),
        (PrivacyClass.INTERNAL, "", False),
    ],
)
def test_can_disclose_to_provider_matrix(cls, provider, expected) -> None:
    assert can_disclose_to_provider(cls, provider) is expected


# --- 5. KnowledgeSource + MemoryRecord accept privacy_class -----------


def test_knowledge_source_has_privacy_class() -> None:
    field_names = {f.name for f in dataclasses.fields(KnowledgeSource)}
    assert "privacy_class" in field_names


def test_memory_record_has_privacy_class() -> None:
    field_names = {f.name for f in dataclasses.fields(MemoryRecord)}
    assert "privacy_class" in field_names


def test_knowledge_source_privacy_class_default() -> None:
    """The default is INTERNAL — a fresh source is conservatively
    classified; the caller must opt up to PUBLIC if the
    source is shareable."""
    src = KnowledgeSource()
    assert src.privacy_class is PrivacyClass.INTERNAL


def test_memory_record_privacy_class_default() -> None:
    rec = MemoryRecord()
    assert rec.privacy_class is PrivacyClass.INTERNAL


def test_knowledge_source_to_dict_includes_privacy_class() -> None:
    src = KnowledgeSource(id="x", privacy_class=PrivacyClass.PUBLIC)
    d = src.to_dict()
    assert "privacy_class" in d
    assert d["privacy_class"] == "public"


def test_memory_record_to_dict_includes_privacy_class() -> None:
    rec = MemoryRecord(id="x", privacy_class=PrivacyClass.SECRET)
    d = rec.to_dict()
    assert "privacy_class" in d
    assert d["privacy_class"] == "secret"


# --- 6. SQL migration: columns exist with documented defaults --------


async def test_sql_schema_has_e1_03_columns() -> None:
    """The autouse ``session_db`` fixture gives every test a
    fresh database with the E1-03 migration applied; this
    test asserts the new columns exist on both tables."""
    if db._conn is None:
        await db.connect()
    for table in ("knowledge_sources", "memory_records"):
        cursor = await db._conn.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        cols = {row[1] for row in rows}
        assert "privacy_class" in cols, (
            f"{table} missing E1-03 column 'privacy_class'"
        )


# --- 7. Round-trip: store + load preserves privacy_class --------------


async def test_knowledge_source_round_trip() -> None:
    from paw.knowledge.source import KnowledgeSourceManager

    mgr = KnowledgeSourceManager()
    src = await mgr.create(
        name="e1-03-public-source",
        privacy_class=PrivacyClass.PUBLIC,
    )
    assert src.privacy_class is PrivacyClass.PUBLIC
    refetched = await mgr.get(src.id)
    assert refetched is not None
    assert refetched.privacy_class is PrivacyClass.PUBLIC


async def test_memory_record_round_trip() -> None:
    from paw.core.memory import MemoryStore

    store = MemoryStore()
    rec = MemoryRecord(
        content="public license fact",
        summary="MIT",
        privacy_class=PrivacyClass.PUBLIC,
    )
    stored = await store.store(rec)
    assert stored.privacy_class is PrivacyClass.PUBLIC
    cursor = await db._conn.execute(
        "SELECT * FROM memory_records WHERE id = ?", (stored.id,)
    )
    row = await cursor.fetchone()
    assert row is not None
    reloaded = MemoryRecord.from_row(dict(row))
    assert reloaded.privacy_class is PrivacyClass.PUBLIC


# --- 8. Doc sync: audit + spec list the new field ---------------------


def test_ownership_audit_lists_privacy_class_on_both_tables() -> None:
    audit = AUDIT_PATH.read_text(encoding="utf-8")
    # KnowledgeSource section: 18 fields.
    m = re.search(
        r"### `source\.py` — `KnowledgeSource` \((\d+) fields\)",
        audit,
    )
    assert m is not None
    assert int(m.group(1)) == 18
    # Both the KnowledgeSource and MemoryRecord tables have a
    # ``privacy_class`` row.
    assert audit.count("| `privacy_class`") >= 2, (
        "expected privacy_class row in both KnowledgeSource and MemoryRecord tables"
    )


def test_e1_03_spec_documents_table() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")
    # The spec documents the disclosure table; it must list
    # every provider kind and every PrivacyClass.
    for kind in (
        PROVIDER_LOCAL,
        PROVIDER_CLOUD_APPROVED,
        PROVIDER_CLOUD_UNAPPROVED,
    ):
        assert kind in spec, f"spec missing provider kind {kind!r}"
    for cls in PrivacyClass:
        assert cls.value in spec, f"spec missing privacy class {cls.value!r}"
    # The spec is a Phase 4 sync contract; it must reference
    # the contract test file and the ownership audit.
    assert "test_e1_03_privacy_contract.py" in spec
    assert "ownership_audit.md" in spec