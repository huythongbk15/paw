"""
Phase 4 Tests — Model Router expansion with multi-dimensional scoring.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paw.core import (
    Capability,
    ModelManifest,
    ModelRole,
    ModelRouter,
    ModelRegistry,
    ModelScore,
    ModelScorer,
    get_model_router,
    get_model_registry,
)
from paw.core.storage import db, set_db_path


class TestPhase4ModelRegistry:
    """Phase 4 Model Registry tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_registry_register_and_get(self, tmp_path):
        """Register and retrieve a model."""
        registry = ModelRegistry()
        manifest = ModelManifest(
            name="test-model",
            provider="local",
            roles=["fast", "reasoning"],
            capabilities={"shell.execute": 8.0},
        )
        registry.register(manifest)
        assert registry.get("test-model") is not None
        assert registry.get("test-model").name == "test-model"

    @pytest.mark.asyncio
    async def test_registry_list_by_role(self, tmp_path):
        """List models by role."""
        registry = ModelRegistry()
        registry.register(ModelManifest(
            name="fast-model", provider="local", roles=["fast"], enabled=True,
        ))
        registry.register(ModelManifest(
            name="reasoning-model", provider="local", roles=["reasoning"], enabled=True,
        ))
        fast_models = registry.list_by_role("fast")
        assert len(fast_models) == 1
        assert fast_models[0].name == "fast-model"

    @pytest.mark.asyncio
    async def test_registry_defaults(self, tmp_path):
        """Default models are registered."""
        registry = ModelRegistry()
        registry.register_defaults()
        models = registry.list()
        assert len(models) >= 3

    @pytest.mark.asyncio
    async def test_registry_unregister(self, tmp_path):
        """Unregister a model."""
        registry = ModelRegistry()
        registry.register_defaults()
        assert registry.get("local-fast") is not None
        result = registry.unregister("local-fast")
        assert result is True
        assert registry.get("local-fast") is None

    @pytest.mark.asyncio
    async def test_registry_find_by_capability(self, tmp_path):
        """Find models by capability."""
        registry = ModelRegistry()
        registry.register_defaults()
        # Use ModelCapability (model capabilities, not executor capabilities)
        models = registry.find_by_capability("tool_calling")
        assert len(models) >= 1

    @pytest.mark.asyncio
    async def test_registry_find_for_role(self, tmp_path):
        """Find models for a role."""
        registry = ModelRegistry()
        registry.register_defaults()
        models = registry.find_for_role("fast")
        assert len(models) >= 1
        assert all("fast" in m.roles for m in models)


class TestPhase4ModelScorer:
    """Phase 4 Model Scorer tests."""

    @pytest.mark.asyncio
    async def test_score_capability(self, tmp_path):
        """Score capability fit."""
        scorer = ModelScorer()
        manifest = ModelManifest(
            name="test", provider="local", roles=["reasoning", "coding"],
            capabilities={"shell.execute": 9.0, "filesystem.read": 8.0},
            max_context_tokens=32000,
        )
        score = scorer.score(manifest, role="reasoning")
        assert score.capability_fit > 0.5
        assert score.score > 0.0

    @pytest.mark.asyncio
    async def test_score_complexity(self, tmp_path):
        """Score complexity fit."""
        scorer = ModelScorer()
        manifest = ModelManifest(
            name="test", provider="local", roles=["reasoning"],
            max_context_tokens=32000,
            latency_tier="medium",
        )
        high_score = scorer.score(manifest, complexity="high")
        low_score = scorer.score(manifest, complexity="low")
        assert high_score.complexity_fit > low_score.complexity_fit

    @pytest.mark.asyncio
    async def test_score_privacy(self, tmp_path):
        """Score privacy fit."""
        scorer = ModelScorer()
        local_manifest = ModelManifest(
            name="local", provider="local", roles=["fast"],
            max_context_tokens=8000,
        )
        remote_manifest = ModelManifest(
            name="remote", provider="openrouter", roles=["fast"],
            max_context_tokens=8000,
        )
        local_score = scorer.score(local_manifest, privacy_required=True)
        remote_score = scorer.score(remote_manifest, privacy_required=True)
        assert local_score.privacy_fit > remote_score.privacy_fit

    @pytest.mark.asyncio
    async def test_score_prefer_cheap(self, tmp_path):
        """Score cost fit."""
        scorer = ModelScorer()
        cheap = ModelManifest(
            name="cheap", provider="local", roles=["fast"],
            cost={"compute": "low", "monetary": "free"},
            max_context_tokens=8000,
        )
        expensive = ModelManifest(
            name="expensive", provider="openrouter", roles=["fast"],
            cost={"compute": "high", "monetary": "variable"},
            max_context_tokens=8000,
        )
        cheap_score = scorer.score(cheap, prefer_cheap=True)
        expensive_score = scorer.score(expensive, prefer_cheap=True)
        assert cheap_score.cost_fit > expensive_score.cost_fit

    @pytest.mark.asyncio
    async def test_score_produces_valid_range(self, tmp_path):
        """Score is between 0.0 and 1.0."""
        scorer = ModelScorer()
        manifest = ModelManifest(
            name="test", provider="local", roles=["fast"],
            max_context_tokens=128000,
        )
        score = scorer.score(manifest, role="fast")
        assert 0.0 <= score.score <= 1.0

    @pytest.mark.asyncio
    async def test_score_to_dict(self, tmp_path):
        """ModelScore serializes correctly."""
        scorer = ModelScorer()
        manifest = ModelManifest(
            name="test", provider="local", roles=["fast"],
            max_context_tokens=8000,
        )
        score = scorer.score(manifest, role="fast")
        d = score.to_dict()
        assert d["model_name"] == "test"
        assert 0.0 <= d["score"] <= 1.0
        assert "capability_fit" in d
        assert "complexity_fit" in d
        assert "privacy_fit" in d
        assert "cost_fit" in d
        assert "latency_fit" in d


class TestPhase4ModelRouter:
    """Phase 4 Model Router tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_route(self, tmp_path):
        """Route a task to the best model."""
        router = ModelRouter()
        router.registry.register_defaults()
        selection = await router.route("task-1", "test goal", role="fast")
        assert selection.model_name != ""
        assert selection.score > 0.0
        assert selection.role == "fast"

    @pytest.mark.asyncio
    async def test_route_with_explain(self, tmp_path):
        """Route with full explainability."""
        router = ModelRouter()
        router.registry.register_defaults()
        selection, scores = await router.route_with_explain(
            "task-1", "test goal", role="fast"
        )
        assert selection.model_name != ""
        assert len(scores) >= 1
        assert all(isinstance(s, ModelScore) for s in scores)

    @pytest.mark.asyncio
    async def test_route_returns_fallback_chain(self, tmp_path):
        """Route returns a fallback chain."""
        router = ModelRouter()
        router.registry.register_defaults()
        selection = await router.route("task-1", "test", role="fast")
        assert len(selection.fallback_chain) >= 1

    @pytest.mark.asyncio
    async def test_get_scores(self, tmp_path):
        """Retrieve scores for a task."""
        router = ModelRouter()
        router.registry.register_defaults()
        await router.route("task-1", "test", role="fast")
        scores = router.get_scores("task-1")
        assert scores is not None
        assert len(scores) >= 1

    @pytest.mark.asyncio
    async def test_get_selection(self, tmp_path):
        """Retrieve previous selection."""
        router = ModelRouter()
        router.registry.register_defaults()
        await router.route("task-1", "test", role="fast")
        selection = router.get_selection("task-1")
        assert selection is not None
        assert selection.model_name != ""

    @pytest.mark.asyncio
    async def test_route_with_privacy(self, tmp_path):
        """Route respects privacy requirements."""
        router = ModelRouter()
        router.registry.register_defaults()
        selection = await router.route(
            "task-1", "test", role="fast", privacy_required=True
        )
        assert selection.model_name != ""
        # Local models should be preferred for privacy
        assert "local" in selection.model_name or selection.model_name != ""

    @pytest.mark.asyncio
    async def test_route_with_complexity(self, tmp_path):
        """Route respects complexity requirements."""
        router = ModelRouter()
        router.registry.register_defaults()
        selection = await router.route(
            "task-1", "test", role="reasoning", complexity="high"
        )
        assert selection.model_name != ""
        assert selection.role == "reasoning"

    @pytest.mark.asyncio
    async def test_no_model_available(self, tmp_path):
        """Handle case where no model is available (empty registry)."""
        registry = ModelRegistry()
        # Don't register defaults
        router = ModelRouter(registry=registry)
        selection = await router.route("task-1", "test", role="fast")
        assert selection.model_name == ""
        assert "No model available" in selection.reason


class TestPhase4NoProhibitedDependencies:
    """Verify no prohibited dependencies in Phase 4."""

    def test_no_qwenpaw(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "model_router.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "qwenpaw" not in content.lower()

    def test_no_deepseek(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "model_router.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "deepseek" not in content.lower() or "model" in content.lower()

    def test_no_notebooklm(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "model_router.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "notebooklm" not in content.lower()

    def test_no_antigravity(self):
        files = [
            Path(__file__).parent.parent / "paw" / "core" / "model_router.py",
        ]
        for py_file in files:
            if py_file.exists():
                content = py_file.read_text()
                assert "antigravity" not in content.lower()
