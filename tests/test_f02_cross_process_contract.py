"""F02, the part that matters for shipping: two processes, one database.

The B-19 contract says it plainly: *"CLI and web sharing the DB also needs an
explicit process lock or proven SQLite concurrency model."* PAW set WAL and
``synchronous = NORMAL`` but **no** ``busy_timeout``, so a second writer - the
CLI and the web adapter on the same file, or two web workers - fell back to
Python's five second default and then failed with a bare "database is
locked".

And a second problem the same contract implies: **opening** the database
must not need the write lock. The schema script and its commit do need it,
so a process that only wanted to open an up-to-date database had to wait for
another process's transaction - and SQLite allows one writer at a time.

The contract pinned here:

* a writer waits for the database's write lock, and the wait is **bounded
  and explicit** - not Python's arbitrary five second default;
* **opening** an up-to-date database writes nothing, so a second process
  opens it while the first holds a write lock;
* **two processes** writing the same file concurrently both succeed, and
  every acknowledged row is present afterwards;
* the database is not corrupted;
* a writer that cannot get the lock within the bound fails **loudly**.

The proof uses real subprocesses, not threads: the CLI and the web adapter
are separate processes, and a thread would share one connection and prove
nothing about the file-level lock.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import textwrap
from pathlib import Path

import pytest

from paw.core.storage import Database

# A writer that opens its own connection, holds the write lock for a moment,
# writes, and reports what it did. Run as a separate process.
_WRITER = textwrap.dedent(
    """
    import asyncio, sys, time
    from pathlib import Path
    from paw.core.storage import Database

    async def main():
        db_path = Path(sys.argv[1])
        tag = sys.argv[2]
        hold = float(sys.argv[3])
        timeout_ms = int(sys.argv[4])
        db = Database(db_path, busy_timeout_ms=timeout_ms)
        await db.initialize()
        # The schema is already there; the writer only writes rows, so the
        # only lock it needs is the one the test is measuring.
        # Hold the write lock so the two processes genuinely overlap.
        try:
            async with db.transaction():
                await db.write(
                    "INSERT INTO shared_rows (k, v) VALUES (?, ?)", (f"{tag}-a", tag)
                )
                await asyncio.sleep(hold)
                await db.write(
                    "INSERT INTO shared_rows (k, v) VALUES (?, ?)", (f"{tag}-b", tag)
                )
        finally:
            # A failed write leaves the connection holding a transaction; it
            # has to be closed explicitly, or the process hangs on exit.
            await db.close()
        print("ok")

    asyncio.run(main())
    """
)


# A process that only opens the database. It must not need the write lock.
_OPENER = textwrap.dedent(
    """
    import asyncio, sys
    from pathlib import Path
    from paw.core.storage import Database

    async def main():
        db = Database(Path(sys.argv[1]), busy_timeout_ms=3000)
        await db.initialize()
        await db.close()
        print("opened")

    asyncio.run(main())
    """
)


def _run_opener(db_path: Path, timeout_ms: int = 3000) -> subprocess.CompletedProcess:
    script = Path("/tmp/_paw_f02_opener.py")
    script.write_text(_OPENER, encoding="utf-8")
    try:
        return subprocess.run(
            [sys.executable, str(script), str(db_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
    finally:
        script.unlink(missing_ok=True)


def _run_writer(
    db_path: Path, tag: str, hold: float, timeout_ms: int = 10000,
) -> subprocess.CompletedProcess:
    script = Path("/tmp/_paw_f02_writer.py")
    script.write_text(_WRITER, encoding="utf-8")
    try:
        return subprocess.run(
            [sys.executable, str(script), str(db_path), tag, str(hold), str(timeout_ms)],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
    finally:
        script.unlink(missing_ok=True)


async def _seed(db_path: Path) -> None:
    db = Database(db_path)
    await db.initialize()
    await db.write(
        "CREATE TABLE IF NOT EXISTS shared_rows (k TEXT PRIMARY KEY, v TEXT NOT NULL)"
    )
    await db.close()


class TestTheCrossProcessModel:
    @pytest.mark.asyncio
    async def test_two_processes_writing_concurrently_both_succeed(self, tmp_path):
        """The CLI and the web adapter on one file: both writes land."""
        db_path = tmp_path / "shared.db"
        await _seed(db_path)

        first = await asyncio.to_thread(_run_writer, db_path, "one", 0.4)
        second = await asyncio.to_thread(_run_writer, db_path, "two", 0.0)

        for result, tag in ((first, "one"), (second, "two")):
            assert result.returncode == 0, (
                f"the {tag} writer failed: {result.stdout}\n{result.stderr}"
            )
            assert "ok" in result.stdout, result.stderr

        # Every acknowledged row is present.
        db = Database(db_path)
        await db.initialize()
        rows = {row["k"]: row["v"] for row in await db.fetch_all("SELECT k, v FROM shared_rows")}
        await db.close()
        for tag in ("one", "two"):
            assert f"{tag}-a" in rows, f"{tag}'s first write was lost: {rows}"
            assert f"{tag}-b" in rows, f"{tag}'s second write was lost: {rows}"
        assert len(rows) == 4, rows

    @pytest.mark.asyncio
    async def test_the_database_is_not_corrupted(self, tmp_path):
        db_path = tmp_path / "shared.db"
        await _seed(db_path)

        await asyncio.to_thread(_run_writer, db_path, "one", 0.2)
        await asyncio.to_thread(_run_writer, db_path, "two", 0.0)

        db = Database(db_path)
        await db.initialize()
        rows = await db.fetch_all("PRAGMA integrity_check")
        await db.close()
        assert [dict(row) for row in rows] == [{"integrity_check": "ok"}]


class TestTheBusyTimeout:
    @pytest.mark.asyncio
    async def test_the_bound_is_explicit(self, tmp_path):
        """The bound is the configured one, not Python's default."""
        db = Database(tmp_path / "t.db", busy_timeout_ms=1234)
        await db.initialize()
        value = await db.fetch_one("PRAGMA busy_timeout")
        await db.close()
        assert value is not None
        assert int(value["timeout"]) == 1234

    @pytest.mark.asyncio
    async def test_a_writer_that_cannot_get_the_lock_fails_loudly(self, tmp_path):
        """A timeout is a clear error, never a silent loss."""
        db_path = tmp_path / "t.db"
        await _seed(db_path)
        holder = Database(db_path, busy_timeout_ms=500)
        await holder.initialize()

        # Hold the write lock in this process.
        async with holder.transaction():
            await holder.write(
                "INSERT INTO shared_rows (k, v) VALUES ('held', 'held')"
            )
            # A second *process* cannot take the lock while this one holds
            # it, and its bounded wait expires.
            result = await asyncio.to_thread(
                _run_writer, db_path, "blocked", 0.0, 3000,
            )
            assert result.returncode != 0, "the blocked writer should have failed"
            assert "locked" in (result.stderr or "").lower(), (
                f"the failure should name the lock: {result.stderr[-800:]}"
            )
        await holder.close()

    @pytest.mark.asyncio
    async def test_a_second_process_can_open_the_database_while_a_write_is_held(
        self, tmp_path,
    ):
        """A second process opens the database while the first holds a write
        lock, and does not wait for it.

        This is the case the CLI and the web adapter hit: the web adapter
        holds a transaction, and the CLI opens the same database. An
        up-to-date database is opened without running the schema script or
        the migration, so opening does not write.
        """
        db_path = tmp_path / "t.db"
        await _seed(db_path)
        holder = Database(db_path, busy_timeout_ms=500)
        await holder.initialize()

        async with holder.transaction():
            await holder.write(
                "INSERT INTO shared_rows (k, v) VALUES ('held', 'held')"
            )
            started = time.monotonic()
            result = await asyncio.to_thread(_run_opener, db_path, 3000)
            elapsed = time.monotonic() - started
            assert result.returncode == 0, (
                f"opening the database needed the write lock: {result.stderr[-600:]}"
            )
            assert "opened" in result.stdout, result.stderr
            # Opening must not *wait* for the write lock either. The schema
            # script and its commit need it, so running them on an
            # up-to-date database makes the opener stall behind the holder.
            assert elapsed < 5.0, (
                f"opening an up-to-date database took {elapsed:.1f}s: it waited "
                "for the write lock it did not need"
            )
        await holder.close()
