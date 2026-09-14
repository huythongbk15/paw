"""E4-11..14: Provider scaffold tests (BLOCKED).

These tests prove that the E4-11..14 contracts are *structurally defined*
but *behaviorally blocked* — they raise NotImplementedError when called,
without importing or activating any provider SDK.

No provider adapter is wired in core (per AGENTS.md scope lock).
"""
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


# === Dataclass structure tests (E4-11..14 pure logic, no provider) ===

class TestCloudTeacherBaselineResultStructure:
    """E4-11: CloudTeacherBaselineResult dataclass is structurally defined."""

    def test_result_has_all_fields(self):
        """E4-11: Result dataclass has all measurement fields including cost."""
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
        """E4-11: Cloud baseline includes cost tracking (cloud-specific)."""
        result = CloudTeacherBaselineResult(
            model_name="gpt-4o-mini", accuracy=0.9,
            mean_latency_ms=200.0, total_tokens=4000,
            examples_evaluated=15, cost_estimate_usd=0.10,
        )
        assert hasattr(result, "cost_estimate_usd")
        assert result.cost_estimate_usd == 0.10


class TestTrainingConfigStructure:
    """E4-12: TrainingConfig dataclass is structurally defined."""

    def test_config_has_all_fields(self):
        """E4-12: Config includes base_model, dataset_hash, hyperparams, budget, consent."""
        config = TrainingConfig(
            base_model="gemma-2b-it",
            dataset_hash="abc123",
            dataset_version="1.0.0",
            epochs=3,
            learning_rate=0.001,
            batch_size=8,
            max_tokens=2048,
            budget_tokens=50000,
            consent_statement="consent",
        )
        assert config.base_model == "gemma-2b-it"
        assert config.epochs == 3
        assert config.learning_rate == 0.001
        assert config.budget_tokens == 50000

    def test_config_hash_is_deterministic(self):
        """E4-12: Config hash is reproducible for immutable configs."""
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
    """E4-13: TrainingArtifact dataclass is structurally defined."""

    def test_artifact_has_all_fields(self):
        """E4-13: Artifact has config, checkpoint, metrics, lineage, status."""
        config = TrainingConfig(
            base_model="gemma", dataset_hash="h1", dataset_version="1.0",
            epochs=3, learning_rate=0.001, batch_size=8,
            max_tokens=2048, budget_tokens=50000,
            consent_statement="consent",
        )
        artifact = TrainingArtifact(
            artifact_id="art_001",
            config=config,
            checkpoint_path="/models/gemma_v1",
            trained_at="2026-09-11T12:00:00Z",
            metrics={"accuracy": 0.88, "loss": 0.15},
            model_version="1.0.0-trained",
            consent_statement="consent",
            retention_days=90,
            deletion_policy="delete_after_retention",
            source_dataset_hash="h1",
        )
        d = artifact.to_dict()
        assert d["artifact_id"] == "art_001"
        assert d["evaluated"] is False
        assert d["accepted"] is False
        assert "artifact_hash" in d

    def test_artifact_hash_is_deterministic(self):
        """E4-13: Artifact hash is reproducible (config + metrics + version)."""
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
            artifact_id="art_002",  # different ID
            config=config,
            checkpoint_path="/models/gemma_v1",
            trained_at="2026-09-11T12:00:00Z",
            metrics={"accuracy": 0.88},
            model_version="1.0.0-trained",
            consent_statement="consent",
            retention_days=90, deletion_policy="delete",
            source_dataset_hash="h1",
        )
        # Different artifact_id → different hash (ID is NOT in hash)
        # Wait — config + metrics + model_version are same → same hash
        assert art_a.artifact_hash == art_b.artifact_hash


class TestTrainingEvaluationStructure:
    """E4-14: TrainingEvaluation dataclass is structurally defined."""

    def test_evaluation_has_all_fields(self):
        """E4-14: Evaluation includes accuracy comparison and acceptance signals."""
        eval_obj = TrainingEvaluation(
            artifact_id="art_001",
            local_baseline_accuracy=0.65,
            cloud_teacher_accuracy=0.92,
            trained_accuracy=0.85,
            improvement_over_local=20.0,
            quality_regression=False,
            cost_reduction_pct=45.0,
        )
        d = eval_obj.to_dict()
        assert d["local_baseline_accuracy"] == 0.65
        assert d["trained_accuracy"] == 0.85
        assert d["quality_regression"] is False
        assert d["verified"] is False


class TestShouldAcceptArtifactLogic:
    """E4-14: should_accept_artifact is pure logic (no provider calls)."""

    def _make_eval(self, **kwargs):
        defaults = {
            "artifact_id": "test",
            "local_baseline_accuracy": 0.50,
            "cloud_teacher_accuracy": 0.90,
            "trained_accuracy": 0.70,
            "improvement_over_local": 20.0,
            "quality_regression": False,
            "cost_reduction_pct": 35.0,
            "verified": True,
        }
        defaults.update(kwargs)
        return TrainingEvaluation(**defaults)

    def test_accept_good_artifact(self):
        """E4-14: Artifact with good improvement, no regression, good cost reduction is accepted."""
        eval_obj = self._make_eval(
            improvement_over_local=25.0,
            quality_regression=False,
            cost_reduction_pct=40.0,
            cloud_teacher_accuracy=0.90,
            verified=True,
        )
        assert should_accept_artifact(eval_obj) is True

    def test_reject_unverified(self):
        """E4-14: Unverified evaluation is rejected."""
        eval_obj = self._make_eval(verified=False)
        assert should_accept_artifact(eval_obj) is False

    def test_reject_quality_regression(self):
        """E4-14: Quality regression blocks acceptance."""
        eval_obj = self._make_eval(quality_regression=True)
        assert should_accept_artifact(eval_obj) is False

    def test_reject_low_improvement(self):
        """E4-14: Improvement below 15 points blocks acceptance."""
        eval_obj = self._make_eval(improvement_over_local=10.0)
        assert should_accept_artifact(eval_obj) is False

    def test_reject_low_cost_reduction_with_cloud(self):
        """E4-14: Cost reduction below 30% with cloud baseline blocks."""
        eval_obj = self._make_eval(
            cost_reduction_pct=20.0,
            cloud_teacher_accuracy=0.90,
        )
        assert should_accept_artifact(eval_obj) is False

    def test_accept_without_cloud_baseline(self):
        """E4-14: No cloud baseline → cost reduction not a blocker."""
        eval_obj = self._make_eval(
            cost_reduction_pct=10.0,  # low, but no cloud baseline
            cloud_teacher_accuracy=0.0,  # cloud not available
            improvement_over_local=25.0,
        )
        assert should_accept_artifact(eval_obj) is True


# === BLOCKED contract tests (E4-11..14 raise NotImplementedError) ===

class TestE4ScaffoldsAreBlocked:
    """E4-11..14: All provider-dependent functions raise NotImplementedError.

    These are scaffolds only — no provider is imported or activated.
    The contracts exist so that a provider adapter can be wired
    externally (per AGENTS.md: 'external providers are replaceable adapters').
    """

    @pytest.mark.asyncio
    async def test_measure_cloud_teacher_baseline_raises_not_implemented(self):
        """E4-11: measure_cloud_teacher_baseline raises NotImplementedError."""
        examples = [DatasetExample(
            trace_id="t1", skill_name="s1", skill_version="1.0",
            input_prompt="test", target_completion="done",
            source_files=[], capabilities=[],
            cost_estimate={}, created_at="2026", redacted=True,
        )]
        with pytest.raises(NotImplementedError, match="provider adapter"):
            await measure_cloud_teacher_baseline(examples, provider=None)

    @pytest.mark.asyncio
    async def test_train_dataset_raises_not_implemented(self):
        """E4-12: train_dataset raises NotImplementedError."""
        config = TrainingConfig(
            base_model="test", dataset_hash="h", dataset_version="1.0",
            epochs=1, learning_rate=0.001, batch_size=1,
            max_tokens=100, budget_tokens=100,
            consent_statement="test",
        )
        with pytest.raises(NotImplementedError, match="provider adapter"):
            await train_dataset(config, provider=None)

    @pytest.mark.asyncio
    async def test_register_training_artifact_raises_not_implemented(self):
        """E4-13: register_training_artifact raises NotImplementedError."""
        config = TrainingConfig(
            base_model="test", dataset_hash="h", dataset_version="1.0",
            epochs=1, learning_rate=0.001, batch_size=1,
            max_tokens=100, budget_tokens=100,
            consent_statement="test",
        )
        artifact = TrainingArtifact(
            artifact_id="a1", config=config, checkpoint_path="/",
            trained_at="2026", metrics={},
            model_version="1.0", consent_statement="test",
            retention_days=90, deletion_policy="delete",
            source_dataset_hash="h",
        )
        with pytest.raises(NotImplementedError, match="E4-12 training"):
            await register_training_artifact(artifact)

    @pytest.mark.asyncio
    async def test_evaluate_training_artifact_raises_not_implemented(self):
        """E4-14: evaluate_training_artifact raises NotImplementedError."""
        config = TrainingConfig(
            base_model="test", dataset_hash="h", dataset_version="1.0",
            epochs=1, learning_rate=0.001, batch_size=1,
            max_tokens=100, budget_tokens=100,
            consent_statement="test",
        )
        artifact = TrainingArtifact(
            artifact_id="a1", config=config, checkpoint_path="/",
            trained_at="2026", metrics={},
            model_version="1.0", consent_statement="test",
            retention_days=90, deletion_policy="delete",
            source_dataset_hash="h",
        )
        local = LocalBaselineResult(
            model_name="local", accuracy=0.5,
            mean_latency_ms=100.0, total_tokens=100, examples_evaluated=10,
        )
        examples = [DatasetExample(
            trace_id="t1", skill_name="s1", skill_version="1.0",
            input_prompt="test", target_completion="done",
            source_files=[], capabilities=[],
            cost_estimate={}, created_at="2026", redacted=True,
        )]
        with pytest.raises(NotImplementedError, match="E4-12"):
            await evaluate_training_artifact(
                artifact, local, cloud_result=None, examples=examples,
            )
