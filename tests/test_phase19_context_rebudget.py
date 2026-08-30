"""
Phase 19 #2 — ContextCompiler progressive skill L0->L1 re-budgets final payload.

After a selected Level-0 skill is upgraded to Level 1 (its body loaded),
the assembled context must still respect ``ContextBudget.max_tokens``. The
fix re-allocates the budget on the upgraded ``selected`` set and drops the
lowest-priority survivors so the final payload never exceeds the budget.
"""

from __future__ import annotations

import pytest

import paw.core.context_compiler as cc
from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCompiler, ContextCandidate
from paw.core.skills import Skill, SkillManifest


def _cand(source, source_id, content, relevance=0.5, priority=0.2, token_estimate=None):
    return ContextCandidate(
        source=source,
        source_id=source_id,
        content=content,
        relevance_score=relevance,
        priority=priority,
        token_estimate=token_estimate if token_estimate is not None else len(content.split()),
    )


def _make_skill(body: str) -> Skill:
    return Skill(
        manifest=SkillManifest(
            name="S1",
            description="demo skill",
            category="coding",
            body=body,
        )
    )


class _FakeFabric:
    def __init__(self, skill):
        self._skill = skill

    def get_skill(self, sid):
        return self._skill


async def _fake_get_skill_fabric(skill):
    return _FakeFabric(skill)


async def _run(compiler, skill, selected, monkeypatch):
    monkeypatch.setattr(
        cc, "get_skill_fabric", lambda: _fake_get_skill_fabric(skill), raising=False
    )
    excluded: list[ContextCandidate] = []
    ctx = await compiler._build_context("t1", selected, excluded, False)
    total = sum(compiler._token_estimator.estimate(f.content) for f in ctx.fragments)
    return ctx, excluded, total


async def test_skill_upgrade_rebudgets_when_over_budget(monkeypatch):
    # Skill body (~160 tokens) fits alone, but not together with all 5 memories
    # (~40 tokens each). Budget = 200 -> skill + only 1 memory should survive.
    skill = _make_skill("token " * 80)
    budget = ContextBudget(
        max_tokens=200, max_content_length=2000, max_fragments=50, max_sources=10
    )
    compiler = ContextCompiler(budget=budget)
    selected = [_cand("skill", "s1", "meta", relevance=0.95, priority=0.9, token_estimate=1)]
    for i in range(5):
        selected.append(
            _cand("memory", f"m{i}", "mem " * 30, relevance=0.2, priority=0.1, token_estimate=40)
        )

    ctx, excluded, total = await _run(compiler, skill, selected, monkeypatch)

    skill_cand = next(c for c in selected if c.source == "skill")
    assert skill_cand.metadata.get("body_loaded") is True
    assert skill_cand.skill_level == 1
    # Final payload respects the budget.
    assert total <= budget.max_tokens, total
    # Skill kept; lower-priority memories dropped to make room for the body.
    sources = [f.source for f in ctx.fragments]
    assert sources.count("skill") == 1
    assert sources.count("memory") == 1
    assert len(excluded) >= 4


async def test_skill_upgrade_no_drop_when_budget_fits(monkeypatch):
    skill = _make_skill("token " * 40)
    budget = ContextBudget(
        max_tokens=2000, max_content_length=4000, max_fragments=50, max_sources=10
    )
    compiler = ContextCompiler(budget=budget)
    selected = [_cand("skill", "s1", "meta", relevance=0.95, priority=0.9, token_estimate=1)]
    for i in range(5):
        selected.append(
            _cand("memory", f"m{i}", "mem " * 20, relevance=0.5, priority=0.3, token_estimate=30)
        )

    ctx, excluded, total = await _run(compiler, skill, selected, monkeypatch)

    assert next(c for c in selected if c.source == "skill").metadata.get("body_loaded") is True
    assert total <= budget.max_tokens, total
    # Everything fits, nothing re-dropped.
    assert len(ctx.fragments) == 6
    assert len(excluded) == 0
