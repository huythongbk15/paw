"""
PAW Core — Base Models and Typed Identifiers

All domain objects are owned by PAW. No external framework types leak into these models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, BeforeValidator, Field

ID_LENGTH = 24
MIN_ID_LENGTH = 8


def _generate_id() -> str:
    return uuid.uuid4().hex[:ID_LENGTH]


def _validate_id(v: str) -> str:
    if not v or len(v) < MIN_ID_LENGTH:
        raise ValueError(f"ID must be at least {MIN_ID_LENGTH} characters")
    return v


ID = Annotated[str, BeforeValidator(_validate_id)]


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskEventType(StrEnum):
    TASK_CREATED = "task_created"
    PLAN_CREATED = "plan_created"
    SKILL_CANDIDATES_FOUND = "skill_candidates_found"
    SKILL_SELECTED = "skill_selected"
    CONTEXT_BUILT = "context_built"
    EXECUTOR_SELECTED = "executor_selected"
    MODEL_SELECTED = "model_selected"
    POLICY_CHECKED = "policy_checked"
    EXECUTION_STARTED = "execution_started"
    TOOL_CALLED = "tool_called"
    ARTIFACT_CREATED = "artifact_created"
    EXECUTION_COMPLETED = "execution_completed"
    MEMORY_PROPOSED = "memory_proposed"
    MEMORY_ACCEPTED = "memory_accepted"
    TASK_COMPLETED = "task_completed"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"
    SANDBOX = "sandbox"


class Capability(StrEnum):
    """EXECUTOR capabilities - action permissions that executors can perform."""
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    SHELL_EXECUTE = "shell.execute"
    NETWORK_HTTP = "network.http"
    PROCESS_SPAWN = "process.spawn"
    GIT_READ = "git.read"
    GIT_WRITE = "git.write"
    SECRETS_READ = "secrets.read"
    DESTRUCTIVE = "destructive"
    FINANCIAL = "financial"


class ModelCapability(StrEnum):
    """MODEL capabilities - cognitive/processing abilities that models possess."""
    REASONING = "reasoning"
    CODING = "coding"
    VISION = "vision"
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    LONG_CONTEXT = "long_context"
    EMBEDDING = "embedding"
    PLANNING = "planning"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"


class ModelRole(StrEnum):
    FAST = "fast"
    REASONING = "reasoning"
    CODING = "coding"
    TOOLS = "tools"
    VISION = "vision"
    EMBEDDING = "embedding"
    FALLBACK = "fallback"


class SkillRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    FACTUAL = "factual"


T = TypeVar("T")


class Result[T](BaseModel):
    """Standard result wrapper for operations that can fail."""
    ok: bool
    value: T | None = None
    error: str | None = None

    @classmethod
    def success(cls, value: T) -> Result[T]:
        return cls(ok=True, value=value)

    @classmethod
    def failure(cls, error: str) -> Result[T]:
        return cls(ok=False, error=error)


class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class Identified(BaseModel):
    id: ID = Field(default_factory=_generate_id)


class Metadata(BaseModel):
    """Generic metadata container for extensibility."""
    data: dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value


# --- TaskResult contract (per prompt spec) ---

class Artifact(BaseModel):
    """A file or artifact produced by task execution."""
    path: str
    artifact_type: str = "file"
    description: str = ""


class Decision(BaseModel):
    """A decision made during task execution."""
    type: str
    rationale: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Evidence(BaseModel):
    """Evidence supporting a claim or result."""
    source: str
    claim: str
    confidence: float = 0.5
    citation: str = ""


class Citation(BaseModel):
    """Source citation for knowledge/evidence."""
    source_id: str
    context: str = ""
    position: int = 0


class Usage(BaseModel):
    """Token/compute usage tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    monetary_cost: float = 0.0
    compute_cost: float = 0.0


class ErrorInfo(BaseModel):
    """Structured error information."""
    code: str = ""
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = False


class TaskResult(BaseModel):
    """Normalized result from any executor. No provider output leaks into PAW Core."""
    task_id: str = ""
    status: str = "completed"  # Literal["completed", "failed", "partial", "blocked"]
    summary: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    executor: str | None = None
    model: str | None = None
    usage: Usage | None = None
    error: ErrorInfo | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# --- Model Router contract ---

class ModelManifest(BaseModel):
    """Metadata about a model and its capabilities."""
    name: str = ""
    provider: str = ""  # 'local', 'ollama', 'openrouter', 'direct'
    roles: list[str] = Field(default_factory=list)  # fast, reasoning, coding, tools, vision, embedding, fallback
    model_capabilities: dict[str, float] = Field(default_factory=dict)  # ModelCapability -> score (0-10)
    cost: dict[str, str] = Field(default_factory=dict)  # compute: low/medium/high, monetary: free/low/variable
    features: dict[str, bool] = Field(default_factory=dict)  # resumable, subagents, streaming, etc.
    max_context_tokens: int = 128000
    latency_tier: str = "medium"  # low, medium, high
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> ModelManifest:
        return cls(**data)


class ModelSelection(BaseModel):
    """The result of model routing for a task."""
    model_name: str = ""
    model_manifest: ModelManifest | None = None
    role: str = "fast"  # ModelRole
    reason: str = ""
    fallback_chain: list[str] = Field(default_factory=list)
    score: float = 0.0


class CapabilityManifest(BaseModel):
    """Declares what an executor/runtime can do and how well."""
    name: str = ""
    capabilities: dict[str, float] = Field(default_factory=dict)  # Capability -> score (0-10)
    cost: dict[str, str] = Field(default_factory=dict)
    features: dict[str, bool] = Field(default_factory=dict)


class CapabilityScore(BaseModel):
    """Score for a capability match between a task requirement and an executor."""
    capability: str = ""
    required_score: float = 0.0
    executor_score: float = 0.0
    matched: float = 0.0
    reason: str = ""
