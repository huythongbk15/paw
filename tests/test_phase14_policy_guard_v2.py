"""
Phase 14 — Policy Guard v2 Tests.

Verifies the v2 policy layer:
  * explainable decisions (which rule / default + reason)
  * aggregate single-authority gate `evaluate_request`
  * fail-closed: non-interactive ASK resolves to DENY/BLOCK
  * ledger audit of every decision
  * autonomy-loop enforcement (ASK -> ASK/WAIT, DENY -> STOP)
  * condition priority (highest-first wins)
  * adversarial: path traversal denied, undeclared capability -> ASK

Note: `PolicyGuard.check()` preserves the RAW decision (ASK stays ASK) for
backward compatibility with Phase 6 assertions; the fail-closed resolution
lives in `evaluate_request`.
"""

from __future__ import annotations

import pytest

from paw.core import (
    AutonomyController,
    AutonomyDecision,
    AutonomyProfile,
    Capability,
    PolicyDecision,
    PolicyGuard,
    StopReason,
)
from paw.core.ledger import TaskLedger
from paw.core.policy import PolicyDecisionDetail, RequestVerdict


# NOTE: ``temp_db`` is provided by tests/conftest.py (Cấp 2): a single
# session-scoped SQLite DB, truncated before/after each test. ``policy_rules``
# ships in the canonical SCHEMA, so it starts EMPTY here (no seeded defaults) —
# exactly the baseline Phase 14 asserts against.


# --------------------------------------------------------------------------- #
# A. Explainable decisions (PolicyDecisionDetail)                              #
# --------------------------------------------------------------------------- #
async def test_check_detailed_default_fallback(temp_db):
    guard = PolicyGuard()
    detail = await guard.check_detailed(Capability.FILESYSTEM_READ)
    assert detail.decision == PolicyDecision.ALLOW
    assert detail.source == "default"
    assert detail.matched_rule is None
    assert "default decision" in detail.reason


async def test_check_detailed_rule_match_explainable(temp_db):
    guard = PolicyGuard()
    # Override FILESYSTEM_READ to DENY via a high-priority rule unconditionally
    rule = await guard.add_rule(Capability.FILESYSTEM_READ, PolicyDecision.DENY, priority=10)
    detail = await guard.check_detailed(Capability.FILESYSTEM_READ)
    assert detail.decision == PolicyDecision.DENY
    assert detail.source == f"rule:{rule.id}"
    assert detail.matched_rule is not None
    assert detail.matched_rule.id == rule.id
    assert "Matched" in detail.reason


async def test_check_detailed_condition_explainable(temp_db):
    guard = PolicyGuard()
    # Allow write only under /safe
    await guard.add_rule(
        Capability.FILESYSTEM_WRITE,
        PolicyDecision.ALLOW,
        priority=5,
        conditions={"path_under": "/safe"},
    )
    ok = await guard.check_detailed(Capability.FILESYSTEM_WRITE, {"path": "/safe/ok.txt"})
    assert ok.decision == PolicyDecision.ALLOW
    assert ok.source.startswith("rule:")
    assert ok.conditions_evaluated == {"path_under": True}

    denied = await guard.check_detailed(Capability.FILESYSTEM_WRITE, {"path": "/etc/passwd"})
    # no rule matched -> default ASK
    assert denied.decision == PolicyDecision.ASK
    assert denied.source == "default"


# --------------------------------------------------------------------------- #
# B. Aggregate single-authority gate (evaluate_request)                        #
# --------------------------------------------------------------------------- #
async def test_evaluate_request_all_allow(temp_db):
    guard = PolicyGuard()  # non-interactive
    verdict = await guard.evaluate_request([Capability.FILESYSTEM_READ, Capability.GIT_READ])
    assert isinstance(verdict, RequestVerdict)
    assert verdict.verdict == "go"
    assert verdict.allowed is True
    assert verdict.decision == PolicyDecision.ALLOW
    assert verdict.stop_reason is None


async def test_evaluate_request_one_deny_blocks(temp_db):
    guard = PolicyGuard()
    verdict = await guard.evaluate_request([Capability.FILESYSTEM_READ, Capability.DESTRUCTIVE])
    assert verdict.verdict == "block"
    assert verdict.allowed is False
    assert Capability.DESTRUCTIVE in verdict.blocked
    assert verdict.stop_reason == StopReason.POLICY_DENIED


async def test_evaluate_request_ask_non_interactive_blocks(temp_db):
    guard = PolicyGuard()  # interactive=False (default)
    verdict = await guard.evaluate_request([Capability.FILESYSTEM_READ, Capability.SHELL_EXECUTE])
    assert verdict.verdict == "block"
    assert verdict.allowed is False
    assert Capability.SHELL_EXECUTE in verdict.asked
    assert verdict.stop_reason == StopReason.POLICY_ASK_REQUIRED
    # detail reflects fail-closed resolution
    assert verdict.details[Capability.SHELL_EXECUTE].interactive_resolved is True
    assert verdict.details[Capability.SHELL_EXECUTE].decision == PolicyDecision.DENY


async def test_evaluate_request_ask_interactive_allowed(temp_db):
    guard = PolicyGuard(interactive=True)
    verdict = await guard.evaluate_request([Capability.FILESYSTEM_READ, Capability.SHELL_EXECUTE])
    assert verdict.verdict == "ask"
    assert verdict.allowed is True
    assert Capability.SHELL_EXECUTE in verdict.asked
    assert verdict.stop_reason is None


async def test_check_preserves_raw_ask_for_backward_compat(temp_db):
    guard = PolicyGuard()  # non-interactive
    # Raw check must still return ASK so Phase 6 assertions hold
    assert await guard.check(Capability.SHELL_EXECUTE) == PolicyDecision.ASK
    assert await guard.check(Capability.FILESYSTEM_WRITE) == PolicyDecision.ASK


# --------------------------------------------------------------------------- #
# C. Condition priority (highest-first wins)                                   #
# --------------------------------------------------------------------------- #
async def test_condition_priority_highest_wins(temp_db):
    guard = PolicyGuard()
    # Default for FILESYSTEM_WRITE is ASK. Add a low-priority DENY and a
    # high-priority ALLOW-with-condition. Highest priority must win when matched.
    await guard.add_rule(Capability.FILESYSTEM_WRITE, PolicyDecision.DENY, priority=1)
    await guard.add_rule(
        Capability.FILESYSTEM_WRITE,
        PolicyDecision.ALLOW,
        priority=100,
        conditions={"path_under": "/safe"},
    )
    ok = await guard.check_detailed(Capability.FILESYSTEM_WRITE, {"path": "/safe/x"})
    assert ok.decision == PolicyDecision.ALLOW
    assert ok.source.startswith("rule:")

    # Without condition match, the next rule (priority 1 DENY) applies
    denied = await guard.check_detailed(Capability.FILESYSTEM_WRITE, {"path": "/elsewhere/x"})
    assert denied.decision == PolicyDecision.DENY


# --------------------------------------------------------------------------- #
# D. Ledger audit                                                              #
# --------------------------------------------------------------------------- #
async def test_policy_decision_logged_to_ledger(temp_db):
    guard = PolicyGuard()
    task_id = "task-audit-001"
    detail = await guard.check_detailed(Capability.SHELL_EXECUTE, {"path": "/x"}, task_id=task_id)
    # Read back ledger events
    events = await TaskLedger.get_events(task_id)
    policy_events = [e for e in events if e.event_type == "policy_checked"]
    assert policy_events, "policy decision must be audited"
    ev = policy_events[-1]
    assert ev.payload["capability"] == "shell.execute"
    assert ev.payload["decision"] == detail.decision.value
    assert "source" in ev.payload and "reason" in ev.payload


async def test_evaluate_request_audits_each_capability(temp_db):
    guard = PolicyGuard()
    task_id = "task-audit-002"
    await guard.evaluate_request([Capability.FILESYSTEM_READ, Capability.DESTRUCTIVE], task_id=task_id)
    events = await TaskLedger.get_events(task_id)
    policy_events = [e for e in events if e.event_type == "policy_checked"]
    assert len(policy_events) >= 2


# --------------------------------------------------------------------------- #
# E. Autonomy-loop enforcement                                                 #
# --------------------------------------------------------------------------- #
async def test_autonomy_loop_blocks_on_deny(temp_db):
    guard = PolicyGuard()
    controller = AutonomyController(policy_guard=guard, profile=AutonomyProfile.BALANCED)
    decision, reason = await controller.decide(
        "task-deny", required_capabilities=[Capability.DESTRUCTIVE]
    )
    assert decision == AutonomyDecision.STOP
    assert reason == StopReason.POLICY_DENIED


async def test_autonomy_loop_asks_on_ask_capability(temp_db):
    guard = PolicyGuard()  # non-interactive -> ASK resolves to BLOCK
    controller = AutonomyController(policy_guard=guard, profile=AutonomyProfile.BALANCED)
    decision, reason = await controller.decide(
        "task-ask", required_capabilities=[Capability.SHELL_EXECUTE]
    )
    # Non-interactive: no approval possible, so the loop must hard-STOP and
    # surface POLICY_ASK_REQUIRED. ASK never maps to execution.
    assert decision == AutonomyDecision.STOP
    assert reason == StopReason.POLICY_ASK_REQUIRED


async def test_autonomy_loop_ask_interactive_surfaces_request(temp_db):
    guard = PolicyGuard(interactive=True)  # interactive -> ASK is allowed but flagged
    controller = AutonomyController(policy_guard=guard, profile=AutonomyProfile.BALANCED)
    decision, reason = await controller.decide(
        "task-ask-int", required_capabilities=[Capability.SHELL_EXECUTE]
    )
    assert decision == AutonomyDecision.ASK
    assert reason == StopReason.POLICY_ASK_REQUIRED


async def test_autonomy_loop_proceeds_when_all_allowed(temp_db):
    guard = PolicyGuard()
    controller = AutonomyController(policy_guard=guard, profile=AutonomyProfile.BALANCED)
    # FILESYSTEM_READ + GIT_READ are default ALLOW -> loop passes policy gate
    # and proceeds to its other checks (budget etc.); ensures no false block.
    decision, reason = await controller.decide(
        "task-ok", required_capabilities=[Capability.FILESYSTEM_READ, Capability.GIT_READ]
    )
    assert reason != StopReason.POLICY_DENIED
    assert reason != StopReason.POLICY_ASK_REQUIRED
    # Not blocked by policy; decision comes from budget/progress (CONTINUE or STOP)
    assert decision in (AutonomyDecision.CONTINUE, AutonomyDecision.STOP)


async def test_autonomy_loop_no_policy_when_capabilities_omitted(temp_db):
    # Legacy behavior: without required_capabilities the loop never gates on policy
    guard = PolicyGuard()
    controller = AutonomyController(policy_guard=guard, profile=AutonomyProfile.BALANCED)
    decision, reason = await controller.decide("task-legacy")
    assert reason != StopReason.POLICY_DENIED
    assert reason != StopReason.POLICY_ASK_REQUIRED


# --------------------------------------------------------------------------- #
# F. Adversarial: fail-closed, path traversal, privilege escalation            #
# --------------------------------------------------------------------------- #
async def test_undeclared_capability_fails_closed(temp_db):
    guard = PolicyGuard()
    # A capability with no rule and no default -> default fallback is ASK
    # (and non-interactive evaluate_request blocks it)
    unknown = Capability.FINANCIAL  # default DENY already, but test the path:
    detail = await guard.check_detailed(unknown)
    assert detail.decision in (PolicyDecision.DENY, PolicyDecision.ASK)
    verdict = await guard.evaluate_request([unknown])
    assert verdict.verdict == "block"


async def test_path_traversal_write_denied(temp_db):
    guard = PolicyGuard()
    # Allow write only under /project; attempt to escape to /etc
    await guard.add_rule(
        Capability.FILESYSTEM_WRITE,
        PolicyDecision.ALLOW,
        priority=5,
        conditions={"path_under": "/project"},
    )
    escape = await guard.check_detailed(
        Capability.FILESYSTEM_WRITE, {"path": "/project/../etc/passwd"}
    )
    # Symlink/escape attempt must NOT match the allow rule -> default ASK
    assert escape.source == "default"
    assert escape.decision == PolicyDecision.ASK
    # And the aggregate gate blocks it in non-interactive mode
    verdict = await guard.evaluate_request(
        [Capability.FILESYSTEM_WRITE], {"path": "/project/../etc/passwd"}
    )
    assert verdict.verdict == "block"


async def test_privilege_escalation_rejected_by_aggregate(temp_db):
    guard = PolicyGuard(interactive=True)  # even interactive mode must reject DENY
    # A skill declares only FILESYSTEM_READ but the executor tries DESTRUCTIVE
    verdict = await guard.evaluate_request(
        [Capability.FILESYSTEM_READ, Capability.DESTRUCTIVE]
    )
    assert verdict.verdict == "block"
    assert verdict.stop_reason == StopReason.POLICY_DENIED
    assert Capability.DESTRUCTIVE in verdict.blocked
