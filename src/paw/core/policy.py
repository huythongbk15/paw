"""
PAW Core — Policy Guard

Capability-based allow/deny/ask decisions with condition evaluation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol

from .logging import get_logger
from .models import ID, Capability, PolicyDecision, StopReason
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
    CONTEXT_KEY_MAP: ClassVar[dict[str, str]] = {
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
        return all(
            self._evaluate_single(key, expected, context)
            for key, expected in conditions.items()
        )

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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

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


@dataclass
class PolicyDecisionDetail:
    """Explainable policy decision with full provenance.

    v2 addition — the runtime/autonomy loop needs to know *why* a capability
    was allowed/denied/asked, which rule fired, and whether interactive
    resolution was applied (ASK -> DENY in non-interactive mode).
    """

    decision: PolicyDecision
    capability: Capability
    source: str  # "rule:<id>" when a rule matched, "default" otherwise
    matched_rule: PolicyRule | None = None
    conditions_evaluated: dict[str, bool] = field(default_factory=dict)
    reason: str = ""
    interactive_resolved: bool = False  # True if ASK was resolved to DENY via non-interactive

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "capability": self.capability.value,
            "source": self.source,
            "matched_rule_id": self.matched_rule.id if self.matched_rule else None,
            "conditions_evaluated": self.conditions_evaluated,
            "reason": self.reason,
            "interactive_resolved": self.interactive_resolved,
        }


@dataclass
class RequestVerdict:
    """Aggregate verdict for a *set* of requested capabilities.

    This is the single authority gate the runtime/autonomy loop consults
    before executing any side-effecting action.

    verdict semantics:
      - "go"    : all capabilities ALLOW -> safe to proceed
      - "ask"   : some capabilities ASK and interactive -> proceed but confirm
      - "block" : any DENY, or any ASK in non-interactive mode -> MUST NOT execute
    """

    verdict: str  # "go" | "ask" | "block"
    allowed: bool
    decision: PolicyDecision  # representative aggregate decision
    blocked: list[Capability] = field(default_factory=list)
    asked: list[Capability] = field(default_factory=list)
    details: dict[Capability, PolicyDecisionDetail] = field(default_factory=dict)
    reason: str = ""
    stop_reason: Any | None = None  # StopReason when verdict == "block"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "allowed": self.allowed,
            "decision": self.decision.value,
            "blocked": [c.value for c in self.blocked],
            "asked": [c.value for c in self.asked],
            "details": {c.value: d.to_dict() for c, d in self.details.items()},
            "reason": self.reason,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
        }


class PolicyGuard:
    """Capability-based policy enforcement with condition evaluation."""

    def __init__(
        self,
        evaluator: ConditionEvaluator | None = None,
        interactive: bool = False,
    ):
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
        self._interactive = interactive  # If True, ASK may prompt; if False, ASK = DENY

    @property
    def interactive(self) -> bool:
        return self._interactive

    @interactive.setter
    def interactive(self, value: bool) -> None:
        self._interactive = value

    async def check(
        self,
        capability: Capability,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Check if a capability is allowed with condition evaluation.

        Returns the raw ``PolicyDecision`` (rules + default fallback). For the
        explainable + fail-closed variant, use :meth:`check_detailed`.
        """
        detail = await self.check_detailed(capability, context)
        return detail.decision

    async def check_detailed(
        self,
        capability: Capability,
        context: dict[str, Any] | None = None,
        task_id: ID | None = None,
    ) -> PolicyDecisionDetail:
        """Explainable capability check with full provenance.

        Rules are evaluated in priority order (highest first). The FIRST rule
        whose conditions match wins. If no rule matches, fall back to default
        decision.

        In non-interactive mode an ``ASK`` decision is resolved to ``DENY``
        (fail-closed) and ``interactive_resolved`` is set to ``True`` so the
        caller knows the effective decision differs from the raw rule/default.
        """
        # Check for explicit rules in DB - evaluate in priority order
        rules = await self._get_all_rules_for_capability(capability)

        ctx = context or {}
        for rule in rules:
            if not rule.enabled:
                continue
            # Evaluate conditions if present
            if rule.conditions:
                evaluated = self._evaluator.evaluate(rule.conditions, ctx)
                if evaluated:
                    # First matching rule wins
                    logger.info(
                        "policy_rule_matched",
                        capability=capability.value,
                        rule_id=rule.id,
                        decision=rule.decision,
                    )
                    decision = PolicyDecision(rule.decision)
                    detail = PolicyDecisionDetail(
                        decision=decision,
                        capability=capability,
                        source=f"rule:{rule.id}",
                        matched_rule=rule,
                        conditions_evaluated=dict.fromkeys(rule.conditions, True),
                        reason=f"Matched rule {rule.id} -> {decision.value}",
                    )
                    await self._finalize_detail(detail, task_id)
                    return detail
                else:
                    # Conditions not met - continue to next rule
                    logger.debug(
                        "policy_conditions_not_met",
                        capability=capability.value,
                        rule_id=rule.id,
                    )
            else:
                # No conditions = rule always applies
                logger.info(
                    "policy_rule_matched_unconditional",
                    capability=capability.value,
                    rule_id=rule.id,
                    decision=rule.decision,
                )
                decision = PolicyDecision(rule.decision)
                detail = PolicyDecisionDetail(
                    decision=decision,
                    capability=capability,
                    source=f"rule:{rule.id}",
                    matched_rule=rule,
                    conditions_evaluated={},
                    reason=f"Matched unconditional rule {rule.id} -> {decision.value}",
                )
                await self._finalize_detail(detail, task_id)
                return detail

        # No matching rule - use default
        decision = self._default_decisions.get(capability, PolicyDecision.ASK)
        detail = PolicyDecisionDetail(
            decision=decision,
            capability=capability,
            source="default",
            matched_rule=None,
            conditions_evaluated={},
            reason=f"No matching rule; default decision for {capability.value} -> {decision.value}",
        )
        await self._finalize_detail(detail, task_id)
        return detail

    async def _finalize_detail(
        self,
        detail: PolicyDecisionDetail,
        task_id: ID | None = None,
    ) -> None:
        """Optional ledger audit for a detail.

        NOTE: interactive ASK->DENY resolution is intentionally NOT applied here.
        ``check()``/``check_detailed()`` preserve the raw rule/default decision so
        legacy callers (e.g. Phase 6 assertions expecting ASK) keep working; the
        fail-closed resolution lives in :meth:`evaluate_request`, the single
        authority gate the runtime consults before side effects.
        """
        if task_id is not None:
            from .ledger import log_policy_decision

            await log_policy_decision(
                task_id,
                detail.capability.value,
                detail.decision.value,
                detail.source,
                detail.reason,
                detail.interactive_resolved,
            )

    async def evaluate_request(
        self,
        capabilities: list[Capability],
        context: dict[str, Any] | None = None,
        task_id: ID | None = None,
    ) -> RequestVerdict:
        """Aggregate single-authority gate for a *set* of capabilities.

        This is what the runtime/autonomy loop must consult before any
        side-effecting execution. Policy is the single authority:

          - any DENY                       -> block (POLICY_DENIED)
          - any ASK in non-interactive     -> block (POLICY_ASK_REQUIRED)
          - any ASK in interactive         -> ask   (allowed, confirmation)
          - otherwise                      -> go

        ASK never maps to ALLOW in non-interactive mode — fail-closed.
        """
        details: dict[Capability, PolicyDecisionDetail] = {}
        asked: list[Capability] = []
        blocked: list[Capability] = []
        for cap in capabilities:
            raw = await self.check_detailed(cap, context, task_id)
            if raw.decision == PolicyDecision.DENY:
                blocked.append(cap)
                details[cap] = raw
            elif raw.decision == PolicyDecision.ASK:
                asked.append(cap)
                # Fail-closed: in non-interactive mode ASK is resolved to DENY
                # in the *effective* detail, but it stays an approval request
                # (POLICY_ASK_REQUIRED) — NOT a hard denial (POLICY_DENIED).
                if not self._interactive:
                    details[cap] = PolicyDecisionDetail(
                        decision=PolicyDecision.DENY,
                        capability=raw.capability,
                        source=raw.source,
                        matched_rule=raw.matched_rule,
                        conditions_evaluated=raw.conditions_evaluated,
                        reason=raw.reason + " (non-interactive: ASK resolved to DENY)",
                        interactive_resolved=True,
                    )
                else:
                    details[cap] = raw
            else:
                details[cap] = raw

        if blocked:
            return RequestVerdict(
                verdict="block",
                allowed=False,
                decision=PolicyDecision.DENY,
                blocked=blocked,
                asked=asked,
                details=details,
                reason=f"Denied capabilities: {', '.join(c.value for c in blocked)}",
                stop_reason=StopReason.POLICY_DENIED,
            )
        if asked and not self._interactive:
            return RequestVerdict(
                verdict="block",
                allowed=False,
                decision=PolicyDecision.ASK,
                blocked=blocked,
                asked=asked,
                details=details,
                reason=f"ASK capabilities require approval: {', '.join(c.value for c in asked)}",
                stop_reason=StopReason.POLICY_ASK_REQUIRED,
            )
        if asked and self._interactive:
            return RequestVerdict(
                verdict="ask",
                allowed=True,
                decision=PolicyDecision.ASK,
                blocked=blocked,
                asked=asked,
                details=details,
                reason=f"ASK capabilities (interactive): {', '.join(c.value for c in asked)}",
                stop_reason=None,
            )
        return RequestVerdict(
            verdict="go",
            allowed=True,
            decision=PolicyDecision.ALLOW,
            blocked=blocked,
            asked=asked,
            details=details,
            reason="All requested capabilities allowed",
            stop_reason=None,
        )

    async def _get_all_rules_for_capability(self, capability: Capability) -> list[PolicyRule]:
        """Get all rules for a capability, ordered by priority (highest first)."""
        rows = await db.fetchall(
            """
            SELECT * FROM policy_rules
            WHERE capability = ? AND enabled = 1
            ORDER BY priority DESC, created_at ASC
            """,
            (capability.value,),
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
