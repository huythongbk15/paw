"""E3-23/E3-25 (D3): E3 integration pack.

End-to-end test proving the full skill lifecycle:
trace -> candidate -> review -> approve -> deprecate -> rollback.

Also proves E3-25: enabled flag cannot bypass reviewed ACTIVE gate.
"""
import pytest

from paw.core.models import Capability, SkillState, ReviewRecord, ApprovalRecord
from paw.core.skills import (
    SkillCandidate,
    SkillTrace,
    SkillFabric,
    SkillManifest,
    validate_skill_transition,
)


def make_trace(
    task_id: str = "task_001",
    workflow_name: str = "lint-and-fix",
    procedure_body: str = "1. Run ruff\n2. Fix issues\n3. Re-run ruff",
    trigger: str = "on lint failure",
    capabilities: list | None = None,
    **overrides,
) -> SkillTrace:
    return SkillTrace(
        task_id=task_id,
        revision="v1",
        source_files=["src/main.py"],
        evidence_sha="sha123",
        workflow_name=workflow_name,
        description="Lint and fix workflow",
        trigger=trigger,
        procedure_body=procedure_body,
        capabilities=capabilities or [Capability.FILESYSTEM_READ],
        allowed_tools=["execute_shell_command"],
        expected_effect="Zero lint errors",
        safety_assessment="Low risk, bounded to src/",
        cost_estimate={"tokens": 100},
        **overrides,
    )


class TestFullLifecycle:
    """E3-23: Full trace to candidate to review to approve to deprecate to rollback."""

    def test_full_lifecycle(self):
        """E3-23: Full skill lifecycle transitions are valid."""
        trace = make_trace()
        candidate = SkillCandidate.from_trace(trace)
        assert candidate.state == SkillState.CANDIDATE

        valid, evidence = validate_skill_transition(SkillState.CANDIDATE, SkillState.REVIEWED)
        assert valid
        assert evidence == "review_record"

        valid, evidence = validate_skill_transition(SkillState.REVIEWED, SkillState.ACTIVE)
        assert valid
        assert evidence == "approval_record"

        valid, evidence = validate_skill_transition(SkillState.ACTIVE, SkillState.DEPRECATED)
        assert valid
        assert evidence == "deprecation_record"

        valid, evidence = validate_skill_transition(SkillState.DEPRECATED, SkillState.ACTIVE)
        assert valid
        assert evidence == "rollback_record"

    def test_candidate_has_trace_links(self):
        """E3-24: Candidate preserves research, decision, implementation, verification links."""
        trace = make_trace()
        candidate = SkillCandidate.from_trace(trace)
        assert len(candidate.metadata.trace_links) == 1
        link = candidate.metadata.trace_links[0]
        assert link.task_id == trace.task_id
        assert link.evidence_sha == trace.evidence_sha
        assert "src/main.py" in link.source_files

    def test_illegal_transition_candidate_to_active(self):
        """E3-03/E3-25: CANDIDATE cannot jump to ACTIVE without review."""
        valid, _ = validate_skill_transition(SkillState.CANDIDATE, SkillState.ACTIVE)
        assert not valid

    def test_illegal_transition_active_to_reviewed(self):
        """E3-03: ACTIVE cannot go back to REVIEWED."""
        valid, _ = validate_skill_transition(SkillState.ACTIVE, SkillState.REVIEWED)
        assert not valid


class TestEnabledCannotBypassActive:
    """E3-25: enabled=True does not make a CANDIDATE/REVIEWED skill selectable."""

    def test_candidate_not_in_active_list(self):
        """E3-25: A CANDIDATE with enabled=True is not in the ACTIVE list."""
        fabric = SkillFabric("/tmp/test_e3_integration")
        manifest = SkillManifest(
            name="cand_skill",
            trigger="test trigger",
            body="test body",
            state=SkillState.CANDIDATE,
            enabled=True,
        )
        fabric._manifest_index = {"cand_skill": manifest}
        active = fabric.list_skills(enabled_only=True)
        assert all(m.state == SkillState.ACTIVE for m in active)
        assert not any(m.name == "cand_skill" for m in active)

    def test_reviewed_not_in_active_list(self):
        """E3-25: A REVIEWED skill with enabled=True is not in the ACTIVE list."""
        fabric = SkillFabric("/tmp/test_e3_integration")
        manifest = SkillManifest(
            name="rev_skill",
            trigger="test trigger",
            body="test body",
            state=SkillState.REVIEWED,
            enabled=True,
        )
        fabric._manifest_index = {"rev_skill": manifest}
        active = fabric.list_skills(enabled_only=True)
        assert not any(m.name == "rev_skill" for m in active)

    def test_active_in_active_list(self):
        """E3-25: An ACTIVE skill appears in the ACTIVE list."""
        fabric = SkillFabric("/tmp/test_e3_integration")
        manifest = SkillManifest(
            name="act_skill",
            trigger="test trigger",
            body="test body",
            state=SkillState.ACTIVE,
            enabled=True,
        )
        fabric._manifest_index = {"act_skill": manifest}
        active = fabric.list_skills(enabled_only=True)
        assert any(m.name == "act_skill" for m in active)


class TestDescribeSkill:
    """E3-22: Inspect output shows skill state, source, provenance."""

    def test_describe_returns_full_info(self):
        """E3-22: describe_skill returns state, version, source, provenance."""
        fabric = SkillFabric("/tmp/test_e3_integration")
        manifest = SkillManifest(
            name="my_skill",
            trigger="on test",
            body="steps",
            state=SkillState.ACTIVE,
            skill_version="1.2.0",
            expected_effect="tests pass",
            review_record=ReviewRecord(
                reviewer="test_user",
                reviewed_at="2026-09-11T00:00:00+00:00",
                diff_summary="initial draft",
                safety_assessment="low",
                expected_effect="tests pass",
            ),
            approval_record=ApprovalRecord(
                approver="test_user",
                approved_at="2026-09-11T01:00:00+00:00",
                skill_version="1.2.0",
                notes="approved",
            ),
        )
        fabric._manifest_index = {"my_skill": manifest}

        info = fabric.describe_skill("my_skill")
        assert info is not None
        assert info["name"] == "my_skill"
        assert info["state"] == "active"
        assert info["skill_version"] == "1.2.0"
        assert info["review_record"]["reviewer"] == "test_user"
        assert info["approval_record"]["approver"] == "test_user"

    def test_describe_returns_none_for_unknown(self):
        """E3-22: describe_skill returns None for unknown skills."""
        fabric = SkillFabric("/tmp/test_e3_integration")
        assert fabric.describe_skill("nonexistent") is None
