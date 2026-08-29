"""
PAW Core — Embeddings & Semantic Retrieval (Phase 12)

Advanced Memory Retrieval: combine lexical relevance (already in
``MemoryRetriever``) with semantic embedding similarity, then fuse and
re-rank. Fully local-first and zero vendor lock-in:

- ``OllamaEmbeddingProvider`` talks to a local Ollama ``/api/embeddings``
  endpoint (no cloud, no third-party SDK — stdlib HTTP only).
- ``LocalEmbeddingProvider`` is a deterministic offline fallback (hashed
  bag-of-words) so retrieval works with zero external dependencies.
- When no embedding provider is available, retrieval degrades gracefully to
  lexical-only — the runtime never depends on a model server.

Embeddings are persisted in a separate ``memory_embeddings`` table (no schema
migration of ``memory_records`` required, backward-compatible).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
from typing import Any, Protocol

from .logging import get_logger
from .storage import db

logger = get_logger(__name__)

EMBEDDING_DIM = 256
EMBEDDING_MODEL_LOCAL = "local-hash"


# --- Math ---


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors in [-1, 1]."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# --- Provider interface ---


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class LocalEmbeddingProvider:
    """Deterministic offline embedding via hashed bag-of-words.

    Not a real semantic model, but produces stable vectors whose cosine
    similarity correlates with lexical overlap. Enables hybrid retrieval and
    tests with zero external dependencies.
    """

    name = "local"

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"\w+", (text or "").lower())
        if not tokens:
            return vec
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            vec[idx] += 1.0
        # normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class OllamaEmbeddingProvider:
    """Local Ollama embedding provider (``/api/embeddings``).

    Pure stdlib HTTP (urllib) wrapped in asyncio.to_thread. Graceful: when
    Ollama is unavailable the provider reports ``available=False`` and callers
    fall back to lexical retrieval.
    """

    name = "ollama"

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._available: bool | None = None

    async def initialize(self) -> None:
        try:
            await self._request("GET", "/api/tags")
            self._available = True
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            self._available = False
            logger.warning("ollama_embed_unavailable", error=str(exc))

    @property
    def available(self) -> bool:
        return bool(self._available)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts via Ollama. Falls back to local on failure."""
        if not self._available:
            logger.warning("ollama_embed_skipped_unavailable")
            return await LocalEmbeddingProvider().embed(texts)
        out: list[list[float]] = []
        for text in texts:
            try:
                data = await self._request(
                    "POST", "/api/embeddings", {"model": self.model, "prompt": text}
                )
                out.append(list(data.get("embedding", [])))
            except (OSError, urllib.error.URLError, TimeoutError) as exc:
                logger.error("ollama_embed_failed", error=str(exc))
                # graceful: one bad item -> local fallback for that item
                local = (await LocalEmbeddingProvider().embed([text]))[0]
                out.append(local)
        return out

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        import asyncio

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        loop = asyncio.get_running_loop()

        def _do() -> Any:
            import urllib.request

            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method=method
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}

        return await asyncio.wait_for(
            loop.run_in_executor(None, _do), timeout=self.timeout + 5
        )


# --- Auto-attach helper (runtime convenience) ---


async def try_ollama_embedding_provider(
    model: str = "nomic-embed-text",
    base_url: str = "http://localhost:11434",
    timeout: float = 30.0,
) -> OllamaEmbeddingProvider | None:
    """Return an available Ollama embedding provider, or ``None`` if Ollama is down.

    Used by the runtime (ContextCompiler / AdvancedSkillSelector) to
    transparently upgrade to hybrid retrieval when a local Ollama embedding
    model is running. Never raises — connection failures degrade to ``None``
    so callers keep working in lexical-only mode.
    """
    provider = OllamaEmbeddingProvider(model=model, base_url=base_url, timeout=timeout)
    try:
        await provider.initialize()
    except Exception as exc:
        logger.warning("ollama_embed_auto_attach_failed", error=str(exc))
        return None
    return provider if provider.available else None


# --- Persistence ---


async def ensure_embedding_table() -> None:
    """Create the (optional) embeddings table if it does not exist."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_embeddings (
            memory_id TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            vector TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


async def store_embedding(memory_id: str, model: str, vector: list[float]) -> None:
    from datetime import UTC, datetime

    await ensure_embedding_table()
    await db.write(
        """
        INSERT OR REPLACE INTO memory_embeddings (memory_id, model, vector, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (memory_id, model, json.dumps(vector), datetime.now(UTC).isoformat()),
    )


async def load_embedding(memory_id: str) -> list[float] | None:
    row = await db.fetch_one(
        "SELECT vector FROM memory_embeddings WHERE memory_id = ?", (memory_id,)
    )
    if not row:
        return None
    try:
        return json.loads(row["vector"])
    except (ValueError, KeyError):
        return None


async def load_embeddings_for(ids: list[str]) -> dict[str, list[float]]:
    if not ids:
        return {}
    await ensure_embedding_table()
    placeholders = ",".join("?" for _ in ids)
    rows = await db.fetch_all(
        f"SELECT memory_id, vector FROM memory_embeddings WHERE memory_id IN ({placeholders})",
        tuple(ids),
    )
    out: dict[str, list[float]] = {}
    for r in rows:
        try:
            out[r["memory_id"]] = json.loads(r["vector"])
        except (ValueError, KeyError):
            continue
    return out
