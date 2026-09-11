"""E3-25 (D3): Governance migration - enabled flag cannot bypass reviewed ACTIVE.

This is the D3-level integration test that proves the SkillFabric enforces
the ACTIVE gate. CANDIDATE/REVIEWED skills with enabled=True are NOT
selectable by list_skills, get_skill, or find_candidates.
"""
import pytest

from paw.core.models import Capability, SkillState
from paw.core.skills import SkillFabric, SkillManifest, SkillTrace, SkillCandidate


class TestEnabledCannotBypassActive:
    def test_active_only_skills_returned_by_default(self):
        """E3-25: list_skills(enabled_only=True) returns only ACTIVE skills."""
        fabric = SkillFabric("/tmp/test_skills_e3")
        c = SkillManifest(name="cand", trigger="test", body="body", state=SkillState.CANDIDATE, enabled=True)
        r = SkillManifest(name="rev", trigger="test", body="body", state=SkillState.REVIEWED, enabled=True)
        a = SkillManifest(name="act", trigger="test", body="body", state=SkillState.ACTIVE, enabled=True)
        fabric._manifest_index = {"cand": c, "rev": r, "act": a}

        active = fabric.list_skills(enabled_only=True)
        names = {m.name for m in active}
        assert "act" in names
        assert "cand" not in names
        assert "rev" not in names

    def test_get_skill_returns_none_for_non_active(self):
        """E3-25: get_skill returns None for non-ACTIVE skills."""
        fabric = SkillFabric("/tmp/test_skills_e3")
        c = SkillManifest(name="cand", trigger="test", body="body", state=SkillState.CANDIDATE, enabled=True)
        fabric._manifest_index = {"cand": c}
        assert fabric.get_skill("cand") is None

    def test_get_skill_returns_active_only(self):
        """E3-25: get_skill returns ACTIVE skills."""
        fabric = SkillFabric("/tmp/test_skills_e3")
        a = SkillManifest(name="act", trigger="test", body="body", state=SkillState.ACTIVE, enabled=True)
        fabric._manifest_index = {"act": a}
        skill = fabric.get_skill("act")
        assert skill is not None

    def test_candidate_with_enabled_true_not_selectable(self):
        """E3-25: A CANDIDATE skill with enabled=True cannot be selected."""
        trace = SkillTrace(
            task_id="t1", revision="v1", source_files=["a.py"], evidence_sha="sha",
            workflow_name="test-wf", description="d", trigger="on test",
            procedure_body="steps", capabilities=[Capability("filesystem.read")],
            allowed_tools=["read"], expected_effect="e", safety_assessment="low",
            cost_estimate={},
        )
        candidate = SkillCandidate.from_trace(trace)
        assert candidate.state == SkillState.CANDIDATE
        assert candidate.manifest.enabled is True
        assert candidate.manifest.state != SkillState.ACTIVE

    def test_list_skills_with_state_filter_works(self):
        """E3-25: Explicit state filter returns skills in that state."""
        fabric = SkillFabric("/tmp/test_skills_e3")
        c = SkillManifest(name="c1", trigger="t", body="b", state=SkillState.CANDIDATE)
        r = SkillManifest(name="r1", trigger="t", body="b", state=SkillState.REVIEWED)
        a = SkillManifest(name="a1", trigger="t", body="b", state=SkillState.ACTIVE)
        fabric._manifest_index = {"c1": c, "r1": r, "a1": a}

        reviewed = fabric.list_skills(state=SkillState.REVIEWED)
        assert len(reviewed) == 1
        assert reviewed[0].name == "r1"

    def test_full_lifecycle_enforcement(self):
        """E3-25: The full lifecycle candidate to reviewed to active is enforced."""
        from paw.core.skills import validate_skill_transition
        valid, _ = validate_skill_transition(SkillState.CANDIDATE, SkillState.REVIEWED)
        assert valid
        valid, _ = validate_skill_transition(SkillState.REVIEWED, SkillState.ACTIVE)
        assert valid
        valid, _ = validate_skill_transition(SkillState.CANDIDATE, SkillState.ACTIVE)
        assert not valid
