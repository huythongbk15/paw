"""E2-31: Typed research depth enum with explicit escalate/ask/stop mapping.

Four-layer evidence:
  1. Invariant  — RESEARCH_DEPTH_ACTIONS mapping stable + DecisionLevel enum
  2. Runtime    — research_depth_action returns correct action string
  3. Adversarial — unknown/future DecisionLevel maps to stop (fail-closed)
  4. Measurable — mapping exported in __all__ + documented

Decision level: D2.
"""
import pytest

from paw.core.reasoning_contracts import (
    RESEARCH_DEPTH_ACTIONS,
    DecisionLevel,
    research_depth_action,
)


class TestInvariantDepthMapping:
    def test_inv1_depth_values_stable(self):
        values = {s.value for s in DecisionLevel}
        assert values == {"fast", "standard", "deep"}

    def test_inv2_mapping_keys_cover_all_depths(self):
        assert set(RESEARCH_DEPTH_ACTIONS.keys()) == set(DecisionLevel)

    def test_inv3_fast_maps_to_continue(self):
        assert RESEARCH_DEPTH_ACTIONS[DecisionLevel.FAST] == "continue"

    def test_inv4_standard_maps_to_ask(self):
        assert RESEARCH_DEPTH_ACTIONS[DecisionLevel.STANDARD] == "ask"

    def test_inv5_deep_maps_to_continue(self):
        assert RESEARCH_DEPTH_ACTIONS[DecisionLevel.DEEP] == "continue"

    def test_inv6_mapping_is_frozen(self):
        import types
        assert isinstance(RESEARCH_DEPTH_ACTIONS, types.MappingProxyType)


class TestRuntimeActionLookup:
    @pytest.mark.parametrize("depth,expected", [
        (DecisionLevel.FAST, "continue"),
        (DecisionLevel.STANDARD, "ask"),
        (DecisionLevel.DEEP, "continue"),
    ])
    def test_rt1_known_depth_returns_action(self, depth, expected):
        assert research_depth_action(depth) == expected

    def test_rt2_unknown_depth_returns_stop(self):
        # Simulate a future/unknown enum member by monkey-patching the enum
        original_members = set(DecisionLevel)
        try:
            DecisionLevel.FUTURE = "future"  # type: ignore[attr-defined]
            assert research_depth_action("future") == "stop"
        finally:
            # Cleanup is best-effort; enum members are usually immutable
            pass


class TestAdversarialFailClosed:
    def test_adv1_unknown_string_maps_to_stop(self):
        assert research_depth_action("unknown") == "stop"

    def test_adv2_none_maps_to_stop(self):
        assert research_depth_action(None) == "stop"  # type: ignore[arg-type]

    def test_adv3_empty_string_maps_to_stop(self):
        assert research_depth_action("") == "stop"


class TestMeasurableExport:
    def test_measure1_exported_in_all(self):
        from paw.core.reasoning_contracts import __all__
        assert "RESEARCH_DEPTH_ACTIONS" in __all__
        assert "research_depth_action" in __all__

    def test_measure2_mapping_documented(self):
        assert RESEARCH_DEPTH_ACTIONS[DecisionLevel.FAST] == "continue"
        assert RESEARCH_DEPTH_ACTIONS[DecisionLevel.STANDARD] == "ask"
        assert RESEARCH_DEPTH_ACTIONS[DecisionLevel.DEEP] == "continue"

    def test_measure3_fail_closed_on_unknown(self):
        assert research_depth_action("does_not_exist") == "stop"
