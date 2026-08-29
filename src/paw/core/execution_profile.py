"""
PAW Core — Execution Profile (K, Phase 10)

Rich configuration object that influences:
- Skill selection (categories, risk tolerance, confidence threshold, progressive loading)
- Model routing (preferred models, privacy, cost/latency priority)
- Autonomy controller (profile + budget overrides)
- Context budget

Designed as a first-class entity so tasks can be executed under
explicitly chosen execution characteristics rather than implicit defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .autonomy import AutonomyBudget, AutonomyProfile
from .context import ContextBudget
from .models import SkillRisk


class PrivacyPreference(StrEnum):
    LOCAL_ONLY = "local_only"
    LOCAL_FIRST = "local_first"
    CLOUD_ALLOWED = "cloud_allowed"


@dataclass
class ExecutionProfile:
    """
    Rich execution configuration.

    A task may declare an ExecutionProfile (by name or inline object) to
    control how skills are selected, which models are routed, how much
    autonomy is granted, and what context budget applies.
    """
    name: str = "default"
    description: str = ""

    # --- Autonomy ---
    autonomy_profile: AutonomyProfile = AutonomyProfile.BALANCED
    autonomy_budget_overrides: dict[str, Any] = field(default_factory=dict)

    # --- Context ---
    context_budget: ContextBudget | None = None

    # --- Model routing ---
    preferred_models: list[str] = field(default_factory=list)
    model_role_priority: dict[str, float] = field(default_factory=dict)
    privacy_preference: PrivacyPreference = PrivacyPreference.LOCAL_FIRST
    cost_priority: float = 0.5          # 0 = ignore cost, 1 = minimize cost
    latency_priority: float = 0.5       # 0 = ignore latency, 1 = minimize latency

    # --- Skill selection ---
    skill_categories: list[str] = field(default_factory=list)  # empty = all
    skill_risk_tolerance: SkillRisk = SkillRisk.LOW
    skill_confidence_threshold: float = 0.0
    progressive_loading: bool = True

    # --- Execution ---
    preferred_executor: str | None = None
    fallback_executors: list[str] = field(default_factory=list)
    max_parallelism: int = 1

    def resolved_autonomy_budget(self) -> AutonomyBudget:
        """Build an AutonomyBudget from profile + overrides."""
        budget = AutonomyBudget.from_profile(self.autonomy_profile)
        for key, value in self.autonomy_budget_overrides.items():
            if hasattr(budget, key):
                setattr(budget, key, value)
        return budget

    def resolved_context_budget(self) -> ContextBudget:
        """Return the context budget, or a default if none set."""
        return self.context_budget or ContextBudget()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "autonomy_profile": self.autonomy_profile.value,
            "autonomy_budget_overrides": self.autonomy_budget_overrides,
            "context_budget": {
                "max_tokens": self.resolved_context_budget().max_tokens,
                "max_fragments": self.resolved_context_budget().max_fragments,
                "max_sources": self.resolved_context_budget().max_sources,
            },
            "preferred_models": self.preferred_models,
            "model_role_priority": self.model_role_priority,
            "privacy_preference": self.privacy_preference.value,
            "cost_priority": self.cost_priority,
            "latency_priority": self.latency_priority,
            "skill_categories": self.skill_categories,
            "skill_risk_tolerance": self.skill_risk_tolerance.value,
            "skill_confidence_threshold": self.skill_confidence_threshold,
            "progressive_loading": self.progressive_loading,
            "preferred_executor": self.preferred_executor,
            "fallback_executors": self.fallback_executors,
            "max_parallelism": self.max_parallelism,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionProfile:
        profile = data.get("autonomy_profile", AutonomyProfile.BALANCED.value)
        if isinstance(profile, str):
            profile = AutonomyProfile(profile)
        privacy = data.get("privacy_preference", PrivacyPreference.LOCAL_FIRST.value)
        if isinstance(privacy, str):
            privacy = PrivacyPreference(privacy)
        risk = data.get("skill_risk_tolerance", SkillRisk.LOW.value)
        if isinstance(risk, str):
            risk = SkillRisk(risk)
        ctx = data.get("context_budget")
        context_budget = None
        if ctx:
            context_budget = ContextBudget(
                max_tokens=ctx.get("max_tokens", ContextBudget().max_tokens),
                max_fragments=ctx.get("max_fragments", ContextBudget().max_fragments),
                max_sources=ctx.get("max_sources", ContextBudget().max_sources),
            )
        return cls(
            name=data.get("name", "default"),
            description=data.get("description", ""),
            autonomy_profile=profile,
            autonomy_budget_overrides=data.get("autonomy_budget_overrides", {}),
            context_budget=context_budget,
            preferred_models=data.get("preferred_models", []),
            model_role_priority=data.get("model_role_priority", {}),
            privacy_preference=privacy,
            cost_priority=data.get("cost_priority", 0.5),
            latency_priority=data.get("latency_priority", 0.5),
            skill_categories=data.get("skill_categories", []),
            skill_risk_tolerance=risk,
            skill_confidence_threshold=data.get("skill_confidence_threshold", 0.0),
            progressive_loading=data.get("progressive_loading", True),
            preferred_executor=data.get("preferred_executor"),
            fallback_executors=data.get("fallback_executors", []),
            max_parallelism=data.get("max_parallelism", 1),
        )


# ── Presets ──

PRECISE = ExecutionProfile(
    name="precise",
    description="Conservative, local-first, low risk tolerance. Maximizes correctness over speed.",
    autonomy_profile=AutonomyProfile.CONSERVATIVE,
    privacy_preference=PrivacyPreference.LOCAL_ONLY,
    cost_priority=0.8,
    latency_priority=0.3,
    skill_risk_tolerance=SkillRisk.LOW,
    skill_confidence_threshold=0.6,
    progressive_loading=True,
    max_parallelism=1,
)

FAST = ExecutionProfile(
    name="fast",
    description="Aggressive, cloud-allowed, high parallelism. Maximizes throughput.",
    autonomy_profile=AutonomyProfile.AGGRESSIVE,
    privacy_preference=PrivacyPreference.CLOUD_ALLOWED,
    cost_priority=0.2,
    latency_priority=0.9,
    skill_risk_tolerance=SkillRisk.MEDIUM,
    skill_confidence_threshold=0.0,
    progressive_loading=True,
    max_parallelism=4,
)

SAFE = ExecutionProfile(
    name="safe",
    description="Interactive, minimal autonomy, frequent human checkpoints.",
    autonomy_profile=AutonomyProfile.INTERACTIVE,
    privacy_preference=PrivacyPreference.LOCAL_FIRST,
    cost_priority=0.5,
    latency_priority=0.5,
    skill_risk_tolerance=SkillRisk.LOW,
    skill_confidence_threshold=0.5,
    progressive_loading=True,
    max_parallelism=1,
)

DEVELOP = ExecutionProfile(
    name="develop",
    description="Balanced profile for development workflows.",
    autonomy_profile=AutonomyProfile.BALANCED,
    privacy_preference=PrivacyPreference.LOCAL_FIRST,
    cost_priority=0.5,
    latency_priority=0.5,
    skill_risk_tolerance=SkillRisk.MEDIUM,
    skill_confidence_threshold=0.3,
    progressive_loading=True,
    max_parallelism=2,
)

PRESETS: dict[str, ExecutionProfile] = {
    "default": DEVELOP,  # balanced default
    "precise": PRECISE,
    "fast": FAST,
    "safe": SAFE,
    "develop": DEVELOP,
}


def get_execution_profile(name: str) -> ExecutionProfile:
    """Return a preset execution profile by name (case-insensitive)."""
    return PRESETS.get(name.lower(), DEVELOP)


def list_execution_profiles() -> list[str]:
    """List available preset profile names."""
    return list(PRESETS.keys())
