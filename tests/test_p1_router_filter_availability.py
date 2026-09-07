"""P1 Router repair — ModelRouter._filter_for_availability contract tests.

The handoff spec (docs/EXECUTION_CHECKLIST.md, "Agent handoff" section)
asks to restore:

1. **Supported-role filtering**: the function must re-verify that every
   returned candidate supports the requested ``role``. A model whose
   ``role in m.roles`` is False must NOT appear in the result, even if
   the upstream ``find_best_for_task`` somehow leaked it.
2. **Descending score**: the local-fallback branch must re-score local
   models using the canonical entry point and sort them by score
   descending. Iterating ``list_enabled()`` in dict-insertion order is
   not an acceptable ordering.
3. **Wrong role** is filtered out.
4. **Reverse registration order** does not change the result order
   (score order wins).
5. **No eligible local** returns ``[]``, not all locals.
6. **Remote unavailable** falls back to local, in score order.
7. **Local-only with all roles** works.
8. **No provider/discovery expansion** (no new branches; only the
   existing ``_filter_for_availability`` is corrected).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paw.core.model_router import ModelManifest, ModelRouter
from paw.core.models import Capability
from paw.core.execution_profile import ExecutionProfile, PrivacyPreference


# --- Helpers ----------------------------------------------------------------


def _manifest(
    name: str,
    provider: str,
    roles: list[str],
    *,
    cost: str = "low",
    latency: str = "low",
    capabilities: dict[str, float] | None = None,
    local_only: bool = False,
    enabled: bool = True,
) -> ModelManifest:
    """Build a ModelManifest for testing.

    ``local_only=True`` marks the model as local (provider "local" is the
    default for offline stand-in models).
    """
    return ModelManifest(
        name=name,
        provider=provider,
        roles=roles,
        model_capabilities=capabilities or {"tool_calling": 7.0},
        cost={"compute": cost, "monetary": "free"},
        features={"resumable": True, "streaming": True},
        max_context_tokens=8000,
        latency_tier=latency,
        enabled=enabled,
    )


def _unavailable_provider(name: str) -> Any:
    """A provider that reports ``available = False``."""
    provider = MagicMock()
    provider.name = name
    provider.provider = name
    provider.available = False
    return provider


def _available_provider(name: str) -> Any:
    """A provider that reports ``available = True``."""
    provider = MagicMock()
    provider.name = name
    provider.provider = name
    provider.available = True
    return provider


# --- Test: supported-role filtering ----------------------------------------


class TestFilterForAvailabilityRoleFiltering:
    """The local-fallback branch must filter by ``role`` support."""

    def test_local_fallback_excludes_models_with_wrong_role(self):
        """A local model whose ``roles`` does NOT contain the requested
        role must be excluded from the local fallback result."""
        router = ModelRouter()
        # Local-1 supports the role "fast"; local-2 only supports "tools".
        router.registry.register(_manifest("local-fast", "local", ["fast"]))
        router.registry.register(_manifest("local-tools-only", "local", ["tools"]))
        # No remote providers are available
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_unavailable_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=[],
                    role="fast",
                    context_size=0,
                    complexity="medium",
                    privacy_required=False,
                    prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        names = [m.name for (m, _s) in result]
        assert "local-fast" in names
        assert "local-tools-only" not in names, (
            "local-fallback leaked a model that does not support role 'fast'"
        )

    def test_local_fallback_excludes_disabled_models(self):
        """A local model with ``enabled=False`` must be excluded."""
        router = ModelRouter()
        router.registry.register(_manifest("local-fast", "local", ["fast"]))
        router.registry.register(
            _manifest("local-fast-disabled", "local", ["fast"], enabled=False)
        )
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_unavailable_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=[], role="fast", context_size=0,
                    complexity="medium", privacy_required=False, prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        names = [m.name for (m, _s) in result]
        assert "local-fast" in names
        assert "local-fast-disabled" not in names


# --- Test: descending score order -----------------------------------------


class TestFilterForAvailabilityScoreOrder:
    """The local-fallback branch must sort by score desc."""

    def test_local_fallback_returns_higher_score_first(self):
        """When two local models support the same role, the one with the
        higher score must come first (NOT the one registered first)."""
        router = ModelRouter()
        # Register in REVERSE of intended score order. "local-fast-cheap"
        # has a high score for "fast"; "local-fast-expensive" has a low
        # score. Registration order: cheap-second, expensive-first.
        router.registry.register(
            _manifest("local-fast-expensive", "local", ["fast"], cost="high", latency="high")
        )
        router.registry.register(
            _manifest("local-fast-cheap", "local", ["fast"], cost="low", latency="low")
        )
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_unavailable_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=[], role="fast", context_size=0,
                    complexity="medium", privacy_required=False, prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        names = [m.name for (m, _s) in result]
        assert names[0] == "local-fast-cheap", (
            f"local-fallback returned {names[0]} first; expected the higher-score "
            f"'local-fast-cheap' to win regardless of registration order"
        )
        # And the score must be descending
        scores = [s.score for (_m, s) in result]
        assert scores == sorted(scores, reverse=True), (
            f"local-fallback scores {scores} are not descending"
        )

    def test_local_fallback_score_order_matches_canonical_scorer(self):
        """The local-fallback scores must equal the scores from
        ``ModelScorer.score_model_for_task`` (the canonical entry point)."""
        router = ModelRouter()
        router.registry.register(_manifest("local-fast", "local", ["fast"]))
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_unavailable_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=[], role="fast", context_size=0,
                    complexity="medium", privacy_required=False, prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        manifest = next(m for (m, _s) in result if m.name == "local-fast")
        # Compute the canonical score via the scorer
        canonical = router.scorer.score_model_for_task(
            manifest, role="fast", context_size=0,
            complexity="medium", privacy_required=False, prefer_cheap=True,
        )
        actual = next(s for (m, s) in result if m.name == "local-fast")
        assert actual.score == canonical.score
        assert actual.reason == canonical.reason


# --- Test: no eligible local -------------------------------------------------


class TestFilterForAvailabilityNoEligibleLocal:
    """When no local model supports the role, return ``[]``."""

    def test_local_fallback_returns_empty_when_no_role_match(self):
        router = ModelRouter()
        # No local-fast model; only local-tools.
        router.registry.register(_manifest("local-tools", "local", ["tools"]))
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_unavailable_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=[], role="fast", context_size=0,
                    complexity="medium", privacy_required=False, prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        assert result == [], (
            f"local-fallback returned {len(result)} models for role 'fast' but no "
            f"local model supports that role; expected []"
        )

    def test_local_fallback_returns_empty_when_no_local_models(self):
        router = ModelRouter()
        # Only remote models
        router.registry.register(
            _manifest("remote-fast", "remote", ["fast"])
        )
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_unavailable_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=[], role="fast", context_size=0,
                    complexity="medium", privacy_required=False, prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        assert result == []


# --- Test: remote unavailable falls back to local in score order ----------


class TestFilterForAvailabilityRemoteUnavailable:
    """When remote providers are unavailable, fall back to local in score order."""

    def test_unavailable_remote_falls_back_to_local(self):
        router = ModelRouter()
        router.registry.register(_manifest("local-fast", "local", ["fast"]))
        # Upstream passed a "remote-fast" model that is now unavailable.
        from paw.core.model_router import ModelScore
        remote = _manifest("remote-fast", "remote", ["fast"])
        remote_score = ModelScore(
            model_name="remote-fast", score=0.9, reason="",
            capability_fit=1.0, complexity_fit=1.0, privacy_fit=1.0,
            cost_fit=1.0, latency_fit=1.0,
        )
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_unavailable_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=[(remote, remote_score)], role="fast", context_size=0,
                    complexity="medium", privacy_required=False, prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        # The remote-fast is unavailable, so the result must come from local.
        assert all(m.provider == "local" for (m, _s) in result), (
            "remote provider is unavailable but remote-fast leaked through"
        )
        assert any(m.name == "local-fast" for (m, _s) in result)

    def test_available_remote_passes_through_unchanged(self):
        """When the upstream scored list contains a model from an available
        provider, that list passes through unchanged (already sorted by
        score desc)."""
        router = ModelRouter()
        from paw.core.model_router import ModelScore
        # Two remote models from the same available provider, in REVERSE
        # score order to prove the upstream sort is preserved.
        good = _manifest("remote-fast-good", "remote", ["fast"])
        good_score = ModelScore(
            model_name="remote-fast-good", score=0.9, reason="good",
            capability_fit=1.0, complexity_fit=1.0, privacy_fit=1.0,
            cost_fit=1.0, latency_fit=1.0,
        )
        okay = _manifest("remote-fast-okay", "remote", ["fast"])
        okay_score = ModelScore(
            model_name="remote-fast-okay", score=0.5, reason="okay",
            capability_fit=0.5, complexity_fit=0.5, privacy_fit=0.5,
            cost_fit=0.5, latency_fit=0.5,
        )
        # Upstream passed: [good, okay] in score order.
        upstream = [(good, good_score), (okay, okay_score)]
        # But the "remote" provider is available, so all of them pass.
        mock_registry = MagicMock()
        mock_registry.list.return_value = [_available_provider("remote")]
        mock_registry.initialize_all = AsyncMock()

        async def do_filter():
            with patch.object(router, "_provider_registry", mock_registry):
                return await router._filter_for_availability(
                    scored=upstream, role="fast", context_size=0,
                    complexity="medium", privacy_required=False, prefer_cheap=True,
                )

        result = asyncio.run(do_filter())
        names = [m.name for (m, _s) in result]
        # All upstream entries survive (because the provider is available)
        assert "remote-fast-good" in names
        assert "remote-fast-okay" in names
        # And the score order is preserved from upstream
        assert names[0] == "remote-fast-good"


# --- Test: no provider registry => pass through ----------------------------


class TestFilterForAvailabilityBackwardCompat:
    """When the router has no provider registry, behavior is unchanged."""

    def test_no_provider_registry_returns_input_unchanged(self):
        """Backward compatibility: a router with no provider registry
        returns the input scored list unchanged (this is the contract
        that the rest of the codebase relies on)."""
        router = ModelRouter()
        # No provider registry is set
        from paw.core.model_router import ModelScore
        m1 = _manifest("local-fast", "local", ["fast"])
        m2 = _manifest("local-reasoning", "local", ["reasoning"])
        scored = [
            (m1, ModelScore(model_name="local-fast", score=0.9, reason="",
                            capability_fit=1.0, complexity_fit=1.0, privacy_fit=1.0,
                            cost_fit=1.0, latency_fit=1.0)),
            (m2, ModelScore(model_name="local-reasoning", score=0.7, reason="",
                            capability_fit=0.7, complexity_fit=0.7, privacy_fit=0.7,
                            cost_fit=0.7, latency_fit=0.7)),
        ]
        # When _provider_registry is None, _available_provider_names returns None
        # and the function must return scored as-is.
        async def do_filter():
            assert router._provider_registry is None
            return await router._filter_for_availability(
                scored=scored, role="fast", context_size=0,
                complexity="medium", privacy_required=False, prefer_cheap=True,
            )

        result = asyncio.run(do_filter())
        assert result == scored
