"""A selected model route cannot silently become a successful local echo."""

from unittest.mock import AsyncMock, Mock

import pytest

from paw.core.model_executor import ModelDispatchError, ModelExecutor
from paw.core.model_router import ProviderRegistry
from paw.core.models import Capability, ModelManifest, ModelSelection, ProposedAction
from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.checkpoint import OperationRecordStore
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.session import SessionManager
from paw.core.storage import db
from paw.core.task import TaskManager
from paw.core.models import StopReason, TaskStatus


def selection(provider="remote"):
    return ModelSelection(
        model_name="selected-model",
        model_manifest=ModelManifest(name="selected-model", provider=provider),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("route", ["absent", "no_route", "no_manifest", "mismatched_model", "unavailable"])
async def test_invalid_route_never_calls_local_or_provider(stream, route):
    registry = ProviderRegistry()
    local = AsyncMock()
    provider = AsyncMock()
    provider.name = "remote"
    provider.available = False
    async def chunks(request):
        yield {"response": "incorrect success"}
    local.stream = Mock(side_effect=chunks)
    provider.stream = Mock(side_effect=chunks)
    picked = selection()
    if route == "unavailable":
        registry.register(provider)
    elif route == "no_route":
        picked = ModelSelection(model_name="")
    elif route == "no_manifest":
        picked = ModelSelection(model_name="selected-model")
    elif route == "mismatched_model":
        picked.model_name = "different-model"
    executor = ModelExecutor(provider_registry=registry, local_fallback=local)
    with pytest.raises(ModelDispatchError):
        if stream:
            _ = [chunk async for chunk in executor.stream(picked, [])]
        else:
            await executor.complete(picked, [])
    local.complete.assert_not_called()
    local.stream.assert_not_called()
    provider.complete.assert_not_called()
    provider.stream.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_explicit_local_remains_available(stream):
    executor = ModelExecutor(provider_registry=ProviderRegistry())
    messages = [{"role": "user", "content": "hello"}]
    if stream:
        result = [chunk async for chunk in executor.stream(selection("local"), messages)]
        assert result[-1]["response"] == "[local-standin] hello"
    else:
        assert (await executor.complete(selection("local"), messages))["response"] == "[local-standin] hello"


@pytest.mark.asyncio
@pytest.mark.parametrize("canonical", [False, True])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("failure", ["missing_provider", "provider_exception", "error_envelope", "no_route"])
async def test_runtime_model_failure_is_durable_and_never_routes_executor(canonical, stream, failure):
    picked = selection()
    registry = ProviderRegistry()
    if failure in ("provider_exception", "error_envelope"):
        provider = AsyncMock()
        provider.name = "remote"
        provider.available = True
        if failure == "provider_exception":
            provider.complete.side_effect = RuntimeError("private payload must not be persisted")
        else:
            provider.complete.return_value = {"error": "private payload must not be persisted", "response": ""}
        async def broken_stream(request):
            yield {"response": "provisional"}
            if failure == "provider_exception":
                raise RuntimeError("private payload must not be persisted")
            yield {"error": "private payload must not be persisted"}
        provider.stream = Mock(side_effect=broken_stream)
        registry.register(provider)
    elif failure == "no_route":
        picked = ModelSelection(model_name="")
    router = AsyncMock()
    router.route.return_value = picked
    router.re_evaluate_routing.return_value = picked
    router.registry = Mock()
    router.registry.get.return_value = picked.model_manifest
    capabilities = AsyncMock()
    runtime = PawRuntime(
        AutonomyController(budget=AutonomyBudget(), policy_guard=PolicyGuard(interactive=False)),
        model_router=router,
        model_executor=ModelExecutor(provider_registry=registry),
        capability_router=capabilities,
    )
    if stream:
        runtime._stream_callback = Mock()
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, "test model failure")
    action = ProposedAction(
        goal=task.goal,
        capabilities=[Capability.MODEL_INFERENCE],
        is_mutating=False,
        metadata={"selected_model": picked.model_name} if canonical else {},
        operation_id="dispatch-failure",
        idempotency_key="dispatch-failure",
    )
    result = await runtime._execute_unit(
        task.id, action, iteration_index=0, step_fn=runtime._execute_action,
        operation_type="model.inference", step_id="model-step",
    )
    assert result.observation.success is False
    assert result.observation.error.startswith("model_dispatch:")
    assert "private payload" not in str(result.observation.model_dump())
    capabilities.route_detailed.assert_not_awaited()
    await db.close()
    await db.connect()
    record = await OperationRecordStore.get(task.id, action.operation_id)
    assert record.status == "failed"
    assert result.operation_completed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("no_route", [False, True])
async def test_public_loop_persists_failed_task_not_completed(no_route):
    router = AsyncMock()
    router.route.return_value = ModelSelection(model_name="") if no_route else selection()
    router.re_evaluate_routing.return_value = router.route.return_value
    router.registry = Mock()
    router.registry.get.return_value = router.route.return_value.model_manifest
    capabilities = AsyncMock()
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, "selected route unavailable")
    proposer = Mock()
    proposer.propose.return_value = ProposedAction(
        goal=task.goal, capabilities=[Capability.MODEL_INFERENCE],
        is_mutating=False, operation_id="failed-loop", metadata={"done": True},
    )
    runtime = PawRuntime(
        AutonomyController(budget=AutonomyBudget(), policy_guard=PolicyGuard(interactive=False)),
        proposer=proposer, model_router=router,
        model_executor=ModelExecutor(provider_registry=ProviderRegistry()),
        capability_router=capabilities, max_iterations=1,
    )
    outcome = await runtime.run(task.id, task_goal=task.goal, step_fn=runtime._execute_action)
    assert outcome.reason == StopReason.TASK_FAILED
    assert outcome.operations_completed == 0
    assert outcome.last_observation.success is False
    capabilities.route_detailed.assert_not_awaited()
    await db.close()
    await db.connect()
    assert (await TaskManager.get(task.id)).status == TaskStatus.FAILED
    assert (await OperationRecordStore.get(task.id, "failed-loop")).status == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["router", "executor"])
async def test_missing_inference_backend_cannot_run_capability_executor(missing):
    capabilities = AsyncMock()
    runtime = PawRuntime(
        AutonomyController(budget=AutonomyBudget(), policy_guard=PolicyGuard(interactive=False)),
        model_router=None if missing == "router" else AsyncMock(),
        model_executor=None if missing == "executor" else ModelExecutor(),
        capability_router=capabilities,
    )
    observation = await runtime._execute_action("missing-backend", ProposedAction(
        goal="inference required", capabilities=[Capability.MODEL_INFERENCE], is_mutating=False,
    ))
    assert observation.success is False
    assert observation.error == "model_dispatch:backend_unavailable"
    capabilities.route_detailed.assert_not_awaited()
