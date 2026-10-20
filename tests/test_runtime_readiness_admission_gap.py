"""Regression: raw READY/research/spike flags never authorize write callbacks."""

from unittest.mock import AsyncMock

import pytest

from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.models import Capability, ExecutionObservation
from paw.core.models import ProposedAction
from paw.core.runtime import PawRuntime
from paw.core.session import SessionManager
from paw.core.task import TaskManager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "readiness, flags",
    [
        ("READY", {}),
        ("NEEDS_RESEARCH", {"is_research": True}),
        ("SPIKE_REQUIRED", {"plan_purpose": "spike", "isolated": True}),
        ("REJECTED", {"is_mutating": False}),
    ],
)
async def test_project_write_without_reviewed_decision_never_calls_callback(
    readiness, flags
):
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, "runtime readiness probe")
    runtime = PawRuntime(
        AutonomyController(budget=AutonomyBudget()),
        readiness=readiness,
    )
    # Policy/Autonomy admission is independent of engineering readiness. Stub
    # it here to isolate the missing shared-unit check, not to claim Policy
    # allows a production write. The existing pipeline contract tests own it.
    runtime._gate_action = AsyncMock(return_value=None)
    step = AsyncMock(
        return_value=ExecutionObservation(
            step_id="probe", action_id="probe", success=True,
            result={"done": True, "progress": 1.0},
        )
    )
    action = ProposedAction(
        goal=task.goal, operation_id="probe", idempotency_key="probe",
        capabilities=[Capability.FILESYSTEM_WRITE], **flags,
    )
    result = await runtime._execute_unit(
        task.id, action, iteration_index=0, step_fn=step,
        operation_type="readiness_probe", step_id="probe",
    )
    runtime._gate_action.assert_awaited_once()
    step.assert_not_awaited()
    assert result.operation_completed is False
    assert result.observation is not None and not result.observation.success
