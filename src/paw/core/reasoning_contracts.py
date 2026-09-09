"""Typed E2 inputs and outputs for governed model reasoning.

This module defines value contracts only. It does not select a model, classify
research depth, authorize escalation, or invoke a provider. Those decisions
remain with the owners named in the architecture and later E2 work items.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
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


class ResearchStopReason(StrEnum):
    """Why research stopped."""

    EVIDENCE_LIMIT = "evidence_limit"
    TIME_LIMIT = "time_limit"
    TOKEN_LIMIT = "token_limit"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ResearchBudget:
    """Bounded budget for local research operations before inference."""

    max_evidence_items: int = 20
    max_time_seconds: float = 300.0
    max_tokens: int = 4000
    stop_reason: ResearchStopReason = field(default=ResearchStopReason.COMPLETED)

    def __post_init__(self) -> None:
        if self.max_evidence_items < 0:
            raise ValueError("max_evidence_items must be non-negative")
        if self.max_time_seconds < 0:
            raise ValueError("max_time_seconds must be non-negative")
        if self.max_tokens < 0:
            raise ValueError("max_tokens must be non-negative")


def check_research_budget(
    budget: ResearchBudget,
    evidence_count: int = 0,
    elapsed_time: float = 0.0,
    tokens_used: int = 0,
) -> ResearchStopReason | None:
    """Return the stop reason if a research budget is exhausted, else None.

    Checks are ordered by priority:
      1. Evidence count
      2. Time
      3. Tokens

    If multiple limits are exceeded simultaneously, the highest-priority
    exhausted limit wins. A budget with stop_reason=COMPLETED and no
    exhausted limit returns None.
    """
    if evidence_count >= budget.max_evidence_items:
        return ResearchStopReason.EVIDENCE_LIMIT
    if elapsed_time >= budget.max_time_seconds:
        return ResearchStopReason.TIME_LIMIT
    if tokens_used >= budget.max_tokens:
        return ResearchStopReason.TOKEN_LIMIT
    return None


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
    research_budget: ResearchBudget | None = None

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




class InferenceClassification(StrEnum):
    """Gate for whether the next reasoning step is a model inference call
    (subject to the remote-disclosure privacy gate from E1-03) or can be
    satisfied by local compute.

    E2-09 defines the *boundary rule*. E2-10/E2-11 consume the classification.
    """

    MODEL_INFERENCE = "model.inference"
    LOCAL_COMPUTE = "local.compute"


def classify_inference(reco: ReconnaissanceResult) -> InferenceClassification:
    """Classify whether the next step requires model inference or can stay local.

    Boundary rule (single authority, fail-closed):
      * If reconnaissance found *no* local evidence (``is_empty``) or the
        evidence confidence falls below the threshold, the step requires
        ``model.inference`` -- local compute cannot proceed safely.
      * Otherwise, the step is classified as ``local.compute``.

    The confidence threshold defaults to 0.25: below that, local evidence
    is too sparse to justify skipping a model call.
    """
    threshold = 0.25
    if reco.is_empty():
        return InferenceClassification.MODEL_INFERENCE
    if reco.evidence_confidence < threshold:
        return InferenceClassification.MODEL_INFERENCE
    return InferenceClassification.LOCAL_COMPUTE


@dataclass(frozen=True)
class ReconnaissanceResult:
    """Bounded, local-first evidence gathered about a task before any
    model is invoked.

    E2-08 defines the *shape* of reconnaissance output only. The actual
    gathering (symbols, git changes, test associations) is deferred to the
    runtime/consumers; E2-09 gates any further inference as ``model.inference``.

    Every field is optional so that partial reconnaissance (e.g. a non-git
    repo) still produces a usable, deterministic result. Empty collections
    are explicit "no evidence found" -- never "haven't looked".
    """

    task_goal: str = ""
    # Bounded local evidence -- counts only, never raw content (privacy).
    symbol_count: int = 0
    symbol_kinds: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    recent_change_count: int = 0
    recent_changed_files: tuple[str, ...] = field(default_factory=tuple)
    test_association_count: int = 0
    knowledge_source_count: int = 0
    privacy_class: PrivacyClass = PrivacyClass.INTERNAL
    # Bounded confidence in local evidence (0.0-1.0). Absent -> 0.0.
    evidence_confidence: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.recent_changed_files, tuple):
            raise TypeError("recent_changed_files must be a tuple")
        if isinstance(self.symbol_kinds, Mapping):
            object.__setattr__(
                self, "symbol_kinds",
                MappingProxyType(self.symbol_kinds),
            )
        if math.isnan(self.evidence_confidence) or self.evidence_confidence < 0.0 or self.evidence_confidence > 1.0:
            raise ValueError("evidence_confidence must be between 0.0 and 1.0")
        if self.symbol_count < 0 or self.recent_change_count < 0:
            raise ValueError("counts must be non-negative")
        if self.test_association_count < 0 or self.knowledge_source_count < 0:
            raise ValueError("counts must be non-negative")

    def is_empty(self) -> bool:
        """True when no local evidence was found at all."""
        return (
            self.symbol_count == 0
            and self.recent_change_count == 0
            and self.test_association_count == 0
            and self.knowledge_source_count == 0
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


class ImplementationReadiness(StrEnum):
    """Readiness level for proceeding with a model inference call.

    E2-27: This is intentionally separate from PolicyDecision, AutonomyDecision,
    StopReason, and AutonomyStopReason. Readiness captures whether the
    *preconditions* for a safe, correct, efficient inference are met — not
    whether the autonomy loop should continue or the policy allows execution.

    Levels (ordered):
      * NEEDS_RESEARCH   — local evidence insufficient; reconnaissance required.
      * NEEDS_CLARIFICATION — goal is ambiguous; question must be asked.
      * SPIKE_REQUIRED   — bounded exploration needed before a real call.
      * READY            — preconditions met; safe to proceed to inference.
      * REJECTED         — the task should not proceed (e.g. privacy-blocked).
    """

class DecisionLevel(StrEnum):
    """Research depth classification: FAST, STANDARD, DEEP.

    E2-29: Classified from recorded TaskSignals, not from heuristic
    defaults. This is a *classification* of how much reasoning depth the
    canonical loop should apply — not a routing or autonomy decision.

    * FAST — routine, low-impact, sufficient context, no uncertainty.
             Can use the cheapest capability tier.
    * STANDARD — moderate novelty or impact, or partial context.
                Use the default capability tier.
    * DEEP — novelty, high/critical impact, insufficient context, or high
             uncertainty. Requires maximum reasoning depth.
    """

    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


def classify_research_depth(signals: TaskSignals) -> DecisionLevel:
    """Classify research depth from recorded task signals.

    E2-29 boundary rule (deterministic, fail-closed):

    Returns ``DEEP`` if any of:
      * impact is HIGH or CRITICAL
      * novelty is NOVEL or UNPRECEDENTED
      * context_sufficiency is INSUFFICIENT
      * uncertainty_score >= 0.7

    Returns ``STANDARD`` if any of:
      * impact is MEDIUM
      * novelty is FAMILIAR
      * context_sufficiency is PARTIAL
      * uncertainty_score is 0.4-0.7

    Returns ``FAST`` only when:
      * impact is LOW
      * novelty is ROUTINE
      * context_sufficiency is SUFFICIENT
      * uncertainty_score is 0.0-0.4
      * budget is not NEAR_LIMIT or EXHAUSTED

    When signals are UNKNOWN (incomplete reconnaissance), returns ``STANDARD``
    as a safe default — never FAST.
    """
    # Hard-deep conditions
    if signals.impact in (ImpactLevel.HIGH, ImpactLevel.CRITICAL):
        return DecisionLevel.DEEP
    if signals.novelty in (NoveltyLevel.NOVEL, NoveltyLevel.UNPRECEDENTED):
        return DecisionLevel.DEEP
    if signals.context_sufficiency is ContextSufficiencyLevel.INSUFFICIENT:
        return DecisionLevel.DEEP
    if signals.uncertainty_score is not None and signals.uncertainty_score >= 0.7:
        return DecisionLevel.DEEP

    # Standard conditions
    if signals.impact is ImpactLevel.MEDIUM:
        return DecisionLevel.STANDARD
    if signals.novelty is NoveltyLevel.FAMILIAR:
        return DecisionLevel.STANDARD
    if signals.context_sufficiency is ContextSufficiencyLevel.PARTIAL:
        return DecisionLevel.STANDARD
    if signals.uncertainty_score is not None and signals.uncertainty_score >= 0.4:
        return DecisionLevel.STANDARD

    # Fast only when all conditions are routine
    if (
        signals.impact is ImpactLevel.LOW
        and signals.novelty is NoveltyLevel.ROUTINE
        and signals.context_sufficiency is ContextSufficiencyLevel.SUFFICIENT
        and signals.uncertainty_score is not None
        and signals.uncertainty_score < 0.4
        and signals.budget not in (BudgetLevel.NEAR_LIMIT, BudgetLevel.EXHAUSTED)
    ):
        return DecisionLevel.FAST

    # Unknown/incomplete signals — safe default, never FAST
    return DecisionLevel.STANDARD


def classify_decision_level(signals: TaskSignals) -> DecisionLevel:
    """Alias for classify_research_depth (E2-29 spec)."""
    return classify_research_depth(signals)



RESEARCH_DEPTH_ACTIONS: MappingProxyType[DecisionLevel, str] = MappingProxyType({
    DecisionLevel.FAST: "continue",
    DecisionLevel.STANDARD: "ask",
    DecisionLevel.DEEP: "continue",
})

@dataclass(frozen=True)
class RoleCeiling:
    role: ModelRole
    max_tokens: int
    max_cost_usd: float

    def __post_init__(self) -> None:
        if self.max_tokens < 0:
            raise ValueError("max_tokens must be non-negative")
        if self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")

ROLE_CEILINGS: MappingProxyType[ModelRole, RoleCeiling] = MappingProxyType({
    ModelRole.FAST: RoleCeiling(role=ModelRole.FAST, max_tokens=2048, max_cost_usd=0.01),
    ModelRole.REASONING: RoleCeiling(role=ModelRole.REASONING, max_tokens=8192, max_cost_usd=0.05),
    ModelRole.CODING: RoleCeiling(role=ModelRole.CODING, max_tokens=8192, max_cost_usd=0.05),
    ModelRole.TOOLS: RoleCeiling(role=ModelRole.TOOLS, max_tokens=8192, max_cost_usd=0.05),
    ModelRole.VISION: RoleCeiling(role=ModelRole.VISION, max_tokens=32768, max_cost_usd=0.20),
    ModelRole.EMBEDDING: RoleCeiling(role=ModelRole.EMBEDDING, max_tokens=2048, max_cost_usd=0.00),
    ModelRole.FALLBACK: RoleCeiling(role=ModelRole.FALLBACK, max_tokens=2048, max_cost_usd=0.01),
})

_DEFAULT_CEILING = ROLE_CEILINGS[ModelRole.FALLBACK]

def check_role_ceiling(
    role: ModelRole,
    requested_tokens: int,
    estimated_cost_usd: float,
) -> str | None:
    """Return the overflow reason if the role ceiling is exceeded, else None.

    Unknown roles fall back to FALLBACK ceilings (fail-closed).
    """
    ceiling = ROLE_CEILINGS.get(role, _DEFAULT_CEILING)
    if requested_tokens > ceiling.max_tokens:
        return "token_limit"
    if estimated_cost_usd > ceiling.max_cost_usd:
        return "cost_limit"
    return None


def research_depth_action(depth: DecisionLevel) -> str:
    """Return the explicit action for a research depth (fail-closed).

    Unknown or future DecisionLevel values map to "stop" so that
    unrecognized depths never silently continue.
    """
    return RESEARCH_DEPTH_ACTIONS.get(depth, "stop")

__all__ = [
    "CANONICAL_ELIGIBILITY_RULES",
    "CANONICAL_ROLE_CONTRACTS",
    "OOD_CONDITIONS",
    "RESEARCH_DEPTH_ACTIONS",
    "ROLE_CEILINGS",
    "BudgetLevel",
    "ContextSufficiencyLevel",
    "DecisionLevel",
    "EligibilityResult",
    "EligibilityRule",
    "ImpactLevel",
    "ImplementationReadiness",
    "InferenceClassification",
    "NoveltyLevel",
    "OODCondition",
    "ProviderKind",
    "ReconnaissanceResult",
    "ResearchBudget",
    "ResearchStopReason",
    "RoleCeiling",
    "RoleContract",
    "TaskSignals",
    "UncertaintyDisposition",
    "check_research_budget",
    "check_role_ceiling",
    "classify_decision_level",
    "classify_inference",
    "classify_research_depth",
    "evaluate_local_eligibility",
    "research_depth_action",
]
