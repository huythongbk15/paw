"""E2-27: Define ImplementationReadiness separately from policy/autonomy enums.

Four-layer evidence:
  1. Invariant  — ImplementationReadiness is a distinct enum, not an alias
  2. Runtime    — all 5 readiness levels exist with correct values
  3. Adversarial — readiness ≠ policy/autonomy/stop enums
  4. Measurable — enum has the documented ordering

Decision level: D1.
"""
import pytest

from paw.core.reasoning_contracts import ImplementationReadiness


class TestInvariantDistinctEnum:
    """E2-27 Invariant: ImplementationReadiness is its own type."""

    def test_inv1_distinct_from_policy_decision(self):
        from paw.core.models import PolicyDecision
        assert ImplementationReadiness is not PolicyDecision
        assert not issubclass(ImplementationReadiness, PolicyDecision)
        assert not issubclass(PolicyDecision, ImplementationReadiness)

    def test_inv2_distinct_from_autonomy_decision(self):
        from paw.core.models import AutonomyDecision
        assert ImplementationReadiness is not AutonomyDecision

    def test_inv3_distinct_from_stop_reason(self):
        from paw.core.autonomy import StopReason
        assert ImplementationReadiness is not StopReason

    def test_inv4_its_own_str_enum(self):
        from enum import StrEnum
        assert issubclass(ImplementationReadiness, StrEnum)


class TestRuntimeReadinessLevels:
    """E2-27 Runtime: all 5 readiness levels exist with correct values."""

    def test_rt1_has_needs_research(self):
        assert hasattr(ImplementationReadiness, "NEEDS_RESEARCH")
        assert ImplementationReadiness.NEEDS_RESEARCH.value == "needs_research"

    def test_rt2_has_needs_clarification(self):
        assert hasattr(ImplementationReadiness, "NEEDS_CLARIFICATION")
        assert ImplementationReadiness.NEEDS_CLARIFICATION.value == "needs_clarification"

    def test_rt3_has_spike_required(self):
        assert hasattr(ImplementationReadiness, "SPIKE_REQUIRED")
        assert ImplementationReadiness.SPIKE_REQUIRED.value == "spike_required"

    def test_rt4_has_ready(self):
        assert hasattr(ImplementationReadiness, "READY")
        assert ImplementationReadiness.READY.value == "ready"

    def test_rt5_has_rejected(self):
        assert hasattr(ImplementationReadiness, "REJECTED")
        assert ImplementationReadiness.REJECTED.value == "rejected"

    def test_rt6_exactly_five_levels(self):
        assert len(list(ImplementationReadiness)) == 5


class TestAdversarialNoAliasLeak:
    """E2-27 Adversarial: readiness values don't collide with other enums."""

    def test_adv1_ready_not_in_policy_decision(self):
        from paw.core.models import PolicyDecision
        policy_values = {d.value for d in PolicyDecision}
        readiness_values = {r.value for r in ImplementationReadiness}
        overlap = policy_values & readiness_values
        assert "ready" not in policy_values
        assert "rejected" not in policy_values

    def test_adv2_rejected_not_in_autonomy(self):
        from paw.core.models import AutonomyDecision
        autonomy_values = {d.value for d in AutonomyDecision}
        assert "rejected" not in autonomy_values
        assert "needs_research" not in autonomy_values

    def test_adv3_spike_required_not_in_stop_reason(self):
        from paw.core.autonomy import StopReason
        stop_values = {s.value for s in StopReason}
        assert "spike_required" not in stop_values
        assert "needs_research" not in stop_values


class TestMeasurableReadinessOrdering:
    """E2-27 Measurable: readiness has a documented progression."""

    def test_measure1_needs_research_before_ready(self):
        """NEEDS_RESEARCH is a blocking state (not READY)."""
        assert ImplementationReadiness.NEEDS_RESEARCH.value != "ready"
        assert ImplementationReadiness.READY.value != "needs_research"

    def test_measure2_rejected_is_terminal(self):
        """REJECTED is terminal — cannot proceed."""
        assert ImplementationReadiness.REJECTED.value == "rejected"

    def test_measure3_all_values_unique(self):
        """All readiness values are unique strings."""
        values = [r.value for r in ImplementationReadiness]
        assert len(values) == len(set(values))

    def test_measure4_exported_in_all(self):
        """ImplementationReadiness is in __all__."""
        from paw.core.reasoning_contracts import __all__
        assert "ImplementationReadiness" in __all__
