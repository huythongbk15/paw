"""
Core Models Tests
"""

from __future__ import annotations

from paw.core.models import (
    ID_LENGTH,
    Capability,
    Identified,
    Metadata,
    ModelRole,
    PolicyDecision,
    Result,
    SkillRisk,
    TaskStatus,
    _generate_id,
    _validate_id,
)


class TestIdentifiers:
    def test_generate_id(self):
        id1 = _generate_id()
        id2 = _generate_id()
        assert len(id1) == ID_LENGTH
        assert len(id2) == ID_LENGTH
        assert id1 != id2

    def test_validate_id_valid(self):
        assert _validate_id("abc123def") == "abc123def"
        assert _validate_id("a" * 8) == "a" * 8

    def test_validate_id_invalid(self):
        try:
            _validate_id("")
            raise AssertionError("Should have raised")
        except ValueError:
            pass

        try:
            _validate_id("short")
            raise AssertionError("Should have raised")
        except ValueError:
            pass


class TestEnums:
    def test_task_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"

    def test_policy_decision_values(self):
        assert PolicyDecision.ALLOW == "allow"
        assert PolicyDecision.DENY == "deny"
        assert PolicyDecision.ASK == "ask"
        assert PolicyDecision.SANDBOX == "sandbox"

    def test_capability_values(self):
        assert Capability.FILESYSTEM_READ == "filesystem.read"
        assert Capability.SHELL_EXECUTE == "shell.execute"
        assert Capability.DESTRUCTIVE == "destructive"

    def test_model_role_values(self):
        assert ModelRole.FAST == "fast"
        assert ModelRole.REASONING == "reasoning"
        assert ModelRole.CODING == "coding"

    def test_skill_risk_values(self):
        assert SkillRisk.LOW == "low"
        assert SkillRisk.HIGH == "high"


class TestResult:
    def test_success(self):
        result = Result.success("hello")
        assert result.ok is True
        assert result.value == "hello"
        assert result.error is None

    def test_failure(self):
        result = Result.failure("something went wrong")
        assert result.ok is False
        assert result.value is None
        assert result.error == "something went wrong"


class TestMetadata:
    def test_get_set(self):
        meta = Metadata()
        meta.set("key1", "value1")
        assert meta.get("key1") == "value1"
        assert meta.get("missing", "default") == "default"


class TestIdentified:
    def test_auto_id(self):
        obj = Identified()
        assert obj.id is not None
        assert len(obj.id) == ID_LENGTH

    def test_custom_id(self):
        obj = Identified(id="custom-id-123456")
        assert obj.id == "custom-id-123456"
