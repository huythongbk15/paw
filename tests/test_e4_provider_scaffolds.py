"""E4-11..14 provider adapter tests.

Tests that E4-11..14 contracts are structurally defined and degrade
gracefully when no provider is available. When OPENAI_API_KEY is set,
provider functions execute against real cloud APIs (skipped otherwise).

No provider SDK imported beyond adapters in src/paw/providers/ (replaceable
per AGENTS.MD). Zero vendor lock-in — provider injected via parameters.
"""
import os

import pytest

from paw.core.dataset import (
    CloudTeacherBaselineResult,
    DatasetExample,
    LocalBaselineResult,
    TrainingArtifact,
    TrainingConfig,
    TrainingEvaluation,
    evaluate_training_artifact,
    measure_cloud_teacher_baseline,
    register_training_artifact,
    should_accept_artifact,
    train_dataset,
)
from paw.providers.openai.provider import (
    OpenAITrainingProvider,
    estimate_training_cost,
)


def _make_examples(n=5):
    """Create n test dataset examples."""
    return [
        DatasetExample(
            trace_id=f"t{i}",
            skill_name="test_skill",
            skill_version="1.0",
            input_prompt=f"Fix bug {i}",
            target_completion=f"fix {i} applied",
            source_files=[],
            capabilities=[],
            cost_estimate={},
            created_at="2026-09-01",
            redacted=True,
        )
        for i in range(n)
    ]


# === Dataclass structure tests (E4-11..14 pure logic, no provider) ===

class TestCloudTeacherBaselineResultStructure:
    def test_result_has_all_fields(self):
        result = CloudTeacherBaselineResult(
            model_name="gpt-4o-mini", accuracy=0.92,
            mean_latency_ms=250.0, total_tokens=5000,
            examples_evaluated=20, cost_estimate_usd=0.15,
        )
        d = result.to_dict()
        assert d["model_name"] == "gpt-4o-mini"
        assert d["accuracy"] == 0.92
        assert d["cost_estimate_usd"] == 0.15
        assert d["examples_evaluated"] == 20

    def test_result_cost_field_present(self):
        result = CloudTeacherBaselineResult(
            model_name="test", accuracy=0.9,
            mean_latency_ms=200.0, total_tokens=4000,
            examples_evaluated=15, cost_estimate_usd=0.10,
        )
        assert hasattr(result, "cost_estimate_usd")
        assert result.cost_estimate_usd == 0.10


class TestTrainingConfigStructure:
    def test_config_has_all_fields(self):
        config = TrainingConfig(
            base_model="gemma-2b-it", dataset_hash="abc123",
            dataset_version="1.0.0", epochs=3,
            learning_rate=0.001, batch_size=8,
            max_tokens=2048, budget_tokens=50000,
            consent_statement="consent",
        )
        assert config.base_model == "gemma-2b-it"
        assert config.epochs == 3
        assert config.learning_rate == 0.001
        assert config.budget_tokens == 50000

    def test_config_hash_is_deterministic(self):
        config_a = TrainingConfig(
            base_model="gemma", dataset_hash="h1", dataset_version="1.0",
            epochs=3, learning_rate=0.001, batch_size=8,
            max_tokens=2048, budget_tokens=50000,
            consent_statement="consent",
        )
        config_b = TrainingConfig(
            base_model="gemma", dataset_hash="h1", dataset_version="1.0",
            epochs=3, learning_rate=0.001, batch_size=8,
            max_tokens=2048, budget_tokens=50000,
            consent_statement="consent",
        )
        assert config_a.config_hash() == config_b.config_hash()


class TestTrainingArtifactStructure:
    def test_artifact_has_all_fields(self):
        config = TrainingConfig(
            base_model="gemma", dataset_hash="h1", dataset_version="1.0",
            epochs=3, learning_rate=0.001, batch_size=8,
            max_tokens=2048, budget_tokens=50000,
            consent_statement="consent",
        )
        artifact = TrainingArtifact(
            artifact_id="art_001", config=config,
            checkpoint_path="/models/gemma_v1",
            trained_at="2026-09-11T12:00:00Z",
            metrics={"accuracy": 0.88, "loss": 0.15},
            model_version="1.0.0-trained",
            consent_statement="consent",
            retention_days=90, deletion_policy="delete_after_retention",
            source_dataset_hash="h1",
        )
        d = artifact.to_dict()
        assert d["artifact_id"] == "art_001"
        assert d["evaluated"] is False
        assert d["accepted"] is False
        assert "artifact_hash" in d

    def test_artifact_hash_is_deterministic(self):
        config = TrainingConfig(
            base_model="gemma", dataset_hash="h1", dataset_version="1.0",
            epochs=3, learning_rate=0.001, batch_size=8,
            max_tokens=2048, budget_tokens=50000,
            consent_statement="consent",
        )
        art_a = TrainingArtifact(
            artifact_id="art_001", config=config,
            checkpoint_path="/models/gemma_v1",
            trained_at="2026-09-11T12:00:00Z",
            metrics={"accuracy": 0.88},
            model_version="1.0.0-trained",
            consent_statement="consent",
            retention_days=90, deletion_policy="delete",
            source_dataset_hash="h1",
        )
        art_b = TrainingArtifact(
            artifact_id="art_002", config=config,
            checkpoint_path="/models/gemma_v1",
            trained_at="2026-09-11T12:00:00Z",
            metrics={"accuracy": 0.88},
            model_version="1.0.0-trained",
            consent_statement="consent",
            retention_days=90, deletion_policy="delete",
            source_dataset_hash="h1",
        )
        # Different artifact_id → same hash (ID not in hash)
        assert art_a.artifact_hash == art_b.artifact_hash


class TestTrainingEvaluationStructure:
    def test_evaluation_has_all_fields(self):
        eval_obj = TrainingEvaluation(
            artifact_id="art_001", local_baseline_accuracy=0.50,
            cloud_teacher_accuracy=0.90, trained_accuracy=0.70,
            improvement_over_local=20.0,
            quality_regression=False,
            cost_reduction_pct=35.0,
        )
        d = eval_obj.to_dict()
        assert d["local_baseline_accuracy"] == 0.50
        assert d["trained_accuracy"] == 0.70
        assert d["quality_regression"] is False

    def test_training_provider_protocol_exists(self):
        """E4-12: TrainingProvider protocol with job status constants."""
        from paw.providers.openai.provider import TrainingProvider
        assert hasattr(TrainingProvider, "JOB_SUCCEEDED")
        assert hasattr(TrainingProvider, "JOB_FAILED")
        assert hasattr(TrainingProvider, "JOB_QUEUED")


# === Graceful degradation tests (no API key) ===

class TestE4GracefulDegradation:
    """When no provider available, E4-11..14 degrade gracefully."""

    @pytest.mark.asyncio
    async def test_measure_cloud_teacher_baseline_unavailable(self):
        """E4-11: No API key → returns zero-accuracy result, not crash."""
        examples = _make_examples(5)
        # Explicitly pass no-key provider
        provider = OpenAITrainingProvider(api_key=None)
        result = await measure_cloud_teacher_baseline(examples, provider=provider)
        assert result.accuracy == 0.0
        assert result.examples_evaluated == 0
        assert result.model_name == "unavailable"

    def test_openai_provider_available_false_without_key(self):
        """E4-11: OpenAI provider reports unavailable without API key."""
        provider = OpenAITrainingProvider(api_key=None)
        assert provider.available is False

    def test_openai_provider_estimates_cost(self):
        """E4-12: Training cost estimate is pure calculation."""
        cost = estimate_training_cost(num_examples=100, epochs=3, model="gpt-3.5-turbo")
        assert cost > 0  # Should be positive for 100 examples
        assert isinstance(cost, float)

    def test_should_accept_artifact_pure_logic(self):
        """E4-14: Acceptance gate is pure logic (no provider)."""
        # Accept: verified, no regression, good improvement, good cost
        good = TrainingEvaluation(
            artifact_id="a1", local_baseline_accuracy=0.5,
            cloud_teacher_accuracy=0.9, trained_accuracy=0.8,
            improvement_over_local=30.0,
            quality_regression=False,
            cost_reduction_pct=50.0,
            verified=True,
        )
        assert should_accept_artifact(good) is True

        # Reject: unverified
        bad_unverified = TrainingEvaluation(
            artifact_id="a1", local_baseline_accuracy=0.5,
            cloud_teacher_accuracy=0.9, trained_accuracy=0.8,
            improvement_over_local=30.0,
            quality_regression=False,
            cost_reduction_pct=50.0,
            verified=False,
        )
        assert should_accept_artifact(bad_unverified) is False

    def test_should_accept_no_cloud_baseline_relaxes_cost(self):
        """E4-14: No cloud baseline → cost reduction not required."""
        eval_no_cloud = TrainingEvaluation(
            artifact_id="a1", local_baseline_accuracy=0.5,
            cloud_teacher_accuracy=0.0,  # cloud unavailable
            trained_accuracy=0.8,
            improvement_over_local=30.0,
            quality_regression=False,
            cost_reduction_pct=10.0,  # low, but no cloud baseline
            verified=True,
        )
        assert should_accept_artifact(eval_no_cloud) is True


# === Conditional live provider tests ===

skip_no_openai_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for live E4-11 provider tests",
)


class TestE4LiveProvider:
    """When OPENAI_API_KEY is set, E4-11 provider functions work against real API."""

    @pytest.mark.asyncio
    @skip_no_openai_key
    async def test_cloud_teacher_baseline_live(self):
        """E4-11: Real provider measures baseline with accuracy > 0."""
        examples = _make_examples(3)
        provider = OpenAITrainingProvider()
        await provider.initialize()
        result = await measure_cloud_teacher_baseline(examples, provider=provider, max_examples=3)
        assert result.model_name != "unavailable"
        assert result.examples_evaluated > 0
        assert 0.0 <= result.accuracy <= 1.0
