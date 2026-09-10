"""E2-32: Per-role token/cost ceiling and overflow rejection.

Four-layer evidence:
  1. Invariant  — RoleCeiling fields stable + ROLE_CEILINGS mapping complete
  2. Runtime    — check_role_ceiling returns correct overflow reason
  3. Adversarial — unknown role fallback + negative inputs + exact-boundary
  4. Measurable — exported in __all__ + documented defaults

Decision level: D2.
"""
import pytest

from paw.core.reasoning_contracts import (
    ModelRole,
    RoleCeiling,
    ROLE_CEILINGS,
    check_role_ceiling,
)


class TestInvariantCeilings:
    def test_inv1_all_roles_have_ceiling(self):
        expected = set(ModelRole)
        assert set(ROLE_CEILINGS.keys()) == expected

    def test_inv2_fast_ceiling(self):
        c = ROLE_CEILINGS[ModelRole.FAST]
        assert c.max_tokens == 2048
        assert c.max_cost_usd == 0.01

    def test_inv3_reasoning_ceiling(self):
        c = ROLE_CEILINGS[ModelRole.REASONING]
        assert c.max_tokens == 8192
        assert c.max_cost_usd == 0.05

    def test_inv4_vision_ceiling(self):
        c = ROLE_CEILINGS[ModelRole.VISION]
        assert c.max_tokens == 32768
        assert c.max_cost_usd == 0.20

    def test_inv5_embedding_ceiling(self):
        c = ROLE_CEILINGS[ModelRole.EMBEDDING]
        assert c.max_tokens == 2048
        assert c.max_cost_usd == 0.00

    def test_inv6_ceiling_rejects_negative_tokens(self):
        with pytest.raises(ValueError):
            RoleCeiling(role=ModelRole.FAST, max_tokens=-1, max_cost_usd=0.01)

    def test_inv7_ceiling_rejects_negative_cost(self):
        with pytest.raises(ValueError):
            RoleCeiling(role=ModelRole.FAST, max_tokens=2048, max_cost_usd=-0.01)


class TestRuntimeOverflow:
    @pytest.mark.parametrize("role,expected", [
        (ModelRole.FAST, "token_limit"),
        (ModelRole.REASONING, "cost_limit"),
        (ModelRole.VISION, None),
    ])
    def test_rt1_token_or_cost_overflow(self, role, expected):
        if role is ModelRole.FAST:
            assert check_role_ceiling(role, requested_tokens=2049, estimated_cost_usd=0.01) == expected
        elif role is ModelRole.REASONING:
            assert check_role_ceiling(role, requested_tokens=1024, estimated_cost_usd=0.06) == expected
        else:
            assert check_role_ceiling(role, requested_tokens=32768, estimated_cost_usd=0.20) == expected

    def test_rt2_no_overflow(self):
        assert check_role_ceiling(ModelRole.FAST, requested_tokens=2048, estimated_cost_usd=0.01) is None

    def test_rt3_both_overflow_token_wins(self):
        result = check_role_ceiling(ModelRole.FAST, requested_tokens=99999, estimated_cost_usd=999.0)
        assert result == "token_limit"


class TestAdversarialFailClosed:
    def test_adv1_unknown_role_falls_back_to_local(self):
        # Unknown role -> LOCAL ceiling (2048 tokens, 0.00 cost)
        assert check_role_ceiling("unknown", requested_tokens=2049, estimated_cost_usd=0.0) == "token_limit"

    def test_adv2_zero_tokens_succeeds(self):
        assert check_role_ceiling(ModelRole.FAST, requested_tokens=0, estimated_cost_usd=0.0) is None

    def test_adv3_exact_boundary_passes(self):
        assert check_role_ceiling(ModelRole.VISION, requested_tokens=32768, estimated_cost_usd=0.20) is None

    def test_adv4_negative_requested_does_not_crash(self):
        assert check_role_ceiling(ModelRole.FAST, requested_tokens=-1, estimated_cost_usd=0.01) is None

    def test_adv5_zero_cost_succeeds(self):
        assert check_role_ceiling(ModelRole.EMBEDDING, requested_tokens=2048, estimated_cost_usd=0.0) is None


class TestMeasurableExport:
    def test_measure1_exported_in_all(self):
        from paw.core.reasoning_contracts import __all__
        assert "RoleCeiling" in __all__
        assert "ROLE_CEILINGS" in __all__
        assert "check_role_ceiling" in __all__

    def test_measure2_ceiling_mapping_frozen(self):
        import types
        assert isinstance(ROLE_CEILINGS, types.MappingProxyType)

    def test_measure3_defaults_stable(self):
        assert ROLE_CEILINGS[ModelRole.FAST].max_tokens == 2048
        assert ROLE_CEILINGS[ModelRole.FAST].max_cost_usd == 0.01
