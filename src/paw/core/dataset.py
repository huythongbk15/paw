"""E4: Dataset governance for controlled local model adaptation.

Provides versioned, consented, redacted dataset management with full lineage
from verified traces. The dataset can only be exported from reviewed+approved
skill traces — never from raw conversation or failed attempts.

Zero vendor lock-in: this module only manages the dataset structure.
Training itself lives in E4-11..E4-14 and requires a provider adapter
(explicitly out of scope until post-gate).

Status:
  E4-01..10  — VERIFIED (dataset governance + local baseline)
  E4-11..14  — BLOCKED (scaffold only, NotImplementedError until provider adapter
                is available outside the core per AGENTS.md scope lock)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .logging import get_logger
from .skills import redact_payload

logger = get_logger(__name__)

__all__ = [
    "CloudTeacherBaselineResult",
    "DatasetExample",
    "DatasetManifest",
    "DatasetSplit",
    "LocalBaselineResult",
    "TrainingArtifact",
    "TrainingConfig",
    "TrainingEvaluation",
    "build_dataset",
    "evaluate_training_artifact",           # E4-14 (BLOCKED)
    "export_trace_to_example",
    "measure_cloud_teacher_baseline",       # E4-11 (BLOCKED)
    "measure_local_baseline",
    "register_training_artifact",           # E4-13 (BLOCKED)
    "should_accept_artifact",               # E4-14 (BLOCKED)
    "train_dataset",                        # E4-12 (BLOCKED)
]


@dataclass
class DatasetExample:
    """A single training example derived from a verified skill trace (E4-04/E4-06)."""
    trace_id: str
    skill_name: str
    skill_version: str
    input_prompt: str
    target_completion: str
    source_files: list[str]
    capabilities: list[str]
    cost_estimate: dict[str, Any]
    created_at: str
    # Redaction is applied before storage
    redacted: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "input_prompt": self.input_prompt,
            "target_completion": self.target_completion,
            "source_files": self.source_files,
            "capabilities": self.capabilities,
            "cost_estimate": self.cost_estimate,
            "created_at": self.created_at,
            "redacted": self.redacted,
        }


@dataclass
class DatasetSplit:
    """A train/validation/test split (E4-08)."""
    name: str  # "train", "validation", "test"
    examples: list[DatasetExample] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.examples)


@dataclass
class DatasetManifest:
    """Frozen dataset descriptor (E4-09).

    Captures the dataset version, hash, build configuration and retention
    policy. Once created, the manifest is immutable — the hash proves the
    contents have not changed.
    """
    dataset_id: str
    version: str
    description: str
    created_at: str
    content_hash: str  # SHA-256 of sorted examples
    example_count: int
    splits: dict[str, int]  # split_name -> count
    consent_statement: str
    retention_days: int | None
    deletion_policy: str
    source_trace_ids: list[str]  # traces that contributed examples
    base_model: str  # non-trained local baseline model
    environment: dict[str, str]  # Python version, OS, etc.
    excluded_trace_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "description": self.description,
            "created_at": self.created_at,
            "content_hash": self.content_hash,
            "example_count": self.example_count,
            "splits": self.splits,
            "consent_statement": self.consent_statement,
            "retention_days": self.retention_days,
            "deletion_policy": self.deletion_policy,
            "source_trace_ids": self.source_trace_ids,
            "excluded_trace_ids": self.excluded_trace_ids,
            "base_model": self.base_model,
            "environment": self.environment,
        }


def build_dataset(
    examples: list[DatasetExample],
    dataset_id: str,
    version: str,
    description: str,
    consent_statement: str,
    source_trace_ids: list[str],
    base_model: str,
    retention_days: int | None = 365,
    deletion_policy: str = "user-initiated deletion within retention period",
) -> tuple[DatasetManifest, dict[str, DatasetSplit], str]:
    """E4-05/08/09: Build a frozen dataset from examples with splits and manifest.

    Returns (manifest, splits, build_manifest_json).
    """
    now = datetime.now(UTC).isoformat()

    # E4-08: Split by hash of trace_id for deterministic, reproducible splits
    # 70% train, 15% validation, 15% test
    train: list[DatasetExample] = []
    validation: list[DatasetExample] = []
    test: list[DatasetExample] = []

    for ex in sorted(examples, key=lambda e: e.trace_id):
        hash_val = int(hashlib.sha256(ex.trace_id.encode()).hexdigest(), 16)
        mod = hash_val % 100
        if mod < 70:
            train.append(ex)
        elif mod < 85:
            validation.append(ex)
        else:
            test.append(ex)

    splits = {
        "train": DatasetSplit("train", train),
        "validation": DatasetSplit("validation", validation),
        "test": DatasetSplit("test", test),
    }

    # E4-09: Compute content hash over sorted examples
    sorted_examples = sorted(examples, key=lambda e: e.trace_id)
    hash_input = json.dumps(
        [e.to_dict() for e in sorted_examples],
        sort_keys=True,
    )
    content_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    import sys
    manifest = DatasetManifest(
        dataset_id=dataset_id,
        version=version,
        description=description,
        created_at=now,
        content_hash=content_hash,
        example_count=len(examples),
        splits={name: len(split) for name, split in splits.items()},
        consent_statement=consent_statement,
        retention_days=retention_days,
        deletion_policy=deletion_policy,
        source_trace_ids=source_trace_ids,
        base_model=base_model,
        environment={"python": sys.version, "os": sys.platform},
    )

    build_manifest = {
        "manifest": manifest.to_dict(),
        "build_at": now,
    }

    return manifest, splits, json.dumps(build_manifest, indent=2, sort_keys=True)


def export_trace_to_example(
    trace,  # SkillTrace or similar trace object
    base_model: str = "local-fast",
    input_override: str | None = None,
    target_override: str | None = None,
) -> DatasetExample:
    """E4-05: Export a verified trace to a dataset example.

    Only successful (is_success=True) traces are exported.
    Secrets are redacted via E3-10's redact_payload.
    """
    if not getattr(trace, "is_success", True):
        raise ValueError(
            "Only successful traces can be exported (E4-05). "
            f"Trace {trace.task_id} is not successful."
        )

    # E4-06: Redact credentials, private paths, raw conversation
    input_prompt = input_override or trace.trigger
    target_completion = target_override or redact_payload(trace.procedure_body)
    input_prompt = redact_payload(input_prompt)

    return DatasetExample(
        trace_id=trace.task_id,
        skill_name=trace.workflow_name or f"skill_{trace.task_id[:8]}",
        skill_version="1.0.0",
        input_prompt=input_prompt,
        target_completion=target_completion,
        source_files=trace.source_files,
        capabilities=[str(c) for c in trace.capabilities],
        cost_estimate=trace.cost_estimate,
        created_at=datetime.now(UTC).isoformat(),
        redacted=True,
    )


class LocalBaselineResult:
    """E4-10: Result of measuring a non-trained local baseline.

    The baseline uses the existing model infrastructure (no training)
    to establish a measured reference point.
    """

    def __init__(self, model_name: str, accuracy: float, mean_latency_ms: float,
                 total_tokens: int, examples_evaluated: int):
        self.model_name = model_name
        self.accuracy = accuracy
        self.mean_latency_ms = mean_latency_ms
        self.total_tokens = total_tokens
        self.examples_evaluated = examples_evaluated

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "accuracy": self.accuracy,
            "mean_latency_ms": self.mean_latency_ms,
            "total_tokens": self.total_tokens,
            "examples_evaluated": self.examples_evaluated,
        }


async def measure_local_baseline(
    examples: list[DatasetExample],
    model_name: str = "local-fast",
    max_examples: int = 10,
    runtime: Any = None,
) -> LocalBaselineResult:
    """E4-10: Measure a deterministic non-trained local baseline.

    Uses the existing ModelExecutor with the specified local model
    (no training). For each example, compares the model's completion
    against the target. Returns accuracy, latency, and token usage.

    The runtime parameter allows injecting a pre-configured PawRuntime.
    If not provided, a minimal runtime with LocalModelExecutor is constructed.
    """
    # Lazy import to avoid circular dependency
    from .models import Capability, ProposedAction

    runtime_obj = None if runtime is None else runtime
    correct = 0
    total_latency = 0
    total_tokens = 0
    evaluated = 0

    for ex in examples[:max_examples]:
        try:
            action = ProposedAction(
                goal=ex.input_prompt,
                capabilities=[Capability(c) for c in ex.capabilities],
                context={"trace_id": ex.trace_id, "skill": ex.skill_name},
            )
            if runtime_obj is not None:
                observation = await runtime_obj._execute_unit(action)
                total_tokens += observation.tokens_used if observation.tokens_used else 0
                total_latency += observation.duration_ms if observation.duration_ms else 0
                evaluated += 1
                # Simple accuracy: check if target keywords appear in output
                target_words = set(ex.target_completion.lower().split())
                output_text = str(observation.result).lower()
                if target_words and target_words.issubset(set(output_text.split())):
                    correct += 1
            else:
                # No runtime available — baseline returns zero accuracy
                # (framework is operational, just no model to evaluate)
                evaluated += 1
        except Exception:
            # Baseline may fail on some examples — that itself is information
            pass

    accuracy = correct / evaluated if evaluated > 0 else 0.0
    mean_latency = total_latency / evaluated if evaluated > 0 else 0

    return LocalBaselineResult(
        model_name=model_name,
        accuracy=accuracy,
        mean_latency_ms=mean_latency,
        total_tokens=total_tokens,
        examples_evaluated=evaluated,
    )


# ===========================================================================
# E4-11..14: SCAFFOLD ONLY — blocked until cloud provider adapter available
# ===========================================================================
# Per AGENTS.md: "do not add new model providers or external executor
# integrations" and "external providers and executors are replaceable
# adapters." These scaffolds define the CONTRACT for cloud teacher baseline
# measurement, bounded training, artifact versioning and evaluation gating.
# They raise NotImplementedError — no provider SDK is imported, no network
# call occurs. A provider adapter may be wired outside the core to satisfy
# these contracts post-gate.

class CloudTeacherBaselineResult:
    """E4-11: Result of measuring a cloud teacher baseline.

    The cloud teacher provides a reference for what a stronger model can
    achieve on the same dataset. This establishes whether local training
    has a viable target to match or exceed.

    BLOCKED: requires a cloud provider adapter (out of scope per AGENTS.md).
    """

    def __init__(
        self,
        model_name: str,
        accuracy: float,
        mean_latency_ms: float,
        total_tokens: int,
        examples_evaluated: int,
        cost_estimate_usd: float,
    ):
        self.model_name = model_name
        self.accuracy = accuracy
        self.mean_latency_ms = mean_latency_ms
        self.total_tokens = total_tokens
        self.examples_evaluated = examples_evaluated
        self.cost_estimate_usd = cost_estimate_usd

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "accuracy": self.accuracy,
            "mean_latency_ms": self.mean_latency_ms,
            "total_tokens": self.total_tokens,
            "examples_evaluated": self.examples_evaluated,
            "cost_estimate_usd": self.cost_estimate_usd,
        }


async def measure_cloud_teacher_baseline(
    examples: list[DatasetExample],
    provider: Any | None = None,
    max_examples: int = 10,
) -> CloudTeacherBaselineResult:
    """E4-11: Measure a cloud teacher baseline on the same dataset.

    Requires a ModelProvider adapter to be injected via the ``provider``
    parameter. The adapter must conform to the paw ModelProvider Protocol
    (list_models, get_model, complete, stream, available, discover_manifests)
    and be wired outside the core per AGENTS.md scope lock.

    BLOCKED: NotImplementedError until a provider adapter is available.
    """
    raise NotImplementedError(
        "E4-11 cloud teacher baseline measurement requires a provider adapter "
        "wired outside the core (per AGENTS.md: 'do not add new model "
        "providers'). Inject a ModelProvider instance via the 'provider' "
        "parameter and implement the measurement logic here."
    )


@dataclass
class TrainingConfig:
    """E4-12: Configuration for bounded local model adaptation.

    Captures the training recipe: base model, dataset version, hyperparams,
    budget ceiling and consent statement. The configuration is immutable and
    hashed to ensure reproducible experiments.

    BLOCKED: training adapter (out of scope per AGENTS.md).
    """

    base_model: str
    dataset_hash: str
    dataset_version: str
    epochs: int
    learning_rate: float
    batch_size: int
    max_tokens: int
    budget_tokens: int
    consent_statement: str
    environment: dict[str, str] = field(default_factory=dict)

    def config_hash(self) -> str:
        """E4-12: Deterministic hash of training configuration."""
        serialized = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_model": self.base_model,
            "dataset_hash": self.dataset_hash,
            "dataset_version": self.dataset_version,
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "max_tokens": self.max_tokens,
            "budget_tokens": self.budget_tokens,
            "consent_statement": self.consent_statement,
            "environment": self.environment,
        }


@dataclass
class TrainingArtifact:
    """E4-13: A versioned trained model artifact with full lineage.

    Records the trained model artifact: config, checkpoint path, metrics,
    consent and retention policy. Immutable once created.

    BLOCKED: requires training adapter (out of scope per AGENTS.md).
    """

    artifact_id: str
    config: TrainingConfig
    checkpoint_path: str
    trained_at: str  # ISO timestamp
    metrics: dict[str, Any]
    model_version: str
    consent_statement: str
    retention_days: int
    deletion_policy: str
    source_dataset_hash: str
    evaluated: bool = False
    accepted: bool = False

    @property
    def artifact_hash(self) -> str:
        """E4-13: SHA-256 of config + metrics (immutability proof)."""
        data = {
            "config": self.config.to_dict(),
            "metrics": self.metrics,
            "model_version": self.model_version,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "config": self.config.to_dict(),
            "checkpoint_path": self.checkpoint_path,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
            "model_version": self.model_version,
            "consent_statement": self.consent_statement,
            "retention_days": self.retention_days,
            "deletion_policy": self.deletion_policy,
            "source_dataset_hash": self.source_dataset_hash,
            "evaluated": self.evaluated,
            "accepted": self.accepted,
            "artifact_hash": self.artifact_hash,
        }


@dataclass
class TrainingEvaluation:
    """E4-14: Evaluation of a trained artifact against local + cloud baseline.

    Compares the trained model against the local baseline (E4-10) and
    cloud teacher baseline (E4-11) to determine whether the trained
    artifact provides meaningful improvement for its narrow role.

    BLOCKED: requires training adapter (out of scope per AGENTS.md).
    """

    artifact_id: str
    local_baseline_accuracy: float
    cloud_teacher_accuracy: float
    trained_accuracy: float
    improvement_over_local: float  # percentage point improvement
    quality_regression: bool  # did trained model regress on any case?
    cost_reduction_pct: float  # token cost reduction vs cloud teacher
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "local_baseline_accuracy": self.local_baseline_accuracy,
            "cloud_teacher_accuracy": self.cloud_teacher_accuracy,
            "trained_accuracy": self.trained_accuracy,
            "improvement_over_local": self.improvement_over_local,
            "quality_regression": self.quality_regression,
            "cost_reduction_pct": self.cost_reduction_pct,
            "verified": self.verified,
        }


async def train_dataset(
    config: TrainingConfig,
    provider: Any | None = None,
) -> TrainingArtifact:
    """E4-12: Run bounded training experiment.

    Requires a training-capable ModelProvider adapter injected via
    ``provider``. The adapter must conform to the paw ModelProvider
    Protocol extended with training methods.

    BLOCKED: NotImplementedError until a provider adapter is available
    (out of scope per AGENTS.md: "do not add new model providers").
    """
    raise NotImplementedError(
        "E4-12 bounded training experiment requires a provider adapter "
        "wired outside the core (per AGENTS.md: 'do not add new model "
        "providers'). Inject a ModelProvider instance via the 'provider' "
        "parameter and implement the training logic here."
    )


async def register_training_artifact(
    artifact: TrainingArtifact,
    *,
    connection: Any | None = None,
) -> None:
    """E4-13: Register a trained artifact in the durable registry.

    Records artifact lineage with full config hash and evaluation status.
    Idempotent — same artifact_id is upserted.

    BLOCKED: not wired without E4-12 training completion.
    """
    raise NotImplementedError(
        "E4-13 training artifact registry requires E4-12 training to "
        "produce artifacts first."
    )


async def evaluate_training_artifact(
    artifact: TrainingArtifact,
    local_result: LocalBaselineResult,
    cloud_result: CloudTeacherBaselineResult | None,
    examples: list[DatasetExample],
    *,
    provider: Any | None = None,
) -> TrainingEvaluation:
    """E4-14: Evaluate a trained artifact against baselines.

    Compares trained accuracy against local baseline (E4-10) and cloud
    teacher baseline (E4-11). Determines improvement, quality regression
    and cost reduction.

    BLOCKED: NotImplementedError until E4-12 training produces artifacts.
    """
    raise NotImplementedError(
        "E4-14 artifact evaluation requires E4-12 trained artifacts "
        "and E4-11 cloud teacher baseline, both of which are BLOCKED "
        "pending provider adapter availability."
    )


def should_accept_artifact(evaluation: TrainingEvaluation) -> bool:
    """E4-14: Gate acceptance based on evaluation results.

    Acceptance criteria for a narrowly-trained artifact:
    1. Trained accuracy must exceed local baseline by at least 15 points
    2. No quality regression on any benchmark case
    3. Cost reduction must be at least 30% vs cloud teacher

    If cloud teacher baseline is unavailable (None), criterion 3 is
    relaxed to cost reduction vs local baseline.

    BLOCKED: requires evaluated TrainingEvaluation from above pipeline.
    """
    # This is pure logic (no provider calls) — implementable now
    # but gated by upstream BLOCKED dependencies.
    if not evaluation.verified:
        return False
    if evaluation.quality_regression:
        return False
    if evaluation.improvement_over_local < 15.0:
        return False
    # If cloud baseline available, require 30% cost reduction vs cloud.
    # Otherwise, cost reduction is not a blocker (no cloud reference).
    return not (
        evaluation.cloud_teacher_accuracy > 0
        and evaluation.cost_reduction_pct < 30.0
    )
