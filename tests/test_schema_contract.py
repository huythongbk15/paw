"""
Schema Contract Tests — Verify database schema matches domain models.

These tests ensure the SQL schema in storage.py is compatible with
the Pydantic/dataclass models in models.py and skills.py.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from paw.core.models import ModelManifest, CapabilityManifest, CapabilityScore
from paw.core.skills import SkillManifest
from paw.core.storage import SCHEMA


def _get_table_columns(schema_sql: str, table_name: str) -> set[str]:
    """Extract column names from CREATE TABLE statement."""
    import re
    # Find the CREATE TABLE for the given table
    pattern = rf"CREATE TABLE IF NOT EXISTS {table_name}\s*\((.*?)\);"
    match = re.search(pattern, schema_sql, re.DOTALL | re.IGNORECASE)
    if not match:
        return set()

    columns_text = match.group(1)
    # Extract column names using regex to match column definitions
    # Each column definition: name TYPE [CONSTRAINTS]
    columns = set()
    # Split by lines, then parse each line
    for line in columns_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        # Remove trailing comma
        line = line.rstrip(",")
        # Column name is first word before space
        parts = line.split()
        if parts:
            col_name = parts[0].strip('"')
            if col_name not in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"):
                columns.add(col_name)
    return columns


def _get_virtual_table_columns(schema_sql: str, table_name: str) -> set[str]:
    """Extract column names from CREATE VIRTUAL TABLE statement."""
    import re
    pattern = rf"CREATE VIRTUAL TABLE IF NOT EXISTS {table_name}\s+USING\s+\w+\s*\((.*?)\);"
    match = re.search(pattern, schema_sql, re.DOTALL | re.IGNORECASE)
    if not match:
        return set()

    columns_text = match.group(1)
    columns = set()
    for part in columns_text.split(","):
        col = part.strip().split()[0].strip('"')
        columns.add(col)
    return columns


class TestSkillTableContract:
    """Verify skills table matches SkillManifest."""

    def test_skills_table_has_required_columns(self):
        """Skills table should have columns for SkillManifest fields."""
        columns = _get_table_columns(SCHEMA, "skills")

        # Core fields in new schema (body replaces manifest)
        required = {
            "id", "name", "version", "description", "category",
            "capabilities", "risk", "network", "write", "trigger",
            "body", "source", "enabled", "created_at", "updated_at", "executors",
            "dependencies", "metadata"
        }
        for col in required:
            assert col in columns, f"skills table missing column: {col}"

    def test_skills_table_matches_skillmanifest_fields(self):
        """All SkillManifest fields should be representable in the schema."""
        # SkillManifest fields should map to columns or manifest JSON
        columns = _get_table_columns(SCHEMA, "skills")

        # New schema has most fields as explicit columns
        manifest_fields_in_columns = {
            "name", "version", "description", "category", "capabilities",
            "risk", "network", "write", "trigger", "body",
            "source", "enabled", "executors", "dependencies", "metadata"
        }
        for field in manifest_fields_in_columns:
            assert field in columns, f"Schema missing column for {field}"

        # Dependencies and metadata are now explicit columns

    def test_skill_fts_exists(self):
        """skill_fts virtual table should exist for full-text search."""
        columns = _get_virtual_table_columns(SCHEMA, "skill_fts")
        assert "name" in columns
        assert "description" in columns
        assert "body" in columns


class TestModelRegistryContract:
    """Verify model_registry table matches ModelManifest."""

    def test_model_registry_has_required_columns(self):
        columns = _get_table_columns(SCHEMA, "model_registry")

        required = {
            "id", "name", "provider", "roles", "capabilities",
            "cost", "features", "max_context_tokens",
            "latency_tier", "enabled", "created_at", "updated_at"
        }
        for col in required:
            assert col in columns, f"model_registry missing column: {col}"

    def test_model_registry_matches_modelmanifest(self):
        """ModelRegistry columns should map to ModelManifest fields."""
        # Schema column -> ModelManifest field mapping
        mapping = {
            "name": "name",
            "provider": "provider",
            "roles": "roles",
            "capabilities": "model_capabilities",  # Schema uses 'capabilities', model uses 'model_capabilities'
            "cost": "cost",
            "features": "features",
            "max_context_tokens": "max_context_tokens",
            "latency_tier": "latency_tier",
            "enabled": "enabled",
        }

        columns = _get_table_columns(SCHEMA, "model_registry")
        for schema_col, model_field in mapping.items():
            assert schema_col in columns, f"Schema missing {schema_col} for model field {model_field}"


class TestCapabilityManifestContract:
    """Verify capability-related tables."""

    def test_executors_table_exists(self):
        columns = _get_table_columns(SCHEMA, "executors")
        required = {"id", "name", "capabilities", "metadata", "created_at", "updated_at"}
        for col in required:
            assert col in columns, f"executors table missing column: {col}"

    def test_executors_table_matches_capabilitymanifest(self):
        """Executors table should store CapabilityManifest."""
        columns = _get_table_columns(SCHEMA, "executors")
        # CapabilityManifest has: name, capabilities (dict), cost (dict), features (dict)
        # Schema stores: name, capabilities (JSON), metadata (JSON)
        assert "capabilities" in columns
        assert "metadata" in columns  # For cost and features


class TestTransactionSemantics:
    """Verify transaction and write semantics."""

    @pytest.mark.asyncio
    async def test_transaction_context_manager_works(self):
        """Database transaction context manager should work."""
        from paw.core.storage import Database
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            db = Database(db_path)
            await db.initialize()
            # Test transaction works
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO tasks (id, session_id, goal, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                                   ("test-1", "sess-1", "test", "pending", "2024-01-01", "2024-01-01"))
            # Verify committed
            row = await db.fetchone("SELECT * FROM tasks WHERE id = ?", ("test-1",))
            assert row is not None
            await db.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_upsert_method_exists(self):
        """Database should have upsert for idempotent writes."""
        from paw.core.storage import Database
        assert hasattr(Database, 'upsert')

    def test_bulk_insert_method_exists(self):
        """Database should have bulk_insert for batch writes."""
        from paw.core.storage import Database
        assert hasattr(Database, 'bulk_insert')


class TestForeignKeyConstraints:
    """Verify FK constraints are appropriate."""

    def test_skill_registry_fk_to_skills(self):
        """skill_registry should reference skills."""
        import re
        # Check for FK in skill_registry
        pattern = r"CREATE TABLE IF NOT EXISTS skill_registry\s*\((.*?)\);"
        match = re.search(pattern, SCHEMA, re.DOTALL | re.IGNORECASE)
        assert match is not None
        table_def = match.group(1)
        assert "FOREIGN KEY (skill_id) REFERENCES skills(id)" in table_def

    def test_memory_task_map_fk(self):
        """memory_task_map should reference memory_records."""
        import re
        pattern = r"CREATE TABLE IF NOT EXISTS memory_task_map\s*\((.*?)\);"
        match = re.search(pattern, SCHEMA, re.DOTALL | re.IGNORECASE)
        assert match is not None
        table_def = match.group(1)
        assert "FOREIGN KEY (memory_id) REFERENCES memory_records(id)" in table_def

    def test_knowledge_chunks_fk_removed(self):
        """knowledge_chunks should NOT have FK to knowledge_sources (removed for test isolation)."""
        import re
        pattern = r"CREATE TABLE IF NOT EXISTS knowledge_chunks\s*\((.*?)\);"
        match = re.search(pattern, SCHEMA, re.DOTALL | re.IGNORECASE)
        assert match is not None
        table_def = match.group(1)
        # Should NOT have FK constraint (per archived state decision)
        assert "FOREIGN KEY" not in table_def


class TestIndexesExist:
    """Verify important indexes exist."""

    def test_tasks_indexes(self):
        import re
        # Check for indexes on tasks
        idx_session = "CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)"
        idx_status = "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
        assert idx_session in SCHEMA
        assert idx_status in SCHEMA

    def test_memory_indexes(self):
        import re
        idx_type = "CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_records(memory_type)"
        idx_project = "CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_records(project_id)"
        idx_created = "CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_records(created_at)"
        idx_task = "CREATE INDEX IF NOT EXISTS idx_memory_task ON memory_records(task_id)"
        for idx in [idx_type, idx_project, idx_created, idx_task]:
            assert idx in SCHEMA, f"Missing index: {idx}"

    def test_knowledge_chunks_index(self):
        assert "CREATE INDEX IF NOT EXISTS idx_chunks_source ON knowledge_chunks(source_id)" in SCHEMA


class TestModelRoundtrip:
    """Test model -> JSON -> schema column roundtrip."""

    def test_modelmanifest_to_schema(self):
        """ModelManifest can be serialized for model_registry columns."""
        manifest = ModelManifest(
            name="test-model",
            provider="ollama",
            roles=["fast", "reasoning"],
            model_capabilities={"reasoning": 8.0, "coding": 7.0},
            cost={"compute": "low", "monetary": "free"},
            features={"streaming": True, "local": True},
            max_context_tokens=8192,
            latency_tier="low",
        )
        # Serialize for each column
        data = manifest.model_dump()
        roles_json = json.dumps(data["roles"])
        capabilities_json = json.dumps(data["model_capabilities"])
        cost_json = json.dumps(data["cost"])
        features_json = json.dumps(data["features"])

        assert isinstance(roles_json, str)
        assert isinstance(capabilities_json, str)
        assert isinstance(cost_json, str)
        assert isinstance(features_json, str)

    def test_skillmanifest_to_schema(self):
        """SkillManifest can be serialized for skills table."""
        manifest = SkillManifest(
            name="test-skill",
            version="1.0.0",
            description="Test skill",
            category="coding",
            capabilities=[],
            risk="low",
            network=False,
            write=False,
            trigger="test",
            body="body content",
            source="installed",
            enabled=True,
            dependencies=[],
            executors=["local"],
        )
        data = manifest.to_dict()
        manifest_json = json.dumps(data)
        assert isinstance(manifest_json, str)
        parsed = json.loads(manifest_json)
        assert parsed["name"] == "test-skill"

    def test_capabilitymanifest_to_schema(self):
        """CapabilityManifest can be serialized for executors table."""
        manifest = CapabilityManifest(
            name="test-executor",
            capabilities={"filesystem.read": 10.0, "shell.execute": 8.0},
            cost={"compute": "low", "monetary": "free"},
            features={"local": True},
        )
        data = manifest.model_dump()
        caps_json = json.dumps(data["capabilities"])
        metadata_json = json.dumps({"cost": data["cost"], "features": data["features"]})
        assert isinstance(caps_json, str)
        assert isinstance(metadata_json, str)


class TestSchemaInitialization:
    """Test schema can be initialized without errors."""

    @pytest.mark.asyncio
    async def test_schema_initializes(self):
        """Full schema should initialize without errors."""
        from paw.core.storage import Database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            db = Database(db_path)
            await db.initialize()
            await db.close()

            # Verify tables exist
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            required_tables = {
                "tasks", "task_nodes", "task_graphs", "task_dependencies",
                "task_events", "executors", "skills", "skill_registry",
                "skill_fts", "sessions", "model_registry", "model_selections",
                "identity", "plans", "policy_rules", "memory_records",
                "memory_fts", "memory_task_map", "knowledge_sources",
                "knowledge_chunks", "evidence", "citations"
            }
            for table in required_tables:
                assert table in tables, f"Table {table} not created"
        finally:
            db_path.unlink(missing_ok=True)


class TestNoProhibitedDependencies:
    """Verify no prohibited dependencies in schema."""

    def test_no_qwenpaw_in_schema(self):
        assert "qwenpaw" not in SCHEMA.lower()

    def test_no_deepseek_in_schema(self):
        assert "deepseek" not in SCHEMA.lower()

    def test_no_notebooklm_in_schema(self):
        assert "notebooklm" not in SCHEMA.lower()

    def test_no_antigravity_in_schema(self):
        assert "antigravity" not in SCHEMA.lower()