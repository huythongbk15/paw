"""
PAW Knowledge Engine (Phase 7)

Knowledge primitives: Source, Chunk, Evidence, Citation, KnowledgeIndex.
Local-first, zero vendor lock-in.
"""

from .chunk import KnowledgeChunk, KnowledgeChunkStore, get_knowledge_chunk
from .citation import KnowledgeCitation, KnowledgeCitationStore, get_knowledge_citation
from .evidence import KnowledgeEvidence, KnowledgeEvidenceStore, get_knowledge_evidence
from .index import KnowledgeIndex, KnowledgeSearchResult, get_knowledge_index
from .normalization import normalize_knowledge_result
from .source import (
    KnowledgeSource,
    KnowledgeSourceManager,
    KnowledgeSourceStatus,
    KnowledgeSourceType,
    get_knowledge_source,
)

__all__ = [
    "KnowledgeChunk",
    "KnowledgeChunkStore",
    "KnowledgeCitation",
    "KnowledgeCitationStore",
    "KnowledgeEvidence",
    "KnowledgeEvidenceStore",
    "KnowledgeIndex",
    "KnowledgeSearchResult",
    "KnowledgeSource",
    "KnowledgeSourceManager",
    "KnowledgeSourceStatus",
    "KnowledgeSourceType",
    "get_knowledge_chunk",
    "get_knowledge_citation",
    "get_knowledge_evidence",
    "get_knowledge_index",
    "get_knowledge_source",
    "normalize_knowledge_result",
]
