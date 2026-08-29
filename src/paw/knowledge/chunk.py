"""
PAW Knowledge Engine — Chunk Module (Phase 7)

KnowledgeChunk represents a chunk of content from a knowledge source.
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
class KnowledgeChunk:
    """A chunk of content from a knowledge source."""
    id: str = ""
    source_id: str = ""
    content: str = ""
    span_start: int = 0
    span_end: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "content": self.content,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> KnowledgeChunk:
        return cls(
            id=row["id"],
            source_id=row["source_id"],
            content=row["content"],
            span_start=row.get("span_start", 0),
            span_end=row.get("span_end", 0),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class KnowledgeChunkStore:
    """Store and retrieve knowledge chunks."""

    async def add_chunk(
        self,
        source_id: str,
        content: str,
        span_start: int = 0,
        span_end: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeChunk:
        """Add a chunk to a source."""
        chunk = KnowledgeChunk(
            id=uuid.uuid4().hex[:16],
            source_id=source_id,
            content=content,
            span_start=span_start,
            span_end=span_end,
            metadata=metadata or {},
        )
        await self._save(chunk)
        logger.info("knowledge_chunk_added", source_id=source_id, chunk_id=chunk.id)
        return chunk

    async def get(self, chunk_id: str) -> KnowledgeChunk | None:
        """Get a chunk by ID."""
        row = await db.fetchone("SELECT * FROM knowledge_chunks WHERE id = ?", (chunk_id,))
        if row:
            return KnowledgeChunk.from_row(dict(row))
        return None

    async def get_by_source(self, source_id: str, limit: int = 100) -> list[KnowledgeChunk]:
        """Get all chunks from a source."""
        rows = await db.fetchall(
            "SELECT * FROM knowledge_chunks WHERE source_id = ? ORDER BY span_start LIMIT ?",
            (source_id, limit),
        )
        return [KnowledgeChunk.from_row(dict(r)) for r in rows]

    async def list(self, limit: int = 100) -> list[KnowledgeChunk]:
        """List all chunks."""
        rows = await db.fetchall(
            "SELECT * FROM knowledge_chunks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [KnowledgeChunk.from_row(dict(r)) for r in rows]

    async def delete_by_source(self, source_id: str) -> int:
        """Delete all chunks from a source."""
        cursor = await db.execute(
            "DELETE FROM knowledge_chunks WHERE source_id = ?", (source_id,)
        )
        return cursor.rowcount

    async def count(self, source_id: str | None = None) -> int:
        """Count chunks."""
        if source_id:
            row = await db.fetchone(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE source_id = ?", (source_id,)
            )
            return row[0] if row else 0
        row = await db.fetchone("SELECT COUNT(*) FROM knowledge_chunks")
        return row[0] if row else 0

    async def _save(self, chunk: KnowledgeChunk) -> None:
        """Save chunk to database."""
        if not chunk.id:
            chunk.id = uuid.uuid4().hex[:16]
        await db.execute(
            """
            INSERT OR REPLACE INTO knowledge_chunks
            (id, source_id, content, span_start, span_end, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.id, chunk.source_id, chunk.content,
                chunk.span_start, chunk.span_end,
                json.dumps(chunk.metadata), chunk.created_at.isoformat(),
            ),
        )


# Global instance
_knowledge_chunk_store: KnowledgeChunkStore | None = None


def get_knowledge_chunk() -> KnowledgeChunkStore:
    """Get global knowledge chunk store."""
    global _knowledge_chunk_store
    if _knowledge_chunk_store is None:
        _knowledge_chunk_store = KnowledgeChunkStore()
    return _knowledge_chunk_store
