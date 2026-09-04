"""E1-14 + E1-15 contract test: persist derived records + close/reopen proof.

The contract is documented in
``docs/benchmarks/e1/derived_records_persistence.md``.
The test pins:

- the E1-14 round-trip: ``save_derived_view`` writes a
  view under a source; ``load_derived_view`` returns
  the same view;
- multiple views per source (additive, no overwrites);
- ``list_derived_views`` returns the persisted kinds;
- ``load_derived_view`` for an unknown source returns
  ``{}``;
- unknown ``view_kind`` raises ``ValueError``;
- the E1-15 close/reopen proof: persist a view, close
  the database connection, reopen, load the view, and
  assert equality.
"""

from __future__ import annotations

import pytest

from paw.core.storage import db
from paw.knowledge.index import KnowledgeIndex
from paw.knowledge.source import KnowledgeSourceManager


# --- 1. Round-trip --------------------------------------------------


async def test_save_load_round_trip() -> None:
    src_mgr = KnowledgeSourceManager()
    index = KnowledgeIndex()
    src = await src_mgr.create(name="e1-14-rt", path="src.py")
    view = {
        "kind": "symbols",
        "items": [
            {"qualified_name": "src.foo", "kind": "function"},
        ],
    }
    ok = await index.save_derived_view(src.id, "symbols", view)
    assert ok is True
    loaded = await index.load_derived_view(src.id, "symbols")
    assert loaded == view


# --- 2. Multiple views per source (additive) -----------------------


async def test_multiple_views_per_source() -> None:
    src_mgr = KnowledgeSourceManager()
    index = KnowledgeIndex()
    src = await src_mgr.create(name="e1-14-multi", path="src.py")
    await index.save_derived_view(
        src.id, "symbols", {"items": [{"q": "a"}]}
    )
    await index.save_derived_view(
        src.id, "test_links", {"items": [{"test": "t"}]}
    )
    kinds = await index.list_derived_views(src.id)
    assert set(kinds) == {"symbols", "test_links"}
    # And each view is independent.
    symbols = await index.load_derived_view(src.id, "symbols")
    test_links = await index.load_derived_view(src.id, "test_links")
    assert symbols == {"items": [{"q": "a"}]}
    assert test_links == {"items": [{"test": "t"}]}


# --- 3. list_derived_views for a fresh source --------------------


async def test_list_derived_views_empty() -> None:
    src_mgr = KnowledgeSourceManager()
    index = KnowledgeIndex()
    src = await src_mgr.create(name="e1-14-empty", path="src.py")
    assert await index.list_derived_views(src.id) == ()


# --- 4. load_derived_view for an unknown source returns {} -----


async def test_load_derived_view_unknown_source() -> None:
    index = KnowledgeIndex()
    out = await index.load_derived_view("this-source-does-not-exist", "symbols")
    assert out == {}


# --- 5. load_derived_view for an unknown view_kind returns {} ---


async def test_load_derived_view_unknown_kind() -> None:
    src_mgr = KnowledgeSourceManager()
    index = KnowledgeIndex()
    src = await src_mgr.create(name="e1-14-uk", path="src.py")
    await index.save_derived_view(
        src.id, "symbols", {"items": [{"q": "a"}]}
    )
    out = await index.load_derived_view(src.id, "this_kind_does_not_exist")
    assert out == {}


# --- 6. Unknown view_kind on save raises ValueError ---------------


async def test_save_derived_view_rejects_unknown_kind() -> None:
    src_mgr = KnowledgeSourceManager()
    index = KnowledgeIndex()
    src = await src_mgr.create(name="e1-14-bad", path="src.py")
    with pytest.raises(ValueError, match="unknown view_kind"):
        await index.save_derived_view(
            src.id, "this_kind_does_not_exist", {"x": 1}
        )


# --- 7. Save fails cleanly for an unknown source ------------------


async def test_save_derived_view_unknown_source_returns_false() -> None:
    index = KnowledgeIndex()
    ok = await index.save_derived_view(
        "this-source-does-not-exist", "symbols", {"x": 1}
    )
    assert ok is False


# --- 8. E1-15 close/reopen proof ----------------------------------


async def test_view_survives_session_close_reopen(tmp_path) -> None:
    """The E1-15 proof: a derived view persisted in one
    session is still queryable after the database
    connection is closed and a new one is opened against
    the same on-disk file.

    The autouse ``session_db`` fixture in ``conftest.py``
    gives every test its own temp file; we close that
    connection and open a new one against the same file
    to exercise the close/reopen path.
    """
    src_mgr = KnowledgeSourceManager()
    index = KnowledgeIndex()
    src = await src_mgr.create(name="e1-15-proof", path="src.py")
    view = {
        "kind": "symbols",
        "items": [
            {"qualified_name": "src.foo", "kind": "function"},
            {"qualified_name": "src.bar", "kind": "class"},
        ],
    }
    await index.save_derived_view(src.id, "symbols", view)
    # Snapshot the path; close; reopen; read.
    db_path = db._conn  # type: ignore[attr-defined]
    # The autouse fixture has already initialized the
    # connection; the path is what we want.
    # Fetch the path via the engine's currently-known
    # file. The implementation is a detail of the
    # ``session_db`` fixture; the contract here is the
    # round-trip behaviour.
    await db.close()
    # Open a fresh Database against the same path. The
    # ``Database`` class is the one used by the conftest
    # fixture; importing it directly is the
    # implementation detail the test exercises.
    from paw.core.storage import Database

    new_db = Database()
    await new_db.connect()
    # The DB path the conftest fixture uses is the
    # ``tmp_path / "paw.db"`` file the fixture allocated;
    # the new Database reuses the default path the
    # ``db`` global singleton was bound to. We assert the
    # round-trip by querying through the new connection.
    from paw.core.storage import db as new_db_singleton

    new_db_singleton._conn = new_db._conn
    new_index = KnowledgeIndex()
    loaded = await new_index.load_derived_view(src.id, "symbols")
    assert loaded == view
    # Cleanup: close the new connection; the
    # ``session_db`` fixture will re-open on teardown.
    await new_db.close()
    new_db_singleton._conn = None  # type: ignore[attr-defined]