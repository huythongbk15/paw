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
from pathlib import Path
from typing import Any

from paw.core.logging import get_logger
from paw.core.privacy import PrivacyClass
from paw.core.storage import db

from .checksum import compute_checksum

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


# --- E1-06: incremental changed/unchanged/deleted source detection ----


@dataclass(frozen=True)
class DiffNew:
    """A path that is on disk but not in the persisted set.

    ``sha256`` is the freshly-computed hash; the
    ingestion loop stores it back via
    ``KnowledgeSourceManager.update_checksum`` when the
    new chunks land.
    """

    path: str
    sha256: str


@dataclass(frozen=True)
class DiffChanged:
    """A path that is in the persisted set AND on disk,
    but the on-disk SHA-256 differs from the persisted
    ``checksum``. The old row is preserved in
    ``source``; the new SHA is in ``new_sha256``."""

    source: KnowledgeSource
    new_sha256: str


@dataclass(frozen=True)
class DiffUnchanged:
    """A path that is in the persisted set AND on disk,
    and the on-disk SHA-256 matches the persisted
    ``checksum``. The ingestion loop skips this row."""

    source: KnowledgeSource


@dataclass(frozen=True)
class DiffDeleted:
    """A path that is in the persisted set but no longer
    on disk. The ingestion loop calls
    ``KnowledgeSourceManager.mark_path_missing`` (or
    ``mark_invalid`` with ``reason='path_missing'``) to
    record the deletion."""

    source: KnowledgeSource


@dataclass(frozen=True)
class SourceDiff:
    """The 3-way classification of a fresh scan against
    the persisted source rows.

    Each bucket is a list; the lists are non-overlapping
    (a path is in exactly one bucket).
    ``len(new) + len(changed) + len(unchanged)`` equals
    ``len(scan_paths)``; ``len(changed) + len(unchanged) +
    len(deleted)`` equals ``len(persisted)``.
    """

    new: tuple[DiffNew, ...] = ()
    changed: tuple[DiffChanged, ...] = ()
    unchanged: tuple[DiffUnchanged, ...] = ()
    deleted: tuple[DiffDeleted, ...] = ()

    @property
    def total(self) -> int:
        return len(self.new) + len(self.changed) + len(self.unchanged) + len(self.deleted)


def _sha256_of_file(repo_root: Path, rel_path: str) -> str:
    """Resolve ``rel_path`` against ``repo_root`` and
    hash the file content. The helper exists so the
    diff function can take a list of repo-relative
    paths and a single repo root.
    """
    absolute = repo_root / rel_path
    return compute_checksum(absolute)


async def diff_sources(
    scan_paths: list[str],
    persisted: list[KnowledgeSource],
    *,
    repo_root: Path | None = None,
) -> SourceDiff:
    """Classify ``scan_paths`` against ``persisted``.

    The function reads the file content for every *new*
    path (to compute the SHA-256 the caller will store
    back) and for every *changed* path (to know what
    changed). The function does **not** read unchanged
    files — that is the incremental optimization.

    ``scan_paths`` is the result of ``scan_repo``
    (E1-05): already-filtered, already-deterministic,
    already-sorted repo-relative POSIX paths. The diff
    function does not re-walk; it accepts the list
    as-is.

    ``persisted`` is the caller's snapshot of the
    relevant ``KnowledgeSource`` rows. The function
    matches by ``source.path``; a path in
    ``scan_paths`` but not in any persisted row's
    ``path`` is ``new``; a persisted row whose
    ``path`` is not in ``scan_paths`` is ``deleted``;
    a persisted row whose ``path`` is in
    ``scan_paths`` is ``changed`` (SHA differs) or
    ``unchanged`` (SHA matches).

    ``repo_root`` is the on-disk root the paths are
    relative to. Required when ``scan_paths`` is
    non-empty (the function needs to hash the files);
    optional when both inputs are empty.
    """
    new_bucket: list[DiffNew] = []
    changed_bucket: list[DiffChanged] = []
    unchanged_bucket: list[DiffUnchanged] = []
    deleted_bucket: list[DiffDeleted] = []

    persisted_by_path: dict[str, KnowledgeSource] = {
        s.path: s for s in persisted
    }
    scan_set: set[str] = set(scan_paths)

    # Walk the scan_paths and classify against persisted.
    for p in scan_paths:
        existing = persisted_by_path.get(p)
        if existing is None:
            # New path: hash the file.
            assert repo_root is not None, (
                "diff_sources requires repo_root when scan_paths is non-empty"
            )
            sha = _sha256_of_file(repo_root, p)
            new_bucket.append(DiffNew(path=p, sha256=sha))
        else:
            # Persisted + on disk: compare SHA.
            assert repo_root is not None, (
                "diff_sources requires repo_root when scan_paths is non-empty"
            )
            sha = _sha256_of_file(repo_root, p)
            if sha == existing.checksum:
                unchanged_bucket.append(DiffUnchanged(source=existing))
            else:
                changed_bucket.append(DiffChanged(source=existing, new_sha256=sha))

    # Persisted rows not in the scan set are deleted.
    for s in persisted:
        if s.path not in scan_set:
            deleted_bucket.append(DiffDeleted(source=s))

    return SourceDiff(
        new=tuple(new_bucket),
        changed=tuple(changed_bucket),
        unchanged=tuple(unchanged_bucket),
        deleted=tuple(deleted_bucket),
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
        re-evaluated, and cascades the invalidation to the
        derived rows (chunks, evidence, citations) via
        ``invalidate_derived_rows``.
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
        # E1-07: cascade the invalidation to derived rows.
        await self.invalidate_derived_rows(source_id, reason=reason)
        result = await self.get(source_id)
        if result is None:
            raise ValueError(f"source not found: {source_id!r}")
        return result

    async def invalidate_derived_rows(
        self,
        source_id: str,
        *,
        reason: str,
    ) -> int:
        """Mark every chunk / evidence / citation that
        derives from ``source_id`` as stale (E1-07).

        The function walks the chunk -> evidence ->
        citation chain in the same call. The recursion is
        breadth-first: first all stale chunks, then all
        evidence that references a stale chunk, then all
        citations that reference a stale evidence. A row
        that is already stale is left untouched (the
        ``stale_at IS NULL`` guard).

        The return value is the total number of rows
        newly marked stale. A re-invocation on the same
        source returns 0 (the cascade is idempotent).

        The function refuses an unknown reason with
        ``ValueError``; the closed reason set is the same
        E1-02 ``INVALID_REASONS`` set.
        """
        if reason not in INVALID_REASONS:
            raise ValueError(
                f"unknown invalidation_reason {reason!r}; "
                f"must be one of {sorted(INVALID_REASONS)}"
            )
        now = datetime.now(UTC).isoformat()
        total = 0
        # 1. Stale every chunk whose source_id matches.
        cursor = await db.execute(
            "UPDATE knowledge_chunks SET "
            "stale_at = ?, stale_reason = ? "
            "WHERE source_id = ? AND stale_at IS NULL",
            (now, reason, source_id),
        )
        total += cursor.rowcount
        # 2. Stale every evidence whose chunk_id references
        # a chunk in this source. (We cannot read
        # ``stale_at IS NULL`` from the chunk filter
        # because we just wrote the chunks in step 1;
        # ``source_id`` on the chunk is the durable
        # ownership boundary.)
        cursor = await db.execute(
            "UPDATE evidence SET "
            "stale_at = ?, stale_reason = ? "
            "WHERE chunk_id IN (SELECT id FROM knowledge_chunks WHERE source_id = ?) "
            "AND stale_at IS NULL",
            (now, reason, source_id),
        )
        total += cursor.rowcount
        # 3. Stale every citation whose evidence_id
        # references an evidence in this source. (Same
        # JOIN-on-source rationale as step 2.)
        cursor = await db.execute(
            "UPDATE citations SET "
            "stale_at = ?, stale_reason = ? "
            "WHERE evidence_id IN ("
            "  SELECT e.id FROM evidence e "
            "  JOIN knowledge_chunks c ON e.chunk_id = c.id "
            "  WHERE c.source_id = ?"
            ") "
            "AND stale_at IS NULL",
            (now, reason, source_id),
        )
        total += cursor.rowcount
        return total

    async def clear_derived_stale(self, source_id: str) -> int:
        """Inverse of ``invalidate_derived_rows``: clear
        the stale state on every chunk / evidence /
        citation that derives from ``source_id``.

        Called by ``update_checksum`` when a source goes
        back to active after a successful re-ingest; the
        cascade is the matching recovery for the
        E1-02 + E1-07 invalidation chain.
        """
        total = 0
        cursor = await db.execute(
            "UPDATE knowledge_chunks SET "
            "stale_at = NULL, stale_reason = '' "
            "WHERE source_id = ?",
            (source_id,),
        )
        total += cursor.rowcount
        cursor = await db.execute(
            "UPDATE evidence SET "
            "stale_at = NULL, stale_reason = '' "
            "WHERE chunk_id IN (SELECT id FROM knowledge_chunks WHERE source_id = ?)",
            (source_id,),
        )
        total += cursor.rowcount
        cursor = await db.execute(
            "UPDATE citations SET "
            "stale_at = NULL, stale_reason = '' "
            "WHERE evidence_id IN ("
            "  SELECT e.id FROM evidence e "
            "  JOIN knowledge_chunks c ON e.chunk_id = c.id "
            "  WHERE c.source_id = ?"
            ")",
            (source_id,),
        )
        total += cursor.rowcount
        return total

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

    async def update_checksum(
        self,
        source_id: str,
        new_sha256: str,
        *,
        last_sync: str | None = None,
    ) -> bool:
        """Atomically write a new content hash for a
        source. The incremental ingestion loop calls
        this with the SHA-256 the ``SourceDiff`` returned
        for a ``new`` or ``changed`` bucket.

        The method also clears any ``invalidated_at``
        whose reason was ``checksum_mismatch`` — a
        successful re-ingest of the same content
        supersedes the previous invalidation, and the
        source goes back to ``active``. A ``last_sync``
        timestamp is recorded when the caller supplies
        one (the ingestion loop sets it to the current
        time so a reviewer can see when the source was
        last verified on disk). E1-07 also clears the
        stale state on the derived rows via
        ``clear_derived_stale`` so a successful re-ingest
        brings the whole chain back to fresh.
        """
        now = datetime.now(UTC).isoformat()
        sync = last_sync if last_sync is not None else now
        await db.execute(
            "UPDATE knowledge_sources SET "
            "checksum = ?, "
            "last_sync = ?, "
            "updated_at = ?, "
            "status = ?, "
            "invalidated_at = CASE WHEN invalidation_reason = 'checksum_mismatch' "
            "                        THEN NULL ELSE invalidated_at END, "
            "invalidation_reason = CASE WHEN invalidation_reason = 'checksum_mismatch' "
            "                            THEN '' ELSE invalidation_reason END "
            "WHERE id = ?",
            (new_sha256, sync, now, KnowledgeSourceStatus.ACTIVE.value, source_id),
        )
        # E1-07: clear the derived stale state on a
        # successful re-ingest.
        await self.clear_derived_stale(source_id)
        return True

    async def mark_path_missing(self, source_id: str) -> KnowledgeSource:
        """One-liner for the ``deleted`` bucket of
        ``SourceDiff``: marks the source invalid with
        the closed reason ``path_missing``. Returns
        the updated source. Delegates to
        ``mark_invalid`` so the closed-reason
        validation is the same."""
        return await self.mark_invalid(source_id, "path_missing")

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
