"""Deliberate public execution contract for PAW Core.

Services, adapters and compatibility helpers are imported from their owning
modules. Keeping this root surface small prevents historical phase APIs from
becoming accidental permanent contracts.
"""

from __future__ import annotations

from .models import (
    CANONICAL_MODEL_ROLES,
    CANONICAL_ROLE_CONTRACTS,
    DEFAULT_TASK_SIGNALS,
    AutonomyDecision,
    BudgetLevel,
    Capability,
    ContextSufficiencyLevel,
    ExecutionObservation,
    ImpactLevel,
    ModelRole,
    NoveltyLevel,
    PolicyDecision,
    PrivacyLevel,
    ProposedAction,
    ResourceUsage,
    RoleContract,
    RoleDefinition,
    StopReason,
    TaskResult,
    TaskSignals,
    TaskStatus,
    classify_task,
)
from .runtime import PawRuntime, RuntimeOutcome

__all__ = [
    "CANONICAL_MODEL_ROLES",
    "CANONICAL_ROLE_CONTRACTS",
    "DEFAULT_TASK_SIGNALS",
    "AutonomyDecision",
    "BudgetLevel",
    "Capability",
    "ContextSufficiencyLevel",
    "ExecutionObservation",
    "ImpactLevel",
    "ModelRole",
    "NoveltyLevel",
    "PawRuntime",
    "PolicyDecision",
    "PrivacyLevel",
    "ProposedAction",
    "ResourceUsage",
    "RoleContract",
    "RoleDefinition",
    "RuntimeOutcome",
    "StopReason",
    "TaskResult",
    "TaskSignals",
    "TaskStatus",
    "classify_task",
]
