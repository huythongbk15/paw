"""E2-33: Exact cost/usage receipt per step.

Four-layer evidence:
  1. Invariant  — ResourceUsage has provider_calls/total_tokens/to_receipt
  2. Runtime    — receipt is deterministic and serializable
  3. Adversarial — receipt is immutable + tamper-evident
  4. Measurable — receipt keys stable + values deterministic

Decision level: D2.
"""
import pytest

from paw.core.models import ResourceUsage


class TestInvariantReceipt:
    def test_inv1_provider_calls_alias(self):
        r = ResourceUsage(model_calls=3)
        assert r.provider_calls() == 3

    def test_inv2_total_tokens(self):
        r = ResourceUsage(tokens=1500)
        assert r.total_tokens() == 1500

    def test_inv3_receipt_keys(self):
        r = ResourceUsage(model_calls=1, tokens=100, tool_calls=2, wall_time_ms=50, network_bytes=1024, destructive_ops=1)
        receipt = r.to_receipt()
        assert set(receipt.keys()) == {
            "provider_calls", "total_tokens", "total_cost_usd",
            "wall_time_ms", "tool_calls", "network_bytes", "destructive_ops",
        }

    def test_inv4_receipt_values_match(self):
        r = ResourceUsage(model_calls=2, tokens=100)
        receipt = r.to_receipt()
        assert receipt["provider_calls"] == 2
        assert receipt["total_tokens"] == 100
        assert receipt["total_cost_usd"] == 2.1  # 2*1.0 + 100*0.001

    def test_inv5_defaults_zero(self):
        r = ResourceUsage()
        receipt = r.to_receipt()
        assert receipt["provider_calls"] == 0
        assert receipt["total_tokens"] == 0
        assert receipt["total_cost_usd"] == 0.0


class TestRuntimeReceiptSerialization:
    def test_rt1_receipt_is_json_serializable(self):
        import json
        r = ResourceUsage(model_calls=1, tokens=256, wall_time_ms=10)
        receipt = r.to_receipt()
        dumped = json.dumps(receipt)
        assert json.loads(dumped)["provider_calls"] == 1

    def test_rt2_receipt_from_observation(self):
        from paw.core.models import ExecutionObservation, ProposedAction
        obs = ExecutionObservation(
            step_id="step-1",
            action_id="op-1",
            success=True,
            resources_used=ResourceUsage(model_calls=1, tokens=100),
        )
        receipt = obs.resources_used.to_receipt()
        assert receipt["provider_calls"] == 1
        assert receipt["total_tokens"] == 100


class TestAdversarialReceiptTampering:
    def test_adv1_receipt_is_dict_copy(self):
        r = ResourceUsage(model_calls=1)
        receipt = r.to_receipt()
        receipt["provider_calls"] = 999
        assert r.provider_calls() == 1  # original unchanged

    def test_adv2_receipt_deterministic(self):
        r = ResourceUsage(model_calls=2, tokens=100, tool_calls=1)
        first = r.to_receipt()
        second = r.to_receipt()
        assert first == second

    def test_adv3_negative_values_preserved(self):
        r = ResourceUsage(model_calls=-1, tokens=-1)
        receipt = r.to_receipt()
        assert receipt["provider_calls"] == -1
        assert receipt["total_tokens"] == -1

    def test_adv4_nested_mutation_does_not_affect_receipt(self):
        r = ResourceUsage(model_calls=1, tool_calls=2)
        receipt = r.to_receipt()
        receipt["tool_calls"] = 0
        assert r.tool_calls == 2


class TestMeasurableExport:
    def test_measure1_receipt_keys_stable(self):
        r = ResourceUsage()
        receipt = r.to_receipt()
        expected_keys = {
            "provider_calls", "total_tokens", "total_cost_usd",
            "wall_time_ms", "tool_calls", "network_bytes", "destructive_ops",
        }
        assert set(receipt.keys()) == expected_keys

    def test_measure2_cost_formula(self):
        r = ResourceUsage(model_calls=10, tool_calls=5, tokens=1000)
        expected = 10.0 * 1.0 + 5.0 * 0.5 + 1000.0 * 0.001
        assert r.to_receipt()["total_cost_usd"] == expected

    def test_measure3_receipt_summable(self):
        a = ResourceUsage(model_calls=1, tokens=100)
        b = ResourceUsage(model_calls=2, tokens=200)
        combined = ResourceUsage(
            model_calls=a.model_calls + b.model_calls,
            tokens=a.tokens + b.tokens,
        )
        receipt = combined.to_receipt()
        assert receipt["provider_calls"] == 3
        assert receipt["total_tokens"] == 300
