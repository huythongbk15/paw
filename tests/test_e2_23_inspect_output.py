"""E2-23: Publish routing reason and escalation summary in inspect output.

Four-layer evidence:
  1. Invariant  — ModelSelection.inspect() returns structured dict with reason
  2. Runtime    — route() result contains inspectable escalation summary
  3. Adversarial — failure_kind surfaced in inspect even on blocked routes
  4. Measurable — inspect dict keys match the documented schema

Decision level: D2 (observability).
"""
import pytest

from paw.core.models import ModelSelection


class TestInvariantInspectSchema:
    """E2-23 Invariant: inspect() returns all required fields."""

    def test_inv1_inspect_returns_reason(self):
        """inspect() must include 'reason' field."""
        s = ModelSelection(model_name="test", reason="E2-12: escalated")
        info = s.inspect()
        assert "reason" in info
        assert info["reason"] == "E2-12: escalated"

    def test_inv2_inspect_returns_escalation_summary(self):
        """inspect() must include 'escalation_summary' with 'escalated' flag."""
        s = ModelSelection(model_name="test", reason="E2-11: role escalated")
        info = s.inspect()
        assert "escalation_summary" in info
        assert info["escalation_summary"]["escalated"] is True

    def test_inv3_inspect_returns_failure_kind(self):
        """inspect() must surface failure_kind for blocked routes."""
        s = ModelSelection(
            model_name="", reason="no models", failure_kind="capability_mismatch",
        )
        info = s.inspect()
        assert info["failure_kind"] == "capability_mismatch"

    def test_inv4_inspect_returns_fallback_chain(self):
        """inspect() must include fallback_chain."""
        s = ModelSelection(
            model_name="model-a",
            fallback_chain=["model-b", "model-c"],
        )
        info = s.inspect()
        assert info["fallback_chain"] == ["model-b", "model-c"]


class TestRuntimeInspectContent:
    """E2-23 Runtime: inspect reflects actual routing decisions."""

    def test_rt1_successful_selection_inspect(self):
        """A successful selection inspects with model_name + manifest info."""
        from paw.core.models import ModelManifest
        manifest = ModelManifest(
            name="claude-3", provider="anthropic",
            roles=["fast", "reasoning"], capabilities="{}",
        )
        s = ModelSelection(
            model_name="claude-3", model_manifest=manifest,
            role="fast", reason="best score", score=0.85,
        )
        info = s.inspect()
        assert info["model_name"] == "claude-3"
        assert info["manifest_provider"] == "anthropic"
        assert info["manifest_max_tokens"] == 128000  # default
        assert info["escalation_summary"]["escalated"] is False

    def test_rt2_escalation_inspect(self):
        """An escalated selection inspects with escalation_summary."""
        from paw.core.models import ModelManifest
        manifest = ModelManifest(
            name="gpt-4", provider="openai",
            roles=["reasoning"], capabilities="{}",
        )
        s = ModelSelection(
            model_name="gpt-4", model_manifest=manifest,
            role="reasoning",
            reason="E2-11: OOD escalation from fast to reasoning",
            score=0.92,
        )
        info = s.inspect()
        assert info["escalation_summary"]["escalated"] is True
        assert info["escalation_summary"]["role_escalated"] is True

    def test_rt3_empty_selection_inspect(self):
        """A blocked selection inspects with failure_kind."""
        s = ModelSelection(
            model_name="", reason="E2-12: no non-local provider",
            failure_kind="retryable", role="reasoning",
        )
        info = s.inspect()
        assert info["model_name"] == ""
        assert info["failure_kind"] == "retryable"
        assert info["escalation_summary"]["escalated"] is False  # E2-11 not in reason


class TestAdversarialInspectFailureKind:
    """E2-23 Adversarial: failure_kind is surfaced even when reason is forged."""

    def test_adv1_forged_reason_but_no_failure_still_surfaces(self):
        """If the reason claims escalation but failure_kind is set, both appear."""
        s = ModelSelection(
            model_name="",
            reason="E2-12: cloud unavailable (forged)",
            failure_kind="retryable",
        )
        info = s.inspect()
        assert info["failure_kind"] == "retryable"
        assert "E2-12" in info["reason"]

    def test_adv2_missing_reason_still_has_fields(self):
        """A selection with empty reason still has all inspect fields."""
        s = ModelSelection(model_name="x", reason="")
        info = s.inspect()
        assert info["model_name"] == "x"
        assert info["reason"] == ""
        assert info["escalation_summary"]["escalated"] is False
        assert info["failure_kind"] is None

    def test_adv3_inspect_is_stable_across_calls(self):
        """inspect() returns the same dict structure on repeated calls."""
        s = ModelSelection(
            model_name="m1", reason="test reason", score=0.5,
        )
        info1 = s.inspect()
        info2 = s.inspect()
        assert info1 == info2


class TestMeasurableInspectKeys:
    """E2-23 Measurable: inspect dict has the documented schema keys."""

    def test_measure1_all_required_keys(self):
        """inspect() output must contain all documented top-level keys."""
        s = ModelSelection(model_name="test", reason="r")
        info = s.inspect()
        required = {
            "model_name", "role", "score", "reason",
            "escalation_summary", "failure_kind",
            "fallback_chain", "manifest_provider", "manifest_max_tokens",
        }
        assert required.issubset(set(info.keys()))

    def test_measure2_escalation_summary_keys(self):
        """escalation_summary must contain 'escalated' and 'role_escalated'."""
        s = ModelSelection(model_name="test", reason="E2-11: escalation")
        summary = s.inspect()["escalation_summary"]
        assert "escalated" in summary
        assert "role_escalated" in summary
        assert isinstance(summary["escalated"], bool)
        assert isinstance(summary["role_escalated"], bool)
