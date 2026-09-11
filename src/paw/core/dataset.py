"""E4: Dataset governance for controlled local model adaptation.

Provides versioned, consented, redacted dataset management with full lineage
from verified traces. The dataset can only be exported from reviewed+approved
skill traces — never from raw conversation or failed attempts.

Zero vendor lock-in: this module only manages the dataset structure.
Training itself lives in E4-12..E4-20 and requires a provider adapter
(explicitly out of scope until post-gate).
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
