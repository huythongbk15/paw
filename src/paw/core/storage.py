"""
PAW Storage — SQLite database initialization and connection management.

Uses aiosqlite for async operations. Schema is defined in SQL for clarity and control.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 3

SCHEMA = """
-- Core tables for PAW

-- Tasks and Task Graph
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    session_id TEXT NOT NULL,
    project_id TEXT,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_capabilities TEXT,
    selected_skills TEXT,
    selected_executor TEXT,
    selected_model TEXT,
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS task_nodes (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    goal TEXT NOT NULL,
    dependencies TEXT,
    skills TEXT,
    context_requirements TEXT,
    capability_requirements TEXT,
    policy_requirements TEXT,
    executor TEXT,
    model TEXT,
    result TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_nodes_task ON task_nodes(task_id);

-- Task Graph (Phase 9)
CREATE TABLE IF NOT EXISTS task_graphs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    schedule_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL DEFAULT 'must_complete',
    condition TEXT,
    created_at TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_dep_from ON task_dependencies(from_node_id);
CREATE INDEX IF NOT EXISTS idx_dep_to ON task_dependencies(to_node_id);

-- Task Ledger
CREATE TABLE IF NOT EXISTS task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_ledger_task ON task_events(task_id);

-- Policy Engine (Phase 6 / 14)
CREATE TABLE IF NOT EXISTS policy_rules (
    id TEXT PRIMARY KEY,
    capability TEXT NOT NULL,
    decision TEXT NOT NULL,
    conditions TEXT,  -- JSON
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Executor Registry
CREATE TABLE IF NOT EXISTS executors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    capabilities TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Skill Fabric
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0.0',
    description TEXT,
    category TEXT NOT NULL DEFAULT 'general',
    capabilities TEXT,  -- JSON array
    risk TEXT NOT NULL DEFAULT 'low',
    network BOOLEAN NOT NULL DEFAULT 0,
    write BOOLEAN NOT NULL DEFAULT 0,
    trigger TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',  -- Body content (was 'manifest')
    source TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    executors TEXT,  -- JSON array
    dependencies TEXT,  -- JSON array of skill names
    metadata TEXT  -- JSON object for nested metadata.paw/
);

-- Migrate existing 'manifest' column to 'body' if needed
-- (SQLite doesn't support RENAME COLUMN before 3.25, so we handle in code)

CREATE TABLE IF NOT EXISTS skill_registry (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    version TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);

-- FTS5 Virtual Table for Skill Search
CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(
    name, description, body, tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS skill_ai AFTER INSERT ON skills BEGIN
    INSERT INTO skill_fts(name, description, body) VALUES (new.name, new.description, new.body);
END;

CREATE TRIGGER IF NOT EXISTS skill_ad AFTER DELETE ON skills BEGIN
    INSERT INTO skill_fts(name, description, body) VALUES (old.name, old.description, old.body);
END;

CREATE TRIGGER IF NOT EXISTS skill_au AFTER UPDATE ON skills BEGIN
    INSERT INTO skill_fts(name, description, body) VALUES (old.name, old.description, old.body);
    INSERT INTO skill_fts(name, description, body) VALUES (new.name, new.description, new.body);
END;

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Durable CLI chat application state. Sessions/tasks remain the canonical
-- domain records; these tables only keep the chat projection and transcript.
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    current_task_id TEXT,
    pending_approval_id TEXT,
    last_checkpoint_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session
    ON chat_messages(session_id, created_at);

-- ASK is a durable, exact-operation boundary. The fingerprint prevents an
-- approval from authorizing a changed proposal that reused an operation id.
CREATE TABLE IF NOT EXISTS approval_requests (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    action TEXT NOT NULL,
    action_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    consumed_at TEXT,
    decided_by TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    UNIQUE (task_id, operation_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_approval_task_status
    ON approval_requests(task_id, status, requested_at DESC);

-- Model Registry
CREATE TABLE IF NOT EXISTS model_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    roles TEXT,
    capabilities TEXT,
    cost TEXT,
    features TEXT,
    max_context_tokens INTEGER NOT NULL DEFAULT 128000,
    latency_tier TEXT NOT NULL DEFAULT 'medium',
    enabled BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Model Selections
CREATE TABLE IF NOT EXISTS model_selections (
    task_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    role TEXT NOT NULL,
    reason TEXT,
    score REAL NOT NULL DEFAULT 0.0,
    fallback_chain TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (task_id, role, created_at));

-- Identity & Preferences
CREATE TABLE IF NOT EXISTS identity (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Plans
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    session_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Memory Records (Phase 3)
CREATE TABLE IF NOT EXISTS memory_records (
    id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL DEFAULT 'semantic',
    content TEXT NOT NULL,
    summary TEXT,
    keywords TEXT,
    metadata TEXT,
    project_id TEXT,
    task_id TEXT,
    confidence REAL NOT NULL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    privacy_class TEXT NOT NULL DEFAULT 'internal'
);

CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_records(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_records(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_records(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_task ON memory_records(task_id);

-- FTS5 Virtual Table for Memory Search
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content,
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory_records BEGIN
    INSERT INTO memory_fts(content) VALUES (new.content);
END;

CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory_records BEGIN
    INSERT INTO memory_fts(content) VALUES (old.content);
END;

CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory_records BEGIN
    INSERT INTO memory_fts(content) VALUES (old.content);
    INSERT INTO memory_fts(content) VALUES (new.content);
END;

-- Memory-Task Mapping
CREATE TABLE IF NOT EXISTS memory_task_map (
    memory_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memory_records(id)
);

-- Knowledge Engine

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    path TEXT,
    metadata TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    last_sync TEXT,
    checksum TEXT,
    external_id TEXT NOT NULL DEFAULT '',
    revision TEXT NOT NULL DEFAULT '',
    invalidated_at TEXT,
    invalidation_reason TEXT NOT NULL DEFAULT '',
    superseded_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    content TEXT NOT NULL,
    span_start INTEGER,
    span_end INTEGER,
    metadata TEXT,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS citations (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    context TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    metadata TEXT,
    created_at TEXT NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_chunks_source ON knowledge_chunks(source_id);

-- Evidence and Citations
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    claim TEXT NOT NULL,
    confidence REAL,
    metadata TEXT,
    created_at TEXT NOT NULL);

-- Durable runtime state. Feature modules must use these canonical tables.
CREATE TABLE IF NOT EXISTS task_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    task_status TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    total_steps INTEGER NOT NULL DEFAULT 0,
    progress_ratio REAL NOT NULL DEFAULT 0.0,
    context TEXT NOT NULL DEFAULT '{}',
    context_compiler_state TEXT NOT NULL DEFAULT '{}',
    autonomy_usage TEXT NOT NULL DEFAULT '{}',
    autonomy_profile TEXT NOT NULL DEFAULT 'balanced',
    progress_history TEXT NOT NULL DEFAULT '[]',
    repetition_state TEXT NOT NULL DEFAULT '{}',
    stall_state TEXT NOT NULL DEFAULT '{}',
    loop_iteration INTEGER NOT NULL DEFAULT 0,
    loop_decision_history TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_task_id
    ON task_checkpoints (task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS operation_records (
    task_id TEXT NOT NULL,
    op_id TEXT NOT NULL,
    op_type TEXT NOT NULL DEFAULT 'step',
    status TEXT NOT NULL DEFAULT 'completed',
    checkpoint_id TEXT,
    result_ref TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (task_id, op_id)
);

CREATE INDEX IF NOT EXISTS idx_oprec_task ON operation_records(task_id, status);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    vector TEXT NOT NULL,
    created_at TEXT NOT NULL
);

"""


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self._conn: aiosqlite.Connection | None = None
        self._initialized = False
        self._transaction_depth = 0

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.execute("PRAGMA synchronous = NORMAL")
        logger.info("database_connected", path=str(self.db_path))

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._initialized = False
            self._transaction_depth = 0
            logger.info("database_closed")

    async def initialize(self) -> None:
        """Create all tables and indexes."""
        if self._initialized and self._conn is not None:
            return
        await self.connect()
        await self._conn.executescript(SCHEMA)
        await self._migrate_schema()
        await self._conn.commit()
        self._initialized = True
        logger.info("database_initialized")

    async def _migrate_schema(self) -> None:
        """Repair known pre-v2 layouts without dropping user data."""
        cursor = await self._conn.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        version = int(row[0]) if row else 0
        if version >= SCHEMA_VERSION:
            return
        # Migrate skills table FIRST: add columns introduced after the table
        # first shipped. The table may already exist from an older schema that
        # lacked these columns; CREATE TABLE IF NOT EXISTS does not alter it,
        # which leaves the skill_ai FTS trigger (created by SCHEMA) referencing
        # non-existent columns. SQLite re-validates every trigger on any ALTER
        # TABLE, so these columns must exist before the model_selections
        # rename below, otherwise that ALTER raises "error in trigger skill_ai".
        skills_cursor = await self._conn.execute("PRAGMA table_info(skills)")
        skills_cols = {row[1] for row in await skills_cursor.fetchall()}
        skills_additions = {
            "version": "TEXT NOT NULL DEFAULT '1.0.0'",
            "description": "TEXT",
            "category": "TEXT NOT NULL DEFAULT 'general'",
            "capabilities": "TEXT",
            "risk": "TEXT NOT NULL DEFAULT 'low'",
            "network": "BOOLEAN NOT NULL DEFAULT 0",
            "write": "BOOLEAN NOT NULL DEFAULT 0",
            "body": "TEXT NOT NULL DEFAULT ''",
            "executors": "TEXT",
            "dependencies": "TEXT",
            "metadata": "TEXT",
        }
        for col, col_def in skills_additions.items():
            if col not in skills_cols:
                await self._conn.execute(
                    f"ALTER TABLE skills ADD COLUMN {col} {col_def}"
                )
        # Migrate knowledge_sources for E1-02: add project-source
        # identity, revision, and invalidation metadata. The columns
        # are additive (NOT NULL DEFAULT '' or nullable), so the
        # existing rows load at their default values without a row
        # rewrite. The CREATE TABLE above declares the same columns
        # so a fresh database gets them without a migration step.
        ks_cursor = await self._conn.execute("PRAGMA table_info(knowledge_sources)")
        ks_cols = {row[1] for row in await ks_cursor.fetchall()}
        ks_additions = {
            "external_id":         "TEXT NOT NULL DEFAULT ''",
            "revision":            "TEXT NOT NULL DEFAULT ''",
            "invalidated_at":      "TEXT",
            "invalidation_reason": "TEXT NOT NULL DEFAULT ''",
            "superseded_by":       "TEXT NOT NULL DEFAULT ''",
            "privacy_class":       "TEXT NOT NULL DEFAULT 'internal'",
        }
        for col, col_def in ks_additions.items():
            if col not in ks_cols:
                await self._conn.execute(
                    f"ALTER TABLE knowledge_sources ADD COLUMN {col} {col_def}"
                )
        # E1-03: also add the privacy_class column to
        # memory_records with the same default. Additive, no
        # row rewrite.
        mr_cursor = await self._conn.execute("PRAGMA table_info(memory_records)")
        mr_cols = {row[1] for row in await mr_cursor.fetchall()}
        if "privacy_class" not in mr_cols:
            await self._conn.execute(
                "ALTER TABLE memory_records "
                "ADD COLUMN privacy_class TEXT NOT NULL DEFAULT 'internal'"
            )
        info_cursor = await self._conn.execute("PRAGMA table_info(model_selections)")
        columns = await info_cursor.fetchall()
        primary_key = [column[1] for column in columns if column[5]]
        if primary_key == ["task_id"]:
            await self._conn.execute("ALTER TABLE model_selections RENAME TO model_selections_legacy")
            await self._conn.execute(
                """CREATE TABLE model_selections (
                    task_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    reason TEXT,
                    score REAL NOT NULL DEFAULT 0.0,
                    fallback_chain TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, role, created_at)
                )"""
            )
            await self._conn.execute(
                """INSERT OR IGNORE INTO model_selections
                (task_id, model_name, role, reason, score, fallback_chain, created_at)
                SELECT task_id, model_name, role, reason, score, fallback_chain, created_at
                FROM model_selections_legacy"""
            )
            await self._conn.execute("DROP TABLE model_selections_legacy")
        await self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        await self.connect()
        self._transaction_depth += 1
        try:
            yield self._conn
            self._transaction_depth -= 1
            if self._transaction_depth == 0:
                await self._conn.commit()
        except Exception:
            self._transaction_depth = max(0, self._transaction_depth - 1)
            if self._transaction_depth == 0:
                await self._conn.rollback()
            raise

    # --- Explicit Storage Mutation Contract (Part A6) ---
    # Read operations - no mutation, safe to call without transaction
    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute a SELECT query and return one row as dict."""
        await self.connect()
        async with self._conn.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT query and return all rows as list of dicts."""
        await self.connect()
        async with self._conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Write operations. They commit immediately unless an explicit transaction
    # is active, so durable state cannot silently remain uncommitted.
    async def write(self, sql: str, params: tuple = ()) -> int:
        """Execute a single INSERT/UPDATE/DELETE statement.
        Must be called within a transaction context.
        Returns: rowcount
        """
        await self.connect()
        cursor = await self._conn.execute(sql, params)
        if self._transaction_depth == 0:
            await self._conn.commit()
        return cursor.rowcount

    async def write_many(self, sql: str, params_list: list[tuple]) -> int:
        """Execute multiple INSERT/UPDATE/DELETE statements.
        Must be called within a transaction context.
        Returns: rowcount
        """
        await self.connect()
        cursor = await self._conn.executemany(sql, params_list)
        if self._transaction_depth == 0:
            await self._conn.commit()
        return cursor.rowcount

    # Backward compatibility - may be removed in future
    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Legacy: executes any SQL. Prefer fetch_one/fetch_all for reads,
        write/write_many for writes inside transactions."""
        await self.connect()
        cursor = await self._conn.execute(sql, params)
        if self._transaction_depth == 0:
            keyword = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
            if keyword in {"CREATE", "INSERT", "UPDATE", "DELETE", "REPLACE", "ALTER", "DROP", "VACUUM", "REINDEX"}:
                await self._conn.commit()
        return cursor

    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        """Legacy: fetch one row. Prefer fetch_one."""
        await self.connect()
        async with self._conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """Legacy: fetch all rows. Prefer fetch_all."""
        await self.connect()
        async with self._conn.execute(sql, params) as cursor:
            return await cursor.fetchall()

    # --- Storage Helpers ---

    async def get_all(
        self,
        table: str,
        where: str = "",
        params: tuple = (),
        order_by: str = "",
        limit: int | None = None,
        columns: str = "*",
    ) -> list[dict]:
        """Get all rows from a table with optional filtering and ordering.

        Args:
            table: Table name
            where: WHERE clause (without "WHERE")
            params: Parameters for WHERE clause
            order_by: ORDER BY clause (without "ORDER BY")
            limit: LIMIT count
            columns: Columns to select (default "*")
        """
        await self.connect()
        sql = f"SELECT {columns} FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += f" LIMIT {limit}"

        async with self._conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_one(
        self,
        table: str,
        where: str,
        params: tuple = (),
        columns: str = "*",
    ) -> dict | None:
        """Get a single row from a table."""
        rows = await self.get_all(table, where, params, columns=columns, limit=1)
        return rows[0] if rows else None

    async def get_or_create(
        self,
        table: str,
        where: str,
        params: tuple,
        defaults: dict | None = None,
    ) -> tuple[dict, bool]:
        """Get existing row or create new one.

        Returns:
            Tuple of (row_dict, created_boolean)
        """
        # Try to get existing
        row = await self.get_one(table, where, params)
        if row:
            return row, False

        # Create new
        if defaults is None:
            defaults = {}

        # Build insert from where params + defaults
        # Parse simple WHERE clauses like "id = ?" or "name = ? AND version = ?"
        insert_data = dict(defaults)
        # We can't easily parse WHERE, so user should provide full data in defaults
        # For safety, we'll just use defaults

        columns = list(insert_data.keys())
        placeholders = ", ".join(["?" for _ in columns])
        values = [insert_data[col] for col in columns]

        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        await self.execute(sql, tuple(values))
        await self._conn.commit()

        # Fetch the created row
        row = await self.get_one(table, where, params)
        return row, True

    async def bulk_insert(
        self,
        table: str,
        rows: list[dict],
        columns: list[str] | None = None,
    ) -> int:
        """Bulk insert multiple rows.

        Args:
            table: Table name
            rows: List of dicts with column->value
            columns: Optional column order (default: keys of first row)

        Returns:
            Number of rows inserted
        """
        if not rows:
            return 0

        if columns is None:
            columns = list(rows[0].keys())

        placeholders = ", ".join(["?" for _ in columns])
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

        await self.connect()
        params_list = [tuple(row.get(col) for col in columns) for row in rows]
        await self._conn.executemany(sql, params_list)
        await self._conn.commit()

        return len(rows)

    async def upsert(
        self,
        table: str,
        row: dict,
        conflict_columns: list[str],
        update_columns: list[str] | None = None,
    ) -> dict:
        """Insert or update a row (UPSERT).

        Args:
            table: Table name
            row: Row data as dict
            conflict_columns: Columns that define uniqueness (for ON CONFLICT)
            update_columns: Columns to update on conflict (default: all except conflict)

        Returns:
            The row after upsert
        """
        columns = list(row.keys())
        placeholders = ", ".join(["?" for _ in columns])

        if update_columns is None:
            update_columns = [c for c in columns if c not in conflict_columns]

        update_clause = ", ".join([f"{col}=excluded.{col}" for col in update_columns])
        conflict_clause = ", ".join(conflict_columns)

        sql = f"""
            INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})
            ON CONFLICT({conflict_clause}) DO UPDATE SET {update_clause}
        """

        await self.execute(sql, tuple(row[col] for col in columns))
        await self._conn.commit()

        # Fetch the row
        where = " AND ".join([f"{col} = ?" for col in conflict_columns])
        params = tuple(row[col] for col in conflict_columns)
        return await self.get_one(table, where, params)


_db_instance: Database | None = None


def get_db_instance() -> Database:
    """Get the global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


async def set_db_path(db_path: Path) -> None:
    """Set the database path for testing. Closes existing connection."""
    global _db_instance
    if _db_instance:
        await _db_instance.close()
    _db_instance = Database(db_path)


# Backward compatibility
class _DatabaseProxy:
    def __getattr__(self, name):
        return getattr(get_db_instance(), name)

db = _DatabaseProxy()


async def get_db() -> Database:
    """Dependency injection helper."""
    return get_db_instance()
