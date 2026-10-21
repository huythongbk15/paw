"""The usage in the ledger must be a receipt, not an estimate.

The runtime recorded ``action.estimated_cost`` as the step's usage. That
says what a call was *expected* to cost, and it was called usage. The
provider's own count - the receipt - was never consulted, so the token
and cost numbers in the ledger could not be used to decide where the
money goes.

The contract pinned here:

* a provider that issues a usage receipt has it recorded as the
  observed usage, and the estimate is replaced;
* a provider that issues no receipt leaves the estimate in place - a
  missing receipt is not a zero;
* the receipt is normalized across the provider dialects (OpenAI's
  ``prompt_tokens``, Ollama's ``prompt_eval_count``);
* the receipt reaches the ledger, so the counted model calls and the
  recorded tokens agree.
"""

from __future__ import annotations

from typing import Any

import pytest

from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.executor import CapabilityRouter, ExecutorRegistry, MockExecutor
from paw.core.ledger import TaskEventType, TaskLedger
from paw.core.model_executor import ModelExecutor
from paw.core.model_router import ModelRouter, ProviderRegistry
from paw.core.models import (
    Capability,
    ModelManifest,
    ProposedAction,
    ResourceUsage,
    UsageReceipt,
)
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager


class _ReceiptProvider:
    """A provider that issues a usage receipt."""

    name = "local"
    initialized = True

    def __init__(self, usage: dict[str, Any] | None) -> None:
        self.usage = usage
        self.payloads: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return True

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def list_models(self) -> list[dict[str, Any]]:
        return [{"name": "local-echo"}]

    async def get_model(self, name: str) -> dict[str, Any] | None:
        return {"name": name}

    async def discover_manifests(self):
        return [
            ModelManifest(
                name="local-echo",
                provider="local",
                roles=["fast", "reasoning"],
                model_capabilities={"tool_calling": 9.0},
                cost={"compute": "low", "monetary": "free"},
                features={"resumable": True, "streaming": True},
                max_context_tokens=32000,
                latency_tier="low",
                enabled=True,
            )
        ]

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(request)
        result: dict[str, Any] = {"response": "echo", "done": True}
        if self.usage is not None:
            result["usage"] = self.usage
        return result

    async def stream(self, request: dict[str, Any]):
        self.payloads.append(request)
        yield {"response": "echo"}


async def _run_with_provider(tmp_path, usage: dict[str, Any] | None):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()

    task = await TaskManager.create("session-usage", "answer a question")
    provider = _ReceiptProvider(usage)
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(providers=registry)
    await router.discover_providers()

    registry_ex = ExecutorRegistry()
    registry_ex.register(MockExecutor())
    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
            policy_guard=PolicyGuard(interactive=False),
        ),
        model_router=router,
        model_executor=ModelExecutor(provider_registry=registry),
        capability_router=CapabilityRouter(registry_ex),
    )

    action = ProposedAction(
        goal=task.goal,
        capabilities=[Capability.MODEL_INFERENCE, Capability.FILESYSTEM_READ],
        context={},
        metadata={},
        operation_id="op-usage",
        idempotency_key="op-usage",
        # An estimate that is deliberately different from the receipt: if
        # it survives, the receipt was not used. The token count is small
        # enough to stay under the fast role's cost ceiling, which is
        # checked against the estimate before the call.
        estimated_cost=ResourceUsage(tokens=7),
    )
    result = await runtime._execute_unit(
        task.id, action, iteration_index=0, step_fn=runtime._execute_action,
        operation_type="step", step_id="step-1",
    )
    return task, result


# --- The receipt shapes ---------------------------------------------------


class TestReceiptNormalization:
    def test_openai_dialect(self):
        receipt = UsageReceipt.from_result(
            {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        )
        assert receipt.prompt_tokens == 10
        assert receipt.completion_tokens == 5
        assert receipt.total_tokens == 15
        assert receipt.model_calls == 1
        assert receipt.issued is True

    def test_ollama_dialect(self):
        receipt = UsageReceipt.from_result(
            {"usage": {"prompt_eval_count": 7, "eval_count": 3}}
        )
        assert receipt.prompt_tokens == 7
        assert receipt.completion_tokens == 3
        assert receipt.total_tokens == 10
        assert receipt.issued is True

    def test_no_usage_is_not_a_zero_receipt(self):
        receipt = UsageReceipt.from_result({"response": "hi"})
        assert receipt.issued is False
        assert receipt.total_tokens == 0

    def test_a_malformed_usage_is_ignored(self):
        receipt = UsageReceipt.from_result({"usage": "not a dict"})
        assert receipt.issued is False
        receipt = UsageReceipt.from_result({"usage": {"total_tokens": "many"}})
        assert receipt.issued is False


# --- The runtime uses the receipt -----------------------------------------


@pytest.mark.asyncio
async def test_the_observed_receipt_replaces_the_estimate(tmp_path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    task, result = await _run_with_provider(
        tmp_path, {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
    )
    observation = result.observation
    assert observation is not None
    assert observation.resources_used.tokens == 150, (
        f"the estimate survived: {observation.resources_used.tokens}"
    )
    assert observation.resources_used.model_calls == 1
    assert observation.result.get("usage_receipt") == {
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "model_calls": 1,
    }


@pytest.mark.asyncio
async def test_without_a_receipt_the_estimate_stays(tmp_path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    _task, result = await _run_with_provider(tmp_path, None)
    observation = result.observation
    assert observation is not None
    assert observation.resources_used.tokens == 7, (
        "a provider that issues no receipt must not zero the usage"
    )
    assert observation.result.get("usage_receipt") is None


@pytest.mark.asyncio
async def test_the_receipt_reaches_the_ledger(tmp_path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    task, result = await _run_with_provider(
        tmp_path, {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50},
    )
    events = await TaskLedger.get_events_by_type(task.id, TaskEventType.STEP_EXECUTED)
    assert events, "the step was not recorded"
    resources = events[0].payload.get("resources_used") or {}
    # The ledger records the observed tokens, not the estimate.
    assert resources.get("tokens") == 50, resources
    # And the model-call count agrees with what was actually served.
    counted = await TaskLedger.get_model_call_count(task.id)
    assert counted == 1, f"the ledger counted {counted} model calls"
