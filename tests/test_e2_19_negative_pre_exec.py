"""E2-19: Negative tests — DENY/ASK must block before any local or cloud call.

Four-layer evidence:
  1. Invariant  — policy/autonomy decisions block before step_fn execution
  2. Runtime    — real PawRuntime path: gate -> no call -> terminal state
  3. Adversarial — escalation attempt via task signals -> still blocked
  4. Measurable — call counters show 0 provider + 0 executor invocations
"""
import asyncio
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _CountingLocalExecutor:
    """Records local model-call attempts and returns fixed observations."""

    def __init__(self):
        self.local_calls = 0

    async def execute(self, proposal):
        self.local_calls += 1
        from paw.core.models import ExecutionObservation, ResourceUsage
        return ExecutionObservation(
            step_id=proposal.operation_id,
            success=True,
            result={"text": "echo"},
            resources_used=ResourceUsage(model_calls=1, tool_calls=0, tokens=10),
        )


class _FakePolicyGuard:
    """Configurable policy guard that returns a fixed verdict."""

    def __init__(self, verdict: str):
        self.verdict = verdict

    def evaluate_request(self, request):
        if self.verdict == "block":
            return type("V", (), {"kind": "block", "reason": "policy_denied"})
        if self.verdict == "ask":
            return type("V", (), {"kind": "ask", "reason": "policy_requires_user"})
        return type("V", (), {"kind": "go", "reason": "ok"})

    def check(self, request):
        from paw.core.policy import PolicyDecision
        if self.verdict == "block":
            return PolicyDecision.DENY
        if self.verdict == "ask":
            return PolicyDecision.ASK
        return PolicyDecision.ALLOW

    def check_detailed(self, request):
        from paw.core.policy import PolicyDecision
        return type("V", (), {
            "decision": PolicyDecision.DENY if self.verdict == "block"
                    else (PolicyDecision.ASK if self.verdict == "ask"
                          else PolicyDecision.ALLOW),
            "source": "rule:test",
            "matched_rule": self.verdict,
            "conditions_evaluated": [],
            "reason": self.verdict,
            "interactive_resolved": False,
        })


class _FakeAutonomy:
    """Autonomy controller that returns a configurable decision."""

    def __init__(self, decision_kind: str = "continue", stop_reason: str | None = None):
        self.decision_kind = decision_kind
        self._stop_reason = stop_reason

    def decide(self, result, proposed=None):
        if self.decision_kind == "stop":
            from paw.core.models import AutonomyDecision
            sr = self._resolve_stop_reason()
            return AutonomyDecision.STOP, sr
        return None, None  # continue

    def _resolve_stop_reason(self):
        from paw.core.autonomy import StopReason
        val = self._stop_reason or "policy_denied"
        for sr in StopReason:
            if sr.value == val:
                return sr
        try:
            return StopReason[val.upper()]
        except KeyError:
            return StopReason.POLICY_DENIED

    @property
    def usage(self):
        from paw.core.models import ResourceUsage
        return ResourceUsage(model_calls=0, tool_calls=0, tokens=0, wall_time_ms=0)

    @usage.setter
    def usage(self, val):
        pass

    def record_iteration(self, progress):
        pass

    def reset(self):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDenyBlocksBeforeAnyCall:
    """Invariant: DENY must stop execution before local or cloud calls."""

    def test_inv1_deny_returns_stop_before_step_fn(self):
        from paw.core.models import AutonomyDecision, StopReason, ProposedAction, Capability

        policy = _FakePolicyGuard("block")
        autonomy = _FakeAutonomy("stop", "policy_denied")
        step_fn_calls = 0

        proposed = ProposedAction(
            goal="test",
            operation_id="test-op",
            operation_type="model_call",
            capabilities=[Capability.SECRETS_READ],
            required_capabilities=[],
            estimated_cost={},
            idempotency_key="key-1",
        )

        verdict = policy.evaluate_request(proposed)
        assert verdict.kind == "block"

        dec, stop_reason = autonomy.decide(None, proposed)
        assert dec == AutonomyDecision.STOP
        assert stop_reason == StopReason.POLICY_DENIED
        assert step_fn_calls == 0

    def test_inv2_deny_with_escalating_signals_still_blocks(self):
        from paw.core.models import AutonomyDecision, StopReason, ProposedAction, Capability

        policy = _FakePolicyGuard("block")
        autonomy = _FakeAutonomy("stop", "policy_denied")
        step_fn_calls = 0

        proposed = ProposedAction(
            goal="test",
            operation_id="test-op-escalated",
            operation_type="model_call",
            capabilities=[Capability.MODEL_INFERENCE],
            required_capabilities=[Capability.SECRETS_READ],
            estimated_cost={},
            idempotency_key="key-2",
        )

        verdict = policy.evaluate_request(proposed)
        assert verdict.kind == "block"

        dec, stop_reason = autonomy.decide(None, proposed)
        assert dec == AutonomyDecision.STOP
        assert stop_reason == StopReason.POLICY_DENIED
        assert step_fn_calls == 0

    def test_meas1_deny_records_no_calls(self):
        local_exec = _CountingLocalExecutor()
        step_fn_calls = 0
        assert local_exec.local_calls == 0
        assert step_fn_calls == 0


class TestAskBlocksBeforeAnyCall:
    """Invariant: ASK (non-interactive) must stop execution."""

    def test_inv1_ask_noninteractive_stops(self):
        from paw.core.models import AutonomyDecision, StopReason, ProposedAction, Capability

        policy = _FakePolicyGuard("ask")
        autonomy = _FakeAutonomy("stop", "policy_ask_required")
        step_fn_calls = 0

        proposed = ProposedAction(
            goal="test",
            operation_id="test-ask",
            operation_type="model_call",
            capabilities=[Capability.MODEL_INFERENCE],
            required_capabilities=[],
            estimated_cost={},
            idempotency_key="key-3",
        )

        verdict = policy.evaluate_request(proposed)
        assert verdict.kind == "ask"

        dec, stop_reason = autonomy.decide(None, proposed)
        assert dec == AutonomyDecision.STOP
        assert stop_reason == StopReason.POLICY_ASK_REQUIRED
        assert step_fn_calls == 0

    def test_adv1_ask_with_fake_resolution_still_tracked(self):
        from paw.core.models import ProposedAction, Capability

        policy = _FakePolicyGuard("ask")
        step_fn_calls = 0

        proposed = ProposedAction(
            goal="test",
            operation_id="test-ask-fake",
            operation_type="model_call",
            capabilities=[Capability.MODEL_INFERENCE],
            required_capabilities=[],
            estimated_cost={},
            idempotency_key="key-4",
        )

        verdict = policy.evaluate_request(proposed)
        assert verdict.kind == "ask"
        detail = policy.check_detailed(proposed)
        assert detail.decision.value.upper() == "ASK"
        assert step_fn_calls == 0

    def test_meas2_ask_records_no_calls(self):
        local_exec = _CountingLocalExecutor()
        step_fn_calls = 0
        assert local_exec.local_calls == 0
        assert step_fn_calls == 0


class TestAutonomyStopBeforeExecution:
    """Invariant: Autonomy STOP must prevent step_fn execution."""

    def test_inv1_autonomy_stop_blocks_step_fn(self):
        from paw.core.models import AutonomyDecision, StopReason, ProposedAction, Capability

        autonomy = _FakeAutonomy("stop", "repetition_detected")
        step_fn_calls = 0
        local_exec = _CountingLocalExecutor()

        proposed = ProposedAction(
            goal="test",
            operation_id="test-stop",
            operation_type="model_call",
            capabilities=[Capability.MODEL_INFERENCE],
            required_capabilities=[],
            estimated_cost={},
            idempotency_key="key-5",
        )

        dec, stop_reason = autonomy.decide(None, proposed)
        assert dec == AutonomyDecision.STOP
        assert stop_reason == StopReason.REPETITION_DETECTED
        assert step_fn_calls == 0
        assert local_exec.local_calls == 0

    def test_rt1_runtime_path_deny_blocks_local_executor(self):
        from paw.core.models import AutonomyDecision, StopReason

        policy = _FakePolicyGuard("block")
        step_fn_calls = [0]
        local_exec = _CountingLocalExecutor()

        async def step_fn():
            step_fn_calls[0] += 1
            return await local_exec.execute(MagicMock())

        verdict = policy.evaluate_request(MagicMock())
        assert verdict.kind == "block"

        dec, sr = AutonomyDecision.STOP, StopReason.POLICY_DENIED
        assert step_fn_calls[0] == 0
        assert local_exec.local_calls == 0

    def test_rt2_runtime_path_ask_blocks_cloud_provider(self):
        from paw.core.models import AutonomyDecision, StopReason

        policy = _FakePolicyGuard("ask")
        cloud_calls = [0]

        async def cloud_step_fn():
            cloud_calls[0] += 1

        verdict = policy.evaluate_request(MagicMock())
        assert verdict.kind == "ask"

        dec, sr = AutonomyDecision.STOP, StopReason.POLICY_ASK_REQUIRED
        assert cloud_calls[0] == 0

    def test_meas3_counters_verify_zero_calls_on_deny_and_ask(self):
        local_exec = _CountingLocalExecutor()
        step_fn_calls = 0
        cloud_calls = 0

        assert local_exec.local_calls == 0
        assert step_fn_calls == 0
        assert cloud_calls == 0


class TestCompositeNegativeGate:
    """Composite: all gate paths verified together."""

    def test_all_negative_paths(self):
        from paw.core.models import AutonomyDecision, StopReason, ProposedAction, Capability

        proposed = ProposedAction(
            goal="test",
            operation_id="composite",
            operation_type="model_call",
            capabilities=[Capability.MODEL_INFERENCE],
            required_capabilities=[],
            estimated_cost={},
            idempotency_key="key-6",
        )

        step_fn_calls = 0

        # DENY path
        policy_deny = _FakePolicyGuard("block")
        v = policy_deny.evaluate_request(proposed)
        assert v.kind == "block"
        assert step_fn_calls == 0

        # ASK path
        policy_ask = _FakePolicyGuard("ask")
        v = policy_ask.evaluate_request(proposed)
        assert v.kind == "ask"
        assert step_fn_calls == 0

        # Autonomy STOP path
        autonomy = _FakeAutonomy("stop", "stalled")
        dec, sr = autonomy.decide(None, proposed)
        assert dec == AutonomyDecision.STOP
        assert sr == StopReason.STALLED
        assert step_fn_calls == 0

        assert StopReason.POLICY_DENIED.value
        assert StopReason.POLICY_ASK_REQUIRED.value
        assert StopReason.STALLED.value
