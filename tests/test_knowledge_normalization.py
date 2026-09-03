"""Regression tests for the stored-knowledge/result contract boundary."""

from __future__ import annotations

import pytest

from paw.core.models import Citation, Evidence, TaskResult
from paw.knowledge import (
    KnowledgeChunk,
    KnowledgeCitation,
    KnowledgeEvidence,
    normalize_knowledge_result,
)


def test_normalize_knowledge_result_preserves_provenance() -> None:
    chunk = KnowledgeChunk(id="chunk-0001", source_id="source-0001", content="PAW is local-first.")
    stored_evidence = KnowledgeEvidence(
        id="evidence-0001",
        chunk_id=chunk.id,
        claim="PAW is local-first.",
        confidence=0.95,
    )
    stored_citations = [
        KnowledgeCitation(
            id="citation-0002",
            task_id="task-0001",
            evidence_id=stored_evidence.id,
            context="second reference",
            position=20,
        ),
        KnowledgeCitation(
            id="citation-0001",
            task_id="task-0001",
            evidence_id=stored_evidence.id,
            context="first reference",
            position=10,
        ),
    ]

    result = normalize_knowledge_result(
        task_id="task-0001",
        summary="Knowledge-backed answer",
        evidence=[stored_evidence],
        chunks={chunk.id: chunk},
        citations=stored_citations,
    )

    assert isinstance(result, TaskResult)
    assert result.evidence == [
        Evidence(
            source="source-0001",
            claim="PAW is local-first.",
            confidence=0.95,
            citation="citation-0001",
            evidence_id="evidence-0001",
            chunk_id="chunk-0001",
        )
    ]
    assert result.citations == [
        Citation(
            source_id="source-0001",
            context="first reference",
            position=10,
            citation_id="citation-0001",
            evidence_id="evidence-0001",
        ),
        Citation(
            source_id="source-0001",
            context="second reference",
            position=20,
            citation_id="citation-0002",
            evidence_id="evidence-0001",
        ),
    ]


def test_normalize_knowledge_result_rejects_broken_provenance() -> None:
    stored_evidence = KnowledgeEvidence(
        id="evidence-0001",
        chunk_id="missing-chunk",
        claim="Untraceable claim",
    )

    with pytest.raises(ValueError, match="missing knowledge chunk"):
        normalize_knowledge_result(
            task_id="task-0001",
            summary="Invalid answer",
            evidence=[stored_evidence],
            chunks={},
            citations=[],
        )


def test_normalize_knowledge_result_rejects_foreign_citation() -> None:
    chunk = KnowledgeChunk(id="chunk-0001", source_id="source-0001", content="content")
    stored_evidence = KnowledgeEvidence(
        id="evidence-0001",
        chunk_id=chunk.id,
        claim="claim",
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        normalize_knowledge_result(
            task_id="task-0001",
            summary="Invalid answer",
            evidence=[stored_evidence],
            chunks={chunk.id: chunk},
            citations=[
                KnowledgeCitation(
                    id="citation-0001",
                    task_id="task-0001",
                    evidence_id="evidence-9999",
                )
            ],
        )
