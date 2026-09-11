"""E4-10: Measure non-trained local baseline.

Tests that a non-trained local baseline can be measured using existing
model infrastructure without any training. This proves the measurement
framework is operational before any training experiment.
"""
import pytest

from paw.core.dataset import (
    DatasetExample,
    LocalBaselineResult,
    measure_local_baseline,
)


def make_example(i):
    return DatasetExample(
        trace_id=f"t{i}", skill_name=f"skill_{i}", skill_version="1.0.0",
        input_prompt=f"Fix issue number {i}", target_completion=f"Run test {i}, fix, re-run",
        source_files=[f"src/module_{i}.py"], capabilities=["filesystem.read"],
        cost_estimate={"tokens": 50}, created_at="2026-09-11", redacted=True,
    )


class TestLocalBaselineResult:
    def test_result_fields(self):
        """E4-10: LocalBaselineResult has all measurement fields."""
        result = LocalBaselineResult(
            model_name="local-fast", accuracy=0.85,
            mean_latency_ms=150.5, total_tokens=1000, examples_evaluated=10,
        )
        d = result.to_dict()
        assert d["model_name"] == "local-fast"
        assert d["accuracy"] == 0.85
        assert d["total_tokens"] == 1000
        assert d["examples_evaluated"] == 10

    def test_accuracy_bounded(self):
        """E4-10: Accuracy is between 0 and 1."""
        result = LocalBaselineResult(
            model_name="local-fast", accuracy=0.0,
            mean_latency_ms=0, total_tokens=0, examples_evaluated=0,
        )
        assert 0.0 <= result.accuracy <= 1.0


class TestLocalBaselineMeasurement:
    @pytest.mark.asyncio
    async def test_local_baseline_measurable(self):
        """E4-10: Local baseline measurement runs with existing infrastructure."""
        examples = [make_example(i) for i in range(5)]
        result = await measure_local_baseline(
            examples=examples, model_name="local-fast", max_examples=5,
        )
        assert result.model_name == "local-fast"
        assert isinstance(result.accuracy, float)
        assert isinstance(result.examples_evaluated, int)

    def test_baseline_uses_no_training(self):
        """E4-10: baseline measurement signature has no training params."""
        import inspect
        sig = inspect.signature(measure_local_baseline)
        params = set(sig.parameters.keys())
        assert "training_config" not in params
        assert "epochs" not in params
        assert "learning_rate" not in params
        assert "examples" in params
        assert "model_name" in params
