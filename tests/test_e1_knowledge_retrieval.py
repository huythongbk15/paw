"""Focused E1 regressions for bounded, fresh knowledge retrieval."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paw.core.embeddings import (
    OllamaEmbeddingProvider,
    load_embeddings_for,
    load_knowledge_chunk_embeddings_for,
    store_embedding,
    store_knowledge_chunk_embedding,
)
from paw.core.storage import db, set_db_path
from paw.knowledge.chunk import KnowledgeChunkStore
from paw.knowledge.index import KnowledgeIndex


@pytest.fixture(autouse=True)
async def isolated_db(tmp_path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    yield
    await db.close()


@pytest.mark.asyncio
async def test_stale_chunk_is_never_retrieved() -> None:
    chunk = await KnowledgeChunkStore().add_chunk(
        "source", "class ExactProjectSymbol:\n    pass",
    )
    await db.write(
        "UPDATE knowledge_chunks SET stale_at = ?, stale_reason = ? WHERE id = ?",
        (datetime.now(UTC).isoformat(), "revision_changed", chunk.id),
    )
    assert await KnowledgeIndex().search_chunks("ExactProjectSymbol") == []


@pytest.mark.asyncio
async def test_exact_definition_outranks_generic_prose() -> None:
    store = KnowledgeChunkStore()
    await store.add_chunk(
        "source", "This long generic explanation mentions task status many times.",
    )
    exact = await store.add_chunk(
        "source", "class TaskStatus(StrEnum):\n    RUNNING = 'running'",
    )
    results = await KnowledgeIndex().search_chunks(
        "Find the file that defines TaskStatus", limit=2,
    )
    assert results[0].chunk_id == exact.id


@pytest.mark.asyncio
async def test_private_method_definition_gets_exact_match_boost() -> None:
    store = KnowledgeChunkStore()
    await store.add_chunk("source", "allocate budget rules and context prose")
    exact = await store.add_chunk(
        "source", "# owner: ContextCompiler\n    def _allocate_budget(self):\n        pass",
    )
    results = await KnowledgeIndex().search_chunks(
        "Find ContextCompiler def _allocate_budget", limit=2,
    )
    assert results[0].chunk_id == exact.id


def test_code_tokenizer_relates_allocation_to_allocate() -> None:
    index = KnowledgeIndex()
    assert "allocate" in index._tokenize("budget allocation logic")
    assert "allocate" in index._tokenize("def _allocate_budget")


@pytest.mark.asyncio
async def test_embedding_cache_is_scoped_to_model() -> None:
    chunk = await KnowledgeChunkStore().add_chunk("source", "cache target")
    await store_knowledge_chunk_embedding(
        chunk.id, "ollama:model-a", [1.0, 0.0],
    )
    assert await load_knowledge_chunk_embeddings_for(
        [chunk.id], "ollama:model-a",
    ) == {chunk.id: [1.0, 0.0]}
    assert await load_knowledge_chunk_embeddings_for(
        [chunk.id], "ollama:model-b",
    ) == {}


@pytest.mark.asyncio
async def test_memory_embedding_cache_is_scoped_to_model() -> None:
    await store_embedding("memory", "ollama:model-a", [1.0, 0.0])
    assert await load_embeddings_for(
        ["memory"], "ollama:model-a",
    ) == {"memory": [1.0, 0.0]}
    assert await load_embeddings_for(["memory"], "ollama:model-b") == {}


@pytest.mark.asyncio
async def test_ollama_uses_one_batched_request(monkeypatch) -> None:
    provider = OllamaEmbeddingProvider()
    provider._available = True
    calls = []

    async def request(method, path, body=None):
        calls.append((method, path, body))
        return {"embeddings": [[1.0, 0.0], [0.0, 1.0]]}

    monkeypatch.setattr(provider, "_request", request)
    assert await provider.embed(["one", "two"]) == [
        [1.0, 0.0], [0.0, 1.0],
    ]
    assert [(method, path) for method, path, _body in calls] == [
        ("POST", "/api/embed"),
    ]


class _Provider:
    name = "stub"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


@pytest.mark.asyncio
async def test_explicit_none_does_not_reuse_index_provider() -> None:
    await KnowledgeChunkStore().add_chunk("source", "class RoutedSymbol: pass")
    index = KnowledgeIndex(embedding_provider=_Provider())
    results = await index.search_chunks(
        "RoutedSymbol", embedding_provider=None,
    )
    assert results
    stored = await db.fetch_all("SELECT * FROM knowledge_chunk_embeddings")
    assert stored == []


@pytest.mark.asyncio
async def test_chunk_delete_removes_cached_embedding() -> None:
    store = KnowledgeChunkStore()
    chunk = await store.add_chunk("source", "temporary chunk")
    await store_knowledge_chunk_embedding(chunk.id, "stub", [1.0])
    assert await store.delete_by_source("source") == 1
    assert await db.fetch_all("SELECT * FROM knowledge_chunk_embeddings") == []
