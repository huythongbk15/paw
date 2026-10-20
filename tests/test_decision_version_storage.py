"""Durable snapshots are evidence, not implementation admission."""

import sqlite3

import pytest

from paw.core.reasoning_contracts import DecisionVersion, DecisionVersionState
from paw.core.storage import db


async def make_parent(**changes):
    await db.write(
        "INSERT INTO tasks (id, session_id, goal, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)", ("t", "s", "review", "now", "now"),
    )
    values = {"task_id": "t", "session_id": "s", "project_revision": "source-hash",
              "constraint_fingerprint": "constraints-hash"}
    values.update(changes)
    return await db.record_decision("readiness", "ready", **values)


def snapshot(parent, version_id="v1", payload=None):
    return DecisionVersion(version_id, parent, DecisionVersionState.FINAL,
                           payload or {"readiness": "ready", "options": [{"name": "A"}]},
                           "2026-10-06T00:00:00+00:00", created_by="reviewer")


async def test_snapshot_reopen_idempotent_and_conflict(session_db):
    parent = await make_parent()
    version = snapshot(parent)
    await db.save_decision_version(version)
    await db.save_decision_version(version)
    with pytest.raises(ValueError, match="conflict"):
        await db.save_decision_version(snapshot(parent, payload={"readiness": "ready", "changed": True}))
    await db.close()
    await db.connect()
    loaded = await db.get_decision_version("v1")
    assert loaded == version
    with pytest.raises(TypeError):
        loaded.payload["options"][0]["name"] = "tampered"
    assert await db.get_decision_version("missing") is None


@pytest.mark.parametrize("changes", [
    {"task_id": "missing"}, {"session_id": "foreign"},
    {"project_revision": ""}, {"constraint_fingerprint": ""},
])
async def test_snapshot_rejects_unbound_parent(changes):
    parent = await make_parent(**changes)
    with pytest.raises(ValueError):
        await db.save_decision_version(snapshot(parent))
    assert await db.get_decision_version("v1") is None


async def test_snapshot_rejects_missing_policy_and_mismatched_readiness():
    parent = await make_parent()
    policy = await db.record_decision("policy", "allow", task_id="t", session_id="s",
                                     project_revision="rev", constraint_fingerprint="fp")
    for version in (snapshot("missing"), snapshot(policy),
                    snapshot(parent, payload={"readiness": "rejected"}),
                    snapshot(parent, payload={"readiness": "READY"})):
        with pytest.raises(ValueError):
            await db.save_decision_version(version)


async def test_snapshot_and_parent_cannot_be_updated_or_deleted():
    parent = await make_parent()
    await db.save_decision_version(snapshot(parent))
    for sql, params in (
        ("UPDATE decision_versions SET payload = '{}' WHERE version_id = ?", ("v1",)),
        ("DELETE FROM decision_versions WHERE version_id = ?", ("v1",)),
        ("UPDATE decision_records SET project_revision = 'tampered' WHERE id = ?", (parent,)),
        ("DELETE FROM decision_records WHERE id = ?", (parent,)),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            await db.write(sql, params)
    assert await db.get_decision_version("v1") == snapshot(parent)


async def test_snapshot_rolls_back_with_parent():
    with pytest.raises(RuntimeError, match="rollback"):
        async with db.transaction():
            parent = await make_parent()
            await db.save_decision_version(snapshot(parent))
            raise RuntimeError("rollback")
    await db.close()
    await db.connect()
    assert await db.get_decision_version("v1") is None
    assert await db.get_decision(parent) is None


async def test_snapshot_replace_cannot_bypass_immutable_triggers():
    parent = await make_parent()
    await db.save_decision_version(snapshot(parent))
    # SQLite REPLACE may delete without firing delete triggers; guard INSERT too.
    for sql, params in (
        ("INSERT OR REPLACE INTO decision_versions "
         "SELECT version_id, decision_id, state, '{}', created_at, created_by, superseded_by "
         "FROM decision_versions WHERE version_id = ?", ("v1",)),
        ("INSERT OR REPLACE INTO decision_records SELECT * FROM decision_records WHERE id = ?",
         (parent,)),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            await db.write(sql, params)
    await db.close()
    await db.connect()
    assert await db.get_decision_version("v1") == snapshot(parent)


async def test_snapshot_additive_v4_upgrade_preserves_legacy(session_db):
    parent = await make_parent()
    # Model the previous schema on this disposable test database only.
    await db.write("DROP TABLE decision_versions")
    await db.write("PRAGMA user_version = 4")
    await db.close()
    await db.initialize()
    assert (await db.get_decision(parent))["decision_value"] == "ready"
    assert await db.get_decision_version("v1") is None
    await db.save_decision_version(snapshot(parent))
    await db.initialize()
    assert await db.get_decision_version("v1") == snapshot(parent)
