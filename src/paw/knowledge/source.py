"""
PAW Knowledge Engine — Source Module (Phase 7)

KnowledgeSource represents a source of knowledge (file, URL, database, etc.)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from paw.core.logging import get_logger
from paw.core.storage import db

logger = get_logger(__name__)


class KnowledgeSourceType(StrEnum):
    """Type of knowledge source."""
    FILE = "file"
    URL = "url"
    DATABASE = "database"
    API = "api"
    MANUAL = "manual"
    FEED = "feed"
    INBOX = "inbox"


class KnowledgeSourceStatus(StrEnum):
    """Status of a knowledge source."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SYNCING = "syncing"
    ERROR = "error"
    ARCHIVED = "archived"


@dataclass
class KnowledgeSource:
    """A knowledge source with metadata and sync status."""
    id: str = ""
    name: str = ""
    type: str = KnowledgeSourceType.FILE.value
    path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = KnowledgeSourceStatus.ACTIVE.value
    chunk_count: int = 0
    last_sync: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "metadata": self.metadata,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "last_sync": self.last_sync,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "checksum": self.checksum,
        }

    @classmethod
    def from_row(cls, row: dict) -> "KnowledgeSource":
        return cls(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            path=row.get("path", ""),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            status=row.get("status", KnowledgeSourceStatus.ACTIVE.value),
            chunk_count=row.get("chunk_count", 0),
            last_sync=row.get("last_sync"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            checksum=row.get("checksum", ""),
        )


class KnowledgeSourceManager:
    """Manage knowledge sources."""

    async def create(
        self,
        name: str,
        source_type: str = KnowledgeSourceType.FILE.value,
        path: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeSource:
        """Create a new knowledge source."""
        source = KnowledgeSource(
            id=uuid.uuid4().hex[:16],
            name=name,
            type=source_type,
            path=path,
            metadata=metadata or {},
        )
        await self._save(source)
        logger.info("knowledge_source_created", name=name, type=source_type)
        return source

    async def get(self, source_id: str) -> KnowledgeSource | None:
        """Get a knowledge source by ID."""
        row = await db.fetchone("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
        if row:
            return KnowledgeSource.from_row(dict(row))
        return None

    async def list(
        self,
        source_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeSource]:
        """List knowledge sources."""
        conditions = []
        params: list[Any] = []
        if source_type:
            conditions.append("type = ?")
            params.append(source_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = await db.fetchall(
            f"SELECT * FROM knowledge_sources {where} ORDER BY created_at DESC LIMIT ?",
            tuple(params + [limit]),
        )
        return [KnowledgeSource.from_row(dict(r)) for r in rows]

    async def update_status(self, source_id: str, status: str) -> bool:
        """Update source status."""
        await db.execute(
            "UPDATE knowledge_sources SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(), source_id),
        )
        return True

    async def update_chunk_count(self, source_id: str, count: int) -> bool:
        """Update chunk count for a source."""
        await db.execute(
            "UPDATE knowledge_sources SET chunk_count = ?, updated_at = ? WHERE id = ?",
            (count, datetime.now(timezone.utc).isoformat(), source_id),
        )
        return True

    async def delete(self, source_id: str) -> bool:
        """Delete a knowledge source."""
        # Remove chunks first
        await db.execute("DELETE FROM knowledge_chunks WHERE source_id = ?", (source_id,))
        cursor = await db.execute("DELETE FROM knowledge_sources WHERE id = ?", (source_id,))
        return cursor.rowcount > 0

    async def _save(self, source: KnowledgeSource) -> None:
        """Save source to database."""
        import json
        if not source.id:
            source.id = uuid.uuid4().hex[:16]
        source.touch() if hasattr(source, 'touch') else None
        source.updated_at = datetime.now(timezone.utc)

        await db.execute(
            """
            INSERT OR REPLACE INTO knowledge_sources
            (id, name, type, path, metadata, status, chunk_count, last_sync, created_at, updated_at, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.id, source.name, source.type, source.path,
                json.dumps(source.metadata), source.status, source.chunk_count,
                source.last_sync, source.created_at.isoformat(),
                source.updated_at.isoformat(), source.checksum,
            ),
        )


# Global instance
_knowledge_source_manager: KnowledgeSourceManager | None = None


def get_knowledge_source() -> KnowledgeSourceManager:
    """Get global knowledge source manager."""
    global _knowledge_source_manager
    if _knowledge_source_manager is None:
        _knowledge_source_manager = KnowledgeSourceManager()
    return _knowledge_source_manager
