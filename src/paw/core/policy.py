"""
PAW Core — Policy Guard

Capability-based allow/deny/ask decisions with condition evaluation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .logging import get_logger
from .models import Capability, PolicyDecision
from .storage import db

logger = get_logger(__name__)


class ConditionEvaluator(Protocol):
    """Protocol for evaluating policy conditions."""

    def evaluate(self, conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        ...


class DefaultConditionEvaluator:
    """Default condition evaluator supporting common condition types.

    Condition format:
        {
            "path_under": {"context_key": "path", "allowed_roots": ["/root1", "/root2"]},
            "max_size": {"context_key": "size", "value": 1024},
        }

    Or shorthand for common cases:
        {
            "path_under": "/root",           # implies context_key="path"
            "max_size": 1024,                # implies context_key="size"
            "path_matches": "*.txt",         # implies context_key="path"
        }
    """

    # Mapping from condition type to default context key
    CONTEXT_KEY_MAP = {
        "path_under": "path",
        "path_not_under": "path",
        "path_matches": "path",
        "capability_in": "capability",
        "capability_not_in": "capability",
        "max_size": "size",
        "min_size": "size",
        "regex_match": "value",
        "equals": "value",
        "not_equals": "value",
        "in": "value",
        "not_in": "value",
    }

    def evaluate(self, conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        """Evaluate all conditions. All must pass (AND logic)."""
        for key, expected in conditions.items():
            if not self._evaluate_single(key, expected, context):
                return False
        return True

    def _get_context_key(self, condition_key: str, expected: Any) -> str:
        """Get the context key for a condition."""
        if isinstance(expected, dict) and "context_key" in expected:
            return expected["context_key"]
        return self.CONTEXT_KEY_MAP.get(condition_key, condition_key)

    def _get_expected_value(self, expected: Any) -> Any:
        """Extract expected value from condition (handles both shorthand and full format)."""
        if isinstance(expected, dict) and "value" in expected:
            return expected["value"]
        if isinstance(expected, dict) and "allowed_roots" in expected:
            return expected["allowed_roots"]
        return expected

    def _evaluate_single(self, key: str, expected: Any, context: dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        context_key = self._get_context_key(key, expected)
        actual = context.get(context_key)
        expected_value = self._get_expected_value(expected)

        if actual is None:
            return False

        if key == "path_under":
            # Check if path is under allowed root(s)
            allowed_roots = expected_value if isinstance(expected_value, list) else [expected_value]
            path = Path(actual).resolve()
            return any(
                path.is_relative_to(Path(root).resolve()) for root in allowed_roots
            )

        if key == "path_not_under":
            # Check if path is NOT under forbidden root(s)
            forbidden_roots = expected_value if isinstance(expected_value, list) else [expected_value]
            path = Path(actual).resolve()
            return all(
                not path.is_relative_to(Path(root).resolve()) for root in forbidden_roots
            )

        if key == "path_matches":
            # Check if path matches pattern (fnmatch)
            import fnmatch
            pattern = expected_value
            return fnmatch.fnmatch(actual, pattern)

        if key == "capability_in":
            # Check if capability is in allowed list
            allowed = expected_value if isinstance(expected_value, list) else [expected_value]
            return actual in allowed

        if key == "capability_not_in":
            # Check if capability is NOT in forbidden list
            forbidden = expected_value if isinstance(expected_value, list) else [expected_value]
            return actual not in forbidden

        if key == "max_size":
            # Check if size is <= max
            try:
                return int(actual) <= int(expected_value)
            except (ValueError, TypeError):
                return False

        if key == "min_size":
            # Check if size is >= min
            try:
                return int(actual) >= int(expected_value)
            except (ValueError, TypeError):
                return False

        if key == "regex_match":
            # Check if value matches regex
            return bool(re.match(expected_value, str(actual)))

        if key == "equals":
            return actual == expected_value

        if key == "not_equals":
            return actual != expected_value

        if key == "in":
            # Check if value is in list
            values = expected_value if isinstance(expected_value, list) else [expected_value]
            return actual in values

        if key == "not_in":
            # Check if value is NOT in list
            values = expected_value if isinstance(expected_value, list) else [expected_value]
            return actual not in values

        # Unknown condition type - deny by default (fail-closed)
        logger.warning("unknown_condition_type", condition=key)
        return False


@dataclass
class PolicyRule:
    """A single policy rule."""
    id: str = ""
    capability: str = ""
    decision: str = ""  # PolicyDecision value
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "capability": self.capability,
            "decision": self.decision,
            "conditions": self.conditions,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
        }


class PolicyGuard:
    """Capability-based policy enforcement with condition evaluation."""

    def __init__(self, evaluator: ConditionEvaluator | None = None):
        self._default_decisions: dict[str, PolicyDecision] = {
            Capability.FILESYSTEM_READ: PolicyDecision.ALLOW,
            Capability.FILESYSTEM_WRITE: PolicyDecision.ASK,
            Capability.FILESYSTEM_DELETE: PolicyDecision.DENY,
            Capability.SHELL_EXECUTE: PolicyDecision.ASK,
            Capability.NETWORK_HTTP: PolicyDecision.ASK,
            Capability.PROCESS_SPAWN: PolicyDecision.DENY,
            Capability.GIT_READ: PolicyDecision.ALLOW,
            Capability.GIT_WRITE: PolicyDecision.ASK,
            Capability.SECRETS_READ: PolicyDecision.DENY,
            Capability.DESTRUCTIVE: PolicyDecision.DENY,
            Capability.FINANCIAL: PolicyDecision.DENY,
        }
        self._evaluator = evaluator or DefaultConditionEvaluator()

    async def check(
        self,
        capability: Capability,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Check if a capability is allowed with condition evaluation."""
        decision = self._default_decisions.get(capability, PolicyDecision.ASK)

        # Check for explicit rules in DB
        rule = await self._get_matching_rule(capability)
        if rule and rule.enabled:
            # Evaluate conditions if present
            if rule.conditions:
                ctx = context or {}
                if not self._evaluator.evaluate(rule.conditions, ctx):
                    # Conditions not met - fall back to default or deny
                    logger.info(
                        "policy_conditions_not_met",
                        capability=capability.value,
                        rule_id=rule.id,
                    )
                else:
                    decision = PolicyDecision(rule.decision)

        await self._log_check(capability, decision, context)
        return decision

    async def check_capabilities(
        self,
        capabilities: list[Capability],
        context: dict[str, Any] | None = None,
    ) -> dict[Capability, PolicyDecision]:
        """Check multiple capabilities at once."""
        results: dict[Capability, PolicyDecision] = {}
        for cap in capabilities:
            results[cap] = await self.check(cap, context)
        return results

    def is_allowed(self, capability: Capability) -> bool:
        """Quick check if capability is allowed (no DB lookup, no conditions)."""
        decision = self._default_decisions.get(capability, PolicyDecision.ASK)
        return decision == PolicyDecision.ALLOW

    def is_denied(self, capability: Capability) -> bool:
        """Quick check if capability is denied (no DB lookup, no conditions)."""
        decision = self._default_decisions.get(capability, PolicyDecision.ASK)
        return decision == PolicyDecision.DENY

    async def _get_matching_rule(self, capability: Capability) -> PolicyRule | None:
        """Get the highest priority matching rule from DB."""
        row = await db.fetchone(
            """
            SELECT * FROM policy_rules
            WHERE capability = ? AND enabled = 1
            ORDER BY priority DESC LIMIT 1
            """,
            (capability.value,),
        )
        if row:
            return PolicyRule(
                id=row["id"],
                capability=row["capability"],
                decision=row["decision"],
                conditions=json.loads(row["conditions"]) if row["conditions"] else {},
                priority=row["priority"],
                enabled=bool(row["enabled"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    async def _log_check(
        self,
        capability: Capability,
        decision: PolicyDecision,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log policy check."""
        logger.info(
            "policy_checked",
            capability=capability.value,
            decision=decision.value,
            context=context,
        )

    async def add_rule(
        self,
        capability: Capability,
        decision: PolicyDecision,
        priority: int = 0,
        conditions: dict[str, Any] | None = None,
    ) -> PolicyRule:
        """Add a policy rule."""
        import uuid
        rule = PolicyRule(
            id=uuid.uuid4().hex[:16],
            capability=capability.value,
            decision=decision.value,
            conditions=conditions or {},
            priority=priority,
        )
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO policy_rules (id, capability, decision, conditions, priority, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.id,
                    rule.capability,
                    rule.decision,
                    json.dumps(rule.conditions),
                    rule.priority,
                    rule.enabled,
                    rule.created_at.isoformat(),
                ),
            )
        logger.info("policy_rule_added", capability=capability.value, decision=decision.value)
        return rule

    async def list_rules(self) -> list[PolicyRule]:
        """List all policy rules."""
        rows = await db.fetchall(
            "SELECT * FROM policy_rules ORDER BY priority DESC, created_at DESC"
        )
        return [
            PolicyRule(
                id=row["id"],
                capability=row["capability"],
                decision=row["decision"],
                conditions=json.loads(row["conditions"]) if row["conditions"] else {},
                priority=row["priority"],
                enabled=bool(row["enabled"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]


# Default policy rules initialization
async def ensure_policy_table() -> None:
    """Ensure policy_rules table exists."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS policy_rules (
            id TEXT PRIMARY KEY,
            capability TEXT NOT NULL,
            decision TEXT NOT NULL,
            conditions TEXT, -- JSON
            priority INTEGER NOT NULL DEFAULT 0,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    # Insert default rules if table is empty
    count = await db.fetchone("SELECT COUNT(*) FROM policy_rules")
    if count and count[0] == 0:
        guard = PolicyGuard()
        for cap, decision in guard._default_decisions.items():
            await guard.add_rule(cap, decision, priority=0)


# Global guard instance
_policy_guard: PolicyGuard | None = None


def get_policy_guard() -> PolicyGuard:
    """Get the global policy guard instance."""
    global _policy_guard
    if _policy_guard is None:
        _policy_guard = PolicyGuard()
    return _policy_guard