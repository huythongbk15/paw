"""
PAW Phase 10 — Execution Profile (K) Integration Tests

Verify:
- ExecutionProfile is a rich config object
- Presets exist (precise, fast, safe, develop)
- resolved_autonomy_budget works
- resolved_context_budget works
- Integration with AutonomyController, ContextCompiler, ModelRouter, SkillFabric
- to_dict / from_dict roundtrip
"""

from __future__ import annotations

import pytest

from paw.core.execution_profile import (
    ExecutionProfile,
    PrivacyPreference,
    PRECISE,
    FAST,
    SAFE,
    DEVELOP,
    PRESETS,
    get_execution_profile,
    list_execution_profiles,
)
from paw.core.autonomy import AutonomyController, AutonomyProfile, AutonomyBudget
from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCompiler, ContextPlan
from paw.core.model_router import ModelRouter
from paw.core.skills import SkillFabric, SkillManifest
from paw.core.models import SkillRisk


def test_execution_profile_is_rich_object():
    """ExecutionProfile should expose rich configuration knobs."""
    p = ExecutionProfile(
        name="test",
        autonomy_profile=AutonomyProfile.AGGRESSIVE,
        privacy_preference=PrivacyPreference.CLOUD_ALLOWED,
        cost_priority=0.9,
        latency_priority=0.1,
        skill_categories=["testing"],
        skill_risk_tolerance=SkillRisk.MEDIUM,
        skill_confidence_threshold=0.4,
        progressive_loading=True,
        max_parallelism=3,
    )
    assert p.name == "test"
    assert p.autonomy_profile == AutonomyProfile.AGGRESSIVE
    assert p.privacy_preference == PrivacyPreference.CLOUD_ALLOWED
    assert p.skill_categories == ["testing"]
    assert p.skill_risk_tolerance == SkillRisk.MEDIUM
    assert p.max_parallelism == 3


def test_execution_profile_presets_exist():
    """Preset profiles must be available."""
    names = list_execution_profiles()
    assert "precise" in names
    assert "fast" in names
    assert "safe" in names
    assert "develop" in names
    assert "default" in names

    assert PRECISE.privacy_preference == PrivacyPreference.LOCAL_ONLY
    assert FAST.autonomy_profile == AutonomyProfile.AGGRESSIVE
    assert SAFE.autonomy_profile == AutonomyProfile.INTERACTIVE
    assert DEVELOP.autonomy_profile == AutonomyProfile.BALANCED


def test_resolved_autonomy_budget():
    """resolved_autonomy_budget should produce a valid AutonomyBudget."""
    budget = PRECISE.resolved_autonomy_budget()
    assert isinstance(budget, AutonomyBudget)
    assert budget.max_iterations > 0

    # Override should apply
    p = ExecutionProfile(
        name="override",
        autonomy_profile=AutonomyProfile.BALANCED,
        autonomy_budget_overrides={"max_iterations": 99},
    )
    b2 = p.resolved_autonomy_budget()
    assert b2.max_iterations == 99


def test_resolved_context_budget():
    """resolved_context_budget should return ContextBudget."""
    cb = FAST.resolved_context_budget()
    assert isinstance(cb, ContextBudget)
    assert cb.max_tokens > 0


def test_execution_profile_dict_roundtrip():
    """to_dict / from_dict should roundtrip."""
    p = SAFE
    d = p.to_dict()
    assert d["name"] == "safe"
    p2 = ExecutionProfile.from_dict(d)
    assert p2.name == p.name
    assert p2.autonomy_profile == p.autonomy_profile
    assert p2.privacy_preference == p.privacy_preference
    assert p2.skill_risk_tolerance == p.skill_risk_tolerance


def test_get_execution_profile_case_insensitive():
    """get_execution_profile should be case-insensitive."""
    assert get_execution_profile("FAST").name == "fast"
    assert get_execution_profile("Precise").name == "precise"
    # Unknown falls back to develop
    assert get_execution_profile("nope").name == "develop"


@pytest.mark.asyncio
async def test_execution_profile_influences_autonomy_controller():
    """AutonomyController should use execution profile budget."""
    controller = AutonomyController(execution_profile=PRECISE)
    assert controller.budget.max_iterations > 0
    assert controller.profile == AutonomyProfile.CONSERVATIVE

    # FAST profile should have higher iterations
    controller_fast = AutonomyController(execution_profile=FAST)
    assert controller_fast.budget.max_iterations > controller.budget.max_iterations


@pytest.mark.asyncio
async def test_execution_profile_influences_context_compiler():
    """ContextCompiler should use execution profile context budget."""
    compiler = ContextCompiler()
    context, candidates = await compiler.compile(
        task_id="test-ep-ctx",
        query="test execution profile context",
        execution_profile=FAST,
    )
    # Budget should be applied (no error)
    assert context is not None


@pytest.mark.asyncio
async def test_execution_profile_influences_skill_fabric():
    """SkillFabric.list_skills should filter by execution profile categories."""
    fabric = SkillFabric.__new__(SkillFabric)
    # Manually populate index with test manifests
    from paw.core.models import Capability
    m1 = SkillManifest(
        name="skill_a", version="1.0.0", description="a",
        category="testing", capabilities=[Capability.FILESYSTEM_READ],
        risk=SkillRisk.LOW, trigger="a", body="body",
    )
    m2 = SkillManifest(
        name="skill_b", version="1.0.0", description="b",
        category="other", capabilities=[Capability.FILESYSTEM_READ],
        risk=SkillRisk.HIGH, trigger="b", body="body",
    )
    fabric._manifest_index = {"skill_a": m1, "skill_b": m2}

    # Default: all enabled
    all_skills = fabric.list_skills()
    assert len(all_skills) == 2

    # Filter by category
    filtered = fabric.list_skills(execution_profile=PRECISE)
    # PRECISE has skill_categories=[] so no filter; risk tolerance LOW excludes HIGH risk
    assert all(s.risk.value != "high" for s in filtered)

    # Category filter
    cat_profile = ExecutionProfile(name="cat", skill_categories=["testing"])
    cat_filtered = fabric.list_skills(execution_profile=cat_profile)
    assert all(s.category == "testing" for s in cat_filtered)
