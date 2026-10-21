"""The cost weights and the role ceilings must be in the same unit.

``ResourceUsage.total_cost()`` and the per-role cost ceilings
(``ROLE_CEILINGS[...].max_cost_usd``, 0.01-0.20 dollars) were compared
against each other while being in **different units**: a model call
counted as 1.0 and a thousand tokens as 1.0, which is a hundred to a
thousand times over every ceiling. The visible effect was that an action
which *declared* an estimate containing a model call was refused by the
role ceiling before the call was ever made.

The contract pinned here:

* the weights are US dollars, and they are named constants rather than
  literals buried in an expression;
* a normal declared estimate fits under the fast role's ceiling, so
  declaring a cost is possible;
* a destructive step does not fit under the fast role's ceiling, so the
  signal that a destructive step needs a bigger role survives;
* the ceilings are unchanged - they were the coherent side of the
  comparison.
"""

from __future__ import annotations

import pytest

from paw.core.models import (
    COST_PER_DESTRUCTIVE_OP_USD,
    COST_PER_MODEL_CALL_USD,
    COST_PER_TOKEN_USD,
    ResourceUsage,
)
from paw.core.reasoning_contracts import (
    ROLE_CEILINGS,
    ModelRole,
    check_role_ceiling,
)


class TestTheUnitIsOneThing:
    def test_the_weights_are_dollars(self):
        # A model call is a fraction of a cent, not a dollar.
        assert 0 < COST_PER_MODEL_CALL_USD < 0.01
        # A token is a millionth of a dollar.
        assert 0 < COST_PER_TOKEN_USD < 0.00001
        # A destructive operation is worth about a cent.
        assert COST_PER_DESTRUCTIVE_OP_USD >= 0.005

    def test_the_weights_are_named_not_inlined(self):
        import inspect

        from paw.core import models

        source = inspect.getsource(models.ResourceUsage.total_cost)
        assert "COST_PER_MODEL_CALL_USD" in source
        assert "COST_PER_TOKEN_USD" in source

    def test_the_ceilings_are_unchanged(self):
        assert ROLE_CEILINGS[ModelRole.FAST].max_cost_usd == 0.01
        assert ROLE_CEILINGS[ModelRole.REASONING].max_cost_usd == 0.05
        assert ROLE_CEILINGS[ModelRole.VISION].max_cost_usd == 0.20


class TestADeclaredEstimateCanNowBeDeclared:
    def test_a_normal_step_fits_under_the_fast_ceiling(self):
        """The bug: declaring a cost was impossible."""
        usage = ResourceUsage(
            model_calls=1, tool_calls=1, tokens=2048, wall_time_ms=1000,
        )
        cost = usage.total_cost()
        assert cost < ROLE_CEILINGS[ModelRole.FAST].max_cost_usd, (
            f"a normal step costs {cost}, over the fast ceiling"
        )
        assert check_role_ceiling(
            ModelRole.FAST, requested_tokens=2048, estimated_cost_usd=cost,
        ) is None

    def test_a_destructive_step_needs_a_bigger_role(self):
        """The signal that a destructive step is expensive survives."""
        usage = ResourceUsage(
            model_calls=1, tool_calls=1, tokens=2048, wall_time_ms=1000,
            destructive_ops=1,
        )
        cost = usage.total_cost()
        assert cost > ROLE_CEILINGS[ModelRole.FAST].max_cost_usd
        assert check_role_ceiling(
            ModelRole.FAST, requested_tokens=2048, estimated_cost_usd=cost,
        ) == "cost_limit"

    def test_the_cost_of_nothing_is_nothing(self):
        assert ResourceUsage().total_cost() == 0.0

    def test_the_cost_is_monotone_in_every_input(self):
        base = ResourceUsage()
        for field in ("model_calls", "tool_calls", "tokens", "wall_time_ms",
                      "network_bytes", "destructive_ops"):
            bigger = ResourceUsage(**{field: 1})
            assert bigger.total_cost() > base.total_cost(), field


@pytest.mark.asyncio
async def test_the_runtime_admits_an_action_that_declares_a_cost(tmp_path):
    """End to end: a declared estimate no longer blocks the call."""
    from paw.core.autonomy import AutonomyBudget, AutonomyController
    from paw.core.executor import CapabilityRouter, ExecutorRegistry, MockExecutor
    from paw.core.model_executor import ModelExecutor
    from paw.core.model_router import ModelRouter, ProviderRegistry
    from paw.core.models import (
        Capability, ModelManifest, ProposedAction,
    )
    from paw.core.policy import PolicyGuard
    from paw.core.runtime import PawRuntime
    from paw.core.storage import db, set_db_path
    from paw.core.task import TaskManager

    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    task = await TaskManager.create("session-cost", "answer a question")

    class _Local:
        name = "local"
        initialized = True

        @property
        def available(self) -> bool:
            return True

        async def initialize(self) -> None:
            self.initialized = True

        async def shutdown(self) -> None:
            self.initialized = False

        async def list_models(self):
            return [{"name": "local-echo"}]

        async def get_model(self, name):
            return {"name": name}

        async def discover_manifests(self):
            return [
                ModelManifest(
                    name="local-echo", provider="local", roles=["fast", "reasoning"],
                    model_capabilities={"tool_calling": 9.0},
                    cost={"compute": "low", "monetary": "free"},
                    features={"resumable": True, "streaming": True},
                    max_context_tokens=32000, latency_tier="low", enabled=True,
                )
            ]

        async def complete(self, request):
            return {"response": "echo", "done": True}

        async def stream(self, request):
            yield {"response": "echo"}

    provider_registry = ProviderRegistry()
    provider_registry.register(_Local())
    router = ModelRouter(providers=provider_registry)
    await router.discover_providers()
    executors = ExecutorRegistry()
    executors.register(MockExecutor())

    runtime = PawRuntime(
        AutonomyController(
            budget=AutonomyBudget(max_iterations=1, max_decisions=5),
            policy_guard=PolicyGuard(interactive=False),
        ),
        model_router=router,
        model_executor=ModelExecutor(provider_registry=provider_registry),
        capability_router=CapabilityRouter(executors),
    )

    action = ProposedAction(
        goal=task.goal,
        capabilities=[Capability.MODEL_INFERENCE, Capability.FILESYSTEM_READ],
        context={},
        metadata={},
        operation_id="op-cost",
        idempotency_key="op-cost",
        # A declared estimate: one model call and a realistic token count.
        estimated_cost=ResourceUsage(model_calls=1, tool_calls=1, tokens=512),
    )
    result = await runtime._execute_unit(
        task.id, action, iteration_index=0, step_fn=runtime._execute_action,
        operation_type="step", step_id="step-1",
    )
    observation = result.observation
    assert observation is not None
    assert observation.success is True, observation.error
