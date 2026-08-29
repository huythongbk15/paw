"""
PAW Phase 15 — Model Router v2 (providers)

Upgrades the ModelRouter from "score-only, blind to provider health" to
"provider-aware, health-checked, fallback-safe".

Key behaviors verified:
  * ``ModelProvider`` Protocol is @runtime_checkable and includes
    ``available`` + ``discover_manifests``.
  * ``ProviderRegistry`` aggregates providers and discovers only the models
    of *available* providers (graceful degradation, zero vendor lock-in).
  * ``ModelRouter.route`` excludes models whose provider is unavailable and
    falls back to ``local`` models when nothing else is reachable.
  * The fallback chain contains only reachable providers.
  * Preferred models from a down provider are skipped.
  * Backward compatibility: a router with no providers routes exactly as before.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from paw.core.model_executor import LocalModelExecutor
from paw.core.model_router import (
    ModelRegistry,
    ModelRouter,
    ModelScorer,
    ProviderRegistry,
)
from paw.core.models import ModelCapability, ModelManifest, ModelSelection
from paw.providers import ModelProvider
from paw.providers.ollama.provider import OllamaProvider


# --- Mock provider (fully conforms to ModelProvider) ---


class _MockProvider:
    """A minimal but complete ModelProvider for tests."""

    def __init__(self, name: str, available: bool = True, models: list[ModelManifest] | None = None):
        self.name = name
        self.version = "9.9.9"
        self._available = available
        self._models = models or []
        self.initialized = False

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def list_models(self) -> list[dict[str, Any]]:
        return [{"name": m.name} for m in self._models]

    async def get_model(self, name: str) -> dict[str, Any] | None:
        for m in self._models:
            if m.name == name:
                return {"name": m.name}
        return None

    async def discover_manifests(self) -> list[ModelManifest]:
        return list(self._models)

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"response": "ok", "model": request.get("model")}

    async def stream(self, request: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        yield {"response": "ok", "model": request.get("model")}


def _mock_llama_manifest() -> ModelManifest:
    return ModelManifest(
        name="mock-llama",
        provider="mockp",
        roles=["fast", "tools"],
        model_capabilities={
            ModelCapability.TOOL_CALLING.value: 9.0,
            ModelCapability.STRUCTURED_OUTPUT.value: 9.0,
        },
        cost={"compute": "low", "monetary": "free"},
        features={"resumable": True, "streaming": True},
        max_context_tokens=32000,
        latency_tier="low",
        enabled=True,
    )


async def _noop_persist(*_a, **_k):  # type: ignore[no-untyped-def]
    return None


# --- Protocol conformance ---


def test_ollama_conforms_to_model_provider_protocol():
    # OllamaProvider implements discovery + execution + availability.
    assert isinstance(OllamaProvider(), ModelProvider)


def test_local_executor_is_not_a_model_provider():
    # LocalModelExecutor is an execution fallback, not a discovering provider.
    assert not isinstance(LocalModelExecutor(), ModelProvider)


def test_mock_provider_conforms():
    assert isinstance(_MockProvider("p"), ModelProvider)


# --- ProviderRegistry ---


async def test_provider_registry_discovers_available_only():
    up = _MockProvider("up", available=True, models=[_mock_llama_manifest()])
    down = _MockProvider(
        "down",
        available=False,
        models=[ModelManifest(name="should-not-appear", provider="down", roles=["fast"])],
    )
    pr = ProviderRegistry()
    pr.register(up)
    pr.register(down)

    await pr.initialize_all()
    assert up.initialized and down.initialized

    registry = ModelRegistry()
    count = await pr.discover_models(registry)

    # Only the available provider's models are discovered
    assert count == 1
    names = {m.name for m in registry.list()}
    assert "mock-llama" in names
    assert "should-not-appear" not in names


# --- Provider-aware routing ---


async def test_router_excludes_unavailable_provider():
    registry = ModelRegistry()
    registry.register_defaults()  # local-fast, local-reasoning, local-embedding
    registry.register(
        ModelManifest(name="cloud-x", provider="cloud", roles=["fast"], enabled=True)
    )

    down = _MockProvider("cloud", available=False)
    router = ModelRouter(registry, providers=[down])
    router.persist_selection = _noop_persist  # avoid DB in unit test

    sel = await router.route("t1", "goal", role="fast")
    assert isinstance(sel, ModelSelection)
    # Unavailable provider excluded -> local model selected
    assert sel.model_name == "local-fast"
    assert "cloud-x" not in sel.fallback_chain
    assert sel.fallback_chain == ["local-fast"]


async def test_router_selects_available_provider_model():
    # No explicit registry -> router registers defaults AND discovers the
    # provider's models automatically.
    mock = _MockProvider("mockp", available=True, models=[_mock_llama_manifest()])
    router = ModelRouter(providers=[mock])
    router.persist_selection = _noop_persist

    sel = await router.route("t2", "goal", role="fast")
    # mock-llama scores above local-fast and its provider is available
    assert sel.model_name == "mock-llama"
    assert "mock-llama" in sel.fallback_chain
    # local fallback still present in chain
    assert "local-fast" in sel.fallback_chain


async def test_router_falls_back_to_local_when_only_provider_down():
    # Custom registry with ONLY a provider model, no local models.
    registry = ModelRegistry()
    registry.register(
        ModelManifest(name="cloud-only", provider="cloud", roles=["fast"], enabled=True)
    )
    down = _MockProvider("cloud", available=False)
    # custom registry -> register_defaults() NOT called -> no local fallback
    router = ModelRouter(registry, providers=[down])
    router.persist_selection = _noop_persist

    sel = await router.route("t3", "goal", role="fast")
    # Nothing reachable -> empty selection
    assert sel.model_name == ""
    assert "No model available" in sel.reason


async def test_router_preferred_model_skips_unavailable_provider():
    from paw.core.execution_profile import ExecutionProfile

    registry = ModelRegistry()
    registry.register_defaults()
    registry.register(
        ModelManifest(name="cloud-pref", provider="cloud", roles=["fast"], enabled=True)
    )
    down = _MockProvider("cloud", available=False)
    router = ModelRouter(registry, providers=[down])
    router.persist_selection = _noop_persist

    prof = ExecutionProfile(name="p", preferred_models=["cloud-pref"])
    sel = await router.route("t4", "goal", role="fast", execution_profile=prof)
    # Preferred provider is down -> skipped -> falls back to local
    assert sel.model_name == "local-fast"
    assert "cloud-pref" not in sel.fallback_chain


async def test_router_backward_compat_no_providers():
    # No providers passed -> behaves exactly like the Phase 4 router.
    router = ModelRouter()
    router.persist_selection = _noop_persist
    sel = await router.route("t5", "goal", role="fast")
    assert sel.model_name == "local-fast"
    assert sel.fallback_chain == ["local-fast"]


async def test_route_with_explain_excludes_unavailable():
    registry = ModelRegistry()
    registry.register_defaults()
    registry.register(
        ModelManifest(name="cloud-x", provider="cloud", roles=["fast"], enabled=True)
    )
    down = _MockProvider("cloud", available=False)
    router = ModelRouter(registry, providers=[down])
    router.persist_selection = _noop_persist

    sel, scores = await router.route_with_explain("t6", "goal", role="fast")
    assert sel.model_name == "local-fast"
    # Scores returned explainably and exclude the down provider
    assert scores
    assert all(s.model_name != "cloud-x" for s in scores)


def test_scorer_is_accessible():
    # Latent bug guard: route() uses ``self.scorer``.
    router = ModelRouter()
    assert isinstance(router.scorer, ModelScorer)
