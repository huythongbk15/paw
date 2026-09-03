"""Deliberate public execution contract for PAW Core.

Services, adapters and compatibility helpers are imported from their owning
modules. Keeping this root surface small prevents historical phase APIs from
becoming accidental permanent contracts.
"""

from __future__ import annotations

from .models import (
    AutonomyDecision,
    Capability,
    ExecutionObservation,
    PolicyDecision,
    ProposedAction,
    ResourceUsage,
    StopReason,
    TaskResult,
    TaskStatus,
)
from .runtime import PawRuntime, RuntimeOutcome

__all__ = [
    "AutonomyDecision",
    "Capability",
    "ExecutionObservation",
    "PawRuntime",
    "PolicyDecision",
    "ProposedAction",
    "ResourceUsage",
    "RuntimeOutcome",
    "StopReason",
    "TaskResult",
    "TaskStatus",
]
