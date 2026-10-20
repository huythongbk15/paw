"""Independent async tasks cannot share a SQLite transaction acknowledgement."""

import asyncio

import pytest

from paw.core.storage import db


async def insert(name):
    await db.write(
        "INSERT INTO policy_rules(id, capability, decision, created_at) VALUES(?, 'read', 'allow', 'test')",
        (name,),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [False, True])
async def test_other_writer_waits_for_rollback_then_survives_reopen(explicit):
    entered = asyncio.Event()
    waiting = asyncio.Event()

    async def failed_writer():
        with pytest.raises(RuntimeError, match="injected"):
            async with db.transaction():
                await insert("failed")
                entered.set()
                await waiting.wait()
                # Give B a chance to finish if ownership is incorrectly shared.
                await asyncio.sleep(0.05)
                raise RuntimeError("injected")

    async def successful_writer():
        await entered.wait()
        waiting.set()
        if explicit:
            async with db.transaction():
                await insert("success")
        else:
            await insert("success")

    await asyncio.wait_for(asyncio.gather(failed_writer(), successful_writer()), 5)
    await db.close()
    await db.initialize()
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='success'")
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='failed'") is None


@pytest.mark.asyncio
async def test_cancelled_transaction_rolls_back_and_releases_ownership():
    entered = asyncio.Event()

    async def writer():
        async with db.transaction():
            await insert("cancelled")
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(writer())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(insert("survivor"), 5)
    await db.close()
    await db.initialize()
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='cancelled'") is None
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='survivor'")


@pytest.mark.asyncio
async def test_caught_nested_failure_rolls_back_inner_only():
    async with db.transaction():
        await insert("outer")
        with pytest.raises(ValueError):
            async with db.transaction():
                await insert("inner")
                raise ValueError("inner failed")
        await insert("after")
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='inner'") is None
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='outer'")
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='after'")


@pytest.mark.asyncio
async def test_reader_cannot_observe_other_tasks_uncommitted_row():
    entered = asyncio.Event()
    waiting = asyncio.Event()

    async def writer():
        with pytest.raises(RuntimeError):
            async with db.transaction():
                await insert("private")
                entered.set()
                await waiting.wait()
                await asyncio.sleep(0.05)
                raise RuntimeError("rollback")

    async def reader():
        await entered.wait()
        waiting.set()
        return await db.fetch_one("SELECT id FROM policy_rules WHERE id='private'")

    _, row = await asyncio.wait_for(asyncio.gather(writer(), reader()), 5)
    assert row is None


@pytest.mark.asyncio
@pytest.mark.parametrize("helper", ["bulk", "upsert", "get_or_create", "legacy"])
async def test_storage_helper_cannot_commit_the_enclosing_transaction(helper):
    row = {"id": "helper", "capability": "read", "decision": "allow", "created_at": "test"}
    with pytest.raises(RuntimeError):
        async with db.transaction():
            if helper == "bulk":
                await db.bulk_insert("policy_rules", [row])
            elif helper == "upsert":
                await db.upsert("policy_rules", row, ["id"])
            elif helper == "get_or_create":
                await db.get_or_create("policy_rules", "id=?", ("helper",), defaults=row)
            else:
                await db.execute(
                    "INSERT INTO policy_rules(id, capability, decision, created_at) VALUES('helper','read','allow','test')"
                )
            raise RuntimeError("outer rollback")
    await db.close()
    await db.initialize()
    assert await db.fetch_one("SELECT id FROM policy_rules WHERE id='helper'") is None
