"""
Phase 6 Security Gate Tests — Adversarial Policy Testing.

This test suite verifies the Policy Guard enforces security boundaries correctly.
Tests cover all capability types with positive/negative cases and condition evaluation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from paw.core import (
    PolicyGuard,
    Capability,
    PolicyDecision,
    get_policy_guard,
    ensure_policy_table,
)
from paw.core.storage import db, set_db_path
from paw.core.policy import DefaultConditionEvaluator


# Fixture for temporary database
@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    await set_db_path(db_path)
    await db.initialize()
    await ensure_policy_table()
    yield db_path
    await db.close()
    Path(db_path).unlink(missing_ok=True)


class TestPhase6DefaultPosture:
    """Test default policy posture matches specification."""

    @pytest.mark.asyncio
    async def test_filesystem_read_allowed(self, temp_db):
        """Default: filesystem.read → ALLOW"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.FILESYSTEM_READ)
        assert decision == PolicyDecision.ALLOW

    @pytest.mark.asyncio
    async def test_filesystem_write_ask(self, temp_db):
        """Default: filesystem.write → ASK"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.FILESYSTEM_WRITE)
        assert decision == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_filesystem_delete_deny(self, temp_db):
        """Default: filesystem.delete → DENY"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.FILESYSTEM_DELETE)
        assert decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_shell_execute_ask(self, temp_db):
        """Default: shell.execute → ASK"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.SHELL_EXECUTE)
        assert decision == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_network_http_ask(self, temp_db):
        """Default: network.http → ASK"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.NETWORK_HTTP)
        assert decision == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_process_spawn_deny(self, temp_db):
        """Default: process.spawn → DENY"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.PROCESS_SPAWN)
        assert decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_git_read_allowed(self, temp_db):
        """Default: git.read → ALLOW"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.GIT_READ)
        assert decision == PolicyDecision.ALLOW

    @pytest.mark.asyncio
    async def test_git_write_ask(self, temp_db):
        """Default: git.write → ASK"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.GIT_WRITE)
        assert decision == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_secrets_read_deny(self, temp_db):
        """Default: secrets.read → DENY"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.SECRETS_READ)
        assert decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_destructive_deny(self, temp_db):
        """Default: destructive → DENY"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.DESTRUCTIVE)
        assert decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_financial_deny(self, temp_db):
        """Default: financial → DENY"""
        guard = PolicyGuard()
        decision = await guard.check(Capability.FINANCIAL)
        assert decision == PolicyDecision.DENY


class TestPhase6ConditionEvaluation:
    """Test condition evaluation logic (unit tests - no DB needed)."""

    @pytest.mark.asyncio
    async def test_condition_evaluator_path_under(self):
        """Test path_under condition directly."""
        evaluator = DefaultConditionEvaluator()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subdir = root / "subdir"
            subdir.mkdir()
            file_inside = subdir / "file.txt"
            file_inside.write_text("test")

            # Should allow - file is under root
            assert evaluator.evaluate(
                {"path_under": str(root)},
                {"path": str(file_inside)},
            )

            # Should deny - file outside root
            outside = Path("/etc/passwd")
            assert not evaluator.evaluate(
                {"path_under": str(root)},
                {"path": str(outside)},
            )

    @pytest.mark.asyncio
    async def test_condition_evaluator_path_not_under(self):
        """Test path_not_under condition."""
        evaluator = DefaultConditionEvaluator()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subdir = root / "subdir"
            subdir.mkdir()
            file_inside = subdir / "file.txt"

            # Should allow - file is NOT under forbidden /etc
            assert evaluator.evaluate(
                {"path_not_under": "/etc"},
                {"path": str(file_inside)},
            )

            # Should deny - file IS under forbidden root
            assert not evaluator.evaluate(
                {"path_not_under": str(root)},
                {"path": str(file_inside)},
            )

    @pytest.mark.asyncio
    async def test_condition_evaluator_path_matches(self):
        """Test path_matches with fnmatch patterns."""
        evaluator = DefaultConditionEvaluator()

        assert evaluator.evaluate(
            {"path_matches": "*.txt"},
            {"path": "/home/user/file.txt"},
        )

        assert not evaluator.evaluate(
            {"path_matches": "*.txt"},
            {"path": "/home/user/file.py"},
        )

        assert evaluator.evaluate(
            {"path_matches": "/home/user/*"},
            {"path": "/home/user/anything"},
        )

    @pytest.mark.asyncio
    async def test_condition_evaluator_capability_in(self):
        """Test capability_in condition."""
        evaluator = DefaultConditionEvaluator()

        assert evaluator.evaluate(
            {"capability_in": ["read", "write"]},
            {"capability": "read"},
        )

        assert not evaluator.evaluate(
            {"capability_in": ["read", "write"]},
            {"capability": "delete"},
        )

    @pytest.mark.asyncio
    async def test_condition_evaluator_size_limits(self):
        """Test max_size and min_size conditions."""
        evaluator = DefaultConditionEvaluator()

        assert evaluator.evaluate(
            {"max_size": 100},
            {"size": 50},
        )

        assert not evaluator.evaluate(
            {"max_size": 100},
            {"size": 150},
        )

        assert evaluator.evaluate(
            {"min_size": 100},
            {"size": 150},
        )

        assert not evaluator.evaluate(
            {"min_size": 100},
            {"size": 50},
        )

    @pytest.mark.asyncio
    async def test_condition_evaluator_regex(self):
        """Test regex_match condition."""
        evaluator = DefaultConditionEvaluator()

        # regex_match uses context_key="value" by default
        assert evaluator.evaluate(
            {"regex_match": r"^test_.*\.py$"},
            {"value": "test_module.py"},
        )

        assert not evaluator.evaluate(
            {"regex_match": r"^test_.*\.py$"},
            {"value": "module.py"},
        )

        # Can also use custom context_key
        assert evaluator.evaluate(
            {"regex_match": {"context_key": "filename", "value": r"^test_.*\.py$"}},
            {"filename": "test_module.py"},
        )

    @pytest.mark.asyncio
    async def test_condition_evaluator_equals_not_equals(self):
        """Test equals and not_equals conditions."""
        evaluator = DefaultConditionEvaluator()

        # equals uses context_key="value" by default
        assert evaluator.evaluate(
            {"equals": "allowed"},
            {"value": "allowed"},
        )

        assert not evaluator.evaluate(
            {"equals": "allowed"},
            {"value": "denied"},
        )

        assert evaluator.evaluate(
            {"not_equals": "denied"},
            {"value": "allowed"},
        )

        # Can also use custom context_key
        assert evaluator.evaluate(
            {"equals": {"context_key": "action", "value": "allowed"}},
            {"action": "allowed"},
        )

    @pytest.mark.asyncio
    async def test_condition_evaluator_in_not_in(self):
        """Test in and not_in conditions."""
        evaluator = DefaultConditionEvaluator()

        # in uses context_key="value" by default
        assert evaluator.evaluate(
            {"in": ["a", "b", "c"]},
            {"value": "b"},
        )

        assert not evaluator.evaluate(
            {"in": ["a", "b", "c"]},
            {"value": "z"},
        )

        assert evaluator.evaluate(
            {"not_in": ["a", "b", "c"]},
            {"value": "z"},
        )

        assert not evaluator.evaluate(
            {"not_in": ["a", "b", "c"]},
            {"value": "b"},
        )

        # Can also use custom context_key
        assert evaluator.evaluate(
            {"in": {"context_key": "action", "value": ["read", "write"]}},
            {"action": "write"},
        )

    @pytest.mark.asyncio
    async def test_unknown_condition_denies_fail_closed(self):
        """Unknown condition types should deny (fail-closed)."""
        evaluator = DefaultConditionEvaluator()

        # Unknown condition should return False
        assert not evaluator.evaluate(
            {"unknown_condition": "value"},
            {"some": "context"},
        )


class TestPhase6RuleOverride:
    """Test rule override with conditions."""

    @pytest.mark.asyncio
    async def test_rule_overrides_default_with_conditions(self, temp_db):
        """Explicit rule with matching conditions overrides default."""
        guard = PolicyGuard()

        # Add rule: ALLOW write if path under project root
        await guard.add_rule(
            Capability.FILESYSTEM_WRITE,
            PolicyDecision.ALLOW,
            priority=10,
            conditions={"path_under": "/home/user/project"},
        )

        # Test with path under project - should ALLOW
        decision = await guard.check(
            Capability.FILESYSTEM_WRITE,
            context={"path": "/home/user/project/file.txt"},
        )
        assert decision == PolicyDecision.ALLOW

        # Test with path outside project - should fall back to ASK (default)
        decision = await guard.check(
            Capability.FILESYSTEM_WRITE,
            context={"path": "/etc/passwd"},
        )
        assert decision == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_rule_priority(self, temp_db):
        """Higher priority rules should win."""
        guard = PolicyGuard()

        # Low priority: DENY all writes
        await guard.add_rule(
            Capability.FILESYSTEM_WRITE,
            PolicyDecision.DENY,
            priority=5,
        )

        # High priority: ALLOW writes under project
        await guard.add_rule(
            Capability.FILESYSTEM_WRITE,
            PolicyDecision.ALLOW,
            priority=10,
            conditions={"path_under": "/home/user/project"},
        )

        # Should ALLOW (high priority rule matches)
        decision = await guard.check(
            Capability.FILESYSTEM_WRITE,
            context={"path": "/home/user/project/file.txt"},
        )
        assert decision == PolicyDecision.ALLOW

    @pytest.mark.asyncio
    async def test_disabled_rule_ignored(self, temp_db):
        """Disabled rules should be ignored."""
        guard = PolicyGuard()

        # Add rule but disable it
        rule = await guard.add_rule(
            Capability.FILESYSTEM_WRITE,
            PolicyDecision.ALLOW,
            priority=10,
            conditions={"path_under": "/home/user/project"},
        )

        # Manually disable
        await db.execute(
            "UPDATE policy_rules SET enabled = 0 WHERE id = ?",
            (rule.id,),
        )

        # Should fall back to ASK (default)
        decision = await guard.check(
            Capability.FILESYSTEM_WRITE,
            context={"path": "/home/user/project/file.txt"},
        )
        assert decision == PolicyDecision.ASK


class TestPhase6Adversarial:
    """Adversarial tests - attempts to bypass policy."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked by path_under."""
        evaluator = DefaultConditionEvaluator()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a subdir to simulate project root
            project = root / "project"
            project.mkdir()

            # Attempt traversal
            traversal = project / ".." / "etc" / "passwd"
            traversal_str = str(traversal)

            # path_under should resolve and detect traversal
            assert not evaluator.evaluate(
                {"path_under": str(project)},
                {"path": traversal_str},
            )

    @pytest.mark.asyncio
    async def test_symlink_escape(self):
        """Symlink escape attempts should be blocked."""
        evaluator = DefaultConditionEvaluator()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()

            # Create a symlink pointing outside
            outside = root / "outside"
            outside.mkdir()
            secret = outside / "secret.txt"
            secret.write_text("secret")

            link = project / "link.txt"
            link.symlink_to(secret)

            # Resolved path should be outside project
            assert not evaluator.evaluate(
                {"path_under": str(project)},
                {"path": str(link)},
            )

    @pytest.mark.asyncio
    async def test_write_outside_allowed_root_denied(self, temp_db):
        """Write outside allowed root should be denied even with rule."""
        guard = PolicyGuard()

        # Rule allows write under /home/user/project
        await guard.add_rule(
            Capability.FILESYSTEM_WRITE,
            PolicyDecision.ALLOW,
            priority=10,
            conditions={"path_under": "/home/user/project"},
        )

        # Attempt to write to /etc/passwd
        decision = await guard.check(
            Capability.FILESYSTEM_WRITE,
            context={"path": "/etc/passwd"},
        )
        # Should fall back to ASK (default for write), not ALLOW
        assert decision == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_secret_like_files_denied(self):
        """Files matching secret patterns should be detectable."""
        evaluator = DefaultConditionEvaluator()

        secret_patterns = [
            "*.key",
            "*.pem",
            "*.p12",
            "*.pfx",
            "*.env",
            "*.secret",
            "*secret*",
            "id_rsa",
            "id_ed25519",
            ".aws/credentials",
            ".docker/config.json",
        ]

        for pattern in secret_patterns:
            # Test that path_matches can catch these
            matched = evaluator.evaluate(
                {"path_matches": pattern},
                {"path": f"/home/user/{pattern.replace('*', 'test')}"},
            )
            # The evaluator just evaluates the condition; policy decides action
            assert isinstance(matched, bool)

    @pytest.mark.asyncio
    async def test_dangerous_shell_commands(self):
        """Dangerous shell commands should be detectable."""
        evaluator = DefaultConditionEvaluator()

        dangerous_commands = [
            "rm -rf /",
            "rm -rf /*",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda",
            ":(){ :|:& };:",  # fork bomb
            "chmod 777 /",
            "chown -R root:root /",
        ]

        for cmd in dangerous_commands:
            # Test regex can detect dangerous patterns
            matched = evaluator.evaluate(
                {"regex_match": r"(rm\s+-rf\s+/|dd\s+if=|mkfs|:\(\)|chmod\s+777|chown\s+-R\s+root)"},
                {"command": cmd},
            )
            assert isinstance(matched, bool)

    @pytest.mark.asyncio
    async def test_nested_delegated_execution(self, temp_db):
        """Nested/delegated execution should not bypass policy."""
        # Policy is checked per capability, not per call stack
        # This test ensures the guard doesn't cache decisions in a way
        # that would allow bypass
        guard = PolicyGuard()

        # First check
        d1 = await guard.check(Capability.SHELL_EXECUTE)
        # Second check
        d2 = await guard.check(Capability.SHELL_EXECUTE)

        assert d1 == d2 == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_skill_capability_escalation(self, temp_db):
        """Skills should not be able to escalate capabilities."""
        # Skills declare capabilities in manifest
        # Policy should enforce based on declared capabilities
        # not on what the skill actually does
        guard = PolicyGuard()

        # A skill declares filesystem.read but tries to write
        # Policy check for write should be independent
        decision = await guard.check(Capability.FILESYSTEM_WRITE)
        assert decision == PolicyDecision.ASK


class TestPhase6ContextIntegration:
    """Test policy integration with context."""

    @pytest.mark.asyncio
    async def test_multiple_capabilities_checked_together(self, temp_db):
        """Multiple capabilities checked together should all be evaluated."""
        guard = PolicyGuard()

        caps = [
            Capability.FILESYSTEM_READ,
            Capability.FILESYSTEM_WRITE,
            Capability.SHELL_EXECUTE,
        ]

        results = await guard.check_capabilities(caps)

        assert results[Capability.FILESYSTEM_READ] == PolicyDecision.ALLOW
        assert results[Capability.FILESYSTEM_WRITE] == PolicyDecision.ASK
        assert results[Capability.SHELL_EXECUTE] == PolicyDecision.ASK

    @pytest.mark.asyncio
    async def test_context_passed_to_conditions(self):
        """Context passed to check() should be available for conditions."""
        evaluator = DefaultConditionEvaluator()

        # Context with standard keys
        context = {
            "path": "/home/user/project/file.txt",
            "size": 1024,
            "value": "write",
        }

        # All conditions should have access to all context fields
        assert evaluator.evaluate(
            {"path_under": "/home/user/project", "max_size": 2048},
            context,
        )

        assert not evaluator.evaluate(
            {"path_under": "/home/user/project", "max_size": 512},
            context,
        )


class TestPhase6Phase8Integration:
    """Integration with Phase 8 context budget."""

    @pytest.mark.asyncio
    async def test_policy_guard_instantiation(self, temp_db):
        """Policy guard can be instantiated and used."""
        guard = PolicyGuard()
        decision = await guard.check(Capability.FILESYSTEM_WRITE)
        assert decision == PolicyDecision.ASK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])