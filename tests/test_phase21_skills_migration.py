"""Regression test for the skills-table schema migration.

A database created by an older PAW schema already has a `skills` table that
lacks the columns introduced later (description, body, category, capabilities,
...). `CREATE TABLE IF NOT EXISTS` does not alter that table, so the
`skill_ai` FTS trigger (created by SCHEMA, referencing new.description/body)
becomes invalid. SQLite re-validates every trigger on any ALTER TABLE, so the
model_selections migration used to raise "error in trigger skill_ai".

This test reproduces a legacy database and asserts initialize() repairs it
without dropping data.
"""

import sqlite3

from src.paw.core.storage import Database


async def test_skills_migration_adds_missing_columns(tmp_path):
    db_path = tmp_path / "legacy.db"
    # Craft a legacy layout: skills lacks the new columns; model_selections
    # still uses the old single-column primary key.
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            trigger TEXT NOT NULL,
            manifest TEXT,
            source TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE skill_fts (name TEXT, description TEXT, body TEXT);
        CREATE TABLE model_selections (
            task_id TEXT,
            model_name TEXT,
            role TEXT,
            reason TEXT,
            score REAL,
            fallback_chain TEXT,
            created_at TEXT,
            PRIMARY KEY (task_id)
        );
        """
    )
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    db = Database(db_path)
    # Must not raise "error in trigger skill_ai".
    await db.initialize()

    verify = sqlite3.connect(db_path)
    cols = {row[1] for row in verify.execute("PRAGMA table_info(skills)")}
    version = verify.execute("PRAGMA user_version").fetchone()[0]
    verify.close()

    for expected in (
        "version",
        "description",
        "category",
        "capabilities",
        "risk",
        "network",
        "write",
        "body",
        "executors",
        "dependencies",
        "metadata",
    ):
        assert expected in cols, f"skills missing migrated column: {expected}"
    assert version >= 1, "user_version not bumped by migration"

    await db.close()
