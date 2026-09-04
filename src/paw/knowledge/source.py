"""
PAW Knowledge Engine — Source Module (Phase 7)

KnowledgeSource represents a source of knowledge (file, URL, database, etc.)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from paw.core.logging import get_logger
from paw.core.privacy import PrivacyClass
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


# Stable invalidation_reason codes (E1-02). The contract test pins
# this set; adding a new code is a change-control surface.
INVALID_REASONS: frozenset[str] = frozenset(
    {
        "checksum_mismatch",
        "revision_changed",
        "path_missing",
        "superseded",
        "manual",
    }
)


@dataclass
class KnowledgeSource:
    """A knowledge source with metadata and sync status.

    E1-02 adds five fields for project-source identity, revision,
    and invalidation metadata. The owner remains ``KnowledgeSource``
    (per the E1-01 ownership audit). All new fields default to a
    value that keeps the existing rows loadable without a migration
    rewrite.
    """
    id: str = ""
    name: str = ""
    type: str = KnowledgeSourceType.FILE.value
    path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = KnowledgeSourceStatus.ACTIVE.value
    chunk_count: int = 0
    last_sync: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    checksum: str = ""
    # --- E1-02: identity, revision, invalidation metadata ---
    external_id: str = ""
    revision: str = ""
    invalidated_at: str | None = None
    invalidation_reason: str = ""
    superseded_by: str = ""
    # --- E1-03: privacy class. Default INTERNAL keeps a fresh
    # source conservatively classified; the caller must opt up
    # to PUBLIC if the source is shareable.
    privacy_class: PrivacyClass = PrivacyClass.INTERNAL

    @property
    def is_stale(self) -> bool:
        """A source is stale when it is invalid, has been
        superseded, or is in the ERROR status.

        The contract test exercises every combination; this is
        the minimal "is the decision still trustworthy" predicate
        the E1 acceptance target asks for.
        """
        if self.invalidated_at is not None:
            return True
        if self.superseded_by:
            return True
        return self.status == KnowledgeSourceStatus.ERROR.value

    @property
    def is_fresh(self) -> bool:
        """Inverse of ``is_stale``."""
        return not self.is_stale

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
            "external_id": self.external_id,
            "revision": self.revision,
            "invalidated_at": self.invalidated_at,
            "invalidation_reason": self.invalidation_reason,
            "superseded_by": self.superseded_by,
            "privacy_class": self.privacy_class.value,
        }

    @classmethod
    def from_row(cls, row: dict) -> KnowledgeSource:
        # The privacy_class column has DEFAULT 'internal' on
        # the SQL side, but a pre-E1-03 SQLite file may not
        # have the column. Defense in depth: fall back to
        # INTERNAL when the value is missing or unrecognized.
        raw_pc = row.get("privacy_class", "")
        try:
            pc = PrivacyClass.parse(raw_pc) if raw_pc else PrivacyClass.INTERNAL
        except ValueError:
            pc = PrivacyClass.INTERNAL
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
            external_id=row.get("external_id", ""),
            revision=row.get("revision", ""),
            invalidated_at=row.get("invalidated_at"),
            invalidation_reason=row.get("invalidation_reason", ""),
            superseded_by=row.get("superseded_by", ""),
            privacy_class=pc,
        )


class KnowledgeSourceManager:
    """Manage knowledge sources."""

    async def create(
        self,
        name: str,
        source_type: str = KnowledgeSourceType.FILE.value,
        path: str = "",
        metadata: dict[str, Any] | None = None,
        external_id: str = "",
        revision: str = "",
        privacy_class: PrivacyClass = PrivacyClass.INTERNAL,
    ) -> KnowledgeSource:
        """Create a new knowledge source.

        The E1-02 ``external_id``/``revision`` and the
        E1-03 ``privacy_class`` parameters are optional; the
        existing call sites that only pass ``name``/
        ``source_type``/``path`` keep working unchanged.
        The ``privacy_class`` defaults to
        ``PrivacyClass.INTERNAL`` so a freshly registered
        source is conservatively classified; the caller
        must opt up to ``PUBLIC`` if the source is shareable.
        """
        source = KnowledgeSource(
            id=uuid.uuid4().hex[:16],
            name=name,
            type=source_type,
            path=path,
            metadata=metadata or {},
            external_id=external_id,
            revision=revision,
            privacy_class=privacy_class,
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
            (*params, limit),
        )
        return [KnowledgeSource.from_row(dict(r)) for r in rows]

    async def list_stale(self) -> list[KnowledgeSource]:
        """Return every source for which ``is_stale`` is ``True``.

        The runner is a small SQL filter on the three persisted
        columns that drive the predicate: ``invalidated_at``,
        ``superseded_by``, and ``status``. The contract test
        exercises the boundary between the SQL filter and the
        in-Python ``is_stale`` predicate to make sure they agree.
        """
        rows = await db.fetchall(
            "SELECT * FROM knowledge_sources "
            "WHERE invalidated_at IS NOT NULL "
            "   OR superseded_by != '' "
            "   OR status = ? "
            "ORDER BY updated_at DESC",
            (KnowledgeSourceStatus.ERROR.value,),
        )
        return [KnowledgeSource.from_row(dict(r)) for r in rows]

    async def mark_invalid(
        self,
        source_id: str,
        reason: str,
        superseded_by: str = "",
    ) -> KnowledgeSource:
        """Atomically mark a source invalid.

        The ``reason`` is validated against the closed
        ``INVALID_REASONS`` set; an unknown reason raises
        ``ValueError``. The method also writes
        ``status = 'error'`` so the SQL filter in ``list_stale``
        picks the source up even before the predicate is
        re-evaluated.
        """
        if reason not in INVALID_REASONS:
            raise ValueError(
                f"unknown invalidation_reason {reason!r}; "
                f"must be one of {sorted(INVALID_REASONS)}"
            )
        now = datetime.now(UTC).isoformat()
        await db.execute(
            "UPDATE knowledge_sources SET "
            "invalidated_at = ?, "
            "invalidation_reason = ?, "
            "superseded_by = ?, "
            "status = ?, "
            "updated_at = ? "
            "WHERE id = ?",
            (
                now,
                reason,
                superseded_by,
                KnowledgeSourceStatus.ERROR.value,
                now,
                source_id,
            ),
        )
        result = await self.get(source_id)
        if result is None:
            raise ValueError(f"source not found: {source_id!r}")
        return result

    async def update_status(self, source_id: str, status: str) -> bool:
        """Update source status."""
        await db.execute(
            "UPDATE knowledge_sources SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(UTC).isoformat(), source_id),
        )
        return True

    async def update_chunk_count(self, source_id: str, count: int) -> bool:
        """Update chunk count for a source."""
        await db.execute(
            "UPDATE knowledge_sources SET chunk_count = ?, updated_at = ? WHERE id = ?",
            (count, datetime.now(UTC).isoformat(), source_id),
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
        source.updated_at = datetime.now(UTC)

        await db.execute(
            """
            INSERT OR REPLACE INTO knowledge_sources
            (id, name, type, path, metadata, status, chunk_count, last_sync,
             created_at, updated_at, checksum,
             external_id, revision, invalidated_at, invalidation_reason,
             superseded_by, privacy_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.id, source.name, source.type, source.path,
                json.dumps(source.metadata), source.status, source.chunk_count,
                source.last_sync, source.created_at.isoformat(),
                source.updated_at.isoformat(), source.checksum,
                source.external_id, source.revision,
                source.invalidated_at, source.invalidation_reason,
                source.superseded_by,
                source.privacy_class.value,
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
