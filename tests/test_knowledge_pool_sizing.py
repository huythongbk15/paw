"""The context budget must be the only binding constraint on knowledge retrieval.

``ContextPlan.max_knowledge_chunks`` used to default to ``10`` and was passed
straight through as ``KnowledgeIndex.search_chunks(limit=...)``, independent of
``ContextBudget``. A chunk that was never a candidate cannot be selected by any
budget, so on a foreign repository that default pushed required evidence out of
the pool entirely: the 2026-09-29 foreign-corpus measurement scored
``min_recall = 0.00`` on 312 chunks while the *correct file* was still being
retrieved, because the specific chunk was never admitted.

The default is now ``None``, meaning "derive the pool from the budget". These
tests pin the derivation, the explicit-override escape hatch, and -- most
importantly -- a negative control proving the derivation is what widened the
pool, so the old constant cannot creep back as the effective value.
"""

from __future__ import annotations

import pytest

from paw.core.context import ContextBudget
from paw.core.context_compiler import (
    KNOWLEDGE_POOL_CEILING,
    KNOWLEDGE_POOL_FLOOR,
    KNOWLEDGE_POOL_HEADROOM,
    ContextPlan,
    knowledge_pool_size,
)


def _plan(**kwargs) -> ContextPlan:
    return ContextPlan(
        task_id="task-pool-01",
        query="find the helper",
        token_budget=5000,
        **kwargs,
    )


class TestPoolDerivation:
    def test_default_plan_derives_from_budget(self):
        """The default must not be a constant any more."""
        assert _plan().max_knowledge_chunks is None

    def test_pool_never_below_the_budget_can_hold(self):
        """A budget that can hold N fragments needs a pool of at least N."""
        for max_fragments in (1, 5, 10, 30, 97):
            budget = ContextBudget(max_fragments=max_fragments)
            assert knowledge_pool_size(_plan(), budget) >= max_fragments

    def test_small_budget_still_gets_the_floor(self):
        """Headroom is useless below the floor; a tiny budget must not fetch 4."""
        budget = ContextBudget(max_fragments=1)
        assert knowledge_pool_size(_plan(), budget) == KNOWLEDGE_POOL_FLOOR

    def test_pool_scales_with_the_budget(self):
        tight = knowledge_pool_size(_plan(), ContextBudget(max_fragments=10))
        loose = knowledge_pool_size(_plan(), ContextBudget(max_fragments=60))
        assert loose > tight

    def test_pool_is_capped(self):
        """The per-candidate cost is bounded, however large the budget gets."""
        budget = ContextBudget(max_fragments=10_000)
        assert knowledge_pool_size(_plan(), budget) == KNOWLEDGE_POOL_CEILING

    def test_headroom_is_above_the_fragment_budget(self):
        """Dedup and the per-source ceiling drop candidates after retrieval."""
        budget = ContextBudget(max_fragments=20)
        pool = knowledge_pool_size(_plan(), budget)
        assert pool == max(KNOWLEDGE_POOL_FLOOR, 20 * KNOWLEDGE_POOL_HEADROOM)
        assert pool > 20


class TestExplicitOverride:
    def test_explicit_value_is_honoured_verbatim(self):
        """A caller may still deliberately ask for a narrow pool."""
        budget = ContextBudget(max_fragments=30)
        assert knowledge_pool_size(_plan(max_knowledge_chunks=10), budget) == 10

    def test_explicit_zero_means_no_knowledge_retrieval(self):
        assert knowledge_pool_size(_plan(max_knowledge_chunks=0), ContextBudget()) == 0

    def test_explicit_override_beats_a_large_budget(self):
        budget = ContextBudget(max_fragments=500)
        assert knowledge_pool_size(_plan(max_knowledge_chunks=7), budget) == 7


class TestOldConstantCannotReturn:
    """Negative control for the regression itself."""

    def test_derived_pool_is_strictly_wider_than_the_old_default(self):
        """The defect was exactly this: a derived pool of 10 or less."""
        budget = ContextBudget(max_fragments=30)
        assert knowledge_pool_size(_plan(), budget) > 10

    def test_no_plan_default_reproduces_the_old_cap(self):
        """Creating a plan must never yield the 10-chunk starvation cap."""
        plan = ContextPlan(task_id="task-pool-02", query="q", token_budget=5000)
        budget = ContextBudget(max_fragments=30)
        assert knowledge_pool_size(plan, budget) != 10

    @pytest.mark.parametrize("max_fragments", [1, 5, 10, 30, 100, 400])
    def test_every_budget_derives_wider_than_ten(self, max_fragments):
        budget = ContextBudget(max_fragments=max_fragments)
        assert knowledge_pool_size(_plan(), budget) > 10
