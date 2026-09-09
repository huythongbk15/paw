"""E2-10: Re-evaluate routing after reconnaissance rather than only from the initial prompt.

Four-layer evidence:
  1. Invariant  — re_evaluate_routing respects classify_inference boundary
  2. Runtime    — PawRuntime re-evaluates routing after _gather_reconnaissance
  3. Adversarial — conflicting/insufficient evidence doesn't cause wrong downgrade
  4. Measurable — re-evaluation actually changes model selection when evidence supports
"""
import pytest

from paw.core.models import ModelSelection, ModelManifest, ModelCapability
from paw.core.reasoning_contracts import (
    ReconnaissanceResult,
    InferenceClassification,
    classify_inference,
)
from paw.core.model_router import ModelRouter


def _make_manifest(name, provider="local", roles=None, capabilities=None):
    """Create a ModelManifest for testing."""
    roles = roles or ["fast"]
    return ModelManifest(
        name=name,
        provider=provider,
        roles=roles,
        model_capabilities=capabilities or {
            ModelCapability.REASONING: 5.0,
            ModelCapability.STRUCTURED_OUTPUT: 5.0,
        },
        cost={"compute": "low", "monetary": "free"},
        features={"streaming": True},
        max_context_tokens=4096,
        latency_tier="low",
        enabled=True,
    )


def _make_router_with_models():
    """Create a ModelRouter with local + mock provider models."""
    router = ModelRouter()
    router.registry.clear()
    router.registry.register(_make_manifest(
        "local-echo", provider="local", roles=["fast", "reasoning"]
    ))
    router.registry.register(_make_manifest(
        "cloud-1", provider="mock_cloud", roles=["fast", "reasoning"]
    ))
    return router


class _MockProvider:
    """Minimal ModelProvider-compatible object."""
    def __init__(self, name, available=True):
        self.name = name
        self.available = available
    def list_models(self): return []
    def get_model(self, name): return None
    async def complete(self, model, prompt, **kw): return {"text": "ok"}
    async def stream(self, model, prompt, **kw):
        yield {"text": "ok"}
    async def discover_manifests(self): return []


# --- 1. Invariant -------------------------------------------------
class TestInvariantReEvaluateRouting:
    """Layer 1: re_evaluate_routing respects classify_inference boundary."""

    async def test_inv1_local_compute_downgrades_to_local(self):
        """When recon shows local compute is sufficient, downgrades cloud->local."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        recon = ReconnaissanceResult(
            task_goal="test",
            symbol_count=10,
            evidence_confidence=0.5,  # >= 0.25 threshold
            privacy_class=__import__(
                "paw.core.privacy", fromlist=["PrivacyClass"],
            ).PrivacyClass.INTERNAL,
        )
        result = await router.re_evaluate_routing("t1", prev, recon)
        # classify_inference should agree with LOCAL_COMPUTE
        assert classify_inference(recon) == InferenceClassification.LOCAL_COMPUTE
        # Downgrade: local model selected
        assert result.model_manifest.provider == "local"
        assert result.model_name == "local-echo"
        assert "E2-10 re-evaluated" in result.reason
        assert "downgraded" in result.reason

    async def test_inv2_model_inference_escalates_when_ood(self):
        """When MODEL_INFERENCE + OOD signals (non-empty), escalates role."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        # Non-empty recon, low confidence → model.inference + OOD
        recon = ReconnaissanceResult(
            task_goal="test",
            symbol_count=1,
            evidence_confidence=0.01,  # < 0.25 → model.inference
        )
        result = await router.re_evaluate_routing("t2", prev, recon)
        # model.inference + OOD → escalate from fast to reasoning
        assert result.role == "reasoning"
        assert classify_inference(recon) == InferenceClassification.MODEL_INFERENCE

    async def test_inv3_empty_recon_yields_model_inference(self):
        """Empty recon → classify_inference returns MODEL_INFERENCE."""
        recon = ReconnaissanceResult(task_goal="x")
        assert recon.is_empty()
        assert classify_inference(recon) == InferenceClassification.MODEL_INFERENCE

    async def test_inv4_returns_same_selection_when_no_change_needed(self):
        """When LOCAL_COMPUTE but no local model supports the role, keeps prev."""
        router = ModelRouter()
        router.registry.clear()
        router.registry.register(_make_manifest(
            "cloud-1", provider="mock_cloud", roles=["reasoning"]
        ))
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud", roles=["reasoning"]),
            role="reasoning",
            reason="initial",
            score=0.9,
        )
        recon = ReconnaissanceResult(
            task_goal="test",
            symbol_count=10,
            evidence_confidence=0.8,
            privacy_class=__import__(
                "paw.core.privacy", fromlist=["PrivacyClass"],
            ).PrivacyClass.INTERNAL,
        )
        result = await router.re_evaluate_routing("t4", prev, recon)
        # No local model supports "reasoning" → downgrade not possible
        assert result.model_name == "cloud-1"


# --- 2. Runtime ---------------------------------------------------
class TestRuntimeReEvaluation:
    """Layer 2: PawRuntime re-evaluates routing after reconnaissance."""

    async def test_rt1_runtime_has_gather_reconnaissance(self):
        """Invariant: PawRuntime has _gather_reconnaissance method."""
        from paw.core.runtime import PawRuntime
        assert hasattr(PawRuntime, "_gather_reconnaissance")

    async def test_rt2_runtime_passes_recon_to_route(self):
        """Invariant: _execute_action passes reconnaissance to route()."""
        import inspect
        from paw.core.runtime import PawRuntime
        src = inspect.getsource(PawRuntime._execute_action)
        assert "reconnaissance=" in src
        assert "re_evaluate_routing" in src

    async def test_rt3_runtime_re_evaluates_after_routing(self):
        """Runtime: re_evaluate_routing is called after initial route()."""
        import inspect
        from paw.core.runtime import PawRuntime
        src = inspect.getsource(PawRuntime._execute_action)
        # The re-evaluation call must come after route()
        route_pos = src.index("route(")
        reeval_pos = src.index("re_evaluate_routing")
        assert reeval_pos > route_pos

    async def test_rt4_reevaluate_method_exists(self):
        """Invariant: ModelRouter has re_evaluate_routing method."""
        assert hasattr(ModelRouter, "re_evaluate_routing")


# --- 3. Adversarial -----------------------------------------------
class TestAdversarialReEvaluation:
    """Layer 3: malformed/edge-case recon doesn't cause wrong routing."""

    async def test_adv1_secret_recon_does_not_downgrade(self):
        """SECRET-class recon must not downgrade to local (privacy safety)."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        from paw.core.privacy import PrivacyClass
        recon = ReconnaissanceResult(
            task_goal="handle secret credentials",
            symbol_count=10,
            evidence_confidence=0.8,  # high confidence
            privacy_class=PrivacyClass.SECRET,  # but SECRET
        )
        result = await router.re_evaluate_routing("t_adv1", prev, recon)
        # SECRET → should NOT downgrade to local
        assert result.model_name != "local-echo"

    async def test_adv2_nan_confidence_does_not_downgrade(self):
        """NaN confidence is rejected by ReconnaissanceResult (E2-08)."""
        from paw.core.privacy import PrivacyClass
        with pytest.raises(ValueError):
            ReconnaissanceResult(evidence_confidence=float("nan"))

    async def test_adv3_stale_recon_keeps_prev(self):
        """Reconnaissance with zero evidence keeps previous selection."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        recon = ReconnaissanceResult(
            task_goal="unknown task",
            symbol_count=0,
            evidence_confidence=0.0,
        )
        # Completely empty recon → is_empty() → keep previous selection
        result = await router.re_evaluate_routing("t_adv3", prev, recon)
        assert result.model_name == "cloud-1"

    async def test_adv4_preferred_provider_not_downgraded(self):
        """When a recon downgrades, the fallback chain preserves the prev model."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        from paw.core.privacy import PrivacyClass
        recon = ReconnaissanceResult(
            task_goal="test",
            symbol_count=10,
            evidence_confidence=0.5,
            privacy_class=PrivacyClass.INTERNAL,
        )
        result = await router.re_evaluate_routing("t_adv4", prev, recon)
        # The fallback chain should include the previous model
        assert "cloud-1" in result.fallback_chain


# --- 4. Measurable ------------------------------------------------
class TestMeasurableReEvaluation:
    """Layer 4: re-evaluation produces measurable changes in selection."""

    async def test_meas1_downgrade_changes_selection(self):
        """Measurable: LOCAL_COMPUTE recon changes model from cloud to local."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial prompt only",
            score=0.9,
        )
        from paw.core.privacy import PrivacyClass
        recon = ReconnaissanceResult(
            task_goal="fix the echo skill",
            symbol_count=42,
            recent_change_count=3,
            test_association_count=5,
            knowledge_source_count=2,
            evidence_confidence=0.8,
            privacy_class=PrivacyClass.INTERNAL,
        )
        result = await router.re_evaluate_routing("t_meas1", prev, recon)
        assert result.model_name == "local-echo"
        assert result.score != prev.score
        assert classify_inference(recon) == InferenceClassification.LOCAL_COMPUTE

    async def test_meas2_initial_vs_reevaluated_selections_differ(self):
        """Measurable: route() initial selection vs re_evaluate differ."""
        router = _make_router_with_models()
        # Initial route (no recon)
        initial = await router.route(
            "t_meas2", "fix echo skill", role="fast",
        )
        from paw.core.privacy import PrivacyClass
        recon = ReconnaissanceResult(
            task_goal="fix echo skill",
            symbol_count=42,
            recent_change_count=3,
            test_association_count=5,
            knowledge_source_count=2,
            evidence_confidence=0.8,
            privacy_class=PrivacyClass.INTERNAL,
        )
        reevaluated = await router.re_evaluate_routing("t_meas2", initial, recon)
        # Initial picks cloud (non-local preferred), re-evaluated picks local
        assert initial.model_manifest.provider == "mock_cloud"
        assert reevaluated.model_manifest.provider == "local"

    async def test_meas3_nonempty_low_confidence_escalates(self):
        """Measurable: non-empty recon with low confidence → escalate role."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        # Non-empty (symbols=1) but very low confidence → model.inference + OOD
        recon = ReconnaissanceResult(
            task_goal="unknown task",
            symbol_count=1,
            evidence_confidence=0.01,  # < 0.25 threshold
        )
        result = await router.re_evaluate_routing("t_meas3", prev, recon)
        # Non-empty recon → model.inference → escalate role (fast->reasoning)
        assert result.role == "reasoning"
        assert classify_inference(recon) == InferenceClassification.MODEL_INFERENCE

    async def test_meas4_reevaluation_idempotent(self):
        """Measurable: calling re_evaluate_routing with same recon is stable."""
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        from paw.core.privacy import PrivacyClass
        recon = ReconnaissanceResult(
            task_goal="test",
            symbol_count=10,
            evidence_confidence=0.5,
            privacy_class=PrivacyClass.INTERNAL,
        )
        first = await router.re_evaluate_routing("t_meas4", prev, recon)
        # Re-evaluate the already-downgraded selection with same recon
        second = await router.re_evaluate_routing("t_meas4", first, recon)
        assert second.model_name == first.model_name
        assert second.model_manifest.provider == "local"

    async def test_meas5_persistence_of_reselection(self):
        """Measurable: re-evaluated selection is persisted to provider registry."""
        from paw.core.storage import db
        router = _make_router_with_models()
        prev = ModelSelection(
            model_name="cloud-1",
            model_manifest=_make_manifest("cloud-1", provider="mock_cloud"),
            role="fast",
            reason="initial",
            score=0.9,
        )
        from paw.core.privacy import PrivacyClass
        recon = ReconnaissanceResult(
            task_goal="test",
            symbol_count=10,
            evidence_confidence=0.5,
            privacy_class=PrivacyClass.INTERNAL,
        )
        result = await router.re_evaluate_routing("t_meas5", prev, recon)
        # Check persisted selection
        history = await router.get_routing_history("t_meas5")
        assert len(history) >= 1
        last = history[-1]
        assert last["model_name"] == result.model_name
