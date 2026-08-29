"""
PAW Phase 10 — Integration Test: Context Stress Gate (B10)

Real-SQLite stress test:
- 100 memories
- 100 knowledge chunks
- 50 skills
Verify budgets respected, skills/evidence integrated, explain mode works.
"""

from __future__ import annotations

import json
import time

import pytest

from paw.core.context_compiler import ContextCompiler, ContextPlan
from paw.core.context import ContextBudget
from paw.core.storage import db, set_db_path
from paw.core.skills import SkillFabric, SkillManifest
from paw.core.models import SkillRisk, Capability


@pytest.mark.asyncio
async def test_b10_context_stress_real_sqlite(tmp_path):
    """B10: 100 memories + 100 knowledge + 50 skills with real SQLite."""
    # Setup temp DB
    test_paw_home = tmp_path / ".paw"
    test_paw_home.mkdir(parents=True, exist_ok=True)
    db_path = test_paw_home / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    # --- Seed 100 memories ---
    memory_rows = []
    for i in range(100):
        memory_rows.append((
            f"mem-{i:03d}",
            "semantic",
            f"Memory number {i} about context compilation and tokens",
            json.dumps({"index": i, "tags": ["memory", f"tag-{i % 5}"]}),
            "project-b10",
            None,
            0.5,
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            i % 10,
        ))
    await db.write_many(
        """
        INSERT INTO memory_records
        (id, memory_type, content, metadata, project_id, task_id, confidence, created_at, updated_at, last_accessed, access_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        memory_rows,
    )

    # --- Seed 50 skills ---
    skill_rows = []
    for i in range(50):
        skill_rows.append((
            f"skill-{i:03d}",
            f"skill_{i}",
            "1.0.0",
            f"Skill {i} description",
            "testing",
            json.dumps([Capability.FILESYSTEM_READ.value]),
            SkillRisk.LOW.value,
            0,
            0,
            f"trigger-{i}",
            f"# Skill {i}\n\nBody for skill {i}.",
            "installed",
            1,
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            json.dumps(["local"]),
            json.dumps([]),
            json.dumps({}),
        ))
    await db.write_many(
        """
        INSERT INTO skills
        (id, name, version, description, category, capabilities, risk,
         network, write, trigger, body, source, enabled, created_at, updated_at, executors, dependencies, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        skill_rows,
    )

    # --- Seed 100 knowledge chunks ---
    knowledge_rows = []
    source_id = "src-b10"
    for i in range(100):
        knowledge_rows.append((
            f"chunk-{i:03d}",
            source_id,
            f"Knowledge content {i} about PAW runtime context and evidence.",
            i * 100,
            i * 100 + 80,
            json.dumps({"chunk_index": i}),
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ))
    await db.write_many(
        """
        INSERT INTO knowledge_chunks
        (id, source_id, content, span_start, span_end, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        knowledge_rows,
    )

    # --- Compile context ---
    compiler = ContextCompiler()
    budget = ContextBudget(max_tokens=2000, max_fragments=20, max_sources=3)
    context, candidates = await compiler.compile(
        task_id="task-b10",
        query="context compilation tokens",
        session_id=None,
        budget=budget,
        explain_mode=True,
    )

    # --- Verify stress behavior ---
    assert context is not None
    assert len(candidates) > 0

    # Budget must be respected: selected fragments must fit budget
    selected = [c for c in candidates if c.metadata.get("included")]
    assert len(selected) <= budget.max_fragments

    # Sources limited
    sources_used = {c.source for c in selected}
    assert len(sources_used) <= budget.max_sources

    # Explain mode should produce report
    from paw.core.context_compiler import format_explain_report
    excluded = [c for c in candidates if not c.metadata.get("included")]
    report = format_explain_report(selected, excluded)
    assert "INCLUDED" in report
    assert "EXCLUDED" in report


@pytest.mark.asyncio
async def test_b10_skills_evidence_integration(tmp_path):
    """Verify skills and knowledge evidence are integrated in candidate content."""
    test_paw_home = tmp_path / ".paw"
    test_paw_home.mkdir(parents=True, exist_ok=True)
    db_path = test_paw_home / "paw.db"
    await set_db_path(db_path)
    await db.initialize()

    # Seed one skill
    await db.execute(
        """
        INSERT INTO skills
        (id, name, version, description, category, capabilities, risk,
         network, write, trigger, body, source, enabled, created_at, updated_at, executors, dependencies, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "skill-evidence",
            "evidence_skill",
            "1.0.0",
            "Evidence integration skill",
            "testing",
            json.dumps([Capability.FILESYSTEM_READ.value]),
            SkillRisk.LOW.value,
            0,
            0,
            "evidence",
            "# Evidence Skill\n\nIntegrates evidence.",
            "installed",
            1,
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            json.dumps(["local"]),
            json.dumps([]),
            json.dumps({}),
        ),
    )

    # Seed one knowledge chunk
    await db.execute(
        """
        INSERT INTO knowledge_chunks
        (id, source_id, content, span_start, span_end, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "chunk-evidence",
            "src-evidence",
            "Evidence content for integration test.",
            0,
            120,
            json.dumps({}),
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )

    compiler = ContextCompiler()
    context, candidates = await compiler.compile(
        task_id="task-evidence",
        query="evidence integration",
        explain_mode=True,
    )

    skill_candidates = [c for c in candidates if c.source == "skill"]
    knowledge_candidates = [c for c in candidates if c.source == "knowledge"]

    assert len(skill_candidates) >= 1
    assert len(knowledge_candidates) >= 1