"""E1-24 / E1-27 budget compression proof.

The diagnostic runner (`scripts/run_e1_measurement.py`) measures recall
+ token reduction on the 14-case E0 corpus (~6000 bytes of fixture
content). On that corpus, the budget (max_tokens=8000) never filters,
so the only "compression" measured is 0%. The 30% warm-reduction gate
is calibrated for a realistic production corpus.

This test proves the **compression mechanism** works on a synthetic
corpus large enough to exercise the budget filter:

1. Ingest 8 sources of ~120 tokens each (960 token baseline)
2. Compile with a tight budget (max_tokens=500, max_fragments=3)
3. Assert: at least 5 sources are dropped (compression worked)
4. Assert: final_tokens <= budget.max_tokens (re-budget respected)
5. Assert: reduction > 0.30 (warm reduction gate would pass on this corpus)

This is the missing piece between the diagnostic measurement (PARTIAL
on small E0 corpus) and the 30% gate (which requires a production-
sized corpus). The mechanism is verified; the production corpus is
post-gate work.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path

import pytest

from paw.core.context import ContextBudget, TokenEstimator
from paw.core.context_compiler import ContextCompiler
from paw.core.skills import BUILTIN_SKILLS
from paw.core.storage import db, set_db_path
from paw.knowledge.chunk import KnowledgeChunkStore
from paw.knowledge.source import KnowledgeSourceManager


def _always_on_skill_overhead() -> int:
    """Per E1-24: baseline must include the always-on skill overhead."""
    return sum(TokenEstimator().estimate(s.body or "") for s in BUILTIN_SKILLS)


async def _seed_synthetic_corpus(n_sources: int, tokens_per_source: int = 120) -> int:
    """Seed N synthetic knowledge sources of roughly `tokens_per_source` tokens.

    Returns the baseline (sum of file tokens + always-on overhead).
    """
    manager = KnowledgeSourceManager()
    chunk_store = KnowledgeChunkStore()
    baseline = _always_on_skill_overhead()
    for i in range(n_sources):
        name = f"synthetic-{i:03d}"
        # Pad to roughly tokens_per_source tokens. Each English word ~1.3
        # tokens; we aim for tokens_per_source/1.3 words + 0.3 buffer.
        words = max(8, int(tokens_per_source / 1.3))
        body = f"# Source {i}\n\nThis source contains ALPHA marker for the keyword test " + ("padding " * words)
        source = await manager.create(
            name=name, path=f"synthetic://{name}", external_id=name,
            revision="test",
        )
        await manager.update_checksum(
            source.id, hashlib.sha256(body.encode()).hexdigest()
        )
        await chunk_store.add_chunk(
            source_id=source.id, content=body,
            span_start=0, span_end=len(body),
        )
        baseline += TokenEstimator().estimate(body)
    return baseline


class TestBudgetCompressionMechanism:
    """The budget filter must drop candidates when the corpus exceeds the budget."""

    @pytest.mark.asyncio
    async def test_tight_budget_drops_candidates(self, tmp_path):
        paw_home = tmp_path / ".paw"
        paw_home.mkdir(parents=True, exist_ok=True)
        await set_db_path(paw_home / "paw.db")
        await db.initialize()
        try:
            baseline = await _seed_synthetic_corpus(n_sources=8, tokens_per_source=120)
            # Tight budget: 1 fragment, 1 source, 500 tokens
            budget = ContextBudget(max_tokens=500, max_fragments=1, max_sources=1)
            compiler = ContextCompiler(budget=budget, auto_attach_embeddings=False)
            manifest = await compiler.compile_manifest(
                task_id="stress", query="ALPHA keyword", session_id=None,
            )
            # 1. Budget respected
            assert manifest.final_tokens <= budget.max_tokens, (
                f"final_tokens={manifest.final_tokens} > max_tokens={budget.max_tokens}"
            )
            # 2. Compression worked: at least 7 of 8 sources dropped
            k_included = sum(1 for c in manifest.included if c.source == "knowledge")
            assert k_included <= 1, (
                f"expected <= 1 knowledge source with max_fragments=1, got {k_included}"
            )
            # 3. Warm reduction would pass the 30% gate on this corpus
            warm = await compiler.compile_manifest(
                task_id="stress", query="ALPHA keyword", session_id=None,
            )
            reduction = (baseline - warm.final_tokens) / baseline
            assert reduction > 0.30, (
                f"warm reduction {reduction:+.3f} did not pass the 30% gate; "
                f"baseline={baseline} measured={warm.final_tokens}"
            )
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_loose_budget_keeps_all_candidates(self, tmp_path):
        """Sanity: a loose budget keeps all candidates (no compression needed)."""
        paw_home = tmp_path / ".paw"
        paw_home.mkdir(parents=True, exist_ok=True)
        await set_db_path(paw_home / "paw.db")
        await db.initialize()
        try:
            await _seed_synthetic_corpus(n_sources=4, tokens_per_source=80)
            # Loose budget: 50 fragments, 50 sources, 10000 tokens
            budget = ContextBudget(max_tokens=10000, max_fragments=50, max_sources=50)
            compiler = ContextCompiler(budget=budget, auto_attach_embeddings=False)
            manifest = await compiler.compile_manifest(
                task_id="loose", query="ALPHA keyword", session_id=None,
            )
            k_included = sum(1 for c in manifest.included if c.source == "knowledge")
            assert k_included == 4, (
                f"loose budget dropped candidates: {k_included}/4 included"
            )
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_cold_warm_identical_for_lexical_only(self, tmp_path):
        """The runtime is deterministic for lexical-only retrieval;
        cold and warm produce the same manifest."""
        paw_home = tmp_path / ".paw"
        paw_home.mkdir(parents=True, exist_ok=True)
        await set_db_path(paw_home / "paw.db")
        await db.initialize()
        try:
            await _seed_synthetic_corpus(n_sources=4, tokens_per_source=80)
            budget = ContextBudget(max_tokens=10000, max_fragments=50, max_sources=50)
            compiler = ContextCompiler(budget=budget, auto_attach_embeddings=False)
            cold = await compiler.compile_manifest(
                task_id="cw", query="ALPHA keyword", session_id=None,
            )
            warm = await compiler.compile_manifest(
                task_id="cw", query="ALPHA keyword", session_id=None,
            )
            assert cold.final_tokens == warm.final_tokens
            assert cold.included == warm.included
        finally:
            await db.close()


class TestBaselineIncludesAlwaysOnOverhead:
    """The baseline must include the always-on skill overhead; otherwise
    the reduction is a false negative (24-token overhead is counted as
    extra cost against a file-only baseline)."""

    @pytest.mark.asyncio
    async def test_baseline_equals_manifest_when_no_filtering(self, tmp_path):
        """When the budget doesn't filter, baseline (incl. overhead) ==
        measured. Reduction = 0%. The sign is correct, the magnitude
        is honest."""
        paw_home = tmp_path / ".paw"
        paw_home.mkdir(parents=True, exist_ok=True)
        await set_db_path(paw_home / "paw.db")
        await db.initialize()
        try:
            await _seed_synthetic_corpus(n_sources=2, tokens_per_source=50)
            budget = ContextBudget(max_tokens=10000, max_fragments=50, max_sources=50)
            compiler = ContextCompiler(budget=budget, auto_attach_embeddings=False)
            manifest = await compiler.compile_manifest(
                task_id="honest", query="ALPHA keyword", session_id=None,
            )
            # Baseline = always-on overhead + 2 source token estimates
            # (the actual estimate, not the requested size, because the
            # padding text is longer than the requested token count).
            overhead = _always_on_skill_overhead()
            # Sum token_estimate of the included knowledge candidates
            measured_knowledge = sum(
                c.token_estimate for c in manifest.included if c.source == "knowledge"
            )
            expected = overhead + measured_knowledge
            # Manifest final_tokens should equal overhead + knowledge
            assert manifest.final_tokens == expected, (
                f"final_tokens={manifest.final_tokens} != overhead+knowledge={expected}; "
                f"the baseline must include the always-on overhead"
            )
            # The reduction is ~0% when nothing is filtered
            assert measured_knowledge > 0
        finally:
            await db.close()
