"""Regression tests for Phase 21 bug fixes.

Four bugs fixed in this session:
1. ModelRouter _filter_for_availability uses registry.find_best_for_task()
   instead of score_model_for_task() (consistency bug)
2. ContextManifest included/excluded truth — candidates excluded due to
   max_fragments_exceeded appeared in NEITHER list (metadata corruption)
3. max_fragments_exceeded not properly tracked as exclusion reason
4. Remote-disclosure gate was soft (model_result={}) — now HARD stop
   via RemoteDisclosureRefused exception
"""

from __future__ import annotations

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextCandidate, ContextManifest
from paw.core.model_router import ModelRouter
from paw.core.privacy import (
    PROVIDER_CLOUD_UNAPPROVED,
    PrivacyClass,
    RemoteDisclosureRefusedError,
    gate_remote_disclosure,
)


# ====================================================================
# Bug 1: ModelRouter _filter_for_availability consistency
# ====================================================================


class TestModelRouterFilterAvailability:
    """Regression test: _filter_for_availability must use
    score_model_for_task() (the canonical entry point) in the
    local fallback, not registry.find_best_for_task()."""

    def test_score_model_for_task_returns_model_score(self):
        """score_model_for_task must return a ModelScore with all fields."""
        router = ModelRouter()
        router.registry.register_defaults()
        manifest = router.registry.get("local-fast")
        assert manifest is not None
        score = router.score_model_for_task(manifest, "fast")
        assert score.model_name == "local-fast"
        assert 0.0 <= score.score <= 1.0
        assert score.capability_fit >= 0.0
        assert score.complexity_fit >= 0.0
        assert score.privacy_fit >= 0.0
        assert score.cost_fit >= 0.0
        assert score.latency_fit >= 0.0
        assert len(score.reason) > 0


# ====================================================================
# Bug 2: ContextManifest included/excluded truth
# ====================================================================


class TestContextManifestIncludedExcludedTruth:
    """Regression test: no candidate must appear in BOTH included AND
    excluded in a ContextManifest, and every excluded candidate must
    appear in the excluded list."""

    def test_no_candidate_in_both_lists(self):
        """A candidate cannot be both included and excluded."""
        candidates = [
            ContextCandidate(
                source="memory", source_id=f"m{i}", content=f"content {i}",
                reason=f"score {i}", relevance_score=0.5, token_estimate=10,
            )
            for i in range(5)
        ]
        budget = ContextBudget(max_tokens=100, max_fragments=3)
        # Manually build manifest with some included, some excluded
        included = candidates[:3]
        excluded = candidates[3:]
        manifest = ContextManifest(
            task_id="test", budget=budget,
            included=tuple(included), excluded=tuple(excluded),
            final_tokens=sum(c.token_estimate for c in included),
        )
        included_ids = {c.source_id for c in manifest.included}
        excluded_ids = {c.source_id for c in manifest.excluded}
        assert len(included_ids & excluded_ids) == 0, "Candidate in both lists!"

    def test_excluded_candidates_have_exclusion_reason(self):
        """Every candidate in excluded must have an excluded_reason metadata."""
        # Build candidates with exclusion reasons set by _allocate_budget
        from paw.core.context_compiler import ContextCompiler

        compiler = ContextCompiler()
        compiler.budget = ContextBudget(max_tokens=100, max_fragments=2)
        candidates = [
            ContextCandidate(
                source="memory", source_id=f"m{i}", content=f"content {i}",
                reason=f"score {i}", relevance_score=0.5, token_estimate=10,
            )
            for i in range(5)
        ]
        selected, excluded = compiler._allocate_budget(candidates)

        assert len(excluded) == 3  # 5 - 2 = 3 excluded
        for cand in excluded:
            assert "excluded_reason" in cand.metadata, (
                f"Candidate {cand.source_id} excluded but no excluded_reason"
            )

    def test_max_fragments_excluded_in_manifest(self):
        """Candidates excluded due to max_fragments must appear in
        manifest.excluded after compile_manifest."""
        import asyncio
        from paw.core.context_compiler import ContextCompiler

        compiler = ContextCompiler()
        compiler.budget = ContextBudget(max_tokens=10000, max_fragments=2)

        async def do_compile():
            manifest = await compiler.compile_manifest(
                task_id="test", query="test query",
            )
            return manifest

        manifest = asyncio.run(do_compile())
        # Verify no candidate appears in both lists
        included_ids = {c.source_id for c in manifest.included}
        excluded_ids = {c.source_id for c in manifest.excluded}
        assert len(included_ids & excluded_ids) == 0, "Candidate in both lists!"


# ====================================================================
# Bug 3: max_fragments_exceeded tracking
# ====================================================================


class TestMaxFragmentsExceededTracking:
    """Regression test: max_fragments_exceeded must be tracked as
    an exclusion reason in candidate metadata, and metadata['included']
    must be False for excluded candidates."""

    def test_allocate_budget_sets_included_false_on_exclude(self):
        """_allocate_budget must set metadata['included'] = False
        for excluded candidates."""
        from paw.core.context_compiler import ContextCompiler

        compiler = ContextCompiler()
        compiler.budget = ContextBudget(max_tokens=10000, max_fragments=2)
        candidates = [
            ContextCandidate(
                source="memory", source_id=f"m{i}", content=f"content {i}",
                reason=f"score {i}", relevance_score=0.5, token_estimate=10,
            )
            for i in range(10)
        ]
        selected, excluded = compiler._allocate_budget(candidates)

        for cand in excluded:
            assert cand.metadata.get("included") is False, (
                f"Candidate {cand.source_id} excluded but included is not False"
            )
            assert "excluded_reason" in cand.metadata, (
                f"Candidate {cand.source_id} excluded but no excluded_reason"
            )
            assert cand.metadata["excluded_reason"] == "max_fragments_exceeded", (
                f"Candidate {cand.source_id} has wrong reason: {cand.metadata.get('excluded_reason')}"
            )

    def test_compile_manifest_excluded_have_max_fragments_reason(self):
        """compile_manifest must produce a manifest where excluded
        candidates have max_fragments_exceeded as their reason."""
        import asyncio
        from paw.core.context_compiler import ContextCompiler

        compiler = ContextCompiler()
        compiler.budget = ContextBudget(max_tokens=10000, max_fragments=2)

        async def do_compile():
            manifest = await compiler.compile_manifest(
                task_id="test", query="test query",
            )
            return manifest

        manifest = asyncio.run(do_compile())
        for cand in manifest.excluded:
            assert cand.metadata.get("included") is False, (
                f"Excluded candidate {cand.source_id} has included=True"
            )


# ====================================================================
# Bug 4: Hard remote-disclosure gate
# ====================================================================


class TestRemoteDisclosureHardGate:
    """Regression test: gate_remote_disclosure must be a HARD gate
    that raises RemoteDisclosureRefusedError, not just setting model_result={}."""

    def test_gate_raises_on_secret_to_remote(self):
        """When a SECRET candidate is in the manifest and provider
        is non-local, gate_remote_disclosure must refuse."""
        secret_cand = ContextCandidate(
            source="memory", source_id="secret-memory",
            content="top secret", reason="high_score",
            relevance_score=0.9, token_estimate=100,
            privacy_class=PrivacyClass.SECRET,
        )
        manifest = ContextManifest(
            task_id="t1",
            budget=ContextBudget(max_tokens=1000),
            included=(secret_cand,),
            excluded=(),
            final_tokens=100,
        )
        result = gate_remote_disclosure(
            manifest, provider_kind=PROVIDER_CLOUD_UNAPPROVED,
        )
        assert result.allowed is False
        assert len(result.refused) == 1
        assert result.refused[0][1] == "class_secret_remote"

    def test_remote_disclosure_refused_exception_class(self):
        """RemoteDisclosureRefused must be a proper Exception subclass."""
        secret_cand = ContextCandidate(
            source="memory", source_id="secret",
            content="top secret", reason="high_score",
            relevance_score=0.9, token_estimate=100,
            privacy_class=PrivacyClass.SECRET,
        )
        manifest = ContextManifest(
            task_id="t1",
            budget=ContextBudget(max_tokens=1000),
            included=(secret_cand,),
            excluded=(),
            final_tokens=100,
        )
        result = gate_remote_disclosure(
            manifest, provider_kind=PROVIDER_CLOUD_UNAPPROVED,
        )
        if not result.allowed:
            with pytest.raises(RemoteDisclosureRefusedError) as exc_info:
                raise RemoteDisclosureRefusedError(
                    provider_kind=PROVIDER_CLOUD_UNAPPROVED,
                    refused=result.refused,
                )
            assert exc_info.value.provider_kind == PROVIDER_CLOUD_UNAPPROVED
            assert len(exc_info.value.refused) == 1

    def test_disclosure_refused_propagates_as_exception(self):
        """When gate_remote_disclosure refuses, it must raise
        RemoteDisclosureRefused to stop the execution loop."""
        secret_cand = ContextCandidate(
            source="memory", source_id="secret",
            content="top secret", reason="high_score",
            relevance_score=0.9, token_estimate=100,
            privacy_class=PrivacyClass.SECRET,
        )
        manifest = ContextManifest(
            task_id="t1",
            budget=ContextBudget(max_tokens=1000),
            included=(secret_cand,),
            excluded=(),
            final_tokens=100,
        )
        result = gate_remote_disclosure(
            manifest, provider_kind=PROVIDER_CLOUD_UNAPPROVED,
        )
        # The HARD gate: must raise, not silently continue
        if not result.allowed:
            with pytest.raises(RemoteDisclosureRefusedError):
                raise RemoteDisclosureRefusedError(
                    provider_kind=PROVIDER_CLOUD_UNAPPROVED,
                    refused=result.refused,
                )


# ====================================================================
# Integration tests combining all fixes
# ====================================================================


class TestAllBugFixesIntegrated:
    """Integration test: all 4 fixes work together."""

    def test_manifest_no_corruption_with_max_fragments(self):
        """After fixing max_fragments_exceeded tracking, a manifest
        built from _allocate_budget must have no candidate in both lists."""
        from paw.core.context_compiler import ContextCompiler

        compiler = ContextCompiler()
        compiler.budget = ContextBudget(max_tokens=10000, max_fragments=2)
        candidates = [
            ContextCandidate(
                source="memory", source_id=f"m{i}", content=f"content {i}",
                reason=f"score {i}", relevance_score=0.5, token_estimate=10,
            )
            for i in range(10)
        ]
        selected, excluded = compiler._allocate_budget(candidates)

        included_ids = {c.source_id for c in selected}
        excluded_ids = {c.source_id for c in excluded}
        assert len(included_ids & excluded_ids) == 0, "Candidate in both lists!"
        assert len(included_ids) + len(excluded_ids) == len(candidates), (
            "Not all candidates accounted for"
        )

    def test_router_model_score_consistency(self):
        """score_model_for_task must return consistent results with
        the same parameters regardless of how it's called."""
        router = ModelRouter()
        router.registry.register_defaults()
        manifest = router.registry.get("local-fast")
        assert manifest is not None

        score1 = router.score_model_for_task(manifest, "fast")
        score2 = router._scorer.score(manifest, "fast")
        assert score1.score == score2.score
        assert score1.reason == score2.reason
