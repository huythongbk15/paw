"""
PAW Knowledge Engine (Phase 7)

Knowledge primitives: Source, Chunk, Evidence, Citation, KnowledgeIndex.
Local-first, zero vendor lock-in.
"""

from .chunk import KnowledgeChunk, KnowledgeChunkStore, get_knowledge_chunk
from .citation import KnowledgeCitation, KnowledgeCitationStore, get_knowledge_citation
from .cross_file import SymbolReference, build_symbol_index, resolve_cross_file
from .evidence import KnowledgeEvidence, KnowledgeEvidenceStore, get_knowledge_evidence
from .index import KnowledgeIndex, KnowledgeSearchResult, get_knowledge_index
from .inheritance import ClassInfo, InheritanceEdge, extract_inheritance
from .normalization import normalize_knowledge_result
from .source import (
    DiffChanged,
    DiffDeleted,
    DiffNew,
    DiffUnchanged,
    KnowledgeSource,
    KnowledgeSourceManager,
    KnowledgeSourceStatus,
    KnowledgeSourceType,
    SourceDiff,
    diff_sources,
    get_knowledge_source,
)
from .type_annotations import AnnotationLink, extract_annotations

__all__ = [
    "AnnotationLink",
    "ClassInfo",
    "DiffChanged",
    "DiffDeleted",
    "DiffNew",
    "DiffUnchanged",
    "InheritanceEdge",
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
    "SourceDiff",
    "SymbolReference",
    "build_symbol_index",
    "diff_sources",
    "extract_annotations",
    "extract_inheritance",
    "get_knowledge_chunk",
    "get_knowledge_citation",
    "get_knowledge_evidence",
    "get_knowledge_index",
    "get_knowledge_source",
    "normalize_knowledge_result",
    "resolve_cross_file",
]
