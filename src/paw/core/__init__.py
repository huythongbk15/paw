"""
PAW Core — Core domain models and services.
"""

from __future__ import annotations

# Config & Settings
from .config import PawSettings, settings
from .context import (
    ContextBudget,
    ContextBuilder,
    ContextFragment,
    ExplainEntry,
    TaskContext,
)

# Executor
from .executor import (
    CapabilityRouter,
    CapabilityScorer,
    ExecutableTask,
    Executor,
    ExecutorCapabilities,
    ExecutorRegistry,
    ExecutorResult,
    MockExecutor,
    execute_task,
    executor_registry,
    get_capability_router,
)
from .executor_policy import (
    ExecutorPolicyEnforcer,
    PolicyCheckResult,
    PolicyEnforcedExecutor,
    get_enforcer,
)

# Intelligent Planner
from .intelligent_planner import DecompositionResult, DecompositionStep, IntelligentPlanner

# Ledger
from .ledger import TaskEvent, TaskEventType, TaskLedger

# Logging
from .logging import configure_logging, get_logger
from .memory import MemoryRecord, MemoryRetriever, MemoryStore, create_memory

# Model Router
from .model_router import (
    ModelRegistry,
    ModelRouter,
    ModelScore,
    ModelScorer,
    get_model_registry,
    get_model_router,
)

# Base Models
from .models import (
    ID,
    ID_LENGTH,
    MIN_ID_LENGTH,
    # TaskResult contract
    Artifact,
    Capability,
    CapabilityManifest,
    CapabilityScore,
    Citation,
    Decision,
    ErrorInfo,
    Evidence,
    Identified,
    MemoryType,
    Metadata,
    ModelCapability,
    # Model Router
    ModelManifest,
    ModelRole,
    ModelSelection,
    PolicyDecision,
    Result,
    SkillRisk,
    TaskResult,
    TaskStatus,
    TimestampMixin,
    Usage,
    _generate_id,
    _validate_id,
)

# Planner
from .planner import Plan, Planner, TaskNode
from .policy import PolicyGuard, PolicyRule, ensure_policy_table, get_policy_guard
from .selector import SkillSelection, SkillSelector
from .semantic import SemanticMatcher, SemanticScore, SemanticSkillSelector, get_semantic_selector

# Session
from .session import Session, SessionManager

# Skills
from .skills import BUILTIN_SKILLS, Skill, SkillFabric, SkillManifest, get_skill_fabric

# Storage
from .storage import Database, db, get_db

# Task
from .task import Task, TaskManager

# CapabilityRouter is imported from .executor above
# Knowledge Engine (Phase 7) — imported separately from paw.knowledge
# (circular import avoidance — see docs)
from .task_scheduler import (
    DependencyType,
    TaskDependency,
    TaskGraph,
    TaskScheduler,
    TaskScheduleStatus,
    ensure_task_scheduler_tables,
    get_task_scheduler,
)

# Task Manager ref

__all__ = [
    # Config
    "settings", "PawSettings",
    # Logging
    "get_logger", "configure_logging",
    # Models
    "ID", "ID_LENGTH", "MIN_ID_LENGTH",
    "Capability", "Identified", "Metadata", "MemoryType", "ModelRole", "ModelCapability",
    "PolicyDecision", "Result", "SkillRisk", "TaskStatus",
    "TimestampMixin", "_generate_id", "_validate_id",
    "Artifact", "Decision", "Evidence", "Citation", "Usage", "ErrorInfo", "TaskResult",
    "ModelManifest", "ModelSelection", "CapabilityManifest", "CapabilityScore",
    # Storage
    "db", "Database", "get_db",
    # Session
    "Session", "SessionManager",
    # Task
    "Task", "TaskManager",
    # Ledger
    "TaskEvent", "TaskLedger", "TaskEventType",
    # Executor
    "Executor", "ExecutorResult", "MockExecutor", "executor_registry",
    "ExecutorCapabilities", "ExecutorRegistry", "ExecutableTask",
    "execute_task",
    # Skills
    "Skill", "SkillManifest", "SkillFabric", "get_skill_fabric", "BUILTIN_SKILLS",
    # Planner
    "Plan", "Planner", "TaskNode",
    # Selector
    "SkillSelection", "SkillSelector",
    # Context
    "ContextBuilder", "ContextFragment", "TaskContext",
    "ContextBudget", "ExplainEntry",
    # Policy
    "PolicyGuard", "PolicyRule", "get_policy_guard", "ensure_policy_table",
    # Phase 3
    "IntelligentPlanner", "DecompositionResult", "DecompositionStep",
    "SemanticMatcher", "SemanticSkillSelector", "SemanticScore",
    "get_semantic_selector",
    "MemoryStore", "MemoryRetriever", "MemoryRecord", "create_memory",
    "ExecutorPolicyEnforcer", "PolicyEnforcedExecutor", "PolicyCheckResult", "get_enforcer",
    # Model Router
    "ModelRouter", "ModelRegistry", "get_model_router", "get_model_registry",
    "ModelScorer", "ModelScore",
    # Capability Router
    "CapabilityRouter", "CapabilityScorer", "get_capability_router",
    # Knowledge Engine — import from paw.knowledge directly (avoid circular import)
    # Task Scheduler
    "TaskScheduler", "TaskGraph", "TaskDependency", "TaskScheduleStatus", "DependencyType",
    "get_task_scheduler", "ensure_task_scheduler_tables",
]
