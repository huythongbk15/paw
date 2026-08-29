"""
PAW Knowledge Engine — Evidence Module (Phase 7)

KnowledgeEvidence represents a claim with supporting evidence and confidence.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from paw.core.logging import get_logger
from paw.core.storage import db

logger = get_logger(__name__)


@dataclass
class KnowledgeEvidence:
    """A piece of evidence supporting a claim, linked to a chunk."""
    id: str = ""
    chunk_id: str = ""
    claim: str = ""
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chunk_id": self.chunk_id,
            "claim": self.claim,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> KnowledgeEvidence:
        return cls(
            id=row["id"],
            chunk_id=row["chunk_id"],
            claim=row["claim"],
            confidence=row.get("confidence", 0.5),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class KnowledgeEvidenceStore:
    """Store and retrieve evidence."""

    async def add_evidence(
        self,
        chunk_id: str,
        claim: str,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeEvidence:
        """Add evidence linked to a chunk."""
        evidence = KnowledgeEvidence(
            id=uuid.uuid4().hex[:16],
            chunk_id=chunk_id,
            claim=claim,
            confidence=min(max(confidence, 0.0), 1.0),
            metadata=metadata or {},
        )
        await self._save(evidence)
        logger.info("evidence_added", chunk_id=chunk_id, claim=claim[:50])
        return evidence

    async def get(self, evidence_id: str) -> KnowledgeEvidence | None:
        """Get evidence by ID."""
        row = await db.fetchone("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
        if row:
            return KnowledgeEvidence.from_row(dict(row))
        return None

    async def get_by_chunk(self, chunk_id: str, limit: int = 50) -> list[KnowledgeEvidence]:
        """Get all evidence for a chunk."""
        rows = await db.fetchall(
            "SELECT * FROM evidence WHERE chunk_id = ? ORDER BY confidence DESC LIMIT ?",
            (chunk_id, limit),
        )
        return [KnowledgeEvidence.from_row(dict(r)) for r in rows]

    async def list_by_claim(self, claim: str, limit: int = 20) -> list[KnowledgeEvidence]:
        """Search evidence by claim text."""
        rows = await db.fetchall(
            "SELECT * FROM evidence WHERE claim LIKE ? LIMIT ?",
            (f"%{claim}%", limit),
        )
        return [KnowledgeEvidence.from_row(dict(r)) for r in rows]

    async def high_confidence(self, min_confidence: float = 0.7, limit: int = 50) -> list[KnowledgeEvidence]:
        """Get high-confidence evidence."""
        rows = await db.fetchall(
            "SELECT * FROM evidence WHERE confidence >= ? ORDER BY confidence DESC LIMIT ?",
            (min_confidence, limit),
        )
        return [KnowledgeEvidence.from_row(dict(r)) for r in rows]

    async def delete_by_chunk(self, chunk_id: str) -> int:
        """Delete evidence linked to a chunk."""
        cursor = await db.execute("DELETE FROM evidence WHERE chunk_id = ?", (chunk_id,))
        return cursor.rowcount

    async def _save(self, evidence: KnowledgeEvidence) -> None:
        """Save evidence to database."""
        if not evidence.id:
            evidence.id = uuid.uuid4().hex[:16]
        await db.execute(
            """
            INSERT OR REPLACE INTO evidence
            (id, chunk_id, claim, confidence, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.id, evidence.chunk_id, evidence.claim,
                evidence.confidence, json.dumps(evidence.metadata),
                evidence.created_at.isoformat(),
            ),
        )


# Global instance
_knowledge_evidence_store: KnowledgeEvidenceStore | None = None


def get_knowledge_evidence() -> KnowledgeEvidenceStore:
    """Get global evidence store."""
    global _knowledge_evidence_store
    if _knowledge_evidence_store is None:
        _knowledge_evidence_store = KnowledgeEvidenceStore()
    return _knowledge_evidence_store
