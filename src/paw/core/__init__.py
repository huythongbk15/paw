"""Deliberate public execution contract for PAW Core.

Services, adapters and compatibility helpers are imported from their owning
modules. Keeping this root surface small prevents historical phase APIs from
becoming accidental permanent contracts.
"""

from __future__ import annotations

from .models import (
    CANONICAL_MODEL_ROLES,
    CANONICAL_ROLE_CONTRACTS,
    AutonomyDecision,
    Capability,
    ExecutionObservation,
    ModelRole,
    PolicyDecision,
    ProposedAction,
    ResourceUsage,
    RoleContract,
    RoleDefinition,
    StopReason,
    TaskResult,
    TaskStatus,
)
from .runtime import PawRuntime, RuntimeOutcome

__all__ = [
    "CANONICAL_MODEL_ROLES",
    "CANONICAL_ROLE_CONTRACTS",
    "AutonomyDecision",
    "Capability",
    "ExecutionObservation",
    "ModelRole",
    "PawRuntime",
    "PolicyDecision",
    "ProposedAction",
    "ResourceUsage",
    "RoleContract",
    "RoleDefinition",
    "RuntimeOutcome",
    "StopReason",
    "TaskResult",
    "TaskStatus",
]
