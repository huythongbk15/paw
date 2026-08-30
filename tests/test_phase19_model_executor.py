"""
PAW Phase 19 — #6 Model Executor hardening.

Proves:
  * ModelExecutor and ModelRouter share the SAME ProviderRegistry instance.
  * The executor dispatches to the provider the router selected, and the
    full ``messages`` list reaches that provider's ``complete``/``stream``.
  * Unknown providers fall back to the in-process LocalModelExecutor.
"""

from __future__ import annotations

from typing import Any

import pytest

from paw.core.model_executor import LocalModelExecutor, ModelExecutor
from paw.core.model_router import ModelRegistry, ModelRouter, ProviderRegistry
from paw.core.models import ModelManifest, ModelSelection
from paw.providers import ModelProvider


class RecordingProvider:
    """Conforms to ModelProvider; records every call + request payload."""

    name = "rec"
    version = "1.0.0"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def list_models(self) -> list[dict[str, Any]]:
        return []

    async def get_model(self, name: str) -> dict[str, Any] | None:
        return None

    async def discover_manifests(self) -> list[ModelManifest]:
        return []

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(request)
        return {"model": request["model"], "response": "rec-out", "echo": request.get("messages")}

    async def stream(self, request: dict[str, Any]):
        self.calls.append(request)
        yield {"model": request["model"], "response": "rec-out"}


def _selection(provider: str = "rec", name: str = "rec-model") -> ModelSelection:
    manifest = ModelManifest(name=name, provider=provider, roles=["fast"])
    return ModelSelection(
        model_name=name,
        model_manifest=manifest,
        role="fast",
        reason="",
        fallback_chain=[],
        score=0.0,
    )


@pytest.mark.asyncio
async def test_executor_and_router_share_one_provider_registry():
    registry = ProviderRegistry()
    router = ModelRouter(providers=registry)
    executor = ModelExecutor(provider_registry=registry)
    # The SAME instance is used by both — no duplicate registries.
    assert router._provider_registry is registry
    assert executor.provider_registry is registry
    assert router._provider_registry is executor.provider_registry


@pytest.mark.asyncio
async def test_executor_calls_selected_provider_with_messages():
    registry = ProviderRegistry()
    rec = RecordingProvider()
    registry.register(rec)
    executor = ModelExecutor(provider_registry=registry)

    messages = [
        {"role": "system", "content": "be concise"},
        {"role": "user", "content": "explain recursion"},
    ]
    result = await executor.complete(_selection(), messages)

    # Provider was actually invoked, with the exact messages + model name.
    assert len(rec.calls) == 1
    req = rec.calls[0]
    assert req["model"] == "rec-model"
    assert req["messages"] == messages
    assert result["response"] == "rec-out"
    assert result["echo"] == messages


@pytest.mark.asyncio
async def test_executor_stream_dispatches_to_selected_provider():
    registry = ProviderRegistry()
    rec = RecordingProvider()
    registry.register(rec)
    executor = ModelExecutor(provider_registry=registry)

    messages = [{"role": "user", "content": "hi"}]
    chunks = [c async for c in executor.stream(_selection(), messages)]

    assert len(rec.calls) == 1
    assert rec.calls[0]["messages"] == messages
    assert chunks[0]["model"] == "rec-model"


@pytest.mark.asyncio
async def test_executor_falls_back_to_local_when_provider_absent():
    # Empty registry: provider "openrouter" is not registered.
    executor = ModelExecutor(provider_registry=ProviderRegistry())
    result = await executor.complete(
        _selection(provider="openrouter", name="gpt-x"),
        [{"role": "user", "content": "hi"}],
    )
    assert "local-standin" in result["response"]


@pytest.mark.asyncio
async def test_local_fallback_echoes_last_user_message():
    fb = LocalModelExecutor()
    out = await fb.complete(
        {
            "model": "local-fast",
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "real question"},
                {"role": "assistant", "content": "prior"},
                {"role": "user", "content": "follow-up"},
            ],
        }
    )
    assert "follow-up" in out["response"]


@pytest.mark.asyncio
async def test_router_discovers_models_executor_uses_same_provider():
    """End-to-end: a provider discovered by the router's registry is the
    exact instance the executor dispatches to (no registry duplication)."""
    registry = ProviderRegistry()
    rec = RecordingProvider()
    registry.register(rec)
    # Discover a model named "rec-model" into a dedicated (non-default) registry.
    async def _fake_discover():
        return [ModelManifest(name="rec-model", provider="rec", roles=["fast"])]
    rec.discover_manifests = _fake_discover  # type: ignore[assignment]
    model_registry = ModelRegistry()
    added = await registry.discover_models(model_registry)
    assert added == 1
    assert model_registry.get("rec-model").provider == "rec"

    # Route from the SAME (non-default) registry so only rec-model is a candidate
    router = ModelRouter(registry=model_registry, providers=registry)
    selection = await router.route("t1", "goal", role="fast")
    assert selection.model_name == "rec-model"
    assert selection.model_manifest.provider == "rec"

    executor = ModelExecutor(provider_registry=registry)
    result = await executor.complete(
        selection, [{"role": "user", "content": "via router"}]
    )
    assert len(rec.calls) == 1
    assert rec.calls[0]["messages"] == [{"role": "user", "content": "via router"}]
