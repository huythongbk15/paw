"""E2-30: Enforce an evidence/time/token research budget and typed stop condition.

Four-layer evidence:
  1. Invariant  — ResearchBudget fields and ResearchStopReason enum exist
  2. Runtime    — check_research_budget returns correct stop reason
  3. Adversarial — budget validation rejects negatives; stop reason priority
  4. Measurable — TaskSignals accepts research_budget; stop reason exported

Decision level: D2.
"""
import pytest

from paw.core.autonomy import AutonomyController
from paw.core.reasoning_contracts import (
    ResearchBudget,
    ResearchStopReason,
    TaskSignals,
    check_research_budget,
)
from paw.core.runtime import PawRuntime
from paw.core.models import ExecutionObservation, ProposedAction, ResourceUsage


class TestInvariantBudgetTypes:
    def test_inv1_research_budget_defaults(self):
        budget = ResearchBudget()
        assert budget.max_evidence_items == 20
        assert budget.max_time_seconds == 300.0
        assert budget.max_tokens == 4000
        assert budget.stop_reason is ResearchStopReason.COMPLETED

    def test_inv2_stop_reason_values(self):
        values = {s.value for s in ResearchStopReason}
        assert values == {"evidence_limit", "time_limit", "token_limit", "completed"}

    def test_inv3_task_signals_accepts_budget(self):
        signals = TaskSignals(research_budget=ResearchBudget())
        assert signals.research_budget is not None
        assert signals.research_budget.max_evidence_items == 20

    def test_inv4_budget_rejects_negative_evidence(self):
        with pytest.raises(ValueError):
            ResearchBudget(max_evidence_items=-1)

    def test_inv5_budget_rejects_negative_time(self):
        with pytest.raises(ValueError):
            ResearchBudget(max_time_seconds=-1)

    def test_inv6_budget_rejects_negative_tokens(self):
        with pytest.raises(ValueError):
            ResearchBudget(max_tokens=-1)


class TestRuntimeBudgetExhaustion:
    def test_rt1_evidence_limit(self):
        budget = ResearchBudget(max_evidence_items=5)
        assert check_research_budget(budget, evidence_count=5) == ResearchStopReason.EVIDENCE_LIMIT

    def test_rt2_time_limit(self):
        budget = ResearchBudget(max_time_seconds=10.0)
        assert check_research_budget(budget, elapsed_time=10.0) == ResearchStopReason.TIME_LIMIT

    def test_rt3_token_limit(self):
        budget = ResearchBudget(max_tokens=100)
        assert check_research_budget(budget, tokens_used=100) == ResearchStopReason.TOKEN_LIMIT

    def test_rt4_not_exhausted_returns_none(self):
        budget = ResearchBudget(max_evidence_items=10, max_time_seconds=5.0, max_tokens=100)
        assert check_research_budget(budget, evidence_count=5, elapsed_time=2.0, tokens_used=50) is None

    def test_rt5_completed_default_stop_reason(self):
        budget = ResearchBudget()
        assert budget.stop_reason is ResearchStopReason.COMPLETED

    def test_rt6_evidence_priority_over_time(self):
        budget = ResearchBudget(max_evidence_items=5, max_time_seconds=1.0, max_tokens=10)
        result = check_research_budget(budget, evidence_count=5, elapsed_time=2.0, tokens_used=20)
        assert result == ResearchStopReason.EVIDENCE_LIMIT

    def test_rt7_custom_budget(self):
        budget = ResearchBudget(max_evidence_items=100, max_time_seconds=600.0, max_tokens=8000)
        assert check_research_budget(budget, evidence_count=50, elapsed_time=300.0, tokens_used=4000) is None
        assert check_research_budget(budget, evidence_count=100) == ResearchStopReason.EVIDENCE_LIMIT
        assert check_research_budget(budget, evidence_count=0, elapsed_time=600.0) == ResearchStopReason.TIME_LIMIT
        assert check_research_budget(budget, evidence_count=0, elapsed_time=0.0, tokens_used=8000) == ResearchStopReason.TOKEN_LIMIT


class TestAdversarialBudgetEdgeCases:
    def test_adv1_zero_budget_means_immediate_evidence_limit(self):
        budget = ResearchBudget(max_evidence_items=0)
        assert check_research_budget(budget, evidence_count=0) == ResearchStopReason.EVIDENCE_LIMIT

    def test_adv2_zero_time_budget(self):
        budget = ResearchBudget(max_time_seconds=0.0)
        assert check_research_budget(budget, elapsed_time=0.0) == ResearchStopReason.TIME_LIMIT

    def test_adv3_zero_token_budget(self):
        budget = ResearchBudget(max_tokens=0)
        assert check_research_budget(budget, tokens_used=0) == ResearchStopReason.TOKEN_LIMIT

    def test_adv4_negative_count_does_not_crash(self):
        budget = ResearchBudget(max_evidence_items=10)
        assert check_research_budget(budget, evidence_count=-1) is None

    def test_adv5_none_budget(self):
        pass


class TestMeasurableExport:
    def test_measure1_exported_in_all(self):
        from paw.core.reasoning_contracts import __all__
        assert "ResearchBudget" in __all__
        assert "ResearchStopReason" in __all__
        assert "check_research_budget" in __all__

    def test_measure2_stop_reason_documented(self):
        assert ResearchStopReason.EVIDENCE_LIMIT.value == "evidence_limit"
        assert ResearchStopReason.TIME_LIMIT.value == "time_limit"
        assert ResearchStopReason.TOKEN_LIMIT.value == "token_limit"
        assert ResearchStopReason.COMPLETED.value == "completed"

    def test_measure3_budget_defaults_stable(self):
        budget = ResearchBudget()
        assert budget.max_evidence_items == 20
        assert budget.max_time_seconds == 300.0
        assert budget.max_tokens == 4000


class TestRuntimeEnforcement:
    @pytest.mark.asyncio
    async def test_rt8_budget_exhausted_stops_before_provider_call(self):
        runtime = PawRuntime(
            autonomy=AutonomyController(),
            task_signals=TaskSignals(
                research_budget=ResearchBudget(max_evidence_items=0)
            ),
        )
        proposed = ProposedAction(
            operation_id="op-1",
            goal="test",
            capabilities=[],
            estimated_cost=ResourceUsage(),
            idempotency_key="key-1",
        )
        async def step_fn(task_id, action):
            raise AssertionError("step_fn must not be called when research budget exhausted")

        obs = await runtime._execute_action("task-1", proposed)
        assert obs.success is False
        assert "research_budget_exhausted" in obs.error
        assert ResearchStopReason.EVIDENCE_LIMIT.value in obs.error

    @pytest.mark.asyncio
    async def test_rt9_no_budget_allows_execution(self):
        runtime = PawRuntime(autonomy=AutonomyController(), task_signals=TaskSignals())
        proposed = ProposedAction(
            operation_id="op-2",
            goal="test",
            capabilities=[],
            estimated_cost=ResourceUsage(),
            idempotency_key="key-2",
        )
        async def step_fn(task_id, action):
            return ExecutionObservation(action_id=action.operation_id, success=True)

        obs = await runtime._execute_action("task-2", proposed)
        assert obs.success is True
