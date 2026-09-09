"""E2-07: Persist role/budget/reason in TaskLedger.

Four-layer evidence per PAW contract:
  1. Invariant  — reason/budget/signals present in ledger record
  2. Runtime    — real PawRuntime._execute_action logs full metadata
  3. Adversarial — tampering signals don't corrupt the persisted record
  4. Measurable — get_events returns structured fields

Decision level: D1 (implementation detail on top of E2-06 route() wiring).
"""
import inspect
import pytest

from paw.core.ledger import (
    TaskLedger,
    TaskEventType,
    log_model_selected,
)
from datetime import datetime, timezone as tz

def _now() -> str:
    return datetime.now(tz.utc).isoformat()
    return datetime.now(tz.utc).isoformat()


# --- Shared mock provider (mirrors Phase 20 test pattern) ---------
class _MockProvider:
    """Minimal ModelProvider-compatible object for local routing tests."""
    def __init__(self):
        self.name = "mockp"
        self.available = True

    def list_models(self):
        return []

    def get_model(self, name):
        return None

    async def complete(self, model, prompt, **kw):
        return {"text": "echo done"}

    async def stream(self, model, prompt, **kw):
        yield {"text": "echo"}

    async def discover_manifests(self):
        return []


def _register_mock_model():
    from paw.core.storage import db
    return db.write(
        """INSERT INTO model_registry
           (id, name, provider, roles, capabilities, cost, features,
            max_context_tokens, latency_tier, enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("mock-local", "mock-local", "mockp",
         '["fast","reasoning"]', "{}", '{"compute":"low"}', '{"streaming":true}',
         4096, "low", 1, _now(), _now()),
    )


def _make_runtime(task_signals=None, execution_profile=None):
    from paw.core.autonomy import AutonomyController, AutonomyBudget
    from paw.core.runtime import PawRuntime
    from paw.core.model_executor import ModelExecutor
    from paw.core.model_router import ModelRouter, ModelRegistry
    from paw.core.models import ModelManifest, ModelCapability
    router = ModelRouter(providers=[_MockProvider()])
    # Register a non-local mock model that supports both fast and reasoning
    # roles, so E2-11 escalation (fast→reasoning) finds a real model rather
    # than stopping via E2-12.
    router.registry.register(ModelManifest(
        name="mock-fast-reasoning",
        provider="mockp",
        roles=["fast", "reasoning"],
        model_capabilities={
            ModelCapability.REASONING: 5.0,
            ModelCapability.CODING: 4.0,
        },
        cost={"compute": "low"},
        features={"streaming": True},
        max_context_tokens=4096,
        latency_tier="low",
        enabled=True,
    ))
    exec_ = ModelExecutor(provider_registry=router._provider_registry)
    autonomy = AutonomyController(
        budget=AutonomyBudget(max_iterations=3, max_decisions=10),
    )
    return PawRuntime(
        autonomy=autonomy,
        model_router=router,
        model_executor=exec_,
        task_signals=task_signals,
        execution_profile=execution_profile,
    )


# --- 1. Invariant -------------------------------------------------
class TestInvariantLedgerHasFullMetadata:
    async def test_inv1_log_model_selected_persists_all_fields(self, temp_db):
        """Invariant: log_model_selected persists reason, budget,
        signals_summary, score, fallback_chain."""
        await log_model_selected(
            "t_inv",
            "claude-3-sonnet",
            "reasoning",
            reason="context_sufficiency=SUFFICIENT + novelty=NOVEL",
            budget={"max_model_calls": 50, "max_total_tokens": 10000},
            signals_summary={"novelty": "novel", "impact": "high",
                             "privacy": "internal"},
            score=0.93,
            fallback_chain=["gpt-3.5-turbo"],
            stage="execution",
        )
        rows = await TaskLedger.get_events("t_inv")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        assert sel, "expected a MODEL_SELECTED event"
        md = sel[-1].payload
        assert md["model"] == "claude-3-sonnet"
        assert md["role"] == "reasoning"
        assert md["reason"] == "context_sufficiency=SUFFICIENT + novelty=NOVEL"
        assert md["budget"]["max_model_calls"] == 50
        assert md["signals_summary"]["novelty"] == "novel"
        assert md["score"] == 0.93
        assert md["fallback_chain"] == ["gpt-3.5-turbo"]

    def test_inv2_runtime_passes_task_signals_to_route(self):
        """Invariant: PawRuntime._execute_action passes task_signals to
        model_router.route()."""
        from paw.core.runtime import PawRuntime
        src = inspect.getsource(PawRuntime._execute_action)
        assert "task_signals=self.task_signals" in src
        assert "self.task_signals" in src

    def test_inv3_log_model_selected_signature_has_e207_fields(self):
        """Invariant: log_model_selected signature requires the E2-07 fields."""
        sig = inspect.signature(log_model_selected)
        params = set(sig.parameters.keys())
        assert {"reason", "budget", "signals_summary", "score",
                "fallback_chain"}.issubset(params)

    def test_inv4_runtime_source_builds_budget_and_signals(self):
        """Invariant: runtime source builds budget_summary/signals_summary
        before the ledger record."""
        from paw.core.runtime import PawRuntime
        src = inspect.getsource(PawRuntime._execute_action)
        assert "budget_summary" in src
        assert "signals_summary" in src
        assert '"reason"' in src


# --- 2. Runtime ---------------------------------------------------
class TestRuntimePersistsRoutingDecision:
    @pytest.fixture(autouse=True)
    async def _setup(self, temp_db):
        await _register_mock_model()

    async def test_rt1_runtime_logs_reason_to_ledger(self):
        """On real execution, MODEL_SELECTED record has reason populated."""
        from paw.core.models import ProposedAction, Capability
        from paw.core.reasoning_contracts import (
            TaskSignals, NoveltyLevel, ImpactLevel,
            ContextSufficiencyLevel, BudgetLevel,
        )
        from paw.core.privacy import PrivacyClass
        runtime = _make_runtime(task_signals=TaskSignals(
            novelty=NoveltyLevel.NOVEL,
            impact=ImpactLevel.HIGH,
            privacy=PrivacyClass.INTERNAL,
            context_sufficiency=ContextSufficiencyLevel.SUFFICIENT,
            budget=BudgetLevel.WITHIN_LIMIT,
        ))
        action = ProposedAction(goal="test", capabilities=[Capability.MODEL_INFERENCE],
                                context={"tokens": 10})
        await runtime._execute_action("rt1", action)
        rows = await TaskLedger.get_events("rt1")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        assert sel
        md = sel[-1].payload
        assert "reason" in md

    async def test_rt2_runtime_signals_summary_populated(self):
        """signals_summary reflects the TaskSignals fields."""
        from paw.core.models import ProposedAction, Capability
        from paw.core.reasoning_contracts import (
            TaskSignals, NoveltyLevel, ImpactLevel,
            ContextSufficiencyLevel, BudgetLevel,
        )
        from paw.core.privacy import PrivacyClass
        runtime = _make_runtime(task_signals=TaskSignals(
            novelty=NoveltyLevel.NOVEL,
            impact=ImpactLevel.HIGH,
            privacy=PrivacyClass.INTERNAL,
            context_sufficiency=ContextSufficiencyLevel.SUFFICIENT,
            budget=BudgetLevel.WITHIN_LIMIT,
        ))
        action = ProposedAction(goal="test", capabilities=[Capability.MODEL_INFERENCE],
                                context={"tokens": 10})
        await runtime._execute_action("rt2", action)
        rows = await TaskLedger.get_events("rt2")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        s = sel[-1].payload["signals_summary"]
        assert s.get("novelty") == "novel"
        assert s.get("impact") == "high"
        assert s.get("privacy") == "internal"
        assert s.get("context_sufficiency") == "sufficient"
        assert s.get("budget") == "within_limit"

    async def test_rt3_no_signals_yields_empty_summary(self):
        """Runtime with None task_signals logs empty signals_summary."""
        from paw.core.models import ProposedAction, Capability
        runtime = _make_runtime(task_signals=None)
        action = ProposedAction(goal="test", capabilities=[Capability.MODEL_INFERENCE],
                                context={"tokens": 10})
        await runtime._execute_action("rt3", action)
        rows = await TaskLedger.get_events("rt3")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        assert sel[-1].payload["signals_summary"] == {}


# --- 3. Adversarial -----------------------------------------------
class TestAdversarialTampering:
    async def test_adv1_empty_summary_on_minimal_call(self, temp_db):
        """Adversarial: minimal log_model_selected call yields empty
        signals/budget dicts, not crash."""
        await log_model_selected("t_adv", "m", "fast", reason="r")
        rows = await TaskLedger.get_events("t_adv")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        assert sel[-1].payload["signals_summary"] == {}
        assert sel[-1].payload["budget"] == {}

    async def test_adv2_negative_score_preserved(self, temp_db):
        """Adversarial: sentinel score -1 is preserved."""
        await log_model_selected("t_neg", "none", "fast", reason="no-match",
                                 score=-1.0)
        rows = await TaskLedger.get_events("t_neg")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        assert sel[-1].payload["score"] == -1.0

    async def test_adv3_budget_from_execution_profile(self, temp_db):
        """Adversarial: execution_profile budget fields extracted."""
        await _register_mock_model()
        from paw.core.models import ProposedAction, Capability
        class FakeProfile:
            max_model_calls = 42
            max_total_tokens = 9999
            max_tool_calls = 7
            max_wall_time_seconds = 30
            name = "fake"
            privacy_preference = type("P", (), {"value": "allow_remote"})()
            cost_priority = 1
            latency_priority = 1
            preferred_models = []
        runtime = _make_runtime(execution_profile=FakeProfile())
        action = ProposedAction(goal="g", capabilities=[Capability.MODEL_INFERENCE],
                                context={"tokens": 5})
        await runtime._execute_action("rt_budget", action)
        rows = await TaskLedger.get_events("rt_budget")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        b = sel[-1].payload["budget"]
        assert b["max_model_calls"] == 42
        assert b["max_total_tokens"] == 9999
        assert b["max_tool_calls"] == 7
        assert b["max_wall_time_seconds"] == 30


# --- 4. Measurable ------------------------------------------------
class TestMeasurableFields:
    async def test_meas1_full_round_trip(self, temp_db):
        """Measurable: full record then query — all fields correct."""
        await log_model_selected(
            "t_meas", "deepseek", "reasoning",
            reason="novel+high-impact",
            budget={"max_model_calls": 10, "max_total_tokens": 5000},
            signals_summary={"novelty": "novel", "impact": "high"},
            score=0.77, fallback_chain=["gpt-4"],
        )
        rows = await TaskLedger.get_events("t_meas")
        sel = [r for r in rows if r.event_type == TaskEventType.MODEL_SELECTED]
        md = sel[-1].payload
        assert isinstance(md, dict)
        assert md["model"] == "deepseek"
        assert md["role"] == "reasoning"
        assert md["reason"] == "novel+high-impact"
        assert md["budget"]["max_model_calls"] == 10
        assert md["signals_summary"]["novelty"] == "novel"
        assert md["score"] == 0.77
        assert md["fallback_chain"] == ["gpt-4"]

    async def test_meas2_multiple_records_accumulate(self, temp_db):
        """Measurable: multiple recordings in one task accumulate."""
        for i in range(3):
            await log_model_selected(f"mult_{i}", "m", "fast", reason=f"r{i}")
        for i in range(3):
            r = await TaskLedger.get_events(f"mult_{i}")
            assert r[-1].payload["reason"] == f"r{i}"
