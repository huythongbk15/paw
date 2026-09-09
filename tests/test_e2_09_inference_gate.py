"""E2-09: Gate reconnaissance inference as model.inference.

Four-layer evidence:
  1. Invariant  — classify_inference is deterministic + fail-closed
  2. Runtime    — PawRuntime uses classification in _execute_action
  3. Adversarial — low-confidence tricks don't bypass the gate
  4. Measurable — threshold boundary is stable
"""
import pytest

from paw.core.reasoning_contracts import (
    InferenceClassification,
    ReconnaissanceResult,
    classify_inference,
)


# --- 1. Invariant -------------------------------------------------
class TestInvariantClassification:
    @pytest.mark.parametrize("reco,expected", [
        (ReconnaissanceResult(), InferenceClassification.MODEL_INFERENCE),
        (ReconnaissanceResult(task_goal="x", symbol_count=1,
                              evidence_confidence=0.0), InferenceClassification.MODEL_INFERENCE),
        (ReconnaissanceResult(task_goal="x", symbol_count=1,
                              evidence_confidence=0.24), InferenceClassification.MODEL_INFERENCE),
        (ReconnaissanceResult(task_goal="x", symbol_count=1,
                              evidence_confidence=0.25), InferenceClassification.LOCAL_COMPUTE),
        (ReconnaissanceResult(task_goal="x", symbol_count=1,
                              evidence_confidence=0.5), InferenceClassification.LOCAL_COMPUTE),
        (ReconnaissanceResult(task_goal="x", symbol_count=1,
                              evidence_confidence=1.0), InferenceClassification.LOCAL_COMPUTE),
    ])
    def test_inv1_threshold_boundary(self, reco, expected):
        assert classify_inference(reco) == expected

    def test_inv2_is_deterministic(self):
        r = ReconnaissanceResult(symbol_count=3, evidence_confidence=0.7)
        results = {classify_inference(r) for _ in range(20)}
        assert len(results) == 1

    def test_inv3_enum_values_stable(self):
        assert InferenceClassification.MODEL_INFERENCE == "model.inference"
        assert InferenceClassification.LOCAL_COMPUTE == "local.compute"


# --- 2. Runtime ---------------------------------------------------
class TestRuntimeClassification:
    def test_rt1_runtime_source_has_classification_call(self):
        import inspect
        from paw.core.runtime import PawRuntime
        src = inspect.getsource(PawRuntime._execute_action)
        assert "classify_inference" in src

    def test_rt2_exported_in_all(self):
        import paw.core.reasoning_contracts as rc
        assert "classify_inference" in rc.__all__
        assert "InferenceClassification" in rc.__all__


# --- 3. Adversarial -----------------------------------------------
class TestAdversarialBypass:
    def test_adv1_just_above_threshold_with_zero_evidence_counts(self):
        r = ReconnaissanceResult(symbol_count=0, evidence_confidence=1.0)
        assert classify_inference(r) == InferenceClassification.MODEL_INFERENCE

    def test_adv2_confidence_just_below_threshold(self):
        r = ReconnaissanceResult(symbol_count=1, evidence_confidence=0.249)
        assert classify_inference(r) == InferenceClassification.MODEL_INFERENCE

    def test_adv3_high_confidence_but_no_evidence(self):
        r = ReconnaissanceResult(symbol_count=0, recent_change_count=0,
                                 test_association_count=0,
                                 knowledge_source_count=0,
                                 evidence_confidence=0.9)
        assert classify_inference(r) == InferenceClassification.MODEL_INFERENCE

    def test_adv4_max_confidence_boundary(self):
        r = ReconnaissanceResult(symbol_count=5, evidence_confidence=1.0)
        assert classify_inference(r) == InferenceClassification.LOCAL_COMPUTE


# --- 4. Measurable ------------------------------------------------
class TestMeasurableThreshold:
    @pytest.mark.parametrize("conf,expected", [
        (0.0, "model"), (0.1, "model"), (0.2, "model"),
        (0.24, "model"), (0.25, "local"), (0.3, "local"),
        (0.5, "local"), (0.75, "local"), (1.0, "local"),
    ])
    def test_meas1_threshold_grid(self, conf, expected):
        r = ReconnaissanceResult(symbol_count=10, evidence_confidence=conf)
        result = classify_inference(r).value
        assert result.startswith(expected)

    def test_meas2_monotonic_after_threshold(self):
        for conf in [0.25, 0.3, 0.5, 0.75, 1.0]:
            r = ReconnaissanceResult(symbol_count=10, evidence_confidence=conf)
            assert classify_inference(r) == InferenceClassification.LOCAL_COMPUTE

    def test_meas3_monotonic_below_threshold(self):
        for conf in [0.0, 0.1, 0.2, 0.24]:
            r = ReconnaissanceResult(symbol_count=10, evidence_confidence=conf)
            assert classify_inference(r) == InferenceClassification.MODEL_INFERENCE
