"""
PAW Core — Core domain models and services.
"""

from __future__ import annotations

# Context Compiler (Phase 10)
# Autonomy Controller (Phase 10)
from .autonomy import (
    AutonomyBudget,
    AutonomyController,
    AutonomyDecision,
    AutonomyProfile,
    AutonomyUsage,
    StopReason,
)

# Checkpoint/Resume (Phase 10)
from .checkpoint import (
    CheckpointManager,
    CheckpointStore,
    ExtendedTaskStatus,
    ResumeManager,
    TaskCheckpoint,
    checkpoint_task,
)

# Config & Settings
from .config import PawSettings, settings
from .context import (
    ContextBudget,
    ContextBuilder,
    ContextFragment,
    ExplainEntry,
    TaskContext,
)

# Context Compiler (Phase 10)
from .context_compiler import (
    ContextCandidate,
    ContextCompiler,
    ContextPlan,
    format_explain_report,
)

# Detectors (Phase 10)
from .detectors import (
    LoopController,
    ProgressConfig,
    ProgressDetector,
    RepetitionConfig,
    RepetitionDetector,
    StallConfig,
    StallDetector,
)

# Execution Profile (K, Phase 10)
from .execution_profile import (
    DEVELOP,
    FAST,
    PRECISE,
    PRESETS,
    SAFE,
    ExecutionProfile,
    PrivacyPreference,
    get_execution_profile,
    list_execution_profiles,
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
    ExecutorScore,
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

# Identity (Phase 4 spec)
from .identity import Identity, IdentityManager

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
    "BUILTIN_SKILLS",
    "DEVELOP",
    "FAST",
    # Models
    "ID",
    "ID_LENGTH",
    "MIN_ID_LENGTH",
    "PRECISE",
    "PRESETS",
    "SAFE",
    "Artifact",
    "AutonomyBudget",
    # Autonomy Controller (Phase 10)
    "AutonomyController",
    # Phase 10 Models
    "AutonomyDecision",
    "AutonomyProfile",
    "AutonomyUsage",
    "Capability",
    "CapabilityManifest",
    # Capability Router
    "CapabilityRouter",
    "CapabilityScore",
    "CapabilityScorer",
    "CheckpointManager",
    "CheckpointStore",
    "Citation",
    "ContextBudget",
    # Context
    "ContextBuilder",
    "ContextCandidate",
    # Context Compiler (Phase 10)
    "ContextCompiler",
    "ContextFragment",
    "ContextPlan",
    "Database",
    "Decision",
    "DecompositionResult",
    "DecompositionStep",
    "DependencyType",
    "ErrorInfo",
    "Evidence",
    "ExecutableTask",
    # Execution Profile (K, Phase 10)
    "ExecutionProfile",
    # Executor
    "Executor",
    "ExecutorCapabilities",
    "ExecutorPolicyEnforcer",
    "ExecutorRegistry",
    "ExecutorResult",
    "ExecutorScore",
    "ExplainEntry",
    "ExtendedTaskStatus",
    "Identified",
    "Identity",
    "IdentityManager",
    # Phase 3
    "IntelligentPlanner",
    "LoopController",
    "MemoryRecord",
    "MemoryRetriever",
    "MemoryStore",
    "MemoryType",
    "Metadata",
    "MockExecutor",
    "ModelCapability",
    "ModelManifest",
    "ModelRegistry",
    "ModelRole",
    # Model Router
    "ModelRouter",
    "ModelScore",
    "ModelScorer",
    "ModelSelection",
    "PawSettings",
    # Planner
    "Plan",
    "Planner",
    "PolicyCheckResult",
    "PolicyDecision",
    "PolicyEnforcedExecutor",
    # Policy
    "PolicyGuard",
    "PolicyRule",
    "PrivacyPreference",
    "ProgressConfig",
    # Detectors (Phase 10)
    "ProgressDetector",
    "RepetitionConfig",
    "RepetitionDetector",
    "Result",
    "ResumeManager",
    "SemanticMatcher",
    "SemanticScore",
    "SemanticSkillSelector",
    # Session
    "Session",
    "SessionManager",
    # Skills
    "Skill",
    "SkillFabric",
    "SkillManifest",
    "SkillRisk",
    # Selector
    "SkillSelection",
    "SkillSelector",
    "StallConfig",
    "StallDetector",
    "StopReason",
    # Task
    "Task",
    # Checkpoint/Resume (Phase 10)
    "TaskCheckpoint",
    "TaskContext",
    "TaskDependency",
    # Ledger
    "TaskEvent",
    "TaskEventType",
    "TaskGraph",
    "TaskLedger",
    "TaskManager",
    "TaskNode",
    "TaskResult",
    "TaskScheduleStatus",
    # Knowledge Engine — import from paw.knowledge directly (avoid circular import)
    # Task Scheduler
    "TaskScheduler",
    "TaskStatus",
    "TimestampMixin",
    "Usage",
    "_generate_id",
    "_validate_id",
    "checkpoint_task",
    "configure_logging",
    "create_memory",
    # Storage
    "db",
    "ensure_policy_table",
    "ensure_task_scheduler_tables",
    "execute_task",
    "executor_registry",
    "format_explain_report",
    "get_capability_router",
    "get_db",
    "get_enforcer",
    "get_execution_profile",
    # Logging
    "get_logger",
    "get_model_registry",
    "get_model_router",
    "get_policy_guard",
    "get_semantic_selector",
    "get_skill_fabric",
    "get_task_scheduler",
    "list_execution_profiles",
    # Config
    "settings",
]
