"""
PAW Knowledge Engine — Citation Module (Phase 7)

KnowledgeCitation represents a source citation for a task,
linking evidence to the task context.
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
class KnowledgeCitation:
    """A citation linking evidence to a task context."""
    id: str = ""
    task_id: str = ""
    evidence_id: str = ""
    context: str = ""
    position: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "evidence_id": self.evidence_id,
            "context": self.context,
            "position": self.position,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> KnowledgeCitation:
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            evidence_id=row["evidence_id"],
            context=row.get("context", ""),
            position=row.get("position", 0),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class KnowledgeCitationStore:
    """Store and retrieve citations."""

    async def add_citation(
        self,
        task_id: str,
        evidence_id: str,
        context: str = "",
        position: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeCitation:
        """Add a citation for a task."""
        citation = KnowledgeCitation(
            id=uuid.uuid4().hex[:16],
            task_id=task_id,
            evidence_id=evidence_id,
            context=context,
            position=position,
            metadata=metadata or {},
        )
        await self._save(citation)
        logger.info("citation_added", task_id=task_id, evidence_id=evidence_id)
        return citation

    async def get(self, citation_id: str) -> KnowledgeCitation | None:
        """Get citation by ID."""
        row = await db.fetchone("SELECT * FROM citations WHERE id = ?", (citation_id,))
        if row:
            return KnowledgeCitation.from_row(dict(row))
        return None

    async def get_by_task(self, task_id: str, limit: int = 100) -> list[KnowledgeCitation]:
        """Get all citations for a task."""
        rows = await db.fetchall(
            "SELECT * FROM citations WHERE task_id = ? ORDER BY position LIMIT ?",
            (task_id, limit),
        )
        return [KnowledgeCitation.from_row(dict(r)) for r in rows]

    async def get_by_evidence(self, evidence_id: str, limit: int = 50) -> list[KnowledgeCitation]:
        """Get citations for an evidence item."""
        rows = await db.fetchall(
            "SELECT * FROM citations WHERE evidence_id = ? ORDER BY position LIMIT ?",
            (evidence_id, limit),
        )
        return [KnowledgeCitation.from_row(dict(r)) for r in rows]

    async def delete_by_task(self, task_id: str) -> int:
        """Delete all citations for a task."""
        cursor = await db.execute("DELETE FROM citations WHERE task_id = ?", (task_id,))
        return cursor.rowcount

    async def _save(self, citation: KnowledgeCitation) -> None:
        """Save citation to database."""
        if not citation.id:
            citation.id = uuid.uuid4().hex[:16]
        await db.execute(
            """
            INSERT OR REPLACE INTO citations
            (id, task_id, evidence_id, context, position, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                citation.id, citation.task_id, citation.evidence_id,
                citation.context, citation.position,
                json.dumps(citation.metadata), citation.created_at.isoformat(),
            ),
        )


# Global instance
_knowledge_citation_store: KnowledgeCitationStore | None = None


def get_knowledge_citation() -> KnowledgeCitationStore:
    """Get global citation store."""
    global _knowledge_citation_store
    if _knowledge_citation_store is None:
        _knowledge_citation_store = KnowledgeCitationStore()
    return _knowledge_citation_store
