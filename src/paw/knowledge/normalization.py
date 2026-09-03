"""Normalize persisted knowledge records into PAW's result contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from paw.core.models import Citation, Evidence, TaskResult

from .chunk import KnowledgeChunk
from .citation import KnowledgeCitation
from .evidence import KnowledgeEvidence


def normalize_knowledge_result(
    *,
    task_id: str,
    summary: str,
    evidence: Sequence[KnowledgeEvidence],
    chunks: Mapping[str, KnowledgeChunk],
    citations: Sequence[KnowledgeCitation],
    status: str = "completed",
) -> TaskResult:
    """Build a result without leaking persistence records across the boundary.

    Persisted evidence refers to a chunk, while the result contract refers to
    the chunk's source. Broken references are rejected rather than silently
    producing evidence that cannot be traced back to its source.
    """
    evidence_by_id: dict[str, KnowledgeEvidence] = {}
    for item in evidence:
        if item.id in evidence_by_id:
            raise ValueError(f"duplicate knowledge evidence ID: {item.id}")
        if item.chunk_id not in chunks:
            raise ValueError(
                f"missing knowledge chunk {item.chunk_id!r} for evidence {item.id!r}"
            )
        evidence_by_id[item.id] = item

    citations_by_evidence: dict[str, list[KnowledgeCitation]] = {
        evidence_id: [] for evidence_id in evidence_by_id
    }
    citation_ids: set[str] = set()
    for item in citations:
        if item.id in citation_ids:
            raise ValueError(f"duplicate knowledge citation ID: {item.id}")
        citation_ids.add(item.id)
        if item.task_id != task_id:
            raise ValueError(
                f"citation {item.id!r} belongs to task {item.task_id!r}, not {task_id!r}"
            )
        if item.evidence_id not in evidence_by_id:
            raise ValueError(
                f"citation {item.id!r} references unknown evidence {item.evidence_id!r}"
            )
        citations_by_evidence[item.evidence_id].append(item)

    result_evidence: list[Evidence] = []
    result_citations: list[Citation] = []
    for item in evidence:
        chunk = chunks[item.chunk_id]
        item_citations = sorted(
            citations_by_evidence[item.id],
            key=lambda citation: (citation.position, citation.id),
        )
        result_evidence.append(
            Evidence(
                source=chunk.source_id,
                claim=item.claim,
                confidence=item.confidence,
                citation=item_citations[0].id if item_citations else "",
                evidence_id=item.id,
                chunk_id=item.chunk_id,
            )
        )
        result_citations.extend(
            Citation(
                source_id=chunk.source_id,
                context=citation.context,
                position=citation.position,
                citation_id=citation.id,
                evidence_id=item.id,
            )
            for citation in item_citations
        )

    return TaskResult(
        task_id=task_id,
        status=status,
        summary=summary,
        evidence=result_evidence,
        citations=result_citations,
    )
