"""The default chat/TUI path must reach a real local model, and degrade safely.

Measured on 2026-09-29: ``paw chat --provider auto`` returned ``local-fast``
and echoed ``[local-standin] ...`` even though Ollama was serving seven usable
models. Isolating the cause: with an identical workspace and cwd, ``auto``
picked the echo stand-in while ``ollama`` picked ``qwen2.5-coder:7b``.

Two things had to be true for the default path to work:

1. The provider name ``local`` is the offline echo stand-in, not a local model.
   Only the Ollama adapter serves a real one. So ``auto`` must prefer
   ``ollama`` rather than leave the choice to scoring, which picks the echo.
2. A provider's ``available`` is ``None`` until ``initialize()`` runs, and
   ``bool(None)`` is ``False``. Reading it before probing therefore reports "no
   local model" even when one is serving. ``ChatService.open()`` now probes.

Degradation still has to work: when no local model is reachable, ``auto`` must
fall back to the stand-in rather than fail.
"""

from __future__ import annotations

import pytest

from paw.application.chat import ChatService
from paw.providers.ollama import OllamaProvider

UNREACHABLE = "http://127.0.0.1:1"  # nothing listens here


class _Provider:
    """Minimal stand-in exposing the attribute the helper reads."""

    def __init__(self, name: str, available: bool) -> None:
        self.name = name
        self.available = available

    async def initialize(self) -> None:
        return None


class _Registry:
    def __init__(self, providers: dict) -> None:
        self._providers = providers

    async def initialize_all(self) -> None:
        return None


def _service(mode: str, providers: dict) -> ChatService:
    service = ChatService.__new__(ChatService)
    service.provider_mode = mode
    service._providers = _Registry(providers)
    return service


class TestPreferredProvider:
    def test_auto_prefers_a_reachable_local_model(self):
        service = _service("auto", {"ollama": _Provider("ollama", True)})
        assert service._preferred_provider() == "ollama"

    def test_auto_falls_back_when_no_local_model(self):
        """Degradation is the requirement, not an error."""
        service = _service("auto", {"ollama": _Provider("ollama", False)})
        assert service._preferred_provider() is None

    def test_explicit_modes_are_passed_through(self):
        assert _service("ollama", {})._preferred_provider() == "ollama"
        assert _service("local", {})._preferred_provider() == "local"

    def test_unknown_mode_has_no_preference(self):
        assert _service("something-else", {})._preferred_provider() is None

    def test_auto_without_any_provider_does_not_raise(self):
        assert _service("auto", {})._preferred_provider() is None


class TestAvailabilityIsProbedNotGuessed:
    @pytest.mark.asyncio
    async def test_open_probes_providers(self, tmp_path, monkeypatch):
        """``available`` must be known before anything consults it."""
        from paw.core.model_router import ProviderRegistry

        calls: list[str] = []
        original = ProviderRegistry.initialize_all

        async def _spy(self):
            calls.append("initialize_all")
            await original(self)

        monkeypatch.setattr(ProviderRegistry, "initialize_all", _spy)
        svc = ChatService(provider_mode="auto", workspace_root=tmp_path)
        await svc.open()
        assert calls == ["initialize_all"], (
            "open() must initialize providers so availability is known before "
            "any mode consults it"
        )
        await svc.close()

    @pytest.mark.asyncio
    async def test_unreachable_provider_degrades_instead_of_raising(self, tmp_path):
        """A dead Ollama must not break the chat path."""
        svc = ChatService(provider_mode="auto", workspace_root=tmp_path)
        svc._providers = _Registry(
            {"ollama": OllamaProvider(base_url=UNREACHABLE, timeout=2.0)},
        )
        await svc.open()
        assert svc._preferred_provider() is None
        await svc.close()