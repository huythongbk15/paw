"""
PAW Knowledge Engine — KnowledgeIndex (Phase 7)

Index and search knowledge chunks, evidence, and citations.
Local-first, no external dependencies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from paw.core.logging import get_logger
from paw.core.storage import db

from .chunk import KnowledgeChunk
from .citation import KnowledgeCitation
from .evidence import KnowledgeEvidence

logger = get_logger(__name__)


@dataclass
class KnowledgeSearchResult:
    """A single search result with relevance score."""
    chunk_id: str = ""
    content: str = ""
    source_id: str = ""
    score: float = 0.0
    evidence_count: int = 0
    citations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "source_id": self.source_id,
            "score": self.score,
            "evidence_count": self.evidence_count,
            "citations": self.citations,
            "metadata": self.metadata,
        }


class KnowledgeIndex:
    """Index and search knowledge content locally."""

    def __init__(self):
        self._chunk_cache: dict[str, KnowledgeChunk] = {}

    async def search_chunks(
        self,
        query: str,
        source_id: str | None = None,
        min_score: float = 0.1,
        limit: int = 20,
    ) -> list[KnowledgeSearchResult]:
        """Search chunks by keyword matching with relevance scoring."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        if source_id:
            rows = await db.fetchall(
                "SELECT * FROM knowledge_chunks WHERE source_id = ? ORDER BY created_at DESC LIMIT 500",
                (source_id,),
            )
        else:
            rows = await db.fetchall(
                "SELECT * FROM knowledge_chunks ORDER BY created_at DESC LIMIT 500",
            )

        results: list[KnowledgeSearchResult] = []
        for row in rows:
            chunk = KnowledgeChunk.from_row(dict(row))
            score = self._score_chunk(chunk, query_tokens)
            if score >= min_score:
                # Count evidence
                evidence_count = await self._count_evidence(chunk.id)
                # Get citations
                citations = await self._get_citation_ids(chunk.id)

                results.append(KnowledgeSearchResult(
                    chunk_id=chunk.id,
                    content=chunk.content[:200],
                    source_id=chunk.source_id,
                    score=score,
                    evidence_count=evidence_count,
                    citations=citations,
                    metadata=chunk.metadata,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def search_evidence(
        self,
        query: str,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list[dict]:
        """Search evidence by claim text."""
        rows = await db.fetchall(
            "SELECT * FROM evidence WHERE confidence >= ? ORDER BY confidence DESC LIMIT ?",
            (min_confidence, limit),
        )
        results = []
        query_lower = query.lower()
        for row in rows:
            claim = row["claim"]
            if query_lower in claim.lower():
                results.append({
                    "evidence_id": row["id"],
                    "claim": claim,
                    "confidence": row["confidence"],
                    "chunk_id": row["chunk_id"],
                })
        return results

    async def get_chunk_with_evidence(self, chunk_id: str) -> dict:
        """Get a chunk with all linked evidence and citations."""
        chunk_row = await db.fetchone("SELECT * FROM knowledge_chunks WHERE id = ?", (chunk_id,))
        if not chunk_row:
            return {}

        chunk = KnowledgeChunk.from_row(dict(chunk_row))
        evidence_rows = await db.fetchall(
            "SELECT * FROM evidence WHERE chunk_id = ? ORDER BY confidence DESC",
            (chunk_id,),
        )
        citation_rows = await db.fetchall(
            "SELECT * FROM citations WHERE evidence_id IN (SELECT id FROM evidence WHERE chunk_id = ?)",
            (chunk_id,),
        )

        evidence_list = [KnowledgeEvidence.from_row(dict(r)) for r in evidence_rows]

        return {
            "chunk": chunk.to_dict(),
            "evidence": [e.to_dict() for e in evidence_list],
            "citations": [KnowledgeCitation.from_row(dict(r)).to_dict() for r in citation_rows],
        }

    async def get_citations_for_task(self, task_id: str) -> list[dict]:
        """Get citations for a task."""
        rows = await db.fetchall(
            "SELECT * FROM citations WHERE task_id = ? ORDER BY position",
            (task_id,),
        )
        return [dict(r) for r in rows]

    async def get_source_stats(self, source_id: str) -> dict:
        """Get statistics for a knowledge source."""
        chunk_count = await self._count_chunks(source_id)
        evidence_rows = await db.fetchall(
            """
            SELECT AVG(confidence) as avg_conf, COUNT(*) as count
            FROM evidence WHERE chunk_id IN (SELECT id FROM knowledge_chunks WHERE source_id = ?)
            """,
            (source_id,),
        )
        avg_conf = evidence_rows[0]["avg_conf"] if evidence_rows else 0.0
        total_evidence = evidence_rows[0]["count"] if evidence_rows else 0

        return {
            "source_id": source_id,
            "chunk_count": chunk_count,
            "evidence_count": total_evidence,
            "average_confidence": round(avg_conf, 3) if avg_conf else 0.0,
        }

    # --- E1-14: persist derived records through existing
    # Knowledge ownership. The persisted state lives in
    # the ``metadata`` JSON column on ``knowledge_sources``;
    # the contract reuses the existing ownership boundary
    # and does not introduce a new table.

    _DERIVED_KEY = "paw_derived_views"
    # A closed set of view kinds the E1-14 contract
    # accepts. New kinds are added by editing this list
    # and the contract test in the same change.
    _DERIVED_VIEW_KINDS: frozenset[str] = frozenset(
        {
            "symbols",
            "test_links",
            "dependency_edges",
            "recent_changes",
            "affected_areas",
        }
    )

    async def save_derived_view(
        self,
        source_id: str,
        view_kind: str,
        view_data: dict,
    ) -> bool:
        """Persist a derived view under the source's
        ``metadata`` JSON, keyed by ``view_kind``.

        The ``view_data`` is a JSON-serializable dict;
        the caller's contract is "what I save is what I
        get back". The function refuses an unknown
        ``view_kind`` with ``ValueError``; the closed set
        is the change-control surface.
        """
        if view_kind not in self._DERIVED_VIEW_KINDS:
            raise ValueError(
                f"unknown view_kind {view_kind!r}; "
                f"must be one of {sorted(self._DERIVED_VIEW_KINDS)}"
            )
        # Read the existing metadata so the save is
        # additive (multiple views per source).
        row = await db.fetchone(
            "SELECT metadata FROM knowledge_sources WHERE id = ?",
            (source_id,),
        )
        if row is None:
            return False
        row_dict = dict(row)
        existing = json.loads(row_dict["metadata"]) if row_dict.get("metadata") else {}
        views = dict(existing.get(self._DERIVED_KEY, {}))
        views[view_kind] = view_data
        existing[self._DERIVED_KEY] = views
        await db.write(
            "UPDATE knowledge_sources SET metadata = ?, updated_at = ? WHERE id = ?",
            (
                json.dumps(existing),
                datetime.now(UTC).isoformat(),
                source_id,
            ),
        )
        return True

    async def load_derived_view(
        self,
        source_id: str,
        view_kind: str,
    ) -> dict:
        """Load a previously-saved derived view.

        Returns ``{}`` when no view has been stored yet
        (the missing-key case is the common one — the
        caller is a fresh session that has not yet
        derived the view).
        """
        row = await db.fetchone(
            "SELECT metadata FROM knowledge_sources WHERE id = ?",
            (source_id,),
        )
        if row is None:
            return {}
        row_dict = dict(row)
        if not row_dict.get("metadata"):
            return {}
        existing = json.loads(row_dict["metadata"])
        views = existing.get(self._DERIVED_KEY, {})
        return dict(views.get(view_kind, {}))

    async def list_derived_views(
        self,
        source_id: str,
    ) -> tuple[str, ...]:
        """Return the view kinds persisted for a
        source. Empty tuple when no views are stored."""
        row = await db.fetchone(
            "SELECT metadata FROM knowledge_sources WHERE id = ?",
            (source_id,),
        )
        if row is None:
            return ()
        row_dict = dict(row)
        if not row_dict.get("metadata"):
            return ()
        existing = json.loads(row_dict["metadata"])
        return tuple(sorted(existing.get(self._DERIVED_KEY, {}).keys()))

    async def get_all_stats(self) -> dict:
        """Get global knowledge statistics."""
        chunk_count = await self._count_chunks()
        source_count = await self._count_sources()
        evidence_count = await self._count_evidence_total()
        citation_count = await self._count_citations_total()

        return {
            "sources": source_count,
            "chunks": chunk_count,
            "evidence": evidence_count,
            "citations": citation_count,
        }

    async def _count_chunks(self, source_id: str | None = None) -> int:
        if source_id:
            row = await db.fetchone(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE source_id = ?", (source_id,)
            )
        else:
            row = await db.fetchone("SELECT COUNT(*) FROM knowledge_chunks")
        return row[0] if row else 0

    async def _count_sources(self) -> int:
        row = await db.fetchone("SELECT COUNT(*) FROM knowledge_sources")
        return row[0] if row else 0

    async def _count_evidence(self, chunk_id: str) -> int:
        row = await db.fetchone(
            "SELECT COUNT(*) FROM evidence WHERE chunk_id = ?", (chunk_id,)
        )
        return row[0] if row else 0

    async def _count_evidence_total(self) -> int:
        row = await db.fetchone("SELECT COUNT(*) FROM evidence")
        return row[0] if row else 0

    async def _count_citations_total(self) -> int:
        row = await db.fetchone("SELECT COUNT(*) FROM citations")
        return row[0] if row else 0

    async def _get_citation_ids(self, chunk_id: str) -> list[str]:
        rows = await db.fetchall(
            """
            SELECT c.id FROM citations c
            JOIN evidence e ON c.evidence_id = e.id
            WHERE e.chunk_id = ?
            """,
            (chunk_id,),
        )
        return [r["id"] for r in rows]

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer."""
        if not text:
            return []
        return re.findall(r'\w+', text.lower())

    def _score_chunk(self, chunk: KnowledgeChunk, query_tokens: list[str]) -> float:
        """Score a chunk for relevance to query tokens."""
        if not query_tokens:
            return 0.0

        content_tokens = self._tokenize(chunk.content)
        metadata_tokens = self._tokenize(json.dumps(chunk.metadata))
        all_tokens = content_tokens + metadata_tokens + chunk.content.lower().split()

        matched = 0
        total = len(query_tokens)

        for qt in query_tokens:
            if qt in all_tokens:
                matched += 1
            elif len(qt) > 3 and qt in chunk.content.lower():
                matched += 0.5

        # Boost for content length (more content = more likely relevant)
        length_bonus = min(len(content_tokens) / 1000, 0.1)

        return min((matched / total) + length_bonus, 1.0)


# Global instance
_knowledge_index: KnowledgeIndex | None = None


def get_knowledge_index() -> KnowledgeIndex:
    """Get global knowledge index."""
    global _knowledge_index
    if _knowledge_index is None:
        _knowledge_index = KnowledgeIndex()
    return _knowledge_index
