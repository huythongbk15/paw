"""
PAW — Phase 13: Enhanced Context Builder

Two concrete enhancements over the base ContextCompiler:
1. Cross-source near-duplicate detection in ``_deduplicate`` (lexical Jaccard,
   upgraded to embedding cosine when a provider is configured) so redundant
   fragments from memory/knowledge/skills don't waste budget.
2. Progressive skill disclosure: selected Level-0 skill candidates are upgraded
   to Level 1 (skill body loaded) so the context carries actionable instructions.

Plus explain metadata (excluded_reason / duplicate_similarity / body_loaded).
"""

from __future__ import annotations

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCompiler, ContextCandidate
from paw.core.skills import Skill, SkillManifest, SkillRisk, Capability
from paw.core.storage import db, set_db_path


# --- Stub embedding provider (controlled vectors, for semantic dedup) ---


class StubDedupProvider:
    name = "stub"

    def __init__(self, table: dict[str, list[float]]):
        self._table = table

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._table.get(t, [0.0, 0.0]) for t in texts]


# --- Helpers ---


def _cand(source, source_id, content, relevance=0.5, priority=0.2):
    return ContextCandidate(
        source=source,
        source_id=source_id,
        content=content,
        relevance_score=relevance,
        priority=priority,
        token_estimate=len(content.split()),
    )


# --- Dedup (lexical) ---


async def test_dedup_removes_exact_same_source_id():
    compiler = ContextCompiler(budget=ContextBudget())
    cands = [
        _cand("memory", "m1", "identical text", relevance=0.9, priority=0.25),
        _cand("memory", "m1", "identical text", relevance=0.4, priority=0.25),
    ]
    kept = await compiler._deduplicate(cands)
    assert len(kept) == 1
    assert kept[0].relevance_score == 0.9


async def test_dedup_drops_cross_source_near_duplicate():
    compiler = ContextCompiler(budget=ContextBudget())
    cands = [
        _cand("memory", "m1", "the build failed due to missing dependency numpy",
              relevance=0.8, priority=0.25),
        _cand("knowledge", "k1", "the build failed due to missing dependency numpy",
              relevance=0.7, priority=0.2),
    ]
    kept = await compiler._deduplicate(cands)
    assert len(kept) == 1
    # memory has higher relevance*priority -> knowledge dropped
    assert kept[0].source_id == "m1"
    dropped = cands[1]
    assert dropped.metadata["excluded_reason"].startswith("duplicate_of:memory:m1")
    assert "duplicate_similarity" in dropped.metadata


async def test_dedup_keeps_distinct_content():
    compiler = ContextCompiler(budget=ContextBudget())
    cands = [
        _cand("memory", "m1", "the build failed due to missing dependency numpy",
              relevance=0.8, priority=0.25),
        _cand("knowledge", "k1", "python virtual environments isolate dependencies",
              relevance=0.7, priority=0.2),
    ]
    kept = await compiler._deduplicate(cands)
    assert len(kept) == 2


async def test_dedup_disabled_keeps_all():
    budget = ContextBudget(dedup_enabled=False)
    compiler = ContextCompiler(budget=budget)
    cands = [
        _cand("memory", "m1", "same text", relevance=0.8, priority=0.25),
        _cand("knowledge", "k1", "same text", relevance=0.7, priority=0.2),
    ]
    kept = await compiler._deduplicate(cands)
    assert len(kept) == 2


# --- Dedup (semantic via embedding provider) ---


async def test_dedup_semantic_detects_paraphrase():
    table = {
        "the cat sat on the mat": [1.0, 0.0],
        "a feline rested on the rug": [1.0, 0.0],  # near-identical vector -> dup
        "the moon orbits the earth": [0.0, 1.0],
    }
    compiler = ContextCompiler(
        budget=ContextBudget(), embedding_provider=StubDedupProvider(table)
    )
    cands = [
        _cand("memory", "m1", "the cat sat on the mat", relevance=0.8, priority=0.25),
        _cand("knowledge", "k1", "a feline rested on the rug", relevance=0.7, priority=0.2),
        _cand("memory", "m2", "the moon orbits the earth", relevance=0.6, priority=0.25),
    ]
    kept = await compiler._deduplicate(cands)
    # paraphrase pair collapsed; unrelated moon fact kept
    assert len(kept) == 2
    ids = {c.source_id for c in kept}
    assert "m2" in ids
    assert "m1" in ids


# --- Progressive skill Level-1 upgrade ---


class FakeFabric:
    def __init__(self, skills_by_name: dict[str, Skill]):
        self._by_name = skills_by_name

    def list_skills(self, enabled_only: bool = True):
        return [s.manifest for s in self._by_name.values()]

    def get_skill(self, name: str):
        return self._by_name.get(name)


def _skill_with_body(name: str, body: str) -> Skill:
    manifest = SkillManifest(
        name=name,
        description=f"{name} does something useful",
        category="coding",
        capabilities=[Capability("filesystem.read")],
        risk=SkillRisk.LOW,
        body=body,
    )
    return Skill(manifest)


@pytest.mark.asyncio
async def test_progressive_skill_level1_upgrade(tmp_path, monkeypatch):
    paw_home = tmp_path / ".paw"
    paw_home.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_home / "paw.db")
    await db.initialize()

    body = "STEPS:\n1. stage changes\n2. commit with message\n3. push to remote"
    skill = _skill_with_body("git_commit", body)
    fab = FakeFabric({"git_commit": skill})

    import paw.core.context_compiler as cc

    async def _fake():
        return fab

    monkeypatch.setattr(cc, "get_skill_fabric", _fake)

    compiler = ContextCompiler(budget=ContextBudget())
    cand = _cand("skill", "git_commit", "git_commit does something useful",
                 relevance=0.9, priority=0.15)
    cand.skill_level = 0
    context = await compiler._build_context("t1", [cand], explain_mode=False)

    assert cand.skill_level == 1
    assert cand.metadata.get("body_loaded") is True
    assert body in cand.content
    assert context.fragments[0].content == body

    await db.close()


@pytest.mark.asyncio
async def test_progressive_skill_body_too_large_skipped(tmp_path, monkeypatch):
    paw_home = tmp_path / ".paw"
    paw_home.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_home / "paw.db")
    await db.initialize()

    big_body = "x" * 1000
    skill = _skill_with_body("big_skill", big_body)
    fab = FakeFabric({"big_skill": skill})

    import paw.core.context_compiler as cc

    async def _fake():
        return fab

    monkeypatch.setattr(cc, "get_skill_fabric", _fake)

    # max_content_length small so body is rejected
    compiler = ContextCompiler(budget=ContextBudget(max_content_length=100))
    cand = _cand("skill", "big_skill", "big_skill does something",
                 relevance=0.9, priority=0.15)
    cand.skill_level = 0
    await compiler._build_context("t1", [cand], explain_mode=False)

    assert cand.skill_level == 0  # not upgraded
    assert cand.metadata.get("body_skipped") == "exceeds_max_content_length"
    assert cand.metadata.get("body_loaded") is not True

    await db.close()
