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


__all__ = [
    "CANONICAL_ROLE_CONTRACTS",
    "BudgetLevel",
    "ContextSufficiencyLevel",
    "ImpactLevel",
    "NoveltyLevel",
    "RoleContract",
    "TaskSignals",
    "UncertaintyDisposition",
]
