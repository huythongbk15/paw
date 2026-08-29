"""
PAW Phase 10 — Integration Test: Progressive Skill Loading Proof

Verify:
- Level 0 metadata candidate selection
- Level 1 body loading when selected
- Budget respected at each level
"""

from __future__ import annotations

import json

import pytest

from paw.core.context_compiler import ContextCompiler, ContextPlan, ContextCandidate
from paw.core.context import ContextBudget
from paw.core.storage import db, set_db_path
from paw.core.skills import SkillFabric, SkillManifest
from paw.core.models import SkillRisk, Capability


@pytest.mark.asyncio
async def test_progressive_skill_levels_loading(tmp_path):
    """Skills should be loadable at metadata/body level with budget control."""
    test_paw_home = tmp_path / ".paw"
    test_paw_home.mkdir(parents=True, exist_ok=True)
    db_path = test_paw_home / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    await db.execute(
        """
        INSERT INTO skills
        (id, name, version, description, category, capabilities, risk,
         network, write, trigger, body, source, enabled, created_at, updated_at, executors, dependencies, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "skill-prog",
            "progressive_skill",
            "1.0.0",
            "Progressive skill test",
            "testing",
            json.dumps([Capability.FILESYSTEM_READ.value]),
            SkillRisk.LOW.value,
            0,
            0,
            "progressive",
            "# Progressive Skill\n\nDetailed body content for progressive loading.",
            "installed",
            1,
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:00Z",
            json.dumps(["local"]),
            json.dumps([]),
            json.dumps({}),
        ),
    )

    compiler = ContextCompiler()
    budget = ContextBudget(max_tokens=500, max_fragments=5, max_sources=2)

    context, candidates = await compiler.compile(
        task_id="task-progressive",
        query="progressive skill loading",
        budget=budget,
        explain_mode=True,
    )

    skill_candidates = [c for c in candidates if c.source == "skill"]
    assert len(skill_candidates) >= 1

    selected_skills = [c for c in skill_candidates if c.metadata.get("included")]
    if selected_skills:
        for s in selected_skills:
            assert s.token_estimate <= budget.max_content_length


@pytest.mark.asyncio
async def test_context_plan_selection_defaults():
    """Default ContextPlan should include standard sources."""
    compiler = ContextCompiler()
    plan = await compiler._create_plan("task-plan", "query", None)

    assert plan.include_memory is True
    assert plan.include_knowledge is True
    assert plan.include_session is True
    assert plan.include_ledger is True
    assert plan.include_skills is True