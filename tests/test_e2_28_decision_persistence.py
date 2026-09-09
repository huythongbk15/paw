"""E2-28: Persist decision and project revision through centralized schema.

Four-layer evidence:
  1. Invariant  - decision_records table exists with required columns
  2. Runtime    - record_decision/get_decision/get_decisions_by_task work
  3. Adversarial - project_revision / constraint_fingerprint tracking
  4. Measurable - migration is additive (no DROP, no data loss)

Decision level: D3.
"""
import json

import pytest

from paw.core.storage import SCHEMA, db


class TestInvariantSchema:
    def test_inv1_table_exists_in_schema(self):
        assert "CREATE TABLE IF NOT EXISTS decision_records" in SCHEMA

    def test_inv2_required_columns(self):
        required = {
            "id", "task_id", "session_id", "decision_type",
            "decision_value", "reason", "project_revision",
            "constraint_fingerprint", "metadata", "created_at", "updated_at",
        }
        for col in required:
            assert col in SCHEMA

    def test_inv3_no_drop_statements(self):
        assert "DROP TABLE" not in SCHEMA.upper()

    def test_inv4_project_revision_column(self):
        assert "project_revision TEXT" in SCHEMA

    def test_inv5_constraint_fingerprint_column(self):
        assert "constraint_fingerprint TEXT" in SCHEMA


class TestRuntimeDecisionCRUD:
    @pytest.mark.asyncio
    async def test_rt1_record_and_retrieve(self, session_db):
        did = await db.record_decision(
            decision_type="readiness", decision_value="ready",
            task_id="task-123", session_id="sess-456",
            reason="preconditions met", project_revision="abc123",
            constraint_fingerprint="fp-789", metadata={"confidence": 0.95},
        )
        record = await db.get_decision(did)
        assert record is not None
        assert record["decision_type"] == "readiness"
        assert record["decision_value"] == "ready"
        assert record["project_revision"] == "abc123"
        assert record["constraint_fingerprint"] == "fp-789"
        assert record["reason"] == "preconditions met"

    @pytest.mark.asyncio
    async def test_rt2_get_decisions_by_task(self, session_db):
        await db.record_decision("readiness", "ready", task_id="t1", session_id="s1")
        await db.record_decision("policy", "allow", task_id="t1", session_id="s1")
        await db.record_decision("autonomy", "continue", task_id="t2", session_id="s2")
        decisions = await db.get_decisions_by_task("t1")
        assert len(decisions) == 2
        assert decisions[0]["decision_type"] == "readiness"
        assert decisions[1]["decision_type"] == "policy"

    @pytest.mark.asyncio
    async def test_rt3_get_nonexistent_returns_none(self, session_db):
        assert await db.get_decision("nonexistent") is None

    @pytest.mark.asyncio
    async def test_rt4_metadata_serialized(self, session_db):
        did = await db.record_decision(
            "readiness", "ready", task_id="t", session_id="s",
            metadata={"key": "value", "count": 3},
        )
        record = await db.get_decision(did)
        meta = json.loads(record["metadata"])
        assert meta["key"] == "value"
        assert meta["count"] == 3

    @pytest.mark.asyncio
    async def test_rt5_revision_tracks_project(self, session_db):
        id1 = await db.record_decision("readiness", "ready", task_id="t1",
                                       session_id="s1", project_revision="v1")
        id2 = await db.record_decision("readiness", "ready", task_id="t2",
                                       session_id="s2", project_revision="v2")
        r1 = await db.get_decision(id1)
        r2 = await db.get_decision(id2)
        assert r1["project_revision"] == "v1"
        assert r2["project_revision"] == "v2"


class TestAdversarialDecisionPersistence:
    @pytest.mark.asyncio
    async def test_adv1_empty_reason_allowed(self, session_db):
        did = await db.record_decision("readiness", "ready", task_id="t", session_id="s")
        record = await db.get_decision(did)
        assert record["reason"] == ""

    @pytest.mark.asyncio
    async def test_adv2_empty_revision_allowed(self, session_db):
        did = await db.record_decision("readiness", "ready", task_id="t", session_id="s")
        record = await db.get_decision(did)
        assert record["project_revision"] == ""

    @pytest.mark.asyncio
    async def test_adv3_null_task_id_allowed(self, session_db):
        did = await db.record_decision("readiness", "ready", task_id=None, session_id="s")
        record = await db.get_decision(did)
        assert record["task_id"] is None

    @pytest.mark.asyncio
    async def test_adv4_id_is_unique(self, session_db):
        id1 = await db.record_decision("readiness", "ready", task_id="t", session_id="s")
        id2 = await db.record_decision("readiness", "right", task_id="t", session_id="s")
        assert id1 != id2


class TestMeasurableMigrationAdditive:
    @pytest.mark.asyncio
    async def test_measure1_existing_tables_intact(self, session_db):
        tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {t["name"] for t in tables}
        assert "tasks" in table_names
        assert "task_events" in table_names
        assert "knowledge_sources" in table_names
        assert "decision_records" in table_names

    @pytest.mark.asyncio
    async def test_measure2_decision_record_count(self, session_db):
        await db.record_decision("readiness", "ready", task_id="t", session_id="s")
        await db.record_decision("policy", "allow", task_id="t", session_id="s")
        count = await db.fetch_one("SELECT COUNT(*) as cnt FROM decision_records")
        assert count["cnt"] == 2
