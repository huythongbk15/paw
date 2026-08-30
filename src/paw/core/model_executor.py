"""
PAW Core — Model Executor (Phase 11, hardened in Phase 19)

Executes a ``ModelSelection`` produced by the ``ModelRouter`` by dispatching
to the correct ``ModelProvider``.

Phase 19 hardening (#6):
  * The executor MUST use the SAME ``ProviderRegistry`` instance as the
    ``ModelRouter``. It no longer keeps a duplicate ``_providers`` dict.
  * Execution receives the full ``messages`` list (not just a flat prompt)
    and forwards it to the selected provider's ``complete``/``stream``.

Local-first, zero vendor lock-in: providers are pluggable. The ``local``
provider resolves to an in-process echo/placeholder executor for offline
operation; real providers (e.g. Ollama) are plugged in as ``ModelProvider``
instances and discovered by the shared registry.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from .logging import get_logger
from .model_router import ProviderRegistry
from .models import ModelSelection

logger = get_logger(__name__)


class LocalModelExecutor:
    """Offline stand-in for ``provider="local"`` models.

    The PAW core does not bundle an LLM; this executor is a deterministic
    offline placeholder so the runtime loop can complete without an external
    model server. It is deliberately NOT a ``ModelProvider`` (it performs no
    model discovery) and is kept OUTSIDE the shared ``ProviderRegistry`` — it
    is the executor's fallback backend only.
    """

    name = "local"
    version = "1.0.0"

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        model = request.get("model", "local")
        messages = request.get("messages") or []
        # Echo the last user turn (deterministic, offline-verifiable output)
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        prompt = request.get("prompt", last_user)
        return {
            "model": model,
            "response": f"[local-standin] {prompt[:200]}",
            "done": True,
        }

    async def stream(self, request: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        result = await self.complete(request)
        yield result


class ModelExecutor:
    """Dispatches model execution to providers in the shared registry.

    The executor holds a reference to a ``ProviderRegistry`` (the same one the
    ``ModelRouter`` uses) so the provider instance that was routed is exactly
    the one that gets executed. ``provider="local"`` selections fall back to an
    in-process ``LocalModelExecutor`` that is NOT part of the registry.
    """

    def __init__(
        self,
        provider_registry: ProviderRegistry | None = None,
        local_fallback: Any | None = None,
    ):
        # Shared with ModelRouter — single source of truth for providers.
        self._provider_registry = provider_registry or ProviderRegistry()
        # Offline fallback backend; kept separate from the registry so that
        # LocalModelExecutor remains a non-ModelProvider execution stand-in.
        self._local_fallback = local_fallback or LocalModelExecutor()

    @property
    def provider_registry(self) -> ProviderRegistry:
        """The registry this executor dispatches through (shared with router)."""
        return self._provider_registry

    def register(self, provider: Any) -> None:
        """Register a ``ModelProvider`` into the shared registry."""
        self._provider_registry.register(provider)
        logger.info("model_provider_registered", name=getattr(provider, "name", "?"))

    def get_provider(self, name: str) -> Any | None:
        return self._provider_registry.get(name)

    async def initialize_all(self) -> None:
        for provider in self._provider_registry.list():
            try:
                if hasattr(provider, "initialize"):
                    await provider.initialize()
            except Exception as exc:
                logger.warning("provider_init_failed", name=provider.name, error=str(exc))
        try:
            if hasattr(self._local_fallback, "initialize"):
                await self._local_fallback.initialize()
        except Exception as exc:
            logger.warning("local_fallback_init_failed", error=str(exc))

    async def shutdown_all(self) -> None:
        for provider in self._provider_registry.list():
            try:
                if hasattr(provider, "shutdown"):
                    await provider.shutdown()
            except Exception as exc:
                logger.warning("provider_shutdown_failed", name=provider.name, error=str(exc))
        try:
            if hasattr(self._local_fallback, "shutdown"):
                await self._local_fallback.shutdown()
        except Exception as exc:
            logger.warning("local_fallback_shutdown_failed", error=str(exc))

    def _resolve_provider(self, selection: ModelSelection) -> Any:
        provider_name = ""
        if selection.model_manifest is not None:
            provider_name = selection.model_manifest.provider
        provider = self._provider_registry.get(provider_name)
        if provider is None:
            logger.warning(
                "provider_not_registered",
                requested=provider_name,
                fallback="local",
            )
            provider = self._local_fallback
        return provider

    async def complete(
        self, selection: ModelSelection, messages: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        """Execute a completion for the selected model.

        ``messages`` is the full conversation list of ``{"role", "content"}``
        dicts forwarded verbatim to the selected provider.
        """
        provider = self._resolve_provider(selection)
        request = {"model": selection.model_name, "messages": messages, **kwargs}
        return await provider.complete(request)

    async def stream(
        self, selection: ModelSelection, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a completion for the selected model.

        ``messages`` is the full conversation list forwarded to the provider.
        """
        provider = self._resolve_provider(selection)
        request = {"model": selection.model_name, "messages": messages, **kwargs}
        async for chunk in provider.stream(request):
            yield chunk
