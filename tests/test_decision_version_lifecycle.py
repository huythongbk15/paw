"""Lifecycle publication is distinct from snapshot storage and execution authority."""

import asyncio
import sqlite3

import pytest

from paw.core.reasoning_contracts import DecisionVersion
from paw.core.storage import db


async def parent():
    await db.write(
        "INSERT INTO tasks (id, session_id, goal, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("t", "s", "review", "now", "now"),
    )
    return await db.record_decision("readiness", "ready", task_id="t", session_id="s",
                                    project_revision="revision", constraint_fingerprint="constraints")


def version(decision_id, identity, state, actor="reviewer"):
    return DecisionVersion(identity, decision_id, state, {"readiness": "ready"},
                           "2026-10-06T00:00:00Z", actor)


async def test_lifecycle_reopen_retry_and_conflict():
    decision = await parent()
    draft = version(decision, "draft", "draft")
    final = version(decision, "final", "final")
    await db.advance_decision_version(draft, expected_version_id=None)
    await db.advance_decision_version(final, expected_version_id="draft")
    await db.advance_decision_version(final, expected_version_id="draft")
    with pytest.raises(ValueError, match="head conflict"):
        await db.advance_decision_version(version(decision, "wrong", "final"), expected_version_id="draft")
    assert await db.get_decision_version("wrong") is None
    await db.close()
    await db.connect()
    assert await db.get_current_decision_version(decision) == final
    assert await db.get_decision_version("draft") == draft
    assert await db.get_current_decision_version("missing") is None


async def test_orphan_final_and_missing_actor_cannot_publish():
    decision = await parent()
    orphan = version(decision, "orphan", "final")
    await db.save_decision_version(orphan)
    assert await db.get_current_decision_version(decision) is None
    with pytest.raises(ValueError, match="initial"):
        await db.advance_decision_version(orphan, expected_version_id=None)
    with pytest.raises(ValueError, match="actor"):
        await db.advance_decision_version(version(decision, "blank", "draft", ""), expected_version_id=None)


@pytest.mark.parametrize("target", ["draft", "final", "stale"])
async def test_terminal_cannot_be_resurrected(target):
    decision = await parent()
    for identity, state, previous in (
        ("draft", "draft", None), ("final", "final", "draft"),
        ("stale", "stale", "final"), ("superseded", "superseded", "stale"),
    ):
        await db.advance_decision_version(version(decision, identity, state), expected_version_id=previous)
    with pytest.raises(ValueError, match="transition"):
        await db.advance_decision_version(version(decision, "resurrect", target), expected_version_id="superseded")
    assert await db.get_decision_version("resurrect") is None


async def test_head_and_version_rollback_together():
    decision = await parent()
    draft = version(decision, "draft", "draft")
    await db.advance_decision_version(draft, expected_version_id=None)
    with pytest.raises(RuntimeError):
        async with db.transaction():
            await db.advance_decision_version(version(decision, "final", "final"), expected_version_id="draft")
            raise RuntimeError("rollback")
    await db.close()
    await db.connect()
    assert await db.get_current_decision_version(decision) == draft
    assert await db.get_decision_version("final") is None


async def test_competing_publications_have_one_winner():
    decision = await parent()
    await db.advance_decision_version(version(decision, "draft", "draft"), expected_version_id=None)
    results = await asyncio.gather(*(
        db.advance_decision_version(version(decision, identity, "final"), expected_version_id="draft")
        for identity in ("one", "two")
    ), return_exceptions=True)
    assert sum(isinstance(result, ValueError) for result in results) == 1
    current = await db.get_current_decision_version(decision)
    loser = "two" if current.version_id == "one" else "one"
    assert await db.get_decision_version(loser) is None


async def test_publication_history_is_append_only():
    decision = await parent()
    await db.advance_decision_version(version(decision, "draft", "draft"), expected_version_id=None)
    await db.advance_decision_version(version(decision, "final", "final"), expected_version_id="draft")
    for sql in (
        "UPDATE decision_version_publications SET previous_version_id = NULL WHERE version_id = 'final'",
        "DELETE FROM decision_version_publications WHERE version_id = 'final'",
        "INSERT OR REPLACE INTO decision_version_publications "
        "SELECT * FROM decision_version_publications WHERE version_id = 'final'",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            await db.write(sql)
    publications = await db.fetch_all("SELECT * FROM decision_version_publications")
    assert len(publications) == 2
    assert (await db.get_current_decision_version(decision)).version_id == "final"


@pytest.mark.parametrize("initial,target", [("draft", "stale"), ("final", "draft"), ("final", "final")])
async def test_invalid_transition_does_not_store_snapshot(initial, target):
    decision = await parent()
    await db.advance_decision_version(version(decision, "draft", "draft"), expected_version_id=None)
    if initial == "final":
        await db.advance_decision_version(version(decision, "final", "final"), expected_version_id="draft")
    with pytest.raises(ValueError, match="transition"):
        await db.advance_decision_version(version(decision, "invalid", target), expected_version_id=initial)
    assert await db.get_decision_version("invalid") is None


async def test_v5_upgrade_keeps_orphan_final_non_current():
    decision = await parent()
    orphan = version(decision, "orphan", "final")
    await db.save_decision_version(orphan)
    # Only a disposable fixture DB: simulate the prior snapshot-only layout.
    await db.write("DROP TABLE decision_version_publications")
    await db.write("PRAGMA user_version = 5")
    await db.close()
    await db.initialize()
    assert await db.get_decision_version("orphan") == orphan
    assert await db.get_current_decision_version(decision) is None
    await db.advance_decision_version(version(decision, "draft", "draft"), expected_version_id=None)
    await db.initialize()
    assert (await db.get_current_decision_version(decision)).version_id == "draft"
