"""
PAW Core — Model Executor (Phase 11)

Executes a ``ModelSelection`` produced by the ``ModelRouter`` by dispatching
to the correct ``ModelProvider``. Providers are registered by name so the
core never depends on any concrete provider implementation.

Local-first, zero vendor lock-in: providers are pluggable. The default
``local`` provider resolves to an in-process echo/placeholder executor for
offline operation; ``ollama`` resolves to the Ollama server when available.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from .logging import get_logger
from .models import ModelSelection

logger = get_logger(__name__)


class LocalModelExecutor:
    """Fallback executor for ``provider="local"`` models.

    The PAW core does not bundle an LLM; this executor is a deterministic
    offline stand-in so the runtime loop can complete without an external
    model server. Real local inference can be wired in later via a provider.
    """

    name = "local"
    version = "1.0.0"

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        model = request.get("model", "local")
        prompt = request.get("prompt", "")
        return {
            "model": model,
            "response": f"[local-standin] {prompt[:200]}",
            "done": True,
        }

    async def stream(self, request: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        result = await self.complete(request)
        yield result


class ModelExecutor:
    """Dispatches model execution to registered providers."""

    def __init__(self):
        self._providers: dict[str, Any] = {}
        self._default_provider = "local"
        self.register(LocalModelExecutor())

    def register(self, provider: Any) -> None:
        """Register a provider instance by its ``name`` attribute."""
        self._providers[provider.name] = provider
        logger.info("model_provider_registered", name=provider.name)

    def get_provider(self, name: str) -> Any | None:
        return self._providers.get(name)

    async def initialize_all(self) -> None:
        for provider in self._providers.values():
            try:
                if hasattr(provider, "initialize"):
                    await provider.initialize()
            except Exception as exc:
                logger.warning("provider_init_failed", name=provider.name, error=str(exc))

    async def shutdown_all(self) -> None:
        for provider in self._providers.values():
            try:
                if hasattr(provider, "shutdown"):
                    await provider.shutdown()
            except Exception as exc:
                logger.warning("provider_shutdown_failed", name=provider.name, error=str(exc))

    def _resolve_provider(self, selection: ModelSelection) -> Any:
        provider_name = ""
        if selection.model_manifest is not None:
            provider_name = selection.model_manifest.provider
        provider = self._providers.get(provider_name)
        if provider is None:
            logger.warning(
                "provider_not_registered",
                requested=provider_name,
                fallback=self._default_provider,
            )
            provider = self._providers.get(self._default_provider)
        return provider

    async def complete(
        self, selection: ModelSelection, prompt: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute a completion for the selected model."""
        provider = self._resolve_provider(selection)
        if provider is None:
            return {"error": "no model provider available", "response": ""}
        request = {"model": selection.model_name, "prompt": prompt, **kwargs}
        return await provider.complete(request)

    async def stream(
        self, selection: ModelSelection, prompt: str, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a completion for the selected model."""
        provider = self._resolve_provider(selection)
        if provider is None:
            yield {"error": "no model provider available"}
            return
        request = {"model": selection.model_name, "prompt": prompt, **kwargs}
        async for chunk in provider.stream(request):
            yield chunk
