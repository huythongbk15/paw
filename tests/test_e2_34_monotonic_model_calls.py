"""E2-34: Persistent counter and monotonicity check for model-call count.

Four-layer evidence:
  1. Invariant  — TaskLedger has get_model_call_count + assert_model_calls_monotonic
  2. Runtime    — counter derived from STEP_EXECUTED events
  3. Adversarial — decreasing count raises RuntimeError
  4. Measurable — export stable + documented

Decision level: D2.
"""
import pytest

from paw.core.ledger import TaskLedger, TaskEventType, log_step_executed


@pytest.mark.usefixtures("session_db")
class TestInvariantHelpers:
    async def test_inv2_empty_task_returns_zero(self):
        assert await TaskLedger.get_model_call_count("task-empty") == 0

    async def test_inv3_single_step_count(self):
        await log_step_executed("task-1", "op-1", True, resources_used={"provider_calls": 3})
        assert await TaskLedger.get_model_call_count("task-1") == 3


@pytest.mark.usefixtures("session_db")
class TestRuntimeCounterDerivation:
    async def test_rt1_multiple_steps_summed(self):
        await log_step_executed("task-2", "op-1", True, resources_used={"provider_calls": 2})
        await log_step_executed("task-2", "op-2", True, resources_used={"provider_calls": 1})
        assert await TaskLedger.get_model_call_count("task-2") == 3

    async def test_rt2_non_step_events_ignored(self):
        await TaskLedger.record("task-3", TaskEventType.TASK_CREATED, {"foo": "bar"})
        await log_step_executed("task-3", "op-1", True, resources_used={"provider_calls": 5})
        assert await TaskLedger.get_model_call_count("task-3") == 5

    async def test_rt3_missing_provider_calls_treated_as_zero(self):
        await log_step_executed("task-4", "op-1", True, resources_used={})
        assert await TaskLedger.get_model_call_count("task-4") == 0


@pytest.mark.usefixtures("session_db")
class TestAdversarialMonotonicity:
    async def test_adv1_monotonic_passes(self):
        await log_step_executed("task-5", "op-1", True, resources_used={"provider_calls": 1, "model_call_count": 1})
        await log_step_executed("task-5", "op-2", True, resources_used={"provider_calls": 2, "model_call_count": 3})
        await TaskLedger.assert_model_calls_monotonic("task-5")  # must not raise

    async def test_adv2_decrease_raises(self):
        await log_step_executed("task-6", "op-1", True, resources_used={"provider_calls": 5})
        await log_step_executed("task-6", "op-2", True, resources_used={"provider_calls": -1})
        with pytest.raises(RuntimeError, match="decreased"):
            await TaskLedger.assert_model_calls_monotonic("task-6")

    async def test_adv3_non_integer_recorded_ignored(self):
        await log_step_executed("task-7", "op-1", True, resources_used={"provider_calls": 1, "model_call_count": "nan"})
        await log_step_executed("task-7", "op-2", True, resources_used={"provider_calls": 2, "model_call_count": 3})
        await TaskLedger.assert_model_calls_monotonic("task-7")  # must not raise


class TestMeasurableExport:
    def test_measure1_methods_callable(self):
        assert callable(TaskLedger.get_model_call_count)
        assert callable(TaskLedger.assert_model_calls_monotonic)

    @pytest.mark.usefixtures("session_db")
    async def test_measure2_zero_when_no_step_executed(self):
        assert await TaskLedger.get_model_call_count("task-8") == 0
