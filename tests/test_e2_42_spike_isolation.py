"""E2-42: Spike isolation — RESEARCH plans execute only research, no implementation steps."""
import pytest

from paw.core.runtime import PawRuntime
from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.models import ProposedAction, Capability, ResourceUsage
from paw.core.planner import Plan
from paw.core.policy import PolicyGuard

pytestmark = pytest.mark.asyncio


class _RecordingExecutor:
    """Records all complete() calls to verify spike isolation."""
    def __init__(self):
        self.calls: list[dict] = []

    @property
    def available(self):
        return True

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def complete(self, request):
        self.calls.append({"request": request})
        return {"done": True, "response": "research note", "thinking": "analyzing"}


class TestSpikeIsolation:
    """E2-42: SPIKE plans must not execute implementation steps.

    A research-purpose plan with default non-interactive PolicyGuard:
      - FILESYSTEM_READ -> ALLOW (research action allowed)
      - FILESYSTEM_WRITE -> ASK -> DENY (implementation action blocked)
    """

    async def test_spike_plan_blocks_implementation_capability(self):
        """A research-purpose plan with WRITE capability gets STOP."""
        plan = Plan(goal="research X", purpose="research")
        budget = AutonomyBudget(max_model_calls=1, max_iterations=2)
        pg = PolicyGuard(interactive=False)
        ac = AutonomyController(budget, policy_guard=pg)
        exec_inst = _RecordingExecutor()
        runtime = PawRuntime(
            autonomy=ac, model_executor=exec_inst,
            max_iterations=2, plan=plan,
        )
        runtime.default_role = "researcher"

        action = ProposedAction(
            goal="modify production file",
            capabilities=[Capability.FILESYSTEM_WRITE],
            context={},
            estimated_cost=ResourceUsage(),
            effect_constraints=[],
            plan_purpose="implementation",
        )
        result = await runtime._gate_action("spike-test", action, 0)
        # Research plan with WRITE cap → policy blocks (ASK->DENY non-interactive)
        assert result is not None
        assert result.stopped is True
        assert result.step_called is False

    async def test_spike_plan_allows_research_action(self):
        """A research-purpose plan allows READ capability."""
        plan = Plan(goal="research X", purpose="research")
        budget = AutonomyBudget(max_model_calls=1, max_iterations=2)
        pg = PolicyGuard(interactive=False)
        ac = AutonomyController(budget, policy_guard=pg)
        exec_inst = _RecordingExecutor()
        runtime = PawRuntime(
            autonomy=ac, model_executor=exec_inst,
            max_iterations=2, plan=plan,
        )
        runtime.default_role = "researcher"

        action = ProposedAction(
            goal="read and analyze file",
            capabilities=[Capability.FILESYSTEM_READ],
            context={},
            estimated_cost=ResourceUsage(),
            effect_constraints=[],
            plan_purpose="research",
        )
        result = await runtime._gate_action("spike-test-2", action, 0)
        # READ is ALLOW by default → action proceeds (gate returns None)
        assert result is None

    async def test_spike_isolation_no_executor_calls_for_blocked(self):
        """Blocked spike action produces zero executor calls."""
        plan = Plan(goal="spike exploration", purpose="research")
        budget = AutonomyBudget(max_model_calls=1, max_iterations=3)
        pg = PolicyGuard(interactive=False)
        ac = AutonomyController(budget, policy_guard=pg)
        exec_inst = _RecordingExecutor()
        runtime = PawRuntime(
            autonomy=ac, model_executor=exec_inst,
            max_iterations=3, plan=plan,
        )
        runtime.default_role = "researcher"

        action = ProposedAction(
            goal="write to file",
            capabilities=[Capability.FILESYSTEM_WRITE],
            context={},
            estimated_cost=ResourceUsage(),
            effect_constraints=[],
            plan_purpose="implementation",
        )
        await runtime._gate_action("spike-test-3", action, 0)
        assert len(exec_inst.calls) == 0


class TestPlanPurposeSpike:
    async def test_research_plan_purpose(self):
        """Research purpose is set on the plan."""
        plan = Plan(goal="research X", purpose="research")
        assert plan.purpose == "research"

    async def test_implementation_plan_purpose(self):
        """Implementation purpose is set on the plan."""
        plan = Plan(goal="implement Y", purpose="implementation")
        assert plan.purpose == "implementation"
