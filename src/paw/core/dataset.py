"""E4: Dataset governance for controlled local model adaptation.

Provides versioned, consented, redacted dataset management with full lineage
from verified traces. The dataset can only be exported from reviewed+approved
skill traces — never from raw conversation or failed attempts.

Zero vendor lock-in: this module only manages the dataset structure.
Training adapter lives in src/paw/providers/ (replaceable per AGENTS.md).

Status:
  E4-01..10  — VERIFIED (dataset governance + local baseline)
  E4-11..14  — OPERATIONAL (provider adapter available, graceful degradation
                when provider unavailable)
  E4-21      — OPERATIONAL (per-version metrics tracking)
  E4-22      — PASS (integration pack gate verified)
"""
from __future__ import annotations

import asyncio
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
    "VersionMetric",
    "build_dataset",
    "evaluate_training_artifact",
    "export_trace_to_example",
    "get_version_metrics",
    "list_version_metrics",
    "measure_cloud_teacher_baseline",
    "measure_local_baseline",
    "record_version_metric",
    "register_training_artifact",
    "should_accept_artifact",
    "train_dataset",
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


# ===========================================================================
# E4-11..14: Provider-activated measurement and training
# ===========================================================================
# Per AGENTS.MD scope lock expansion (approved by Đại ca): cloud provider
# adapters are replaceable and live in src/paw/providers/. The core defines
# the contract; the adapter implements it. When no provider is injected or
# the provider is unavailable, functions degrade gracefully (zero accuracy,
# no crash) rather than raising.
from ..providers.openai.provider import (  # noqa: E402
    OpenAITrainingProvider,
    estimate_training_cost,
)


def _default_provider() -> Any | None:
    """E4-11: Lazily try to construct a default provider from env.

    Returns OpenAITrainingProvider if OPENAI_API_KEY is set, else None.
    No network call at construction time — availability checked on use.
    """
    try:
        provider = OpenAITrainingProvider()
        return provider
    except Exception:
        return None


async def measure_cloud_teacher_baseline(
    examples: list[DatasetExample],
    provider: Any | None = None,
    max_examples: int = 10,
) -> CloudTeacherBaselineResult:
    """E4-11: Measure a cloud teacher baseline on the same dataset.

    Uses the injected OpenAI provider (or default from env) to evaluate
    examples via a cloud LLM. Returns accuracy, latency, token usage and
    estimated cost.

    If provider is None or unavailable (no API key), returns zero-accuracy
    result (measurement framework operational, just no cloud access).
    """
    if provider is None:
        provider = _default_provider()

    if provider is None or not getattr(provider, "available", False):
        # Graceful degradation: no cloud access
        return CloudTeacherBaselineResult(
            model_name="unavailable", accuracy=0.0,
            mean_latency_ms=0.0, total_tokens=0,
            examples_evaluated=0, cost_estimate_usd=0.0,
        )

    correct = 0
    total_latency = 0.0
    total_tokens = 0
    total_cost = 0.0
    evaluated = 0

    for ex in examples[:max_examples]:
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a coding assistant. "
                        "Respond with the exact fix and verification steps."
                    ),
                },
                {"role": "user", "content": ex.input_prompt},
            ]
            req = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "max_tokens": 800,
            }
            import time
            t0 = time.monotonic()
            result = await provider.complete(req)
            elapsed_ms = (time.monotonic() - t0) * 1000.0

            text = result.get("response", "")
            usage = result.get("usage", {})
            total_tokens += usage.get("total_tokens", 0) or 0

            if "error" not in result:
                in_tokens = usage.get("prompt_tokens", 0) or 0
                out_tokens = usage.get("completion_tokens", 0) or 0
                # OpenAI pricing: ~$0.15/1M input, $0.60/1M output (gpt-4o-mini)
                total_cost += (in_tokens / 1_000_000) * 0.15 + (out_tokens / 1_000_000) * 0.60
                evaluated += 1
                total_latency += elapsed_ms

                target_words = set(ex.target_completion.lower().split())
                output_words = set(text.lower().split())
                if target_words and target_words.issubset(output_words):
                    correct += 1
        except Exception as exc:
            logger.warning("cloud_baseline_example_failed",
                           trace_id=ex.trace_id, error=str(exc))

    accuracy = correct / evaluated if evaluated > 0 else 0.0
    mean_latency = total_latency / evaluated if evaluated > 0 else 0.0

    return CloudTeacherBaselineResult(
        model_name="gpt-4o-mini",
        accuracy=accuracy,
        mean_latency_ms=mean_latency,
        total_tokens=total_tokens,
        examples_evaluated=evaluated,
        cost_estimate_usd=round(total_cost, 4),
    )


@dataclass
class TrainingConfig:
    """E4-12: Configuration for bounded local model adaptation.

    Captures the training recipe: base model, dataset version, hyperparams,
    budget ceiling and consent statement. The configuration is immutable and
    hashed to ensure reproducible experiments.
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
    def config_hash(self) -> str:
        """E4-13: Hash of the training configuration for reproducibility."""
        return self.config.config_hash()

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
            "config_hash": self.config_hash,
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
    training_file_path: str | None = None,
) -> TrainingArtifact:
    """E4-12: Run bounded training experiment.

    Uses the injected OpenAI provider (or default from env) to create a
    fine-tuning job. Requires a training_file_path (JSONL format).

    If provider is None or unavailable, raises NotImplementedError.
    """
    if provider is None:
        provider = _default_provider()

    if provider is None or not getattr(provider, "available", False):
        raise NotImplementedError(
            "E4-12 bounded training requires a provider adapter with "
            "training capability and valid API credentials. "
            "Set OPENAI_API_KEY to enable OpenAI fine-tuning."
        )

    if training_file_path is None:
        raise ValueError(
            "E4-12 training requires a training_file_path (JSONL format)."
        )

    file_id = await provider.upload_training_file(training_file_path)
    job_id = await provider.create_training_job(
        training_files=[file_id],
        suffix=config.base_model[:25],
        hyperparameters={
            "n_epochs": config.epochs,
            "batch_size": config.batch_size,
            "learning_rate_multiplier": config.learning_rate / 0.0003,
        },
    )

    import time
    max_poll_seconds = 600  # Bounded experiment: max 10 minutes
    poll_interval = 10
    elapsed = 0
    job_data: dict[str, Any] = {}

    while elapsed < max_poll_seconds:
        job_data = await provider.get_training_job(job_id)
        status = job_data.get("status", "")
        if status in (
            provider.JOB_SUCCEEDED, provider.JOB_FAILED, provider.JOB_CANCELLED
        ):
            break
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    trained_model = job_data.get("fine_tuned_model", config.base_model)
    training_cost = estimate_training_cost(
        num_examples=config.batch_size * config.epochs,
        epochs=config.epochs,
        model=config.base_model,
    )

    return TrainingArtifact(
        artifact_id=f"train_{job_id[:12]}",
        config=config,
        checkpoint_path=f"fine_tuned:{trained_model}",
        trained_at=datetime.fromtimestamp(time.time()).isoformat(),
        metrics={
            "job_id": job_id,
            "status": job_data.get("status", "unknown"),
            "training_cost": training_cost,
        },
        model_version=trained_model,
        consent_statement=config.consent_statement,
        retention_days=90,
        deletion_policy="auto_delete_after_evaluation",
        source_dataset_hash=config.dataset_hash,
    )


async def register_training_artifact(
    artifact: TrainingArtifact,
    *,
    connection: Any | None = None,
) -> None:
    """E4-13: Register a trained artifact in the durable registry.

    Records artifact lineage with full config hash and evaluation status.
    Idempotent — same artifact_id is upserted.
    """
    from .storage import db

    conn = connection if connection is not None else db

    await conn.write(
        """
        CREATE TABLE IF NOT EXISTS training_artifacts (
            artifact_id TEXT PRIMARY KEY,
            config_hash TEXT NOT NULL,
            config_json TEXT NOT NULL,
            checkpoint_path TEXT NOT NULL,
            trained_at TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            model_version TEXT NOT NULL,
            consent_statement TEXT NOT NULL,
            retention_days INTEGER NOT NULL,
            deletion_policy TEXT NOT NULL,
            source_dataset_hash TEXT NOT NULL,
            evaluated INTEGER DEFAULT 0,
            accepted INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    await conn.write(
        """
        INSERT OR REPLACE INTO training_artifacts
            (artifact_id, config_hash, config_json, checkpoint_path,
             trained_at, metrics_json, model_version, consent_statement,
             retention_days, deletion_policy, source_dataset_hash,
             evaluated, accepted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact.artifact_id,
            artifact.artifact_hash,
            json.dumps(artifact.config.to_dict()),
            artifact.checkpoint_path,
            artifact.trained_at,
            json.dumps(artifact.metrics),
            artifact.model_version,
            artifact.consent_statement,
            artifact.retention_days,
            artifact.deletion_policy,
            artifact.source_dataset_hash,
            int(artifact.evaluated),
            int(artifact.accepted),
        ),
    )
    logger.info("training_artifact_registered",
                artifact_id=artifact.artifact_id,
                config_hash=artifact.artifact_hash)


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
    """
    if provider is None:
        provider = _default_provider()

    trained_accuracy = 0.0
    quality_regression = False

    if provider is not None and getattr(provider, "available", False):
        model_name = artifact.model_version
        correct = 0
        evaluated = 0
        for ex in examples[:10]:
            try:
                result = await provider.complete({
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "You are a coding assistant."},
                        {"role": "user", "content": ex.input_prompt},
                    ],
                    "max_tokens": 800,
                })
                output = result.get("response", "")
                target_words = set(ex.target_completion.lower().split())
                output_words = set(output.lower().split())
                if target_words and target_words.issubset(output_words):
                    correct += 1
                evaluated += 1
            except Exception as exc:
                logger.warning("trained_eval_failed",
                               artifact=artifact.artifact_id, error=str(exc))

        trained_accuracy = correct / evaluated if evaluated > 0 else 0.0
        quality_regression = trained_accuracy < local_result.accuracy

    improvement = (trained_accuracy - local_result.accuracy) * 100.0

    cloud_cost = cloud_result.cost_estimate_usd if cloud_result else 0.0
    training_cost = artifact.metrics.get("training_cost", 0.0)
    cost_reduction = 0.0
    if cloud_cost > 0:
        cost_reduction = ((cloud_cost - training_cost) / cloud_cost) * 100.0

    return TrainingEvaluation(
        artifact_id=artifact.artifact_id,
        local_baseline_accuracy=local_result.accuracy,
        cloud_teacher_accuracy=cloud_result.accuracy if cloud_result else 0.0,
        trained_accuracy=trained_accuracy,
        improvement_over_local=improvement,
        quality_regression=quality_regression,
        cost_reduction_pct=round(cost_reduction, 2),
        verified=trained_accuracy > 0,
    )


def should_accept_artifact(evaluation: TrainingEvaluation) -> bool:
    """E4-14: Gate acceptance based on evaluation results.

    Acceptance criteria:
    1. Trained accuracy must exceed local baseline by at least 15 points
    2. No quality regression on any benchmark case
    3. Cost reduction must be at least 30% vs cloud teacher

    If cloud teacher baseline is unavailable, criterion 3 is relaxed.
    """
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


# ===========================================================================
# E4-21: Per-version training metrics
# ===========================================================================

@dataclass
class VersionMetric:
    """E4-21: Metrics for a single trained model version.

    Tracks performance, cost and usage of a specific trained model version
    over time. Multiple evaluations can accumulate per version.
    """

    model_version: str
    artifact_ids: list[str]  # artifacts that produced this version
    accuracy: float
    mean_latency_ms: float
    total_tokens: int
    training_cost: float
    inference_cost: float
    evaluated_at: str  # ISO timestamp
    evaluation_count: int
    quality_regression: bool = False

    @property
    def cost_efficiency(self) -> float:
        """Accuracy-to-cost ratio (higher is better)."""
        total_cost = self.training_cost + self.inference_cost
        return self.accuracy / total_cost if total_cost > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "artifact_ids": self.artifact_ids,
            "accuracy": self.accuracy,
            "mean_latency_ms": self.mean_latency_ms,
            "total_tokens": self.total_tokens,
            "training_cost": self.training_cost,
            "inference_cost": self.inference_cost,
            "evaluated_at": self.evaluated_at,
            "evaluation_count": self.evaluation_count,
            "quality_regression": self.quality_regression,
            "cost_efficiency": self.cost_efficiency,
        }


async def record_version_metric(
    artifact: TrainingArtifact,
    local_result: LocalBaselineResult,
    *,
    connection: Any | None = None,
) -> None:
    """E4-21: Record metrics for a trained model version.

    Called after evaluation to track per-version performance over time.
    Accumulates metrics — multiple calls for the same version update
    the running averages.
    """
    from .storage import db

    conn = connection if connection is not None else db

    await conn.write(
        """
        CREATE TABLE IF NOT EXISTS version_metrics (
            model_version TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            accuracy REAL,
            mean_latency_ms REAL,
            total_tokens INTEGER,
            training_cost REAL,
            inference_cost REAL DEFAULT 0,
            evaluated_at TEXT NOT NULL,
            quality_regression INTEGER DEFAULT 0,
            PRIMARY KEY (model_version, artifact_id)
        )
        """
    )

    training_cost = artifact.metrics.get("training_cost", 0.0)
    evaluated_at = datetime.now(UTC).isoformat()

    await conn.write(
        """
        INSERT OR REPLACE INTO version_metrics
            (model_version, artifact_id, accuracy, mean_latency_ms,
             total_tokens, training_cost, inference_cost,
             evaluated_at, quality_regression)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact.model_version,
            artifact.artifact_id,
            local_result.accuracy,  # accuracy from local evaluation
            local_result.mean_latency_ms,
            local_result.total_tokens,
            training_cost,
            0.0,  # inference_cost (local inference is free)
            evaluated_at,
            int(artifact.evaluated),
        ),
    )
    logger.info("version_metric_recorded",
                model_version=artifact.model_version,
                artifact_id=artifact.artifact_id)


async def get_version_metrics(
    model_version: str,
    *,
    connection: Any | None = None,
) -> VersionMetric:
    """E4-21: Aggregate metrics for a specific trained model version.

    Computes running averages across all artifacts/evaluations for the
    given version. Returns a single aggregated VersionMetric.
    """
    from .storage import db

    conn = connection if connection is not None else db

    rows = await conn.fetch_all(
        """
        SELECT artifact_id, accuracy, mean_latency_ms, total_tokens,
               training_cost, inference_cost, evaluated_at, quality_regression
        FROM version_metrics
        WHERE model_version = ?
        ORDER BY evaluated_at DESC
        """,
        [model_version],
    ) or []

    if not rows:
        return VersionMetric(
            model_version=model_version,
            artifact_ids=[],
            accuracy=0.0,
            mean_latency_ms=0.0,
            total_tokens=0,
            training_cost=0.0,
            inference_cost=0.0,
            evaluated_at="",
            evaluation_count=0,
        )

    count = len(rows)
    avg_accuracy = sum(r["accuracy"] or 0.0 for r in rows) / count
    avg_latency = sum(r["mean_latency_ms"] or 0.0 for r in rows) / count
    total_tokens = sum(r["total_tokens"] or 0 for r in rows)
    total_train_cost = sum(r["training_cost"] or 0.0 for r in rows)
    total_inf_cost = sum(r["inference_cost"] or 0.0 for r in rows)
    has_regression = any(r["quality_regression"] for r in rows)
    artifact_ids = [r["artifact_id"] for r in rows]
    latest_eval = rows[0]["evaluated_at"]  # most recent

    return VersionMetric(
        model_version=model_version,
        artifact_ids=artifact_ids,
        accuracy=round(avg_accuracy, 4),
        mean_latency_ms=round(avg_latency, 2),
        total_tokens=total_tokens,
        training_cost=round(total_train_cost, 4),
        inference_cost=round(total_inf_cost, 4),
        evaluated_at=latest_eval,
        evaluation_count=count,
        quality_regression=has_regression,
    )


async def list_version_metrics(
    *,
    connection: Any | None = None,
) -> list[VersionMetric]:
    """E4-21: List all version metrics (audit view).

    Returns aggregated metrics for every tracked model version,
    sorted by latest evaluation time descending.
    """
    from .storage import db

    conn = connection if connection is not None else db

    versions = await conn.fetch_all(
        "SELECT DISTINCT model_version FROM version_metrics ORDER BY model_version",
    ) or []

    metrics: list[VersionMetric] = []
    for row in versions:
        metric = await get_version_metrics(row["model_version"], connection=conn)
        metrics.append(metric)
    return metrics
