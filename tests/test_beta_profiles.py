"""BETA B-01: Verify the four daily profiles are configuration, not separate runtimes.

Each profile is a BetaProfile (ExecutionProfile + SideEffectPolicy) — they all
share the canonical PawRuntime. Side-effect defaults:
  - analyze/ideate: read-only
  - change: explicitly gated
  - review: non-mutating
"""

import pytest

from paw.core.beta_profiles import (
    BETA_PROFILES,
    ANALYZE,
    IDEOATE,
    CHANGE,
    REVIEW,
    SideEffectPolicy,
    is_side_effect_capability,
    get_beta_profile,
    list_beta_profiles,
)
from paw.core.models import Capability


class TestBetaProfiles:
    def test_all_four_daily_profiles_present(self):
        assert set(list_beta_profiles()) == {"analyze", "ideate", "change", "review"}

    def test_profiles_are_beta_profile_objects(self):
        for profile in BETA_PROFILES.values():
            assert hasattr(profile, "execution_profile")
            assert hasattr(profile, "side_effect_policy")
            assert hasattr(profile, "name")
            assert hasattr(profile, "description")

    def test_analyze_is_read_only(self):
        assert ANALYZE.side_effect_policy == SideEffectPolicy.READ_ONLY
        for cap in ANALYZE.allowed_capabilities or []:
            assert not is_side_effect_capability(cap), \
                f"analyze must not allow side-effect capability: {cap}"

    def test_ideate_is_read_only(self):
        assert IDEOATE.side_effect_policy == SideEffectPolicy.READ_ONLY
        for cap in IDEOATE.allowed_capabilities or []:
            assert not is_side_effect_capability(cap), \
                f"ideate must not allow side-effect capability: {cap}"

    def test_change_is_gated(self):
        assert CHANGE.side_effect_policy == SideEffectPolicy.GATED
        assert Capability.FILESYSTEM_WRITE in CHANGE.gated_capabilities
        assert Capability.SHELL_EXECUTE in CHANGE.gated_capabilities

    def test_review_is_non_mutating(self):
        assert REVIEW.side_effect_policy == SideEffectPolicy.NON_MUTATING
        for cap in REVIEW.allowed_capabilities or []:
            assert not is_side_effect_capability(cap), \
                f"review must not allow side-effect capability: {cap}"

    def test_get_beta_profile_case_insensitive(self):
        assert get_beta_profile("ANALYZE") is not None
        assert get_beta_profile("analyze") is ANALYZE
        assert get_beta_profile("Change") is CHANGE
        assert get_beta_profile("UNKNOWN") is None

    def test_all_four_share_canonical_runtime(self):
        """Profiles are config objects, not runtimes — they share the same PawRuntime."""
        # Verify all profiles have the same execution_profile type
        # (i.e., they're configs, not separate runtime instances)
        from paw.core.execution_profile import ExecutionProfile
        for profile in BETA_PROFILES.values():
            assert isinstance(profile.execution_profile, ExecutionProfile)
