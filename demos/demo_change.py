"""BETA B-06: Change demo - multi-file change with approval and verification.

Uses the 'change' profile (gated) to create a file. When approve=True,
the policy gate allows the write and the file is created + verified.
When approve=False, the policy gate blocks the write (no side effects).
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from paw.core.autonomy import AutonomyController
from paw.core.beta_profiles import CHANGE, is_side_effect_capability
from paw.core.model_executor import LocalModelExecutor
from paw.core.model_router import ModelRouter
from paw.core.models import Capability, ExecutionObservation, ResourceUsage
from paw.core.policy import PolicyDecision, PolicyDecisionDetail, PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path


class _DemoGuard(PolicyGuard):
    """PolicyGuard that allows FILESYSTEM_WRITE when approve=True."""

    def __init__(self, approve: bool):
        super().__init__(interactive=approve)
        self._approve = approve

    async def check_detailed(self, cap, context=None, task_id=None):
        if cap == Capability.FILESYSTEM_WRITE and self._approve:
            return PolicyDecisionDetail(
                decision=PolicyDecision.ALLOW,
                capability=cap,
                source="demo:approve", matched_rule="demo_approve_write",
                conditions_evaluated=[{"capability": cap.value}],
                reason="Demo approval granted",
            )
        return await super().check_detailed(cap, context, task_id)


async def _bootstrap(task_id, goal):
    await db.initialize()
    await db.execute(
        "INSERT OR REPLACE INTO tasks (id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, "session-1", goal, "pending",
         datetime.now(UTC).isoformat(),
         datetime.now(UTC).isoformat()),
    )


async def run_change_demo(approve=True, work_dir="/tmp/paw_beta_change") -> dict:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    paw_db = work_dir / "demo.db"
    await set_db_path(str(paw_db))
    await _bootstrap("beta-change-01", "Create a verified test file")

    profile = CHANGE.execution_profile
    guard = _DemoGuard(approve=approve)
    autonomy = AutonomyController(policy_guard=guard, budget=profile.resolved_autonomy_budget())
    runtime = PawRuntime(
        autonomy=autonomy, context_compiler=None, model_router=ModelRouter(),
        model_executor=LocalModelExecutor(), execution_profile=profile,
        readiness="READY", current_revision="HEAD",
        checkpoint_interval=100, auto_checkpoint=False,
    )

    async def change_step(task_id, proposed) -> ExecutionObservation:
        has_write = any(c == Capability.FILESYSTEM_WRITE for c in proposed.capabilities) or                     any(is_side_effect_capability(c) for c in proposed.capabilities)
        file_written = False
        verification_passed = False

        if not approve:
            return ExecutionObservation(
                step_id=proposed.operation_id, action_id=proposed.operation_id,
                result={"done": False, "progress": 0.0,
                        "error": "write denied by policy gate (no approval)"},
                success=False, resources_used=ResourceUsage(),
            )
        if has_write:
            target_file = work_dir / "changed_file.txt"
            target_file.write_text("PAW beta change demo - verified file.")
            file_written = True
            read_back = target_file.read_text()
            verification_passed = "verified file" in read_back
        return ExecutionObservation(
            step_id=proposed.operation_id, action_id=proposed.operation_id,
            result={"done": has_write, "progress": 1.0 if has_write else 0.0,
                    "file_written": file_written, "verification_passed": verification_passed},
            success=has_write and verification_passed,
            resources_used=ResourceUsage(tool_calls=1, destructive_ops=1 if has_write else 0),
        )

    outcome = await runtime.run("beta-change-01",
        task_goal=f"Create a file in {work_dir} and verify its content",
        step_fn=change_step,
        available_skills=[{"name": "create_file", "required_capabilities": ["filesystem.write"]}])
    if outcome.last_observation and outcome.last_observation.result:
        ro = outcome.last_observation.result
        outcome.uncertainty = {"confidence": 0.95, "approval_granted": approve,
            "file_written": ro.get("file_written", False),
            "verification_passed": ro.get("verification_passed", False)}
        outcome.evidence = [{"type": "change_record", "approved": approve,
            "file_written": ro.get("file_written", False),
            "verification_passed": ro.get("verification_passed", False)}]
        if approve and ro.get("verification_passed"):
            outcome.next_action = "Change verified. Inspect with `paw beta inspect context beta-change-01`."
        elif not approve:
            outcome.next_action = "Change denied by policy gate. No side effects occurred."
    else:
        # Denied or blocked — no observation recorded
        outcome.uncertainty = {"confidence": 0.95, "approval_granted": approve,
            "file_written": False, "verification_passed": False}
        outcome.evidence = [{"type": "change_blocked", "approved": approve,
            "reason": str(outcome.reason) if outcome.reason else "blocked"}]
        outcome.next_action = "Change denied by policy gate. No side effects occurred."
    await db.close()
    return outcome.to_answer()


if __name__ == "__main__":
    r1 = asyncio.run(run_change_demo(approve=True))
    print("=== APPROVED ===")
    print(json.dumps(r1, indent=2, default=str, ensure_ascii=False))
    r2 = asyncio.run(run_change_demo(approve=False))
    print("\n=== DENIED ===")
    print(json.dumps(r2, indent=2, default=str, ensure_ascii=False))
