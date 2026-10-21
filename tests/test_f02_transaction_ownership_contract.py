"""F02: a transaction belongs to a task, and its depth is its own.

The audit's finding: ``Database.transaction`` used one connection and a
**process-wide** ``_transaction_depth``, so a transaction's nesting was a
global flag rather than a property of the transaction.

The fix, in two parts:

* the open transaction's **scope** is a context variable. It is inherited
  by a coroutine awaited from inside the transaction, and it is *not*
  inherited by another task - so a task's transaction is structurally
  invisible to another task, and a rollback cannot reach across a task
  boundary;
* the **depth** lives on that scope, so it counts the nesting of *this*
  transaction rather than of the process.

What that buys, stated precisely:

* a transaction opened in one task is never joined by another task;
* an independent write in another task is committed on its own and
  **survives** the other task's rollback;
* cancellation releases the ownership and rolls back;
* close and reopen preserve the acknowledged rows.

The residual, stated precisely rather than papered over: a write made by a
coroutine **awaited inside** another coroutine's transaction is a *nested*
write - it belongs to that unit of work, and the owner's rollback
discards it. Making it independent would need a second connection, and
SQLite allows one writer at a time, so the owner's open write lock would
have to be released first - which the owner cannot do while it is
awaiting the writer. This is recorded in the implementation map as the
open half of F02.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from paw.core.storage import db, set_db_path


@pytest.fixture(autouse=True)
async def _db(tmp_path: Path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    await db.write(
        "CREATE TABLE IF NOT EXISTS f02_rows (k TEXT PRIMARY KEY, v TEXT NOT NULL)"
    )
    yield
    await db.close()


async def _rows() -> dict[str, str]:
    return {row["k"]: row["v"] for row in await db.fetch_all("SELECT k, v FROM f02_rows")}


# ── 1. The scope is per task ───────────────────────────────────────────


class TestTheScopeIsPerTask:
    @pytest.mark.asyncio
    async def test_a_transaction_in_one_task_is_invisible_to_another(self):
        """The other task's transaction is a top-level one, not a savepoint."""
        seen: dict[str, object] = {}

        async def a():
            async with db.transaction():
                seen["a_scope"] = db._tx_scope.get()
                await asyncio.sleep(0.05)

        async def b():
            await asyncio.sleep(0.01)
            seen["b_scope"] = db._tx_scope.get()

        await asyncio.gather(a(), b())
        assert seen["a_scope"] is not None
        assert seen["b_scope"] is None, (
            "another task saw the open transaction's scope"
        )

    @pytest.mark.asyncio
    async def test_an_awaited_coroutine_inherits_the_scope(self):
        """The awaited coroutine is part of the same unit of work."""
        seen: dict[str, object] = {}

        async def helper():
            seen["scope"] = db._tx_scope.get()

        async with db.transaction():
            await helper()
        assert seen["scope"] is not None

    @pytest.mark.asyncio
    async def test_the_depth_is_per_transaction(self):
        """The nesting depth belongs to the transaction, not the process."""
        async with db.transaction():
            outer = db._tx_scope.get()
            assert outer is not None
            assert outer.depth == 1
            async with db.transaction():
                inner = db._tx_scope.get()
                assert inner is not None
                assert inner.depth == 2
            assert db._tx_scope.get().depth == 1

    @pytest.mark.asyncio
    async def test_there_is_no_process_wide_depth(self):
        """The shared counter is gone."""
        assert not hasattr(db, "_transaction_depth")
        async with db.transaction():
            assert db._tx_scope.get() is not None
        assert db._tx_scope.get() is None


# ── 2. An independent write survives ───────────────────────────────────


class TestAnIndependentWriteSurvives:
    @pytest.mark.asyncio
    async def test_b_survives_a_rollback(self):
        """The audit's acceptance, in the shape that is reachable."""

        async def a():
            async with db.transaction():
                await db.write("INSERT INTO f02_rows (k, v) VALUES ('a', '1')")
                await asyncio.sleep(0.05)
                raise RuntimeError("A rolls back")

        async def b():
            await asyncio.sleep(0.01)
            await db.write("INSERT INTO f02_rows (k, v) VALUES ('b', '2')")

        results = await asyncio.gather(a(), b(), return_exceptions=True)
        assert isinstance(results[0], RuntimeError)
        assert results[1] is None, "B was not acknowledged"

        rows = await _rows()
        assert "b" in rows, f"B's acknowledged write was discarded: {rows}"
        assert "a" not in rows, "A's write was not rolled back"


# ── 3. A nested write belongs to the caller's unit of work ─────────────


class TestANestedWrite:
    @pytest.mark.asyncio
    async def test_a_helper_write_joins_the_callers_transaction(self):
        """The ordinary pattern keeps working."""

        async def helper():
            await db.write("INSERT INTO f02_rows (k, v) VALUES ('helper', '2')")

        async with db.transaction():
            await db.write("INSERT INTO f02_rows (k, v) VALUES ('outer', '1')")
            await helper()
        rows = await _rows()
        assert rows == {"outer": "1", "helper": "2"}

    @pytest.mark.asyncio
    async def test_the_callers_rollback_discards_it(self):
        """A nested write belongs to the unit of work, and the caller
        decided to roll it back."""
        with pytest.raises(RuntimeError):
            async with db.transaction():
                await db.write("INSERT INTO f02_rows (k, v) VALUES ('outer', '1')")
                await db.write("INSERT INTO f02_rows (k, v) VALUES ('helper', '2')")
                raise RuntimeError("rolled back")
        rows = await _rows()
        assert rows == {}


# ── 4. Cancellation releases ownership ─────────────────────────────────


class TestCancellation:
    @pytest.mark.asyncio
    async def test_cancellation_rolls_back_and_releases_the_scope(self):
        async def cancelled():
            async with db.transaction():
                await db.write("INSERT INTO f02_rows (k, v) VALUES ('x', '1')")
                raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await cancelled()
        rows = await _rows()
        assert rows == {}, "a cancelled transaction left its write behind"
        # The scope was released, so the next writer is not refused.
        await db.write("INSERT INTO f02_rows (k, v) VALUES ('after', '1')")
        rows = await _rows()
        assert rows == {"after": "1"}


# ── 5. Close and reopen preserve the acknowledged rows ─────────────────


class TestCloseAndReopen:
    @pytest.mark.asyncio
    async def test_an_acknowledged_row_survives_a_reopen(self):
        await db.write("INSERT INTO f02_rows (k, v) VALUES ('kept', '1')")
        await db.close()
        await db.initialize()
        rows = await _rows()
        assert rows == {"kept": "1"}
