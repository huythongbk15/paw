"""
PAW — Advanced Semantic Skill Selector (Phase 11 deferred item, Phase 12 pattern)

Hybrid (lexical + semantic embedding) skill selection, reusing the
``embeddings`` + ``AdvancedMemoryRetriever`` pattern. Verifies:
- lexical-only degradation (no provider)
- hybrid re-ranking with controlled embedding vectors
- graceful degradation when embedding provider fails
- ContextCompiler wires real relevance scores into skill candidates
"""

from __future__ import annotations

import asyncio

import pytest

from paw.core.embeddings import LocalEmbeddingProvider, cosine_similarity
from paw.core.semantic import AdvancedSkillResult, AdvancedSkillSelector
from paw.core.skills import SkillManifest, SkillRisk, Capability
from paw.core.storage import db, set_db_path


# --- Fake fabric (selector only needs list_skills + skill.manifest) ---


class FakeFabric:
    def __init__(self, skills: list[SkillManifest]):
        self._skills = skills

    def list_skills(self, enabled_only: bool = True) -> list[SkillManifest]:
        if enabled_only:
            return [s for s in self._skills if s.enabled]
        return list(self._skills)


def _skill(name: str, description: str, trigger: str = "", category: str = "general",
           capabilities: list[str] | None = None) -> SkillManifest:
    return SkillManifest(
        name=name,
        description=description,
        trigger=trigger,
        category=category,
        capabilities=[Capability(c) for c in (capabilities or [])],
        risk=SkillRisk.LOW,
    )


# --- Stub embedding provider (controlled vectors) ---


class StubEmbeddingProvider:
    name = "stub"

    def __init__(self, table: dict[str, list[float]], query_vec: list[float]):
        self._table = table
        self._query_vec = query_vec

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            out.append(self._table.get(t, self._query_vec))
        return out


def _doc(manifest: SkillManifest) -> str:
    return AdvancedSkillSelector._skill_doc(manifest)


# --- Tests ---


@pytest.mark.asyncio
async def test_lexical_only_degradation():
    """No provider -> lexical (SemanticMatcher) ranking still works."""
    s_git = _skill("git_commit", "Commit changes to the repository", trigger="commit push")
    s_cook = _skill("cooking", "Prepare a meal recipe", trigger="cook")
    fabric = FakeFabric([s_git, s_cook])

    selector = AdvancedSkillSelector(fabric, embedding_provider=None)
    results = await selector.select("commit my changes to git", max_results=5)
    assert results
    assert all(not r.has_embedding for r in results)
    # git_commit must rank first (shared 'commit')
    assert results[0].manifest.name == "git_commit"


@pytest.mark.asyncio
async def test_hybrid_rerank_with_embeddings():
    """Semantic similarity must re-rank beyond lexical overlap."""
    s_loan = _skill("loan_calc", "Amortization schedule and APR computation", trigger="loan")
    s_book = _skill("book_rec", "Recommend a good novel to read", trigger="book")
    fabric = FakeFabric([s_loan, s_book])

    # Query vector close to s_loan's doc, far from s_book's
    qvec = [1.0, 0.0]
    table = {
        _doc(s_loan): [0.9, 0.1],
        _doc(s_book): [0.0, 1.0],
    }
    stub = StubEmbeddingProvider(table, qvec)
    selector = AdvancedSkillSelector(fabric, embedding_provider=stub, lexical_weight=0.5, semantic_weight=0.5)
    results = await selector.select("compute the interest rate on a mortgage", max_results=5, min_score=0.0)
    assert results
    assert results[0].has_embedding is True
    assert results[0].manifest.name == "loan_calc"
    by_name = {r.manifest.name: r for r in results}
    assert by_name["loan_calc"].semantic_score > by_name["book_rec"].semantic_score


@pytest.mark.asyncio
async def test_capability_filter():
    s_fs = _skill("read_file", "Read a file from disk", capabilities=["filesystem.read"])
    s_net = _skill("fetch_url", "Download a web page", capabilities=["network.http"])
    fabric = FakeFabric([s_fs, s_net])
    selector = AdvancedSkillSelector(fabric, embedding_provider=None)
    results = await selector.select("do something", requested_capabilities=["network.http"], min_score=0.0)
    assert [r.manifest.name for r in results] == ["fetch_url"]


@pytest.mark.asyncio
async def test_embedding_provider_failure_degrades():
    """If embed() raises, selection must still return lexical results."""
    s_a = _skill("alpha", "alpha task description")
    s_b = _skill("beta", "beta task description")
    fabric = FakeFabric([s_a, s_b])

    class BoomProvider:
        name = "boom"

        async def embed(self, texts):
            raise RuntimeError("embedding service down")

    selector = AdvancedSkillSelector(fabric, embedding_provider=BoomProvider())
    results = await selector.select("alpha", max_results=5)
    assert results
    assert all(not r.has_embedding for r in results)  # degraded to lexical


@pytest.mark.asyncio
async def test_local_embedding_provider_semantic_signal():
    """LocalEmbeddingProvider produces real vectors usable for skill ranking."""
    s_calc = _skill("calculator", "Arithmetic calculation and math evaluation")
    s_music = _skill("music_player", "Play songs from the library")
    fabric = FakeFabric([s_calc, s_music])

    provider = LocalEmbeddingProvider()
    selector = AdvancedSkillSelector(fabric, embedding_provider=provider, semantic_weight=0.7)
    results = await selector.select("evaluate the arithmetic expression", max_results=5)
    assert results
    assert results[0].has_embedding is True
    # 'calculator' shares 'arithmetic'/'calculation' tokens -> ranked first
    assert results[0].manifest.name == "calculator"


# --- ContextCompiler integration ---


@pytest.mark.asyncio
async def test_context_compiler_skill_relevance_scores(tmp_path, monkeypatch):
    """ContextCompiler must assign real (non-flat-0.5) relevance to skills."""
    paw_home = tmp_path / ".paw"
    paw_home.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_home / "paw.db")
    await db.initialize()

    fab = FakeFabric([
        _skill("git_commit", "Commit staged changes", trigger="commit"),
        _skill("cooking", "Cook a recipe", trigger="cook"),
    ])

    import paw.core.context_compiler as cc

    async def _fake_get():
        return fab

    monkeypatch.setattr(cc, "get_skill_fabric", _fake_get)

    from paw.core.context_compiler import ContextCompiler, ContextPlan

    compiler = ContextCompiler(embedding_provider=None)  # lexical advanced selector
    plan = ContextPlan(task_id="t1", query="commit my staged changes", token_budget=2000)
    candidates = await compiler._retrieve_skill_candidates(plan)
    assert candidates, "skill candidates should be produced"
    for c in candidates:
        assert "lexical_score" in c.metadata
        assert "semantic_score" in c.metadata
    top = max(candidates, key=lambda c: c.relevance_score)
    assert "commit" in top.source_id.lower() or top.source_id == "git_commit"

    await db.close()
