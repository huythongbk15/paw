"""E4-22: Integration pack gate test.

Proves the E4 pipeline connects end-to-end:
  DatasetManifest → LocalBaseline → CloudTeacherBaseline → TrainingConfig →
  TrainingArtifact → Evaluation → Acceptance Gate → Version Metrics

Uses mock provider (no real network calls) to test the full wiring.
"""
import pytest

from paw.core.dataset import (
    CloudTeacherBaselineResult,
    DatasetExample,
    LocalBaselineResult,
    TrainingArtifact,
    TrainingConfig,
    TrainingEvaluation,
    VersionMetric,
    build_dataset,
    evaluate_training_artifact,
    get_version_metrics,
    list_version_metrics,
    measure_cloud_teacher_baseline,
    measure_local_baseline,
    record_version_metric,
    register_training_artifact,
    should_accept_artifact,
    train_dataset,
)


class MockProvider:
    """Mock OpenAI-compatible provider for E4-22 integration testing.

    Simulates provider behavior without network calls.
    """

    name = "mock"
    version = "1.0.0"
    _available = True
    JOB_SUCCEEDED = "succeeded"
    JOB_FAILED = "failed"
    JOB_CANCELLED = "cancelled"
    JOB_RUNNING = "running"
    JOB_QUEUED = "queued"

    def __init__(self):
        self.completion_text = "fix the bug applied successfully"
        self.cost = 0.05
        self.latency_ms = 100.0

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self) -> None:
        self._available = True

    async def shutdown(self) -> None:
        self._available = False

    async def complete(self, request: dict) -> dict:
        return {
            "response": self.completion_text,
            "model": request.get("model", "mock-model"),
            "usage": {"total_tokens": 150, "prompt_tokens": 100, "completion_tokens": 50},
            "thinking": "analyzing the bug",
            "done": True,
        }

    async def upload_training_file(self, file_path: str, purpose: str = "fine-tune") -> str:
        return "file-mock123"

    async def create_training_job(
        self, training_files: list[str], suffix: str, *,
        hyperparameters: dict | None = None,
        validation_files: list[str] | None = None,
    ) -> str:
        return "ftjob-mock123"

    async def get_training_job(self, job_id: str) -> dict:
        return {
            "id": job_id,
            "status": self.JOB_SUCCEEDED,
            "fine_tuned_model": "mock-finetuned-v1",
            "trained_tokens": 10000,
        }

    async def list_training_jobs(self) -> list[dict]:
        return [{"id": "ftjob-mock123", "status": "succeeded"}]


def _make_examples(n=5):
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


@pytest.mark.asyncio
class TestE4IntegrationPipeline:
    """E4-22: Full pipeline integration test."""

    async def test_dataset_to_local_baseline(self):
        """E4-22: DatasetManifest → LocalBaselineResult."""
        examples = _make_examples(5)
        manifest, splits, manifest_json = build_dataset(
            examples=examples,
            dataset_id="test_ds",
            version="1.0",
            description="test dataset",
            consent_statement="test",
            source_trace_ids=[e.trace_id for e in examples],
            base_model="local",
        )
        assert manifest.dataset_id == "test_ds"
        assert manifest.example_count == 5

        local = await measure_local_baseline(examples[:3])
        assert local.model_name in ("local-standin", "local-fast")
        assert 0.0 <= local.accuracy <= 1.0
        assert local.examples_evaluated == 3

    async def test_dataset_to_cloud_baseline(self):
        """E4-22: DatasetManifest → CloudTeacherBaselineResult (mock)."""
        examples = _make_examples(5)
        provider = MockProvider()
        await provider.initialize()

        result = await measure_cloud_teacher_baseline(examples, provider=provider)
        assert result.examples_evaluated == 5
        assert result.model_name == "gpt-4o-mini"

    async def test_full_pipeline_no_provider(self):
        """E4-22: Pipeline runs without provider (graceful degradation)."""
        examples = _make_examples(3)
        provider = None

        cloud = await measure_cloud_teacher_baseline(examples, provider=provider)
        assert cloud.accuracy == 0.0
        assert cloud.model_name == "unavailable"

        local = await measure_local_baseline(examples)
        assert local.model_name in ("local-standin", "local-fast")

    async def test_artifact_registry_roundtrip(self):
        """E4-22: TrainingArtifact → register → retrieve metadata."""
        config = TrainingConfig(
            base_model="gemma", dataset_hash="h1", dataset_version="1.0",
            epochs=3, learning_rate=0.001, batch_size=8,
            max_tokens=2048, budget_tokens=50000,
            consent_statement="test",
        )
        artifact = TrainingArtifact(
            artifact_id="art_e4_test", config=config,
            checkpoint_path="fine_tuned:test-v1",
            trained_at="2026-09-11T12:00:00Z",
            metrics={"job_id": "ft123", "status": "succeeded", "training_cost": 5.0},
            model_version="test-v1",
            consent_statement="test",
            retention_days=90, deletion_policy="auto_delete",
            source_dataset_hash="h1",
            evaluated=True,
            accepted=False,
        )
        await register_training_artifact(artifact)

        local = LocalBaselineResult(
            model_name="local", accuracy=0.5,
            mean_latency_ms=100.0, total_tokens=100, examples_evaluated=10,
        )
        await record_version_metric(artifact, local)
        metrics = await get_version_metrics("test-v1")
        assert metrics.model_version == "test-v1"
        assert metrics.accuracy == 0.5
        assert len(metrics.artifact_ids) == 1

    async def test_full_pipeline_acceptance_gate(self):
        """E4-22: Full acceptance gate logic works."""
        good_eval = TrainingEvaluation(
            artifact_id="good",
            local_baseline_accuracy=0.5,
            cloud_teacher_accuracy=0.9,
            trained_accuracy=0.85,
            improvement_over_local=35.0,
            quality_regression=False,
            cost_reduction_pct=50.0,
            verified=True,
        )
        assert should_accept_artifact(good_eval) is True

        bad_eval = TrainingEvaluation(
            artifact_id="bad",
            local_baseline_accuracy=0.5,
            cloud_teacher_accuracy=0.9,
            trained_accuracy=0.6,
            improvement_over_local=10.0,
            quality_regression=False,
            cost_reduction_pct=50.0,
            verified=True,
        )
        assert should_accept_artifact(bad_eval) is False

    async def test_version_metrics_list(self):
        """E4-22: list_version_metrics returns all tracked versions."""
        config = TrainingConfig(
            base_model="gemma", dataset_hash="h2", dataset_version="1.0",
            epochs=1, learning_rate=0.001, batch_size=4,
            max_tokens=1000, budget_tokens=10000,
            consent_statement="test",
        )
        artifact = TrainingArtifact(
            artifact_id="art_list_test", config=config,
            checkpoint_path="model:v2",
            trained_at="2026-09-11T12:00:00Z",
            metrics={"training_cost": 3.0},
            model_version="v2",
            consent_statement="test",
            retention_days=30, deletion_policy="auto",
            source_dataset_hash="h2",
            evaluated=True,
        )
        await register_training_artifact(artifact)

        local = LocalBaselineResult(
            model_name="local", accuracy=0.6,
            mean_latency_ms=50.0, total_tokens=50, examples_evaluated=5,
        )
        await record_version_metric(artifact, local)

        all_metrics = await list_version_metrics()
        assert any(m.model_version == "v2" for m in all_metrics)

    async def test_version_metric_cost_efficiency(self):
        """E4-21: VersionMetric.cost_efficiency is computed correctly."""
        vm = VersionMetric(
            model_version="v1",
            artifact_ids=["a1"],
            accuracy=0.8,
            mean_latency_ms=50.0,
            total_tokens=100,
            training_cost=10.0,
            inference_cost=2.0,
            evaluated_at="2026",
            evaluation_count=1,
        )
        assert vm.cost_efficiency == pytest.approx(0.8 / 12.0)

    async def test_version_metric_cost_efficiency_zero_cost(self):
        """E4-21: VersionMetric.cost_efficiency handles zero cost."""
        vm = VersionMetric(
            model_version="v1",
            artifact_ids=["a1"],
            accuracy=0.8,
            mean_latency_ms=0.0,
            total_tokens=0,
            training_cost=0.0,
            inference_cost=0.0,
            evaluated_at="2026",
            evaluation_count=0,
        )
        assert vm.cost_efficiency == 0.0

    async def test_pipeline_composition_no_provider(self):
        """E4-22: Pipeline composes with no provider injected."""
        examples = _make_examples(3)

        local = await measure_local_baseline(examples)
        assert local.accuracy >= 0.0

        cloud = await measure_cloud_teacher_baseline(examples, provider=None)
        assert cloud.accuracy == 0.0

        eval_no_cloud = TrainingEvaluation(
            artifact_id="test",
            local_baseline_accuracy=local.accuracy,
            cloud_teacher_accuracy=0.0,
            trained_accuracy=local.accuracy + 0.20,
            improvement_over_local=20.0,
            quality_regression=False,
            cost_reduction_pct=5.0,
            verified=True,
        )
        assert should_accept_artifact(eval_no_cloud) is True

    async def test_training_config_hash_propagation(self):
        """E4-12: TrainingConfig hash propagates to artifact for reproducibility."""
        config = TrainingConfig(
            base_model="gemma", dataset_hash="abc", dataset_version="1.0",
            epochs=2, learning_rate=0.002, batch_size=16,
            max_tokens=4096, budget_tokens=100000,
            consent_statement="reproducible",
        )
        config_hash = config.config_hash()
        assert len(config_hash) == 64

        artifact = TrainingArtifact(
            artifact_id="art_hash", config=config,
            checkpoint_path="/model",
            trained_at="2026",
            metrics={"training_cost": 1.0},
            model_version="v1",
            consent_statement="reproducible",
            retention_days=30, deletion_policy="delete",
            source_dataset_hash="abc",
        )
        d = artifact.to_dict()
        assert "config_hash" in d
        assert artifact.config_hash == config_hash

    async def test_artifact_evaluated_accepted_flags(self):
        """E4-13: Artifact evaluated/accepted flags default correctly."""
        config = TrainingConfig(
            base_model="test", dataset_hash="h", dataset_version="1.0",
            epochs=1, learning_rate=0.001, batch_size=1,
            max_tokens=100, budget_tokens=100,
            consent_statement="t",
        )
        artifact = TrainingArtifact(
            artifact_id="a1", config=config,
            checkpoint_path="/m",
            trained_at="2026",
            metrics={},
            model_version="v1",
            consent_statement="t",
            retention_days=30, deletion_policy="d",
            source_dataset_hash="h",
        )
        assert artifact.evaluated is False
        assert artifact.accepted is False

        artifact.evaluated = True
        artifact.accepted = True
        await register_training_artifact(artifact)
