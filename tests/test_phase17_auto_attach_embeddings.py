"""Tests for optional backlog: auto-attach OllamaEmbeddingProvider (Phase 17).

Verifies that ContextCompiler / AdvancedSkillSelector transparently upgrade to
hybrid (lexical + semantic) retrieval when a local Ollama embedding model is
running, and degrade gracefully to lexical-only when it is not.
"""

from __future__ import annotations

import pytest

from paw.core.context_compiler import ContextCompiler
from paw.core.semantic import AdvancedSkillSelector
from paw.core.skills import Capability, SkillManifest


class FakeEmbeddingProvider:
    """In-memory embedding provider used to simulate a running Ollama model."""

    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


async def _provider_down() -> None:
    return None


async def _provider_up() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def fake_manifest() -> SkillManifest:
    return SkillManifest(
        name="Search",
        category="web",
        description="search the web",
        trigger="search",
        capabilities=[Capability.NETWORK_HTTP],
    )


class FakeFabric:
    def __init__(self, manifests: list[SkillManifest]) -> None:
        self._manifests = manifests

    def list_skills(self, enabled_only: bool = True) -> list[SkillManifest]:
        return self._manifests


async def test_auto_attach_none_when_ollama_down(temp_db, monkeypatch):
    """When Ollama is unavailable, the compiler stays lexical-only and compiles."""
    monkeypatch.setattr(
        "paw.core.embeddings.try_ollama_embedding_provider", _provider_down
    )
    compiler = ContextCompiler(embedding_provider=None, auto_attach_embeddings=True)
    context, _ = await compiler.compile("task1", "test query", session_id="sess1")
    assert compiler.embedding_provider is None
    assert context is not None


async def test_auto_attach_uses_ollama_when_available(temp_db, monkeypatch):
    """When Ollama is available, the compiler auto-attaches the provider."""
    monkeypatch.setattr(
        "paw.core.embeddings.try_ollama_embedding_provider", _provider_up
    )
    compiler = ContextCompiler(embedding_provider=None, auto_attach_embeddings=True)
    await compiler.compile("task1", "test query", session_id="sess1")
    assert compiler.embedding_provider is not None
    assert compiler.embedding_provider.name == "fake"
    # Semantic similarity now uses the attached provider.
    sim = await compiler._semantic_similarity("alpha beta", "alpha gamma")
    assert isinstance(sim, float)
    assert sim >= 0.0


async def test_explicit_provider_not_overridden(temp_db, monkeypatch):
    """An explicitly passed provider is never replaced by auto-attach."""
    monkeypatch.setattr(
        "paw.core.embeddings.try_ollama_embedding_provider", _provider_up
    )
    explicit = FakeEmbeddingProvider()
    compiler = ContextCompiler(embedding_provider=explicit, auto_attach_embeddings=True)
    await compiler.compile("task1", "test query", session_id="sess1")
    assert compiler.embedding_provider is explicit


async def test_auto_attach_disabled(temp_db, monkeypatch):
    """With auto_attach disabled, the provider helper is never invoked."""
    calls = {"n": 0}

    async def _recorder():
        calls["n"] += 1
        return None

    monkeypatch.setattr(
        "paw.core.embeddings.try_ollama_embedding_provider", _recorder
    )
    compiler = ContextCompiler(embedding_provider=None, auto_attach_embeddings=False)
    await compiler.compile("task1", "test query", session_id="sess1")
    assert compiler.embedding_provider is None
    assert calls["n"] == 0


async def test_selector_standalone_auto_attach(fake_manifest, monkeypatch):
    """AdvancedSkillSelector attaches a provider when used standalone."""
    monkeypatch.setattr(
        "paw.core.embeddings.try_ollama_embedding_provider", _provider_up
    )
    selector = AdvancedSkillSelector(
        fabric=FakeFabric([fake_manifest]),
        embedding_provider=None,
        auto_attach_embeddings=True,
    )
    await selector.select("search the web")
    assert selector.embedding_provider is not None
    assert selector.embedding_provider.name == "fake"
