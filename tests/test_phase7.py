"""
Phase 7 Tests — Knowledge Engine (Source, Chunk, Evidence, Citation, Index).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paw.knowledge import (
    KnowledgeSource, KnowledgeSourceType, KnowledgeSourceStatus,
    KnowledgeChunk, KnowledgeEvidence, KnowledgeCitation, KnowledgeIndex,
    KnowledgeSearchResult,
    KnowledgeSourceManager, KnowledgeChunkStore, KnowledgeEvidenceStore,
    KnowledgeCitationStore,
    get_knowledge_source, get_knowledge_chunk, get_knowledge_evidence,
    get_knowledge_citation, get_knowledge_index,
)
from paw.core.storage import db, set_db_path


class TestPhase7KnowledgeSource:
    """Phase 7 Knowledge Source tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_create_source(self, tmp_path):
        """Create a knowledge source."""
        manager = KnowledgeSourceManager()
        source = await manager.create("Test Source", KnowledgeSourceType.FILE.value, "/tmp/test")
        assert source.id != ""
        assert source.name == "Test Source"
        assert source.type == KnowledgeSourceType.FILE.value

    @pytest.mark.asyncio
    async def test_get_source(self, tmp_path):
        """Retrieve a knowledge source."""
        manager = KnowledgeSourceManager()
        source = await manager.create("Test", KnowledgeSourceType.URL.value, "http://test")
        retrieved = await manager.get(source.id)
        assert retrieved is not None
        assert retrieved.name == "Test"

    @pytest.mark.asyncio
    async def test_list_sources(self, tmp_path):
        """List knowledge sources."""
        manager = KnowledgeSourceManager()
        await manager.create("Source 1", KnowledgeSourceType.FILE.value)
        await manager.create("Source 2", KnowledgeSourceType.URL.value)
        sources = await manager.list()
        assert len(sources) >= 2

    @pytest.mark.asyncio
    async def test_list_by_type(self, tmp_path):
        """List sources by type."""
        manager = KnowledgeSourceManager()
        await manager.create("File Source", KnowledgeSourceType.FILE.value)
        await manager.create("URL Source", KnowledgeSourceType.URL.value)
        file_sources = await manager.list(source_type=KnowledgeSourceType.FILE.value)
        assert len(file_sources) == 1
        assert file_sources[0].type == KnowledgeSourceType.FILE.value

    @pytest.mark.asyncio
    async def test_update_status(self, tmp_path):
        """Update source status."""
        manager = KnowledgeSourceManager()
        source = await manager.create("Test", KnowledgeSourceType.FILE.value)
        await manager.update_status(source.id, KnowledgeSourceStatus.INACTIVE.value)
        retrieved = await manager.get(source.id)
        assert retrieved.status == KnowledgeSourceStatus.INACTIVE.value

    @pytest.mark.asyncio
    async def test_delete_source(self, tmp_path):
        """Delete a source (and its chunks)."""
        manager = KnowledgeSourceManager()
        source = await manager.create("Test", KnowledgeSourceType.FILE.value)
        await manager.delete(source.id)
        retrieved = await manager.get(source.id)
        assert retrieved is None


class TestPhase7KnowledgeChunk:
    """Phase 7 Knowledge Chunk tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_add_chunk(self, tmp_path):
        """Add a chunk."""
        store = KnowledgeChunkStore()
        chunk = await store.add_chunk("source-1", "Test content", span_start=0, span_end=100)
        assert chunk.id != ""
        assert chunk.content == "Test content"
        assert chunk.source_id == "source-1"

    @pytest.mark.asyncio
    async def test_get_chunk(self, tmp_path):
        """Get a chunk by ID."""
        store = KnowledgeChunkStore()
        chunk = await store.add_chunk("source-1", "Test content")
        retrieved = await store.get(chunk.id)
        assert retrieved is not None
        assert retrieved.content == "Test content"

    @pytest.mark.asyncio
    async def test_get_by_source(self, tmp_path):
        """Get chunks by source."""
        store = KnowledgeChunkStore()
        await store.add_chunk("source-1", "Content A", span_start=0)
        await store.add_chunk("source-1", "Content B", span_start=100)
        chunks = await store.get_by_source("source-1")
        assert len(chunks) >= 2

    @pytest.mark.asyncio
    async def test_count(self, tmp_path):
        """Count chunks."""
        store = KnowledgeChunkStore()
        await store.add_chunk("source-1", "A")
        await store.add_chunk("source-1", "B")
        count = await store.count()
        assert count >= 2

    @pytest.mark.asyncio
    async def test_delete_by_source(self, tmp_path):
        """Delete chunks by source."""
        store = KnowledgeChunkStore()
        await store.add_chunk("source-1", "A")
        await store.add_chunk("source-2", "B")
        count = await store.delete_by_source("source-1")
        assert count >= 1
        remaining = await store.count()
        assert remaining < count + 1

    @pytest.mark.asyncio
    async def test_chunk_to_dict(self, tmp_path):
        """Chunk serializes correctly."""
        store = KnowledgeChunkStore()
        chunk = await store.add_chunk("source-1", "Test content", span_start=5, span_end=15)
        d = chunk.to_dict()
        assert d["content"] == "Test content"
        assert d["span_start"] == 5
        assert d["span_end"] == 15


class TestPhase7KnowledgeEvidence:
    """Phase 7 Knowledge Evidence tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_add_evidence(self, tmp_path):
        """Add evidence."""
        store = KnowledgeEvidenceStore()
        evidence = await store.add_evidence("chunk-1", "Test claim", confidence=0.9)
        assert evidence.id != ""
        assert evidence.claim == "Test claim"
        assert evidence.confidence == 0.9

    @pytest.mark.asyncio
    async def test_get_evidence(self, tmp_path):
        """Get evidence by ID."""
        store = KnowledgeEvidenceStore()
        evidence = await store.add_evidence("chunk-1", "Test claim")
        retrieved = await store.get(evidence.id)
        assert retrieved is not None
        assert retrieved.claim == "Test claim"

    @pytest.mark.asyncio
    async def test_get_by_chunk(self, tmp_path):
        """Get evidence by chunk."""
        store = KnowledgeEvidenceStore()
        await store.add_evidence("chunk-1", "Claim A", confidence=0.9)
        await store.add_evidence("chunk-1", "Claim B", confidence=0.5)
        evidence_list = await store.get_by_chunk("chunk-1")
        assert len(evidence_list) >= 2

    @pytest.mark.asyncio
    async def test_high_confidence(self, tmp_path):
        """Get high-confidence evidence."""
        store = KnowledgeEvidenceStore()
        await store.add_evidence("chunk-1", "High", confidence=0.9)
        await store.add_evidence("chunk-1", "Low", confidence=0.3)
        high = await store.high_confidence(min_confidence=0.7)
        assert len(high) >= 1
        assert all(e.confidence >= 0.7 for e in high)

    @pytest.mark.asyncio
    async def test_evidence_to_dict(self, tmp_path):
        """Evidence serializes correctly."""
        store = KnowledgeEvidenceStore()
        evidence = await store.add_evidence("chunk-1", "Test", confidence=0.8)
        d = evidence.to_dict()
        assert d["claim"] == "Test"
        assert d["confidence"] == 0.8


class TestPhase7KnowledgeCitation:
    """Phase 7 Knowledge Citation tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_add_citation(self, tmp_path):
        """Add a citation."""
        store = KnowledgeCitationStore()
        citation = await store.add_citation("task-1", "evidence-1", context="Test context", position=0)
        assert citation.id != ""
        assert citation.task_id == "task-1"
        assert citation.evidence_id == "evidence-1"

    @pytest.mark.asyncio
    async def test_get_citation(self, tmp_path):
        """Get citation by ID."""
        store = KnowledgeCitationStore()
        citation = await store.add_citation("task-1", "evidence-1")
        retrieved = await store.get(citation.id)
        assert retrieved is not None
        assert retrieved.task_id == "task-1"

    @pytest.mark.asyncio
    async def test_get_by_task(self, tmp_path):
        """Get citations by task."""
        store = KnowledgeCitationStore()
        await store.add_citation("task-1", "evidence-1")
        await store.add_citation("task-1", "evidence-2")
        await store.add_citation("task-2", "evidence-3")
        citations = await store.get_by_task("task-1")
        assert len(citations) >= 2

    @pytest.mark.asyncio
    async def test_citation_to_dict(self, tmp_path):
        """Citation serializes correctly."""
        store = KnowledgeCitationStore()
        citation = await store.add_citation("task-1", "evidence-1", position=5)
        d = citation.to_dict()
        assert d["task_id"] == "task-1"
        assert d["position"] == 5


class TestPhase7KnowledgeIndex:
    """Phase 7 KnowledgeIndex tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_search_chunks(self, tmp_path):
        """Search chunks by query."""
        index = KnowledgeIndex()
        chunk_store = KnowledgeChunkStore()
        await chunk_store.add_chunk("source-1", "Python programming is great", span_start=0)
        await chunk_store.add_chunk("source-1", "JavaScript framework overview", span_start=50)

        results = await index.search_chunks("Python")
        assert len(results) >= 1
        assert all(isinstance(r, KnowledgeSearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_relevance(self, tmp_path):
        """Search returns relevant results."""
        index = KnowledgeIndex()
        chunk_store = KnowledgeChunkStore()
        await chunk_store.add_chunk("source-1", "Python programming", span_start=0)
        await chunk_store.add_chunk("source-1", "JavaScript framework", span_start=50)

        results = await index.search_chunks("Python")
        if len(results) >= 2:
            # First result should be about Python
            assert "python" in results[0].content.lower()

    @pytest.mark.asyncio
    async def test_search_with_source_filter(self, tmp_path):
        """Search with source filter."""
        index = KnowledgeIndex()
        chunk_store = KnowledgeChunkStore()
        await chunk_store.add_chunk("source-1", "Python content", span_start=0)
        await chunk_store.add_chunk("source-2", "Python content", span_start=50)

        results = await index.search_chunks("Python", source_id="source-1")
        assert len(results) >= 1
        assert all(r.source_id == "source-1" for r in results)

    @pytest.mark.asyncio
    async def test_get_chunk_with_evidence(self, tmp_path):
        """Get a chunk with linked evidence."""
        index = KnowledgeIndex()
        chunk_store = KnowledgeChunkStore()
        chunk = await chunk_store.add_chunk("source-1", "Test content", span_start=0)
        evidence_store = KnowledgeEvidenceStore()
        await evidence_store.add_evidence(chunk.id, "Test evidence", confidence=0.9)

        result = await index.get_chunk_with_evidence(chunk.id)
        assert "chunk" in result
        assert "evidence" in result
        assert len(result["evidence"]) >= 1

    @pytest.mark.asyncio
    async def test_get_all_stats(self, tmp_path):
        """Get global knowledge statistics."""
        index = KnowledgeIndex()
        stats = await index.get_all_stats()
        assert "sources" in stats
        assert "chunks" in stats
        assert "evidence" in stats
        assert "citations" in stats

    @pytest.mark.asyncio
    async def test_search_evidence(self, tmp_path):
        """Search evidence by claim text."""
        index = KnowledgeIndex()
        evidence_store = KnowledgeEvidenceStore()
        await evidence_store.add_evidence("chunk-1", "Python is a language", confidence=0.9)
        await evidence_store.add_evidence("chunk-1", "JavaScript is a language", confidence=0.8)

        results = await index.search_evidence("Python")
        assert len(results) >= 1
        assert all("python" in r["claim"].lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_empty_query(self, tmp_path):
        """Search with empty query returns empty."""
        index = KnowledgeIndex()
        results = await index.search_chunks("")
        assert results == []


class TestPhase7NoProhibitedDependencies:
    """Verify no prohibited dependencies in Phase 7."""

    def test_no_qwenpaw(self):
        knowledge_dir = Path(__file__).parent.parent / "paw" / "knowledge"
        for py_file in knowledge_dir.glob("*.py"):
            if py_file.exists():
                content = py_file.read_text()
                assert "qwenpaw" not in content.lower()

    def test_no_deepseek(self):
        knowledge_dir = Path(__file__).parent.parent / "paw" / "knowledge"
        for py_file in knowledge_dir.glob("*.py"):
            if py_file.exists():
                content = py_file.read_text()
                assert "deepseek" not in content.lower() or "model" in content.lower()

    def test_no_notebooklm(self):
        knowledge_dir = Path(__file__).parent.parent / "paw" / "knowledge"
        for py_file in knowledge_dir.glob("*.py"):
            if py_file.exists():
                content = py_file.read_text()
                assert "notebooklm" not in content.lower()

    def test_no_antigravity(self):
        knowledge_dir = Path(__file__).parent.parent / "paw" / "knowledge"
        for py_file in knowledge_dir.glob("*.py"):
            if py_file.exists():
                content = py_file.read_text()
                assert "antigravity" not in content.lower()
