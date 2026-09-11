"""E3-08/09/10/11/12: Candidate creation pipeline.

Tests creating candidates from traces, redacting secrets, detecting
duplicates and generating diffs.
"""
import pytest

from paw.core.models import Capability, SkillState
from paw.core.skills import (
    SkillCandidate,
    SkillTrace,
    redact_payload,
    detect_duplicate_candidates,
    generate_skill_diff,
    validate_skill_transition,
)


def make_trace(**overrides) -> SkillTrace:
    """Create a SkillTrace with defaults overrideable by keyword args."""
    params = {
        "task_id": "task_abc123",
        "revision": "rev_001",
        "source_files": ["src/main.py", "tests/test_main.py"],
        "evidence_sha": "abc123def456",
        "workflow_name": "fix-and-test",
        "description": "fix test failures",
        "trigger": "on test failure",
        "procedure_body": "1. Run tests\n2. Fix the bug\n3. Re-run tests",
        "capabilities": [Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE],
        "allowed_tools": ["read_file", "write_file", "execute_shell_command"],
        "expected_effect": "tests pass after fix",
        "safety_assessment": "low risk, bounded to test directory",
        "cost_estimate": {"tokens": 500, "time_s": 60},
        "non_applicable_when": [],
    }
    params.update(overrides)
    return SkillTrace(**params)


class TestCandidateFromTrace:
    def test_candidate_starts_as_candidate_state(self):
        """E3-02: New candidates start in CANDIDATE state."""
        trace = make_trace()
        candidate = SkillCandidate.from_trace(trace)
        assert candidate.state == SkillState.CANDIDATE

    def test_trace_links_preserved(self):
        """E3-09: The candidate preserves source trace links with provenance."""
        trace = make_trace(task_id="task_xyz789", revision="rev_002")
        candidate = SkillCandidate.from_trace(trace)
        assert len(candidate.metadata.trace_links) == 1
        link = candidate.metadata.trace_links[0]
        assert link.task_id == "task_xyz789"
        assert link.task_version == "rev_002"
        assert link.evidence_sha == "abc123def456"
        assert "src/main.py" in link.source_files

    def test_candidate_manifest_has_state(self):
        """E3-09: The manifest carries CANDIDATE state."""
        trace = make_trace()
        candidate = SkillCandidate.from_trace(trace)
        assert candidate.manifest.state == SkillState.CANDIDATE
        assert candidate.manifest.source == "trace_derived"

    def test_candidate_procedure_body_is_skills_only(self):
        """E3-09: The procedure body comes from the trace, not raw conversation."""
        trace = make_trace(procedure_body="Step 1: analyze\nStep 2: fix\nStep 3: verify")
        candidate = SkillCandidate.from_trace(trace)
        assert "Step 1: analyze" in candidate.manifest.body
        assert "Step 3: verify" in candidate.manifest.body

    def test_create_candidate_from_workflow(self):
        """E3-09: Structured workflow inputs create a valid candidate."""
        candidate = SkillCandidate.create_candidate_from_workflow(
            workflow_name="deploy-app",
            description="Deploy to staging",
            trigger="on git push to main",
            procedure_body="1. Build\n2. Test\n3. Deploy",
            capabilities=[Capability.SHELL_EXECUTE],
            allowed_tools=["execute_shell_command"],
            expected_effect="App deployed to staging",
            safety_assessment="medium - requires approval",
            cost_estimate={"tokens": 200},
            task_id="task_001",
            task_version="v1",
            source_files=["src/app.py"],
            evidence_sha="sha256:abc",
        )
        assert candidate.name == "deploy-app"
        assert candidate.state == SkillState.CANDIDATE
        assert "deploy-app" in candidate.manifest.name


class TestSecretRedaction:
    def test_api_key_redacted(self):
        """E3-10: API keys are redacted."""
        body = "Set api_key=sk-1234567890abcdef in environment"
        redacted = redact_payload(body)
        assert "sk-1234567890abcdef" not in redacted
        assert "REDACTED" in redacted

    def test_bearer_token_redacted(self):
        """E3-10: Bearer tokens are redacted."""
        body = "Authorization: bearer abc123.def456.ghi789"
        redacted = redact_payload(body)
        assert "abc123.def456.ghi789" not in redacted
        assert "bearer redacted" in redacted.lower()

    def test_private_path_redacted(self):
        """E3-10: Absolute private paths are redacted."""
        body = "Config is at /home/user/.config/app/config.yaml"
        redacted = redact_payload(body)
        assert "/home/user" not in redacted
        assert "[REDACTED_PATH]" in redacted

    def test_safe_content_preserved(self):
        """E3-10: Non-sensitive content is not redacted."""
        body = "Run tests with pytest\nCheck the output"
        redacted = redact_payload(body)
        assert redact_payload(body) == body

    def test_empty_input_safe(self):
        """E3-10: Empty input returns empty string."""
        assert redact_payload("") == ""
        assert redact_payload("no secrets here") == "no secrets here"


class TestDuplicateDetection:
    def test_exact_duplicate_detected(self):
        """E3-11: Identical candidates are flagged as duplicates."""
        trace = make_trace()
        c1 = SkillCandidate.from_trace(trace)
        c2 = SkillCandidate.from_trace(trace)
        dupes = detect_duplicate_candidates([c1, c2])
        assert len(dupes) > 0

    def test_distinct_candidates_not_flagged(self):
        """E3-11: Different triggers + different bodies are not duplicates."""
        c1 = SkillCandidate.from_trace(make_trace(
            trigger="on test failure", procedure_body="Fix the bug"
        ))
        c2 = SkillCandidate.from_trace(make_trace(
            task_id="task_diff",
            trigger="on feature request", procedure_body="Add feature"
        ))
        dupes = detect_duplicate_candidates([c1, c2])
        assert len(dupes) == 0

    def test_overlapping_trigger_detected(self):
        """E3-11: Same trigger words (overlapping) are flagged."""
        c1 = SkillCandidate.from_trace(make_trace(trigger="fix failing tests", procedure_body="A"))
        c2 = SkillCandidate.from_trace(make_trace(task_id="t2", trigger="fix failing tests", procedure_body="B"))
        dupes = detect_duplicate_candidates([c1, c2])
        assert len(dupes) > 0


class TestGenerateSkillDiff:
    def test_new_skill_diff(self):
        """E3-12: New skill diff shows it as new."""
        candidate = SkillCandidate.from_trace(make_trace())
        diff = generate_skill_diff(candidate, existing=None)
        assert "new skill" in diff.lower()
        assert candidate.name in diff

    def test_modified_skill_diff(self):
        """E3-12: Diff against existing shows changes."""
        trace = make_trace(procedure_body="Step 1: analyze")
        candidate = SkillCandidate.from_trace(trace)
        existing = SkillCandidate.from_trace(make_trace(
            procedure_body="Step 1: old approach"
        )).to_manifest()
        diff = generate_skill_diff(candidate, existing=existing)
        assert "Diff" in diff
        assert "old approach" in diff or "analyze" in diff
