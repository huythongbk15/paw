"""E2-45: Extend canonical Plan with RESEARCH, SPIKE, IMPLEMENTATION purpose and effect constraints.

Four-layer evidence:
  1. Invariant  — Plan dataclass has purpose + effect_constraints fields
  2. Runtime    — PlanPurpose enum values; effect_constraints persisted
  3. Adversarial — invalid purpose rejected by runtime gate (E2-46)
  4. Measurable — to_dict includes new fields; schema has new columns

Decision level: D2.
"""
import json

import pytest

from paw.core.planner import Plan, Planner
from paw.core.reasoning_contracts import PlanPurpose
from paw.core.storage import db


def test_plan_purpose_default():
    plan = Plan(goal="test")
    assert plan.purpose == "implementation"
    assert plan.effect_constraints == []


def test_plan_purpose_values():
    assert PlanPurpose.RESEARCH.value == "research"
    assert PlanPurpose.SPIKE.value == "spike"
    assert PlanPurpose.IMPLEMENTATION.value == "implementation"


def test_plan_to_dict_includes_new_fields():
    plan = Plan(goal="test", purpose="research", effect_constraints=["read", "model_inference"])
    d = plan.to_dict()
    assert d["purpose"] == "research"
    assert d["effect_constraints"] == ["read", "model_inference"]


def test_plan_effect_constraints_json_roundtrip():
    constraints = ["read", "write", "network"]
    plan = Plan(goal="test", effect_constraints=constraints)
    d = plan.to_dict()
    json_str = json.dumps(d)
    d2 = json.loads(json_str)
    assert d2["effect_constraints"] == constraints


@pytest.mark.asyncio
async def test_plan_purpose_and_effect_constraints_persisted():
    """E2-45 runtime proof: purpose + effect_constraints survive DB round-trip."""
    planner = Planner()
    await db.write(
        "INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("task-ec-1", "sess-ec-1", "persist plan fields", "pending", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    plan = Plan(task_id="task-ec-1", session_id="sess-ec-1", goal="persist plan fields")
    plan.id = "plan-ec-1"
    plan.purpose = "research"
    plan.effect_constraints = ["read", "model_inference"]
    await planner._save(plan)

    loaded = await planner.get_plan(plan.id)
    assert loaded is not None
    assert loaded.purpose == "research"
    assert loaded.effect_constraints == ["read", "model_inference"]
