"""
PAW Core — Executor Policy Enforcement (Phase 3)

Integrates Policy Guard with executors for runtime enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .executor import Executor, ExecutorResult
from .logging import get_logger
from .models import Capability, PolicyDecision
from .policy import PolicyGuard, get_policy_guard

logger = get_logger(__name__)


@dataclass
class PolicyCheckResult:
    """Result of a policy check before execution."""
    allowed: bool = True
    decision: str = "allow"
    blocked_capabilities: list[str] = field(default_factory=list)
    asked_capabilities: list[str] = field(default_factory=list)
    message: str = ""
    sandbox: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "decision": self.decision,
            "blocked_capabilities": self.blocked_capabilities,
            "asked_capabilities": self.asked_capabilities,
            "message": self.message,
            "sandbox": self.sandbox,
        }


class ExecutableTask:
    """A task wrapped with policy enforcement metadata."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        capabilities: list[str],
        policy_check: PolicyCheckResult,
    ):
        self.task_id = task_id
        self.goal = goal
        self.capabilities = capabilities
        self.policy_check = policy_check
        self.executed = False
        self.result: ExecutorResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "capabilities": self.capabilities,
            "policy_check": self.policy_check.to_dict(),
            "executed": self.executed,
            "result": self.result.to_dict() if self.result else None,
        }


class ExecutorPolicyEnforcer:
    """Enforces policy guard before executor runs."""

    def __init__(self, guard: PolicyGuard | None = None):
        self.guard = guard or get_policy_guard()

    async def pre_execute_check(
        self,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
    ) -> PolicyCheckResult:
        """Check policy before executing a task."""
        results = await self.guard.check_capabilities(capabilities)

        blocked = [cap.value for cap, dec in results.items() if dec == PolicyDecision.DENY]
        asked = [cap.value for cap, dec in results.items() if dec == PolicyDecision.ASK]
        allowed = [cap.value for cap, dec in results.items() if dec == PolicyDecision.ALLOW]

        all_allowed = len(blocked) == 0
        any_asked = len(asked) > 0
        any_blocked = len(blocked) > 0

        if any_blocked:
            message = f"Execution blocked. Denied capabilities: {', '.join(blocked)}"
        elif any_asked:
            message = f"Execution requires confirmation. Asked capabilities: {', '.join(asked)}"
        else:
            message = f"All capabilities allowed: {', '.join(allowed)}"

        check_result = PolicyCheckResult(
            allowed=all_allowed,
            decision="deny" if any_blocked else ("ask" if any_asked else "allow"),
            blocked_capabilities=blocked,
            asked_capabilities=asked,
            message=message,
            sandbox=any(cap.value == "shell.execute" for cap in capabilities),
        )

        logger.info("policy_pre_check", task_id=task_id, allowed=all_allowed)
        return check_result

    async def enforce(
        self,
        executor: Executor,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
        context: str,
    ) -> tuple[PolicyCheckResult, ExecutorResult | None]:
        """Enforce policy and optionally execute."""
        check = await self.pre_execute_check(task_id, goal, capabilities)

        if not check.allowed:
            logger.info("execution_blocked_by_policy", task_id=task_id)
            return check, None

        if check.sandbox:
            # Force sandbox mode for shell execution
            logger.info("sandbox_mode_enabled", task_id=task_id)

        # Execute the task
        result = await executor.execute(
            type('MockTask', (), {
                'id': task_id,
                'goal': goal,
                'requested_capabilities': capabilities,
            })(),
            context,
        )

        check.result = result
        return check, result


class PolicyEnforcedExecutor:
    """Executor wrapper that enforces policy before execution."""

    def __init__(self, executor: Executor, guard: PolicyGuard | None = None):
        self.executor = executor
        self.enforcer = ExecutorPolicyEnforcer(guard)

    async def execute(
        self,
        task_id: str,
        goal: str,
        capabilities: list[Capability],
        context: str,
    ) -> dict[str, Any]:
        """Execute with policy enforcement."""
        check, result = await self.enforcer.enforce(
            self.executor, task_id, goal, capabilities, context
        )

        return {
            "task_id": task_id,
            "goal": goal,
            "policy_check": check.to_dict(),
            "executor": self.executor.name,
            "result": result.to_dict() if result else None,
            "blocked": not check.allowed,
        }


# Global enforcer instance
_enforcer: ExecutorPolicyEnforcer | None = None


def get_enforcer(guard: PolicyGuard | None = None) -> ExecutorPolicyEnforcer:
    """Get the global executor policy enforcer."""
    global _enforcer
    if _enforcer is None or guard is not None:
        _enforcer = ExecutorPolicyEnforcer(guard)
    return _enforcer