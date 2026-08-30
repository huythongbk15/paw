"""
Phase 19 #3 — Knowledge context uses ``get_chunk_with_evidence``.

Previously ``_retrieve_knowledge_candidates`` linked evidence by calling
``search_evidence(result.chunk_id)``, which matched the chunk id *textually
inside an evidence claim* — wrong linkage. The correct path joins evidence by
the chunk_id foreign key via ``get_chunk_with_evidence``.
"""

from __future__ import annotations

import pytest

import paw.knowledge.index as ki
from paw.core.context_compiler import ContextCompiler, ContextPlan


class _SearchResult:
    def __init__(self, chunk_id, source_id, score, citations):
        self.chunk_id = chunk_id
        self.source_id = source_id
        self.score = score
        self.content = "UNUSED_OLD_PATH"
        self.evidence_count = 0
        self.citations = citations


class FakeKnowledgeIndex:
    def __init__(self):
        self.get_chunk_calls = []
        self.search_evidence_calls = []

    async def search_chunks(self, query, limit=10):
        return [_SearchResult("c1", "s1", 0.9, [])]

    async def get_chunk_with_evidence(self, chunk_id):
        self.get_chunk_calls.append(chunk_id)
        return {
            "chunk": {"id": "c1", "content": "chunk content about X", "source_id": "s1"},
            "evidence": [
                {"claim": "evidence claim A", "confidence": 0.8},
                {"claim": "evidence claim B", "confidence": 0.6},
            ],
            "citations": [{"url": "http://x", "title": "T"}],
        }

    async def search_evidence(self, query, min_confidence=0.0, limit=20):
        self.search_evidence_calls.append(query)
        return []


async def test_knowledge_uses_get_chunk_with_evidence(monkeypatch):
    fake = FakeKnowledgeIndex()
    monkeypatch.setattr(ki, "get_knowledge_index", lambda: fake)

    compiler = ContextCompiler()
    plan = ContextPlan(
        task_id="t1",
        query="X",
        token_budget=1000,
        knowledge_query="X",
        max_knowledge_chunks=10,
    )
    cands = await compiler._retrieve_knowledge_candidates(plan)

    # Correct linkage method used; buggy textual search_evidence never called.
    assert fake.get_chunk_calls == ["c1"]
    assert fake.search_evidence_calls == []

    assert len(cands) == 1
    c = cands[0]
    assert c.source == "knowledge"
    assert "chunk content about X" in c.content
    assert "evidence claim A" in c.content
    assert "evidence claim B" in c.content
    assert c.metadata["evidence_count"] == 2
    assert c.metadata["citation_count"] == 1
    # Old path content must not leak through.
    assert "UNUSED_OLD_PATH" not in c.content
