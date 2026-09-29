"""Exact lexical evidence must survive semantic re-ranking.

The 2026-09-29 foreign-corpus measurement produced a real regression: enabling
the hybrid re-rank (real `nomic-embed-text`) *lowered* required-evidence recall
on `textdistance`. ``counter_helpers`` went 1.00 -> 0.33 and ``edit_family``
1.00 -> 0.67, while ``min_recall`` stayed 0.00 either way. A change that is
nominally "better" made verified recall worse, which is the Charter's
quality-preserving-optimization invariant failing in the retrieval path.

The mechanism is not yet established. Dedup configuration was byte-identical
across both runs, so it is not the discriminating factor. What is established is
the *shape* of the risk: a query containing an exact identifier should still
retrieve the chunk that defines it, whichever ranking path runs.

These tests pin that invariant on a purpose-built in-repo fixture whose shape
reproduces the measured corpus: one class contributing many near-identical
method chunks, plus a distinctive method the query names exactly. Two arms are
compiled -- lexical-only and with a deterministic local embedding provider --
and the exact evidence must survive both.

The fixture is deliberately small and synthetic so the test is hermetic and
deterministic. It is a guard, not a replacement for the foreign-corpus
measurement: it protects the invariant in CI, where /tmp corpora and a local
Ollama server are not available.
"""

from __future__ import annotations

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCompiler
from paw.core.embeddings import LocalEmbeddingProvider
from paw.core.storage import db
from paw.knowledge.chunk import KnowledgeChunkStore
from paw.knowledge.source import KnowledgeSourceManager

# The distinctive method the query names exactly.
TARGET_EVIDENCE = "def _prepare_counters(self, *sequences)"
# A second exact identifier, to catch a guard that only checks the first hit.
SECOND_EVIDENCE = "def _intersect_counters(self, *counters)"

# Many methods under one class, so most chunks share the same owner header --
# the shape that produced 18 of 23 identical "# owner: Base" first lines in the
# real measurement.
CLASS_BODY = "".join(
    f'''
    def _method_{index:02d}(self, *args: int) -> int:
        """Routine {index} that returns a deterministic value."""
        return sum(args) + {index}
'''
    for index in range(24)
)

SOURCE_TEXT = f'''class Base:
    """Shared base with many small helpers."""

    def _get_counters(self, *sequences):
        return [list(sequence) for sequence in sequences]

    def _intersect_counters(self, *counters):
        shared = set(counters[0])
        for counter in counters[1:]:
            shared &= set(counter)
        return shared

    def _prepare_counters(self, *sequences):
        counters = self._get_counters(*sequences)
        return counters, self._intersect_counters(*counters)
{CLASS_BODY}'''


async def _ingest() -> None:
    sources = KnowledgeSourceManager()
    chunks = KnowledgeChunkStore()
    source = await sources.create(
        name="synthetic/base.py",
        path="synthetic/base.py",
        external_id="synthetic/base.py",
        revision="synthetic",
    )
    # One chunk per top-level symbol plus one per method, mirroring the
    # production chunker closely enough to reproduce the owner-header shape.
    lines = SOURCE_TEXT.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("def "):
            body = "\n".join(lines[index:index + 3])
            await chunks.add_chunk(
                source_id=source.id,
                content=f"# owner: Base\n{body}",
                span_start=index + 1,
                span_end=index + 3,
                metadata={"file": "synthetic/base.py"},
            )


async def _compile(provider):
    compiler = ContextCompiler(
        budget=ContextBudget(max_tokens=4000, max_fragments=12, max_sources=5),
        auto_attach_embeddings=False,
        embedding_provider=provider,
    )
    return await compiler.compile_manifest(
        "task-exact-evidence",
        "Find the helper that prepares counters and computes their intersection "
        "on the shared Base class.",
    )


def _included_text(manifest) -> str:
    return "\n".join(item.content for item in manifest.included)


@pytest.fixture(autouse=True)
async def _corpus():
    await _ingest()
    yield


class TestExactEvidenceSurvives:
    @pytest.mark.asyncio
    async def test_lexical_only_arm_keeps_the_exact_identifier(self):
        manifest = await _compile(None)
        text = _included_text(manifest)
        assert TARGET_EVIDENCE in text
        assert SECOND_EVIDENCE in text

    @pytest.mark.asyncio
    async def test_embedding_arm_keeps_the_exact_identifier(self):
        """The regression this guards: the hybrid arm lost exact evidence."""
        manifest = await _compile(LocalEmbeddingProvider())
        text = _included_text(manifest)
        assert TARGET_EVIDENCE in text, (
            "semantic re-ranking dropped the chunk defining the exact "
            "identifier the query named"
        )
        assert SECOND_EVIDENCE in text

    @pytest.mark.asyncio
    async def test_embedding_arm_is_not_worse_than_lexical_only(self):
        """The invariant: re-ranking may not reduce exact-lexical evidence."""
        lexical = _included_text(await _compile(None))
        embedded = _included_text(await _compile(LocalEmbeddingProvider()))
        for evidence in (TARGET_EVIDENCE, SECOND_EVIDENCE):
            assert (evidence in embedded) >= (evidence in lexical), (
                f"embedding arm lost exact evidence present in the lexical arm: {evidence}"
            )


class TestGuardIsNotVacuous:
    """A guard that cannot fail is worse than no guard."""

    @pytest.mark.asyncio
    async def test_the_two_arms_are_not_trivially_identical(self):
        """The fixture must actually exercise the ranking interaction."""
        lexical = await _compile(None)
        embedded = await _compile(LocalEmbeddingProvider())
        assert len(lexical.included) > 0, "fixture produced no context at all"
        scores_lex = [round(item.relevance_score, 6) for item in lexical.included]
        scores_emb = [round(item.relevance_score, 6) for item in embedded.included]
        assert scores_lex != scores_emb, (
            "lexical and embedding arms scored identically, so this fixture "
            "would not have caught a re-ranking regression"
        )
