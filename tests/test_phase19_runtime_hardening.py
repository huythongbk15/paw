"""
Phase 19 Runtime Hardening — Acceptance Tests

Tests all 8 hardening points as a black-box integration using real SQLite:
  1. ProposedAction with operation_id, estimated_cost, idempotency_key
  2. ExecutionObservation typed (replaces arbitrary dict)
  3. ActionProposer as single source of truth for next action
  4. AutonomyBudget / ResourceUsage with per-resource-type tracking
  5. OperationRecord for idempotent replay safety
  6. CheckpointManager integration in runtime loop
  7. TaskLedger integration with full event trail
  8. Real SQLite black-box acceptance (this test)
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from paw.core.autonomy import (
    AutonomyController,
    AutonomyBudget,
    AutonomyDecision,
    AutonomyProfile,
    AutonomyUsage,
    StopReason,
)
from paw.core.checkpoint import CheckpointManager, OperationRecord, OperationRecordStore
from paw.core.ledger import TaskLedger, TaskEventType
from paw.core.models import (
    Capability,
    ExecutionObservation,
    ProposedAction,
    ResourceUsage,
)
from paw.core.policy import PolicyGuard
from paw.core.runtime import ActionProposer, PawRuntime, RuntimeOutcome
from paw.core.storage import db, set_db_path


@pytest.fixture
async def temp_db():
    """Create a temporary database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Set the DB path before any imports that use it
    await set_db_path(db_path)

    # Ensure all tables exist
    await db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            goal TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS model_selections (
            task_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            role TEXT NOT NULL,
            reason TEXT,
            score REAL NOT NULL DEFAULT 0.0,
            fallback_chain TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (task_id, role, created_at)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS model_registry (
            name TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            roles TEXT NOT NULL DEFAULT '[]',
            model_capabilities TEXT NOT NULL DEFAULT '{}',
            cost TEXT NOT NULL DEFAULT '{}',
            features TEXT NOT NULL DEFAULT '{}',
            max_context_tokens INTEGER NOT NULL DEFAULT 128000,
            latency_tier TEXT NOT NULL DEFAULT 'medium',
            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS policy_rules (
            id TEXT PRIMARY KEY,
            capability TEXT NOT NULL,
            decision TEXT NOT NULL,
            conditions TEXT NOT NULL DEFAULT '[]',
            priority INTEGER NOT NULL DEFAULT 0,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS task_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            task_status TEXT NOT NULL,
            current_step INTEGER NOT NULL DEFAULT 0,
            total_steps INTEGER NOT NULL DEFAULT 0,
            progress_ratio REAL NOT NULL DEFAULT 0.0,
            context TEXT NOT NULL DEFAULT '{}',
            context_compiler_state TEXT NOT NULL DEFAULT '{}',
            autonomy_usage TEXT NOT NULL DEFAULT '{}',
            autonomy_profile TEXT NOT NULL DEFAULT 'balanced',
            progress_history TEXT NOT NULL DEFAULT '[]',
            repetition_state TEXT NOT NULL DEFAULT '{}',
            stall_state TEXT NOT NULL DEFAULT '{}',
            loop_iteration INTEGER NOT NULL DEFAULT 0,
            loop_decision_history TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            metadata TEXT NOT NULL DEFAULT '{}'
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS operation_records (
            task_id TEXT NOT NULL,
            op_id TEXT NOT NULL,
            op_type TEXT NOT NULL DEFAULT 'step',
            status TEXT NOT NULL DEFAULT 'completed',
            checkpoint_id TEXT,
            result_ref TEXT,
            created_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (task_id, op_id)
        )
    """)

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def autonomy_controller():
    """Create an AutonomyController with a test budget."""
    budget = AutonomyBudget(
        max_decisions=10,
        max_model_calls=5,
        max_tool_calls=5,
        max_total_tokens=5000,
        max_wall_time_seconds=60,
        max_iterations=5,
        max_retries_per_step=2,
        min_progress_per_iteration=0.1,
    )
    return AutonomyController(budget=budget)


@pytest.fixture
def policy_guard():
    """Create a PolicyGuard with default rules (allow filesystem.read)."""
    return PolicyGuard()


class TestPhase19RuntimeHardening:
    """Black-box acceptance tests for Phase 19 runtime hardening."""

    async def test_1_proposed_action_has_operation_id_estimated_cost_idempotency(
        self, temp_db, autonomy_controller
    ):
        """Point 1: ProposedAction includes operation_id, estimated_cost, idempotency_key."""
        proposer = ActionProposer()
        proposed = proposer.propose(
            task_id="test_task_1",
            task_goal="Read a file",
            context={},
            skills=[{"name": "read_file", "required_capabilities": ["filesystem.read"]}],
        )

        assert isinstance(proposed, ProposedAction)
        assert proposed.operation_id.startswith("op_test_task_1_")
        assert isinstance(proposed.estimated_cost, ResourceUsage)
        assert proposed.estimated_cost.model_calls >= 1  # Base model call
        assert proposed.estimated_cost.tool_calls >= 1  # Tool call for filesystem.read
        assert proposed.idempotency_key is None  # Optional, can be set

    async def test_2_execution_observation_typed_replaces_dict(
        self, temp_db, autonomy_controller
    ):
        """Point 2: ExecutionObservation is a typed class replacing arbitrary dict."""
        obs = ExecutionObservation(
            step_id="step_1",
            action_id="op_test_1",
            result={"done": True, "progress": 1.0, "summary": "File read"},
            resources_used=ResourceUsage(
                model_calls=1, tool_calls=1, tokens=500, wall_time_ms=100
            ),
            success=True,
            error=None,
        )

        assert isinstance(obs, ExecutionObservation)
        assert obs.step_id == "step_1"
        assert obs.action_id == "op_test_1"
        assert obs.success is True
        assert obs.resources_used.model_calls == 1
        assert obs.resources_used.tool_calls == 1

        # Can serialize to dict for logging
        obs_dict = obs.to_dict()
        assert obs_dict["step_id"] == "step_1"
        assert obs_dict["resources_used"]["model_calls"] == 1

    async def test_3_action_proposer_single_source_of_truth(
        self, temp_db, autonomy_controller
    ):
        """Point 3: ActionProposer is single source of truth for next action."""
        proposer = ActionProposer()

        # First proposal
        p1 = proposer.propose(
            task_id="test_task_3",
            task_goal="Write a file",
            context={},
            skills=[{"name": "write_file", "required_capabilities": ["filesystem.write"]}],
        )

        # Second proposal (simulating second iteration)
        p2 = proposer.propose(
            task_id="test_task_3",
            task_goal="Write a file",
            context={"previous": "done"},
            skills=[{"name": "write_file", "required_capabilities": ["filesystem.write"]}],
            last_observation=ExecutionObservation(
                step_id="step_1", action_id=p1.operation_id, result={}, success=True
            ),
        )

        assert p1.operation_id != p2.operation_id
        assert p2.metadata["proposal_number"] == 2
        assert p2.metadata["has_last_observation"] is True

    async def test_4_autonomy_budget_resource_usage_per_resource_type(
        self, temp_db, autonomy_controller
    ):
        """Point 4: AutonomyBudget tracks per-resource-type (model, tool, tokens, wall_time, network, destructive)."""
        budget = AutonomyBudget(
            max_model_calls=3,
            max_tool_calls=5,
            max_total_tokens=1000,
            max_wall_time_seconds=30,
        )
        controller = AutonomyController(budget=budget)

        # Simulate usage
        controller.usage.record_model_call(100)
        controller.usage.record_model_call(200)
        controller.usage.record_tool_call(50)
        controller.usage.record_tool_call(50)
        controller.usage.wall_time_seconds = 10.0

        assert controller.usage.model_calls == 2
        assert controller.usage.tool_calls == 2
        assert controller.usage.total_tokens == 400
        assert controller.usage.wall_time_seconds == 10.0

        # Check budget enforcement
        allowed, reason = await controller.check_budget()
        assert allowed is True

        # Exceed model calls budget
        controller.usage.record_model_call(100)  # 3rd call
        controller.usage.record_model_call(100)  # 4th call - exceeds

        allowed, reason = await controller.check_budget()
        assert allowed is False
        assert reason == StopReason.BUDGET_MODEL_CALLS_EXHAUSTED

    async def test_5_operation_record_idempotent_replay_safety(
        self, temp_db, autonomy_controller
    ):
        """Point 5: OperationRecord enables idempotent replay (skip completed ops)."""
        task_id = "test_task_5"

        # Record some completed operations
        await OperationRecordStore.record(OperationRecord(
            task_id=task_id,
            op_id="op_1",
            op_type="step",
            status="completed",
            result_ref="observation:step_1",
        ))
        await OperationRecordStore.record(OperationRecord(
            task_id=task_id,
            op_id="op_2",
            op_type="tool_call",
            status="completed",
            result_ref="tool:result_1",
        ))

        # Check they're marked completed
        assert await OperationRecordStore.is_completed(task_id, "op_1") is True
        assert await OperationRecordStore.is_completed(task_id, "op_2") is True
        assert await OperationRecordStore.is_completed(task_id, "op_3") is False

        # Get all completed op IDs for replay skipping
        completed = await OperationRecordStore.get_completed_op_ids(task_id)
        assert "op_1" in completed
        assert "op_2" in completed
        assert len(completed) == 2

    async def test_6_checkpoint_manager_integration_in_runtime(
        self, temp_db, autonomy_controller, policy_guard
    ):
        """Point 6: CheckpointManager integrated in runtime loop (auto + forced)."""
        controller = AutonomyController(
            budget=AutonomyBudget(max_iterations=10, max_decisions=20),
            policy_guard=policy_guard,
        )
        checkpoint_mgr = CheckpointManager()
        checkpoint_mgr.set_checkpoint_interval(2)
        checkpoint_mgr.enable_auto_checkpoint(True)

        runtime = PawRuntime(
            autonomy=controller,
            checkpoint_mgr=checkpoint_mgr,
            max_iterations=5,
        )

        step_count = 0

        async def step_fn(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
            nonlocal step_count
            step_count += 1
            return ExecutionObservation(
                step_id=f"step_{step_count}",
                action_id=proposed.operation_id,
                result={
                    "done": step_count >= 3,  # Complete after 3 steps
                    "progress": step_count / 3.0,
                },
                resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
                success=True,
            )

        outcome = await runtime.run(
            task_id="test_task_6",
            task_goal="Complete in 3 steps",
            initial_context={},
            available_skills=[],
            step_fn=step_fn,
        )

        assert outcome.stopped is True
        assert outcome.iterations == 3
        assert outcome.operations_completed == 3
        assert outcome.checkpoint_id is not None  # Final checkpoint created

        # Verify checkpoint was persisted
        from paw.core.checkpoint import CheckpointStore
        checkpoint = await CheckpointStore.get_latest("test_task_6")
        assert checkpoint is not None
        assert checkpoint.task_status == "completed"
        assert checkpoint.current_step == 3

    async def test_7_task_ledger_full_event_trail(
        self, temp_db, autonomy_controller, policy_guard
    ):
        """Point 7: TaskLedger captures full event trail (policy, autonomy, checkpoint, step, operation)."""
        controller = AutonomyController(
            budget=AutonomyBudget(max_iterations=5, max_decisions=10),
            policy_guard=policy_guard,
        )
        runtime = PawRuntime(
            autonomy=controller,
            max_iterations=3,
        )

        async def step_fn(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
            return ExecutionObservation(
                step_id="step_1",
                action_id=proposed.operation_id,
                result={"done": True, "progress": 1.0},
                resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
                success=True,
            )

        await runtime.run(
            task_id="test_task_7",
            task_goal="Test ledger",
            initial_context={},
            available_skills=[],
            step_fn=step_fn,
        )

        # Retrieve all events
        events = await TaskLedger.get_events("test_task_7")

        # Should have events for: TASK_CREATED, STEP_PROPOSED, POLICY_GATE_EVALUATED,
        # AUTONOMY_GATE_EVALUATED, STEP_EXECUTED, OPERATION_RECORDED,
        # STEP_COMPLETED, CHECKPOINT_CREATED, TASK_COMPLETED
        event_types = [e.event_type for e in events]

        assert TaskEventType.TASK_CREATED in event_types
        assert TaskEventType.STEP_PROPOSED in event_types
        assert TaskEventType.POLICY_GATE_EVALUATED in event_types
        assert TaskEventType.AUTONOMY_GATE_EVALUATED in event_types
        assert TaskEventType.STEP_EXECUTED in event_types
        assert TaskEventType.OPERATION_RECORDED in event_types
        assert TaskEventType.STEP_COMPLETED in event_types
        assert TaskEventType.CHECKPOINT_CREATED in event_types
        assert TaskEventType.TASK_COMPLETED in event_types

        # Verify event payloads have expected structure
        step_proposed = next(e for e in events if e.event_type == TaskEventType.STEP_PROPOSED)
        assert "action_id" in step_proposed.payload
        assert "capabilities" in step_proposed.payload

    async def test_8_black_box_real_sqlite_full_loop(
        self, temp_db, autonomy_controller, policy_guard
    ):
        """Point 8: Full black-box integration with real SQLite - no mocks for core subsystems."""
        # Add explicit ALLOW rule for filesystem.write to avoid ASK
        from paw.core.policy import PolicyDecision
        await policy_guard.add_rule(
            capability=Capability.FILESYSTEM_WRITE,
            decision=PolicyDecision.ALLOW,
            priority=100,
            conditions={},
        )

        controller = AutonomyController(
            budget=AutonomyBudget(
                max_iterations=10,
                max_decisions=20,
                max_model_calls=10,
                max_tool_calls=10,
                max_total_tokens=10000,
            ),
            policy_guard=policy_guard,
        )

        runtime = PawRuntime(
            autonomy=controller,
            checkpoint_mgr=CheckpointManager(),
            max_iterations=5,
        )

        # Track state across steps
        step_states = []

        async def step_fn(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
            step_num = len(step_states) + 1
            step_states.append({
                "step": step_num,
                "action_id": proposed.operation_id,
                "capabilities": [c.value for c in proposed.capabilities],
            })

            # Complete after 2 steps
            done = step_num >= 2
            return ExecutionObservation(
                step_id=f"step_{step_num}",
                action_id=proposed.operation_id,
                result={
                    "done": done,
                    "progress": step_num / 2.0,
                    "summary": f"Step {step_num} complete",
                },
                resources_used=ResourceUsage(
                    model_calls=1,
                    tool_calls=1,
                    tokens=300,
                    wall_time_ms=50,
                ),
                success=True,
            )

        outcome = await runtime.run(
            task_id="test_task_8",
            task_goal="Black box integration test",
            initial_context={"user_preference": "concise"},
            available_skills=[
                {"name": "skill_a", "required_capabilities": ["filesystem.read"]},
                {"name": "skill_b", "required_capabilities": ["filesystem.write"]},
            ],
            step_fn=step_fn,
        )

        # Verify outcome
        assert outcome.stopped is True
        assert outcome.reason == StopReason.TASK_COMPLETED
        assert outcome.decision == AutonomyDecision.STOP_SUCCESS
        assert outcome.iterations == 2
        assert outcome.step_called is True
        assert outcome.operations_completed == 2
        assert outcome.last_observation is not None
        assert outcome.last_observation.result["done"] is True

        # Verify ledger has complete trail
        events = await TaskLedger.get_events("test_task_8")
        assert len(events) >= 9  # Minimum expected events

        # Verify checkpoint exists
        from paw.core.checkpoint import CheckpointStore
        checkpoint = await CheckpointStore.get_latest("test_task_8")
        assert checkpoint is not None
        assert checkpoint.task_status == "completed"
        assert checkpoint.progress_ratio == 1.0

        # Verify operation records exist for replay
        completed_ops = await OperationRecordStore.get_completed_op_ids("test_task_8")
        assert len(completed_ops) == 2

        # Verify step states tracked (proposer uses all available skills each time)
        assert len(step_states) == 2
        for state in step_states:
            assert "filesystem.read" in state["capabilities"]
            assert "filesystem.write" in state["capabilities"]

    async def test_resume_skips_completed_operations(
        self, temp_db, autonomy_controller, policy_guard
    ):
        """Resume from checkpoint skips already-completed operations."""
        # Use larger budget to allow resume to continue
        controller = AutonomyController(
            budget=AutonomyBudget(max_iterations=10, max_decisions=20),
            policy_guard=policy_guard,
        )
        checkpoint_mgr = CheckpointManager()
        runtime = PawRuntime(
            autonomy=controller,
            checkpoint_mgr=checkpoint_mgr,
            max_iterations=5,
        )

        step_count = 0

        async def step_fn(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
            nonlocal step_count
            step_count += 1
            return ExecutionObservation(
                step_id=f"step_{step_count}",
                action_id=proposed.operation_id,
                result={"done": False, "progress": step_count / 5.0},
                resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
                success=True,
            )

        # Run first time - complete 5 steps (max_iterations)
        outcome1 = await runtime.run(
            task_id="test_resume",
            task_goal="Test resume",
            initial_context={},
            available_skills=[],
            step_fn=step_fn,
        )

        # Should stop at max_iterations since we don't return done
        assert outcome1.iterations == 5
        assert step_count == 5

        # Get checkpoint
        from paw.core.checkpoint import CheckpointStore
        checkpoint = await CheckpointStore.get_latest("test_resume")
        assert checkpoint is not None

        # Now resume with same step_fn - should skip completed operations
        # Create new runtime with fresh budget for resume
        controller2 = AutonomyController(
            budget=AutonomyBudget(max_iterations=10, max_decisions=20),
            policy_guard=policy_guard,
        )
        runtime2 = PawRuntime(
            autonomy=controller2,
            checkpoint_mgr=checkpoint_mgr,
            max_iterations=5,
        )
        step_count = 0

        async def step_fn_resumed(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
            nonlocal step_count
            step_count += 1
            return ExecutionObservation(
                step_id=f"step_{step_count}",
                action_id=proposed.operation_id,
                result={"done": True, "progress": 1.0},
                resources_used=ResourceUsage(model_calls=1, tool_calls=1, tokens=200),
                success=True,
            )

        outcome2 = await runtime2.run(
            task_id="test_resume",
            task_goal="Test resume",
            initial_context={},
            available_skills=[],
            step_fn=step_fn_resumed,
            resume_from_checkpoint=checkpoint.checkpoint_id,
        )

        # Should skip the 5 completed operations and only run the new step
        # Note: proposer._proposal_count is advanced to skip completed ops
        assert step_count == 1  # Only 1 new step executed
        assert outcome2.operations_completed == 1

    async def test_policy_deny_blocks_before_execution(
        self, temp_db, autonomy_controller, policy_guard
    ):
        """Policy DENY blocks execution before step_fn is called."""
        # Add a deny rule for shell.execute
        from datetime import UTC, datetime
        await db.execute(
            """
            INSERT INTO policy_rules (id, capability, decision, conditions, priority, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("rule_deny_shell", "shell.execute", "deny", "[]", 100, 1, datetime.now(UTC).isoformat()),
        )

        controller = AutonomyController(
            budget=AutonomyBudget(max_iterations=5, max_decisions=10),
            policy_guard=policy_guard,
        )
        runtime = PawRuntime(
            autonomy=controller,
            max_iterations=3,
        )

        step_called = False

        async def step_fn(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
            nonlocal step_called
            step_called = True
            return ExecutionObservation(
                step_id="step_1",
                action_id=proposed.operation_id,
                result={"done": True, "progress": 1.0},
                resources_used=ResourceUsage(),
                success=True,
            )

        # Propose action requiring shell.execute
        outcome = await runtime.run(
            task_id="test_policy_deny",
            task_goal="Run shell command",
            initial_context={},
            available_skills=[{"name": "run_cmd", "required_capabilities": ["shell.execute"]}],
            step_fn=step_fn,
        )

        assert outcome.stopped is True
        assert outcome.reason == StopReason.POLICY_DENIED
        assert outcome.step_called is False  # step_fn never called!
        assert step_called is False

    async def test_ask_non_interactive_blocks(
        self, temp_db, autonomy_controller
    ):
        """Policy ASK (non-interactive) blocks execution."""
        # Create a policy guard that requires ASK for filesystem.write
        from paw.core.policy import PolicyGuard, PolicyDecision
        guard = PolicyGuard()
        await guard.add_rule(
            capability=Capability.FILESYSTEM_WRITE,
            decision=PolicyDecision.ASK,
            priority=50,
            conditions={},
        )

        controller = AutonomyController(
            budget=AutonomyBudget(max_iterations=5, max_decisions=10),
            policy_guard=guard,
        )
        runtime = PawRuntime(
            autonomy=controller,
            max_iterations=3,
        )

        step_called = False

        async def step_fn(task_id: str, proposed: ProposedAction) -> ExecutionObservation:
            nonlocal step_called
            step_called = True
            return ExecutionObservation(
                step_id="step_1",
                action_id=proposed.operation_id,
                result={"done": True, "progress": 1.0},
                resources_used=ResourceUsage(),
                success=True,
            )

        outcome = await runtime.run(
            task_id="test_policy_ask",
            task_goal="Write file",
            initial_context={},
            available_skills=[{"name": "write_file", "required_capabilities": ["filesystem.write"]}],
            step_fn=step_fn,
        )

        assert outcome.stopped is True
        assert outcome.reason == StopReason.POLICY_ASK_REQUIRED
        assert outcome.waiting_for_approval is True
        assert outcome.step_called is False  # step_fn never called!
        assert step_called is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])