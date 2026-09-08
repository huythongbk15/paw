"""Typed E2 inputs and outputs for governed model reasoning.

This module defines value contracts only. It does not select a model, classify
research depth, authorize escalation, or invoke a provider. Those decisions
remain with the owners named in the architecture and later E2 work items.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .models import ModelRole
from .privacy import PrivacyClass


class UncertaintyDisposition(StrEnum):
    """Required control response when a role result misses its confidence bar."""

    STOP = "stop"
    ASK = "ask"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class RoleContract:
    """Immutable output, evidence and uncertainty contract for one E2 role."""

    role: ModelRole
    description: str
    scenario_tags: tuple[str, ...]
    output_schema: str
    requires_evidence: bool
    allowed_evidence_types: tuple[str, ...]
    reports_uncertainty: bool
    minimum_confidence: float | None
    low_confidence_disposition: UncertaintyDisposition
    requires_citation: bool

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("role description must not be empty")
        if not self.scenario_tags or any(not tag.strip() for tag in self.scenario_tags):
            raise ValueError("role scenario_tags must contain non-empty values")
        if not self.output_schema.strip():
            raise ValueError("role output_schema must not be empty")
        if self.minimum_confidence is not None:
            if not 0.0 <= self.minimum_confidence <= 1.0:
                raise ValueError("minimum_confidence must be between 0.0 and 1.0")
            if not self.reports_uncertainty:
                raise ValueError("a confidence threshold requires uncertainty output")
        if self.requires_evidence and not self.allowed_evidence_types:
            raise ValueError("an evidence-requiring role must name evidence types")
        if self.requires_citation and not self.requires_evidence:
            raise ValueError("citations cannot be required without evidence")


# The existing ModelRole enum also contains VISION and EMBEDDING modalities and
# a FALLBACK routing marker. They remain compatible manifest values but are not
# separate cognitive roles in the minimum E2 engineering loop.
CANONICAL_ROLE_CONTRACTS: Mapping[ModelRole, RoleContract] = MappingProxyType(
    {
        ModelRole.FAST: RoleContract(
            role=ModelRole.FAST,
            description="Bounded classification and concise synthesis for low-risk work.",
            scenario_tags=("classification", "summary"),
            output_schema="concise_assessment",
            requires_evidence=False,
            allowed_evidence_types=(),
            reports_uncertainty=True,
            minimum_confidence=0.80,
            low_confidence_disposition=UncertaintyDisposition.ESCALATE,
            requires_citation=False,
        ),
        ModelRole.REASONING: RoleContract(
            role=ModelRole.REASONING,
            description="Research, diagnosis and architecture option assessment.",
            scenario_tags=("research", "diagnosis", "architecture"),
            output_schema="reasoning_assessment",
            requires_evidence=True,
            allowed_evidence_types=("project_source", "test", "decision", "external"),
            reports_uncertainty=True,
            minimum_confidence=0.70,
            low_confidence_disposition=UncertaintyDisposition.ESCALATE,
            requires_citation=True,
        ),
        ModelRole.CODING: RoleContract(
            role=ModelRole.CODING,
            description="Source-backed implementation or review proposal for code changes.",
            scenario_tags=("implementation", "refactor", "review"),
            output_schema="implementation_proposal",
            requires_evidence=True,
            allowed_evidence_types=("project_source", "test", "decision"),
            reports_uncertainty=True,
            minimum_confidence=0.75,
            low_confidence_disposition=UncertaintyDisposition.ESCALATE,
            requires_citation=True,
        ),
        ModelRole.TOOLS: RoleContract(
            role=ModelRole.TOOLS,
            description="Structured proposal for one tool operation; never execution authority.",
            scenario_tags=("tool_proposal",),
            output_schema="operation_proposal",
            requires_evidence=False,
            allowed_evidence_types=(),
            reports_uncertainty=True,
            minimum_confidence=0.90,
            low_confidence_disposition=UncertaintyDisposition.STOP,
            requires_citation=False,
        ),
    }
)


class NoveltyLevel(StrEnum):
    UNKNOWN = "unknown"
    ROUTINE = "routine"
    FAMILIAR = "familiar"
    NOVEL = "novel"
    UNPRECEDENTED = "unprecedented"


class ImpactLevel(StrEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContextSufficiencyLevel(StrEnum):
    UNKNOWN = "unknown"
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class BudgetLevel(StrEnum):
    """Remaining research/model budget, not a routing or autonomy decision."""

    UNKNOWN = "unknown"
    WITHIN_LIMIT = "within_limit"
    NEAR_LIMIT = "near_limit"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True)
class TaskSignals:
    """Recorded inputs for later depth, eligibility and routing decisions.

    Unknown defaults are deliberate: absence of reconnaissance must never be
    interpreted as evidence that a task is routine, low-impact or ready for a
    fast route.
    """

    novelty: NoveltyLevel = NoveltyLevel.UNKNOWN
    impact: ImpactLevel = ImpactLevel.UNKNOWN
    privacy: PrivacyClass = PrivacyClass.INTERNAL
    context_sufficiency: ContextSufficiencyLevel = ContextSufficiencyLevel.UNKNOWN
    budget: BudgetLevel = BudgetLevel.UNKNOWN
    uncertainty_score: float | None = None
    estimated_tokens: int | None = None

    def __post_init__(self) -> None:
        enum_fields = (
            ("novelty", self.novelty, NoveltyLevel),
            ("impact", self.impact, ImpactLevel),
            ("privacy", self.privacy, PrivacyClass),
            ("context_sufficiency", self.context_sufficiency, ContextSufficiencyLevel),
            ("budget", self.budget, BudgetLevel),
        )
        for name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise TypeError(f"{name} must be {enum_type.__name__}")
        if self.uncertainty_score is not None and not (
            0.0 <= self.uncertainty_score <= 1.0
        ):
            raise ValueError("uncertainty_score must be between 0.0 and 1.0")
        if self.estimated_tokens is not None and self.estimated_tokens < 0:
            raise ValueError("estimated_tokens must be non-negative")

    @property
    def complete(self) -> bool:
        """Whether reconnaissance supplied every input required by E2-04."""

        return (
            self.novelty is not NoveltyLevel.UNKNOWN
            and self.impact is not ImpactLevel.UNKNOWN
            and self.context_sufficiency is not ContextSufficiencyLevel.UNKNOWN
            and self.budget is not BudgetLevel.UNKNOWN
            and self.uncertainty_score is not None
            and self.estimated_tokens is not None
        )


# --- E2-05: Local eligibility and out-of-distribution conditions per role ---

class ProviderKind(StrEnum):
    """Where a candidate model lives, in increasing disclosure risk."""

    LOCAL = "local"
    CLOUD_APPROVED = "cloud_approved"
    CLOUD_UNAPPROVED = "cloud_unapproved"


class OODCondition(StrEnum):
    """Explicit out-of-distribution conditions for a role."""

    NO_MATCHING_CAPABILITY = "no_matching_capability"
    MISSING_EVIDENCE = "missing_evidence"
    LOW_CONFIDENCE = "low_confidence"
    NOVEL_TASK = "novel_task"
    HIGH_IMPACT = "high_impact"
    PRIVACY_BLOCKED = "privacy_blocked"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNKNOWN = "unknown"


# Closed set: a condition not in this set is rejected at construction time.
#: Closed set of OOD conditions. Closed by construction; unknown values raise.
OOD_CONDITIONS: frozenset[OODCondition] = frozenset(OODCondition)


@dataclass(frozen=True)
class EligibilityRule:
    """One eligibility rule for a role.

    A rule names the conditions under which a candidate model is NOT eligible
    to serve the role locally. Eligibility is a value contract: it does not
    select a model, authorize escalation or invoke a provider.
    """

    role: ModelRole
    conditions: tuple[OODCondition, ...]
    description: str

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("rule description must not be empty")
        for condition in self.conditions:
            if not isinstance(condition, OODCondition):
                raise TypeError(
                    f"condition {condition!r} must be an OODCondition"
                )


@dataclass(frozen=True)
class EligibilityResult:
    """Result of evaluating one role's local eligibility."""

    role: ModelRole
    eligible: bool
    conditions: tuple[OODCondition, ...]
    matched_rule: str | None

    def is_out_of_distribution(self) -> bool:
        """True when the role is not eligible for local execution."""
        return not self.eligible


#: Canonical local eligibility rules per role. Closed by construction.
CANONICAL_ELIGIBILITY_RULES: Mapping[ModelRole, EligibilityRule] = MappingProxyType(
    {
        ModelRole.FAST: EligibilityRule(
            role=ModelRole.FAST,
            conditions=(
                OODCondition.NO_MATCHING_CAPABILITY,
                OODCondition.PROVIDER_UNAVAILABLE,
                OODCondition.BUDGET_EXHAUSTED,
            ),
            description="FAST is eligible locally unless no model matches, "
            "every provider is down, or budget is exhausted.",
        ),
        ModelRole.REASONING: EligibilityRule(
            role=ModelRole.REASONING,
            conditions=(
                OODCondition.NO_MATCHING_CAPABILITY,
                OODCondition.MISSING_EVIDENCE,
                OODCondition.LOW_CONFIDENCE,
                OODCondition.NOVEL_TASK,
                OODCondition.HIGH_IMPACT,
                OODCondition.PRIVACY_BLOCKED,
                OODCondition.PROVIDER_UNAVAILABLE,
                OODCondition.BUDGET_EXHAUSTED,
            ),
            description="REASONING is eligible locally only when evidence is "
            "present, confidence is adequate, the task is not novel or "
            "high-impact, privacy permits it, a provider is reachable and "
            "budget remains.",
        ),
        ModelRole.CODING: EligibilityRule(
            role=ModelRole.CODING,
            conditions=(
                OODCondition.NO_MATCHING_CAPABILITY,
                OODCondition.MISSING_EVIDENCE,
                OODCondition.LOW_CONFIDENCE,
                OODCondition.NOVEL_TASK,
                OODCondition.HIGH_IMPACT,
                OODCondition.PRIVACY_BLOCKED,
                OODCondition.PROVIDER_UNAVAILABLE,
                OODCondition.BUDGET_EXHAUSTED,
            ),
            description="CODING is eligible locally only when source evidence is "
            "present, confidence is adequate, the task is not novel or "
            "high-impact, privacy permits it, a provider is reachable and "
            "budget remains.",
        ),
        ModelRole.TOOLS: EligibilityRule(
            role=ModelRole.TOOLS,
            conditions=(
                OODCondition.NO_MATCHING_CAPABILITY,
                OODCondition.PRIVACY_BLOCKED,
                OODCondition.PROVIDER_UNAVAILABLE,
                OODCondition.BUDGET_EXHAUSTED,
            ),
            description="TOOLS is eligible locally unless no model matches, "
            "privacy blocks it, every provider is down, or budget is exhausted.",
        ),
    }
)


def evaluate_local_eligibility(
    role: ModelRole,
    observed_conditions: frozenset[OODCondition],
) -> EligibilityResult:
    """Evaluate one role's local eligibility against observed OOD conditions.

    The rule is the single authority. ``observed_conditions`` is the set of
    conditions detected by reconnaissance; any overlap with the rule's
    conditions makes the role out-of-distribution for local execution.
    """
    rule = CANONICAL_ELIGIBILITY_RULES.get(role)
    if rule is None:
        return EligibilityResult(
            role=role,
            eligible=False,
            conditions=(OODCondition.UNKNOWN,),
            matched_rule=None,
        )
    overlap = frozenset(rule.conditions) & observed_conditions
    return EligibilityResult(
        role=role,
        eligible=not overlap,
        conditions=tuple(sorted(overlap, key=lambda c: c.value)),
        matched_rule=rule.description,
    )


__all__ = [
    "CANONICAL_ELIGIBILITY_RULES",
    "CANONICAL_ROLE_CONTRACTS",
    "OOD_CONDITIONS",
    "BudgetLevel",
    "ContextSufficiencyLevel",
    "EligibilityResult",
    "EligibilityRule",
    "ImpactLevel",
    "NoveltyLevel",
    "OODCondition",
    "ProviderKind",
    "RoleContract",
    "TaskSignals",
    "UncertaintyDisposition",
]
