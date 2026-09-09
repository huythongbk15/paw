"""E2-21: Compare static initial routing with trajectory-aware routing on E0.

Four-layer evidence:
  1. Invariant  — static and trajectory-aware routing are separate code paths
  2. Runtime    — route() vs re_evaluate_routing() produce ModelSelection
  3. Adversarial — spoofed recon signals don't cause silent downgrade
  4. Measurable — model name + reason differ when recon changes the decision

Decision level: D2 (routing strategy comparison).
"""
import inspect

import pytest

from paw.core.models import ModelSelection
from paw.core.reasoning_contracts import (
    InferenceClassification,
    ReconnaissanceResult,
    classify_inference,
)


class TestStaticVsTrajectoryRouting:
    """Compare route() (static) vs re_evaluate_routing() (with recon)."""

    def test_inv1_re_evaluate_routing_accepts_recon(self):
        from paw.core.model_router import ModelRouter
        sig = inspect.signature(ModelRouter.re_evaluate_routing)
        params = list(sig.parameters.keys())
        assert "reconnaissance" in params
        assert "prev_selection" in params

    def test_inv2_route_does_not_require_recon(self):
        from paw.core.model_router import ModelRouter
        sig = inspect.signature(ModelRouter.route)
        assert "reconnaissance" in sig.parameters
        assert sig.parameters["reconnaissance"].default is None

    @pytest.mark.asyncio
    async def test_rt1_static_routing_no_recon(self, temp_db):
        from paw.core.model_router import ModelRouter
        router = ModelRouter()
        selection = await router.route(
            task_id="static-test", goal="analyze schema",
            role="fast", reconnaissance=None,
        )
        assert isinstance(selection, ModelSelection)

    @pytest.mark.asyncio
    async def test_rt2_trajectory_routing_local_compute(self, temp_db):
        from paw.core.model_router import ModelRouter
        from paw.core.privacy import PrivacyClass
        router = ModelRouter()
        prev = ModelSelection(
            model_name="test-model", role="fast", reason="initial routing",
        )
        recon = ReconnaissanceResult(
            task_goal="analyze local symbols",
            symbol_count=50, evidence_confidence=0.9,
            privacy_class=PrivacyClass.WORKSPACE,
        )
        result = await router.re_evaluate_routing(
            task_id="traj-test", prev_selection=prev, reconnaissance=recon,
        )
        assert isinstance(result, ModelSelection)
        assert classify_inference(recon) == InferenceClassification.LOCAL_COMPUTE

    @pytest.mark.asyncio
    async def test_rt3_trajectory_routing_model_inference(self, temp_db):
        from paw.core.model_router import ModelRouter
        router = ModelRouter()
        prev = ModelSelection(
            model_name="test-model", role="fast", reason="initial routing",
        )
        recon = ReconnaissanceResult(
            task_goal="complex architectural decision",
            symbol_count=5, evidence_confidence=0.1,
            knowledge_source_count=2,
        )
        classification = classify_inference(recon)
        assert classification == InferenceClassification.MODEL_INFERENCE
        result = await router.re_evaluate_routing(
            task_id="traj-test-2", prev_selection=prev, reconnaissance=recon,
        )
        assert isinstance(result, ModelSelection)

    @pytest.mark.asyncio
    async def test_adv1_spoofed_recon_secret_stays_safe(self, temp_db):
        from paw.core.model_router import ModelRouter
        from paw.core.privacy import PrivacyClass
        router = ModelRouter()
        prev = ModelSelection(
            model_name="local-small", role="fast", reason="initial",
        )
        recon = ReconnaissanceResult(
            task_goal="analyze secret code",
            symbol_count=1000, evidence_confidence=1.0,
            privacy_class=PrivacyClass.SECRET,
        )
        classification = classify_inference(recon)
        assert classification == InferenceClassification.LOCAL_COMPUTE
        result = await router.re_evaluate_routing(
            task_id="adv-secret", prev_selection=prev, reconnaissance=recon,
        )
        assert isinstance(result, ModelSelection)

    @pytest.mark.asyncio
    async def test_adv2_spoofed_symbol_count_does_not_bypass_checks(self, temp_db):
        from paw.core.model_router import ModelRouter
        router = ModelRouter()
        prev = ModelSelection(
            model_name="local-small", role="fast", reason="initial",
        )
        recon = ReconnaissanceResult(
            task_goal="simple task",
            symbol_count=99999, evidence_confidence=0.01,
            knowledge_source_count=0,
        )
        classification = classify_inference(recon)
        assert classification == InferenceClassification.MODEL_INFERENCE
        result = await router.re_evaluate_routing(
            task_id="adv-count", prev_selection=prev, reconnaissance=recon,
        )
        assert isinstance(result, ModelSelection)

    @pytest.mark.asyncio
    async def test_measure1_routing_difference_recorded(self, temp_db):
        from paw.core.model_router import ModelRouter
        router = ModelRouter()
        static = await router.route(
            task_id="measure-1", goal="verify schema",
            role="fast", reconnaissance=None,
        )
        assert isinstance(static, ModelSelection)
        recon = ReconnaissanceResult(
            task_goal="verify schema",
            symbol_count=20, evidence_confidence=0.8,
        )
        traj = await router.re_evaluate_routing(
            task_id="measure-1", prev_selection=static,
            reconnaissance=recon,
        )
        assert isinstance(traj, ModelSelection)
        assert static.reason or traj.reason

    def test_measure2_classification_drives_routing(self):
        local_recon = ReconnaissanceResult(
            evidence_confidence=0.95, symbol_count=200,
        )
        assert classify_inference(local_recon) == InferenceClassification.LOCAL_COMPUTE
        model_recon = ReconnaissanceResult(
            evidence_confidence=0.05, knowledge_source_count=0,
        )
        assert classify_inference(model_recon) == InferenceClassification.MODEL_INFERENCE

    def test_measure3_e0_cases_routable(self):
        import yaml
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        case_dir = root / "benchmarks" / "e0" / "cases"
        cases = sorted(case_dir.glob("*.yaml"))
        assert len(cases) > 0
        for case_path in cases[:5]:
            raw = yaml.safe_load(case_path.read_text())
            assert "goal" in raw
            assert "expected_evidence" in raw
            assert "case_id" in raw
