"""F02, the last half: a write that must survive its transaction's rollback.

The audit's acceptance is *"Independent B survives A rollback"*, and the
honest question is what "independent" can mean under SQLite's rule that
there is one writer.

**A whole independent transaction cannot be opened inside another one.** The
owner holds the database's write lock while it is awaiting the writer, so
the writer could neither take the lock nor commit. That is not a
configuration problem; it is the shape of the constraint.

**A statement can be deferred.** It is applied on its own connection once
the owner has released the lock, and it is committed independently of the
owner's outcome. So the contract is not "a nested write becomes
independent" - that would break the caller's atomicity - but:

* ``write()`` **joins** the enclosing unit of work, so a convenience write
  is discarded with the transaction it belongs to. That is what a rollback
  means, and the party that rolled back owns the outcome.
* ``write_independent()`` is the explicit form: the write must outlive
  the transaction that queued it - an audit row, a receipt, the record
  that the attempt happened at all.

The contract pinned here:

* an independent write **survives** the enclosing transaction's rollback;
* a convenience write is discarded with the transaction it joined;
* outside a transaction an independent write is an ordinary durable write
  and reports its real row count;
* a failure to apply a deferred write is raised **by the enclosing
  transaction**, so the party that owns the transaction is the one that
  learns about it - not a writer that already returned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.core.storage import Database, db, set_db_path


@pytest.fixture(autouse=True)
async def _db(tmp_path: Path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    await db.write("CREATE TABLE IF NOT EXISTS rows_t (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
    yield
    await db.close()


async def _rows() -> dict[str, str]:
    return {row["k"]: row["v"] for row in await db.fetch_all("SELECT k, v FROM rows_t")}


class TestTheIndependentWrite:
    @pytest.mark.asyncio
    async def test_it_survives_the_rollbacks_of_the_transaction_that_queued_it(self):
        """The audit's acceptance, in the form SQLite allows."""
        with pytest.raises(RuntimeError, match="rolled back"):
            async with db.transaction():
                await db.write("INSERT INTO rows_t (k, v) VALUES ('joined', '1')")
                await db.write_independent(
                    "INSERT INTO rows_t (k, v) VALUES ('independent', '2')"
                )
                raise RuntimeError("rolled back")
        rows = await _rows()
        assert "independent" in rows, (
            f"the independent write was discarded with the transaction: {rows}"
        )

    @pytest.mark.asyncio
    async def test_a_convenience_write_joins_the_unit_of_work(self):
        """The caller's atomicity is intact: a rollback discards it."""
        with pytest.raises(RuntimeError, match="rolled back"):
            async with db.transaction():
                await db.write("INSERT INTO rows_t (k, v) VALUES ('joined', '1')")
                raise RuntimeError("rolled back")
        rows = await _rows()
        assert "joined" not in rows, rows

    @pytest.mark.asyncio
    async def test_it_survives_a_commit_too(self):
        """An independent write is independent of the outcome, not just the
        rollback."""
        async with db.transaction():
            await db.write_independent("INSERT INTO rows_t (k, v) VALUES ('kept', '1')")
        rows = await _rows()
        assert rows == {"kept": "1"}, rows

    @pytest.mark.asyncio
    async def test_outside_a_transaction_it_is_an_ordinary_durable_write(self):
        """No transaction, no deferral: the write lands and counts."""
        count = await db.write_independent(
            "INSERT INTO rows_t (k, v) VALUES ('direct', '1')"
        )
        assert count == 1
        rows = await _rows()
        assert rows == {"direct": "1"}, rows

    @pytest.mark.asyncio
    async def test_a_deferred_write_reports_no_row_count_yet(self):
        """The row count is not known until the write is applied."""
        async with db.transaction():
            count = await db.write_independent(
                "INSERT INTO rows_t (k, v) VALUES ('later', '1')"
            )
        assert count == 0
        rows = await _rows()
        assert rows == {"later": "1"}, rows

    @pytest.mark.asyncio
    async def test_a_failure_to_apply_is_raised_by_the_owning_transaction(self):
        """The party that owns the transaction is the one that learns.

        The writer already returned - it cannot know the outcome, because
        the write is applied after it returns. So the failure surfaces at
        the end of the transaction that queued it.
        """
        with pytest.raises(Exception) as exc:
            async with db.transaction():
                # A constraint violation: the key already exists.
                await db.write("INSERT INTO rows_t (k, v) VALUES ('dupe', '1')")
                await db.write_independent(
                    "INSERT INTO rows_t (k, v) VALUES ('dupe', '2')"
                )
        assert "dupe" in str(exc.value) or "unique" in str(exc.value).lower(), (
            f"the failure should name the constraint: {exc.value}"
        )


class TestTheIndependentWriteIsOnItsOwnConnection:
    @pytest.mark.asyncio
    async def test_it_does_not_join_the_owners_transaction(self):
        """A deferred write is applied on a separate connection, so the
        owner's outcome cannot reach it."""
        await db.write("INSERT INTO rows_t (k, v) VALUES ('owner', '1')")
        async with db.transaction():
            await db.write_independent("INSERT INTO rows_t (k, v) VALUES ('other', '2')")
        rows = await _rows()
        assert rows == {"owner": "1", "other": "2"}, rows
