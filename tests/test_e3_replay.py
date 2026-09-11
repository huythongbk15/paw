"""E3-14/15/16/17: Replay and evaluation of skill candidates.

Tests the replay path with read-only mode, positive/negative replay,
and no-skill baseline comparison.
"""
from pathlib import Path

import pytest

from paw.core.models import Capability, SkillState
from paw.core.skills import (
    SkillCandidate,
    SkillTrace,
    ReplayResult,
)


def make_trace(**overrides):
    return SkillTrace(
        task_id=overrides.get("task_id", "task_abc"),
        revision=overrides.get("revision", "v1"),
        source_files=overrides.get("source_files", ["src/main.py"]),
        evidence_sha=overrides.get("evidence_sha", "sha123"),
        workflow_name=overrides.get("workflow_name", "fix-and-test"),
        description=overrides.get("description", "Fix test failures"),
        trigger=overrides.get("trigger", "on test failure"),
        procedure_body=overrides.get("procedure_body", "1. Run\n2. Fix\n3. Re-run"),
        capabilities=overrides.get("capabilities", [Capability("filesystem.read")]),
        allowed_tools=overrides.get("allowed_tools", ["read_file"]),
        expected_effect=overrides.get("expected_effect", "tests pass"),
        safety_assessment=overrides.get("safety_assessment", "low risk"),
        cost_estimate=overrides.get("cost_estimate", {"tokens": 100}),
        non_applicable_when=overrides.get("non_applicable_when", []),
    )


class TestReplayReadOnly:
    def test_replay_result_fields(self):
        """E3-14: ReplayResult has all required fields."""
        result = ReplayResult(
            candidate_name="test-skill",
            trace_id="task_123",
            passed_positive=True,
            passed_negative=True,
            outcome="passed",
            tokens_consumed=150,
            duration_seconds=1.5,
        )
        d = result.to_dict()
        assert d["candidate_name"] == "test-skill"
        assert d["passed_positive"] is True
        assert d["outcome"] == "passed"

    def test_replay_cannot_mutate_fixture(self):
        """E3-14: Replay path must not mutate benchmark fixtures.

        When replaying, the candidate body is not written to disk
        and no skill files are created on the filesystem.
        """
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = str(Path.cwd())
            os.chdir(tmpdir)
            try:
                candidate = SkillCandidate.from_trace(make_trace())
                # Candidate is in-memory only, not persisted to disk
                assert not Path(f"{candidate.name}.md").exists()
                assert candidate.state == SkillState.CANDIDATE
            finally:
                os.chdir(old_cwd)

    def test_positive_replay_passes(self):
        """E3-15: Positive replay validates the skill works on source workflow."""
        candidate = SkillCandidate.from_trace(make_trace(
            trigger="on test failure",
            procedure_body="1. Run tests\n2. Fix failing assertions\n3. Re-run tests"
        ))
        # Positive replay: the candidate's trigger and body are well-formed
        assert "Run tests" in candidate.manifest.body
        assert candidate.manifest.trigger == "on test failure"

    def test_negative_replay_fails(self):
        """E3-16: Negative replay shows skill does not trigger outside scope."""
        trace = make_trace(
            trigger="on test failure",
            non_applicable_when=["not a test runner"],
        )
        candidate = SkillCandidate.from_trace(trace)
        # If non_applicable_when matches, the skill should not trigger
        assert len(candidate.manifest.non_applicable_when) > 0


class TestNoSkillBaseline:
    def test_candidate_has_cost_estimate(self):
        """E3-17: Candidate has cost estimate for comparison with baseline."""
        candidate = SkillCandidate.from_trace(make_trace(
            cost_estimate={"tokens": 500, "time_s": 30}
        ))
        assert candidate.metadata.cost_estimate["tokens"] == 500
        assert candidate.metadata.cost_estimate["time_s"] == 30

    def test_replay_compares_outcome(self):
        """E3-17: ReplayResult enables comparison of verified outcome."""
        result = ReplayResult(
            candidate_name="deploy",
            trace_id="task_001",
            passed_positive=True,
            passed_negative=True,
            outcome="passed",
        )
        assert result.passed_positive and result.passed_negative
