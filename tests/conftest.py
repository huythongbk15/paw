"""Shared pytest fixtures for PAW tests — per-test DB isolation (Cấp 2 + race fix).

Strategy
--------
Every test gets its **own** SQLite database file + connection (function-scoped),
built once per test. This eliminates the cross-test / cross-module connection
sharing that previously caused intermittent ``no such table: task_events``
errors (the global ``db`` singleton could be left pointing at a different file
by an unrelated test that called ``set_db_path``).

Why per-test (not module-scoped)?
    PAW's schema contains an FTS5 virtual table (``skill_fts``). Sharing a
    single file across many tests and truncating it repeatedly corrupts the
    FTS5 index (``vtable constructor failed`` / ``database disk image is
    malformed``). A fresh file per test isolates each FTS index and removes
    the need to truncate-share at all.

``policy_rules`` is part of the canonical SCHEMA (storage.py), so every fresh
DB already contains it (empty); Phase 14 tests observe the intended
"no seeded rules" baseline without manual table creation.
"""

from __future__ import annotations

import pytest

from paw.core.storage import db, set_db_path


@pytest.fixture(autouse=True)
async def session_db(tmp_path):
    """One fresh temp SQLite DB per *test* (schema built once per test).

    Autouse + function-scoped so every test starts from a clean,
    fully-initialized DB on its own file — no connection is ever shared
    across tests, so the global ``db`` singleton cannot leak state between
    tests. Tests that need a custom path call ``set_db_path`` themselves and
    override this baseline.
    """
    db_path = tmp_path / "paw.db"
    await set_db_path(db_path)
    await db.initialize()
    yield db_path
    # Teardown: close the connection and remove the file.
    await db.close()
    db_path.unlink(missing_ok=True)


async def _truncate_all_tables() -> None:
    """Delete every row from every user table, keeping the schema intact.

    FTS5 virtual tables (e.g. ``skill_fts``) do not support a plain
    ``DELETE FROM`` — doing so corrupts the index and later writes fail with
    ``vtable constructor failed``. For those we issue the special
    ``'delete-all'`` command instead.
    """
    if db._conn is None:
        await db.connect()
    rows = await db.fetch_all(
        "SELECT name, sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'"
    )
    for row in rows:
        name = row["name"]
        sql = (row["sql"] or "").lower()
        try:
            if "fts5" in sql:
                await db.write(f"INSERT INTO {name}({name}) VALUES('delete-all')")
            else:
                await db.write(f"DELETE FROM {name}")
        except Exception:
            # Table created lazily by some code path; safe to skip.
            pass


@pytest.fixture
async def reset_db(session_db):
    """Re-point the global connection at this test's DB and truncate all tables.

    A fresh connection per test mirrors isolated, no-cross-test state. Truncation
    gives a clean baseline on top of the fresh schema.
    """
    if db._conn is not None:
        await db.close()
    await set_db_path(session_db)
    await db.connect()
    await _truncate_all_tables()
    yield
    await _truncate_all_tables()


@pytest.fixture
async def temp_db(reset_db, session_db):
    """Default empty-DB fixture (no seeded policy rules).

    Yields the per-test DB path for backwards compatibility with tests that
    referenced the fixture's return value.
    """
    yield session_db
