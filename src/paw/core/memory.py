"""
PAW Core — Memory Integration (Phase 3)

Episodic and semantic memory storage and retrieval.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .logging import get_logger
from .models import MemoryType
from .storage import db

logger = get_logger(__name__)


@dataclass
class MemoryRecord:
    """A memory record with episodic or semantic content."""
    id: str = ""
    memory_type: MemoryType = MemoryType.SEMANTIC
    content: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    project_id: str | None = None
    task_id: str | None = None
    confidence: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime | None = None
    access_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "summary": self.summary,
            "keywords": self.keywords,
            "metadata": self.metadata,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
        }

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    @classmethod
    def from_row(cls, row: dict) -> MemoryRecord:
        """Create a MemoryRecord from a database row."""
        content = ""
        summary = ""
        keywords = []
        metadata = {}
        if row.get("content"):
            content = row["content"]
        if row.get("summary"):
            summary = row["summary"]
        if row.get("keywords"):
            try:
                keywords = json.loads(row["keywords"])
            except (json.JSONDecodeError, TypeError):
                keywords = []
        if row.get("metadata"):
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        return cls(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            content=content,
            summary=summary,
            keywords=keywords,
            metadata=metadata,
            project_id=row.get("project_id"),
            task_id=row.get("task_id"),
            confidence=row.get("confidence", 0.5),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_accessed=datetime.fromisoformat(row["last_accessed"]) if row.get("last_accessed") else None,
            access_count=row.get("access_count", 0),
        )


class MemoryRetriever:
    """Retrieve memories by type, keyword, and relevance."""

    async def get_by_id(self, memory_id: str) -> MemoryRecord | None:
        """Get a memory record by ID."""
        row = await db.fetchone("SELECT * FROM memory_records WHERE id = ?", (memory_id,))
        if row:
            return MemoryRecord.from_row(dict(row))
        return None

    async def get_by_type(self, memory_type: MemoryType, limit: int = 50) -> list[MemoryRecord]:
        """Get memories by type."""
        rows = await db.fetchall(
            "SELECT * FROM memory_records WHERE memory_type = ? ORDER BY last_accessed DESC NULLS LAST, access_count DESC LIMIT ?",
            (memory_type.value, limit),
        )
        return [MemoryRecord.from_row(dict(r)) for r in rows]

    async def get_by_project(self, project_id: str, limit: int = 50) -> list[MemoryRecord]:
        """Get memories by project."""
        rows = await db.fetchall(
            "SELECT * FROM memory_records WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit),
        )
        return [MemoryRecord.from_row(dict(r)) for r in rows]

    async def get_by_task(self, task_id: str, limit: int = 50) -> list[MemoryRecord]:
        """Get memories associated with a task."""
        rows = await db.fetchall(
            """
            SELECT mr.* FROM memory_records mr
            JOIN memory_task_map mtm ON mr.id = mtm.memory_id
            WHERE mtm.task_id = ?
            ORDER BY mtm.created_at DESC
            """,
            (task_id, limit),
        )
        return [MemoryRecord.from_row(dict(r)) for r in rows]

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search memories by keyword matching."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build query
        conditions = []
        params = []

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        rows = await db.fetchall(
            f"SELECT * FROM memory_records {where_clause} ORDER BY created_at DESC LIMIT ?",
            tuple(params + [limit]),
        )

        results = []
        for row in rows:
            record = MemoryRecord.from_row(dict(row))
            score = self._relevance_score(record, query_tokens)
            if score > 0.1:
                results.append({
                    "record": record,
                    "relevance_score": score,
                })

        # Sort by relevance
        results.sort(key=lambda r: r["relevance_score"], reverse=True)
        return results[:limit]

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer."""
        if not text:
            return []
        return re.findall(r'\w+', text.lower())

    def _relevance_score(self, record: MemoryRecord, query_tokens: list[str]) -> float:
        """Calculate relevance score between query tokens and memory record."""
        if not query_tokens:
            return 0.0

        record_tokens = self._tokenize(record.content + " " + " ".join(record.keywords))
        record_lower = record.content.lower()

        matched = 0
        total = len(query_tokens)

        for qt in query_tokens:
            if qt in record_tokens:
                matched += 1
            elif len(qt) > 3 and qt in record_lower:
                matched += 0.5

        # Boost for recent access
        recency_bonus = min(record.access_count * 0.02, 0.2)
        confidence_bonus = record.confidence * 0.1

        return min((matched / total) + recency_bonus + confidence_bonus, 1.0)

    async def get_recent(self, limit: int = 20) -> list[MemoryRecord]:
        """Get most recently accessed memories."""
        rows = await db.fetchall(
            """
            SELECT * FROM memory_records
            ORDER BY last_accessed DESC NULLS LAST, access_count DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [MemoryRecord.from_row(dict(r)) for r in rows]

    async def get_all_memory_types(self) -> dict[str, int]:
        """Get counts by memory type."""
        rows = await db.fetchall(
            """
            SELECT memory_type, COUNT(*) as count
            FROM memory_records
            GROUP BY memory_type
            """
        )
        return {row["memory_type"]: row["count"] for row in rows}


class MemoryStore:
    """Store memories with metadata tracking."""

    async def store(self, memory: MemoryRecord) -> MemoryRecord:
        """Store a memory record."""
        if not memory.id:
            memory.id = uuid.uuid4().hex[:16]
        memory.touch()

        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO memory_records (
                    id, memory_type, content, summary, keywords,
                    metadata, project_id, task_id, confidence,
                    created_at, updated_at, last_accessed, access_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.memory_type.value,
                    memory.content,
                    memory.summary,
                    json.dumps(memory.keywords),
                    json.dumps(memory.metadata),
                    memory.project_id,
                    memory.task_id,
                    memory.confidence,
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.last_accessed.isoformat() if memory.last_accessed else None,
                    memory.access_count,
                ),
            )

            # Link to task if specified
            if memory.task_id:
                await self._link_to_task(memory.id, memory.task_id)

        logger.info("memory_stored", id=memory.id, type=memory.memory_type.value)
        return memory

    async def update_access(self, memory_id: str) -> None:
        """Update access tracking."""
        await db.execute(
            """
            UPDATE memory_records
            SET last_accessed = ?, access_count = access_count + 1
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), memory_id),
        )

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory record."""
        # Remove task links first
        await db.execute("DELETE FROM memory_task_map WHERE memory_id = ?", (memory_id,))
        cursor = await db.execute("DELETE FROM memory_records WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    async def _link_to_task(self, memory_id: str, task_id: str) -> None:
        """Link memory to a task."""
        await db.execute(
            """
            INSERT OR IGNORE INTO memory_task_map (memory_id, task_id, created_at)
            VALUES (?, ?, ?)
            """,
            (memory_id, task_id, datetime.now(timezone.utc).isoformat()),
        )

    async def get_by_id(self, memory_id: str) -> MemoryRecord | None:
        """Get a memory record by ID."""
        row = await db.fetchone("SELECT * FROM memory_records WHERE id = ?", (memory_id,))
        if row:
            return MemoryRecord.from_row(dict(row))
        return None

    async def get_by_type(self, memory_type: MemoryType, limit: int = 50) -> list[MemoryRecord]:
        """Get memories by type."""
        rows = await db.fetchall(
            "SELECT * FROM memory_records WHERE memory_type = ? ORDER BY last_accessed DESC NULLS LAST, access_count DESC LIMIT ?",
            (memory_type.value, limit),
        )
        return [MemoryRecord.from_row(dict(r)) for r in rows]

    async def get_by_project(self, project_id: str, limit: int = 50) -> list[MemoryRecord]:
        """Get memories by project."""
        rows = await db.fetchall(
            "SELECT * FROM memory_records WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit),
        )
        return [MemoryRecord.from_row(dict(r)) for r in rows]

    async def search(self, query: str, memory_type: MemoryType | None = None, limit: int = 20) -> list[dict]:
        """Search memories by keyword matching."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        conditions = []
        params = []
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = await db.fetchall(
            f"SELECT * FROM memory_records {where_clause} ORDER BY created_at DESC LIMIT ?",
            tuple(params + [limit]),
        )

        results = []
        for row in rows:
            record = MemoryRecord.from_row(dict(row))
            score = self._relevance_score(record, query_tokens)
            if score > 0.1:
                results.append({"record": record, "relevance_score": score})

        results.sort(key=lambda r: r["relevance_score"], reverse=True)
        return results[:limit]

    async def get_recent(self, limit: int = 20) -> list[MemoryRecord]:
        """Get most recently accessed memories."""
        rows = await db.fetchall(
            """
            SELECT * FROM memory_records
            ORDER BY last_accessed DESC NULLS LAST, access_count DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [MemoryRecord.from_row(dict(r)) for r in rows]

    async def get_all_memory_types(self) -> dict[str, int]:
        """Get counts by memory type."""
        rows = await db.fetchall(
            """
            SELECT memory_type, COUNT(*) as count
            FROM memory_records
            GROUP BY memory_type
            """
        )
        return {row["memory_type"]: row["count"] for row in rows}

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer."""
        if not text:
            return []
        import re
        return re.findall(r'\w+', text.lower())

    def _relevance_score(self, record: MemoryRecord, query_tokens: list[str]) -> float:
        """Calculate relevance score between query tokens and memory record."""
        if not query_tokens:
            return 0.0
        record_tokens = self._tokenize(record.content + " ".join(record.keywords))
        record_lower = record.content.lower()
        matched = 0
        total = len(query_tokens)
        for qt in query_tokens:
            if qt in record_tokens:
                matched += 1
            elif len(qt) > 3 and qt in record_lower:
                matched += 0.5
        recency_bonus = min(record.access_count * 0.02, 0.2)
        confidence_bonus = record.confidence * 0.1
        return min((matched / total) + recency_bonus + confidence_bonus, 1.0)


# Memory lifecycle helper
async def create_memory(
    memory_type: MemoryType,
    content: str,
    summary: str = "",
    project_id: str | None = None,
    task_id: str | None = None,
    keywords: list[str] | None = None,
    confidence: float = 0.5,
    metadata: dict[str, Any] | None = None,
) -> MemoryRecord:
    """Create and store a memory record."""
    record = MemoryRecord(
        memory_type=memory_type,
        content=content,
        summary=summary,
        project_id=project_id,
        task_id=task_id,
        keywords=keywords or [],
        confidence=confidence,
        metadata=metadata or {},
    )
    store = MemoryStore()
    return await store.store(record)