"""
PAW Phase 12 — Advanced Memory Retrieval

Tests the hybrid (lexical + semantic embedding) memory retriever, re-ranking,
graceful degradation, and ContextCompiler integration.

Two embedding providers are exercised:
- ``StubEmbeddingProvider`` returns controlled vectors to prove the fusion /
  re-ranking math is correct (unit-level, deterministic).
- ``OllamaEmbeddingProvider`` is exercised against a mock ``/api/embeddings``
  server and verified to degrade gracefully when Ollama is unreachable.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCompiler, ContextPlan
from paw.core.embeddings import (
    LocalEmbeddingProvider,
    OllamaEmbeddingProvider,
    cosine_similarity,
    load_embeddings_for,
    store_embedding,
)
from paw.core.memory import (
    AdvancedMemoryRetriever,
    MemoryRecord,
    MemoryStore,
    MemoryType,
)
from paw.core.storage import db, set_db_path


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    paw_home = tmp_path / ".paw"
    paw_home.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_home / "paw.db")
    await db.initialize()
    yield
    await db.close()


# --- Helpers ---


def _make_record(content: str, mid: str = "", memory_type: MemoryType = MemoryType.SEMANTIC) -> MemoryRecord:
    return MemoryRecord(
        id=mid or f"mem-{abs(hash(content)) % 10_000}",
        memory_type=memory_type,
        content=content,
        summary=content[:40],
        confidence=0.7,
    )


class StubEmbeddingProvider:
    """Returns caller-controlled vectors for deterministic fusion tests."""

    name = "stub"

    def __init__(self, table: dict[str, list[float]], query_vec: list[float]):
        self._table = table
        self._query_vec = query_vec

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if t in self._table:
                out.append(self._table[t])
            elif t == "_QUERY_":
                out.append(self._query_vec)
            else:
                out.append(self._query_vec)  # single query at a time in our usage
        return out


# --- Math ---


def test_cosine_similarity():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-9
    assert abs(cosine_similarity(a, c)) < 1e-9
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity(a, [1, 2]) == 0.0  # mismatched length


def test_local_embedding_deterministic():
    p = LocalEmbeddingProvider()
    v1 = asyncio.run(p.embed(["the cat sat on the mat"]))[0]
    v2 = asyncio.run(p.embed(["the cat sat on the mat"]))[0]
    assert v1 == v2
    v3 = asyncio.run(p.embed(["dog ran under table"]))[0]
    assert cosine_similarity(v1, v2) > cosine_similarity(v1, v3)


# --- Persistence ---


@pytest.mark.asyncio
async def test_embedding_persistence():
    await store_embedding("m1", "local-hash", [0.1, 0.2, 0.3])
    loaded = await load_embeddings_for(["m1", "missing"])
    assert loaded["m1"] == [0.1, 0.2, 0.3]
    assert "missing" not in loaded


# --- AdvancedMemoryRetriever: lexical-only degradation ---


@pytest.mark.asyncio
async def test_advanced_retriever_lexical_only():
    store = MemoryStore()
    await store.store(_make_record("How to calculate interest rate", "a1"))
    await store.store(_make_record("Favorite recipe for pasta", "a2"))
    await store.store(_make_record("Debugging a segfault in C", "a3"))

    retr = AdvancedMemoryRetriever(embedding_provider=None)
    results = await retr.search("calculate interest", limit=10)
    assert results, "should return lexical hits"
    assert "calculate" in results[0].record.content.lower()
    assert all(not r.has_embedding for r in results)


# --- AdvancedMemoryRetriever: hybrid re-ranking (controlled vectors) ---


@pytest.mark.asyncio
async def test_advanced_retriever_hybrid_rerank():
    """Semantic similarity must override weaker lexical score in ranking."""
    store = MemoryStore()
    # rec_b shares MORE lexical tokens with the query but is semantically off;
    # rec_a is lexically weaker but semantically on-target.
    rec_a = _make_record("Loan amortization and annual percentage yield", "h1")
    rec_b = _make_record("interest in a good book is nice", "h2")
    await store.store(rec_a)
    await store.store(rec_b)

    # Vectors: query close to rec_a, far from rec_b
    qvec = [1.0, 0.0]
    table = {
        "Loan amortization and annual percentage yield": [0.9, 0.1],
        "interest in a good book is nice": [0.0, 1.0],
    }
    stub = StubEmbeddingProvider(table, qvec)

    # Pre-store embeddings so the semantic path is exercised
    for rec in (rec_a, rec_b):
        await store_embedding(rec.id, "stub", table[rec.content])

    retr = AdvancedMemoryRetriever(embedding_provider=stub, lexical_weight=0.5, semantic_weight=0.5)
    results = await retr.search("loan interest rate calculation", limit=10)
    assert results
    top = results[0]
    assert top.has_embedding is True
    # rec_a must win: high semantic similarity despite weaker lexical overlap
    assert top.record.id == "h1"
    # rec_a's semantic score is high; rec_b's is ~0
    by_id = {r.record.id: r for r in results}
    assert by_id["h1"].semantic_score > by_id["h2"].semantic_score


# --- Mock Ollama embeddings server ---


class _MockOllamaEmbedHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        import hashlib
        import math

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            req = {}
        if self.path == "/api/embeddings":
            dim = 32
            vec = [0.0] * dim
            for tok in re.findall(r"\w+", req.get("prompt", "").lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vec = [v / norm for v in vec]
            self._send({"embedding": vec})
        else:
            self._send({"error": "not found"}, status=404)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send({"models": []})
        else:
            self._send({"error": "not found"}, status=404)


@pytest.fixture
def mock_ollama_embed():
    server = HTTPServer(("127.0.0.1", 0), _MockOllamaEmbedHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.mark.asyncio
async def test_ollama_embedding_provider(mock_ollama_embed):
    provider = OllamaEmbeddingProvider(base_url=mock_ollama_embed, model="nomic-embed-text")
    await provider.initialize()
    assert provider.available is True
    vecs = await provider.embed(["hello world", "foo bar"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 32
    assert vecs[0] == vecs[0]


@pytest.mark.asyncio
async def test_ollama_embedding_provider_unavailable():
    provider = OllamaEmbeddingProvider(base_url="http://127.0.0.1:1")
    await provider.initialize()
    assert provider.available is False
    # embed() must never raise; degrades to local fallback vectors
    vecs = await provider.embed(["x"])
    assert len(vecs) == 1
    assert len(vecs[0]) > 0


@pytest.mark.asyncio
async def test_hybrid_with_ollama_embeddings(mock_ollama_embed):
    store = MemoryStore()
    # Shared tokens so the (hashed bag-of-words) mock produces a real signal
    rec_a = _make_record("compound interest formula calculation", "o1")
    rec_b = _make_record("bake chocolate cake recipe dessert", "o2")
    await store.store(rec_a)
    await store.store(rec_b)

    provider = OllamaEmbeddingProvider(base_url=mock_ollama_embed)
    await provider.initialize()
    retr = AdvancedMemoryRetriever(embedding_provider=provider, semantic_weight=0.7)
    results = await retr.search("compound interest calculation", limit=10)
    assert results
    assert results[0].has_embedding is True
    # rec_a shares 'compound','interest','calculation' -> ranks first
    assert results[0].record.id == "o1"


# --- ContextCompiler integration ---


@pytest.mark.asyncio
async def test_context_compiler_uses_advanced_retriever():
    """ContextCompiler must assign real (non-flat-0.5) relevance to memory."""
    store = MemoryStore()
    await store.store(_make_record("Calculate the mortgage payment", "c1"))
    await store.store(_make_record("Grill vegetables on bbq", "c2"))

    await db.write(
        "INSERT INTO tasks (id, session_id, project_id, goal, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "task-x",
            "sess-x",
            "proj-x",
            "goal",
            "active",
            "2024-01-01T00:00:00+00:00",
            "2024-01-01T00:00:00+00:00",
        ),
    )
    await db.write(
        "INSERT INTO memory_task_map (memory_id, task_id, created_at) VALUES (?,?,?)",
        ("c1", "task-x", "2024-01-01T00:00:00+00:00"),
    )
    await db.write(
        "INSERT INTO memory_task_map (memory_id, task_id, created_at) VALUES (?,?,?)",
        ("c2", "task-x", "2024-01-01T00:00:00+00:00"),
    )

    compiler = ContextCompiler(embedding_provider=None)  # lexical advanced retriever
    plan = ContextPlan(task_id="task-x", query="how to calculate mortgage", token_budget=2000)
    candidates = await compiler._retrieve_memory_candidates(plan)
    assert candidates, "memory candidates should be produced"
    for c in candidates:
        # Relevance comes from the advanced retriever, not a flat 0.5
        assert "lexical_score" in c.metadata
        assert "semantic_score" in c.metadata
    top = max(candidates, key=lambda c: c.relevance_score)
    assert "mortgage" in top.content.lower() or "calculate" in top.content.lower()
