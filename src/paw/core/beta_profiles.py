"""
PAW Beta — Daily engineering-partner profiles.

Profiles as configuration, not separate runtimes. Each profile maps to an
``ExecutionProfile`` preset and declares a side-effect policy:

- analyze/ideate: read-only (no WRITE/DELETE/SHELL capabilities)
- change: explicitly gated (policy ASK → user approval before execution)
- review: non-mutating by default

The side-effect policy is enforced by the PolicyGuard before any side effect.
The profile configuration controls which capabilities are permitted, required,
or gated per profile type.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum

from .execution_profile import PRECISE, ExecutionProfile
from .execution_profile import get_execution_profile as _get_preset
from .models import Capability


class SideEffectPolicy(StrEnum):
    """Side-effect enforcement policy for daily profiles.

    - READ_ONLY: no write/delete/execute capabilities permitted.
    - GATED: all side-effect capabilities require explicit user approval (ASK).
    - NON_MUTATING: non-mutating by default, side effects gated like GATED.
    """
    READ_ONLY = "read_only"
    GATED = "gated"
    NON_MUTATING = "non_mutating"


# Capabilities that constitute side effects (write/delete/execute).
WRITE_CAPABILITIES = frozenset({
    Capability.FILESYSTEM_WRITE,
    Capability.FILESYSTEM_DELETE,
    Capability.SHELL_EXECUTE,
    Capability.PROCESS_SPAWN,
    Capability.GIT_WRITE,
    Capability.DESTRUCTIVE,
    Capability.FINANCIAL,
})

# Read-only profile capabilities — excludes all write/delete/execute.
READ_ONLY_CAPABILITIES = frozenset(
    c for c in Capability if c not in WRITE_CAPABILITIES
)


@dataclass
class BetaProfile:
    """A daily engineering-partner profile.

    Combines an ``ExecutionProfile`` (autonomy, context budgets, model routing)
    with a ``SideEffectPolicy`` that the PolicyGuard enforces before execution.
    """
    name: str
    description: str
    execution_profile: ExecutionProfile
    side_effect_policy: SideEffectPolicy
    allowed_capabilities: frozenset[Capability] | None = None
    # Capabilities that must be approved (ASK) before execution.
    gated_capabilities: frozenset[Capability] = frozenset()


# ── Profile definitions ──

# Analyze: read-only investigation and analysis.
ANALYZE = BetaProfile(
    name="analyze",
    description="Read-only investigation and analysis. No side effects permitted.",
    execution_profile=deepcopy(PRECISE),
    side_effect_policy=SideEffectPolicy.READ_ONLY,
    allowed_capabilities=READ_ONLY_CAPABILITIES,
)

# Ideate: creative problem exploration (read-only, cloud models allowed).
IDEOATE = BetaProfile(
    name="ideate",
    description="Creative problem exploration. Cloud models allowed for idea generation, no file/process side effects.",
    execution_profile=deepcopy(_get_preset("fast")),
    side_effect_policy=SideEffectPolicy.READ_ONLY,
    allowed_capabilities=READ_ONLY_CAPABILITIES,
)

# Change: multi-file change with approval and verification.
CHANGE = BetaProfile(
    name="change",
    description="Multi-file change with approval and verification. Explicit policy gate on all side effects.",
    execution_profile=deepcopy(_get_preset("safe")),
    side_effect_policy=SideEffectPolicy.GATED,
    gated_capabilities=WRITE_CAPABILITIES,
)

# Review: non-mutating review of code and decisions.
REVIEW = BetaProfile(
    name="review",
    description="Non-mutating review of code, knowledge, and decisions. No writes permitted by default.",
    execution_profile=deepcopy(PRECISE),
    side_effect_policy=SideEffectPolicy.NON_MUTATING,
    allowed_capabilities=READ_ONLY_CAPABILITIES,
)


# Named profile registry: the four daily profiles plus presets.
BETA_PROFILES: dict[str, BetaProfile] = {
    # Daily profiles
    "analyze": ANALYZE,
    "ideate": IDEOATE,
    "change": CHANGE,
    "review": REVIEW,
}

def get_beta_profile(name: str) -> BetaProfile | None:
    """Return a beta profile by name (case-insensitive). Returns None if unknown."""
    return BETA_PROFILES.get(name.lower())


def list_beta_profiles() -> list[str]:
    """List beta profile names."""
    return list(BETA_PROFILES.keys())


def is_side_effect_capability(cap: Capability) -> bool:
    """Return True if a capability constitutes a side effect (write/delete/execute)."""
    return cap in WRITE_CAPABILITIES


# Re-export ExecutionProfile for convenience
__all__ = [
    "ANALYZE",
    "BETA_PROFILES",
    "CHANGE",
    "IDEOATE",
    "READ_ONLY_CAPABILITIES",
    "REVIEW",
    "WRITE_CAPABILITIES",
    "BetaProfile",
    "ExecutionProfile",
    "SideEffectPolicy",
    "get_beta_profile",
    "is_side_effect_capability",
    "list_beta_profiles",
]
