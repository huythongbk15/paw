"""BETA B-04: Analyze demo - read-only investigation over a non-trivial repo."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from paw.core.autonomy import AutonomyController
from paw.core.beta_profiles import ANALYZE, is_side_effect_capability
from paw.core.model_executor import LocalModelExecutor
from paw.core.model_router import ModelRouter
from paw.core.models import ExecutionObservation, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path


async def _bootstrap(task_id: str, goal: str) -> None:
    await db.initialize()
    await db.execute(
        "INSERT OR REPLACE INTO tasks (id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, "s1", goal, "pending",
         datetime.now(UTC).isoformat(),
         datetime.now(UTC).isoformat()),
    )


async def run_analyze_demo(repo_root: str | Path = ".") -> dict:
    repo_root = Path(repo_root)
    paw_db = Path("/tmp/paw_beta_analyze/demo.db")
    paw_db.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_db)
    await _bootstrap("beta-analyze-01", "Investigate PAW source tree.")

    profile = ANALYZE.execution_profile
    guard = PolicyGuard(interactive=False)
    autonomy = AutonomyController(policy_guard=guard, budget=profile.resolved_autonomy_budget())

    runtime = PawRuntime(
        autonomy=autonomy,
        context_compiler=None,
        model_router=ModelRouter(),
        model_executor=LocalModelExecutor(),
        execution_profile=profile,
        readiness="READY", current_revision="HEAD",
        checkpoint_interval=100, auto_checkpoint=False,
    )

    async def analyze_step(task_id: str, proposed) -> ExecutionObservation:
        evidence = [{"type": "repo_inventory", "repo_root": str(repo_root)}]
        py_files = list(repo_root.rglob("*.py"))
        md_files = list(repo_root.rglob("*.md"))
        evidence.append({"type": "file_counts", "py_files": len(py_files), "md_files": len(md_files)})
        # Verify no side-effect capabilities in the proposed action
        side_effects = [c for c in proposed.capabilities if is_side_effect_capability(c)]
        return ExecutionObservation(
            step_id=proposed.operation_id, action_id=proposed.operation_id,
            result={"done": True, "progress": 1.0, "evidence": evidence,
                    "side_effects_blocked": len(side_effects)},
            success=True, resources_used=ResourceUsage(),
        )

    outcome = await runtime.run(
        "beta-analyze-01",
        task_goal="Investigate the PAW source tree, count files by type.",
        step_fn=analyze_step,
    )
    if outcome.last_observation and outcome.last_observation.result:
        ro_data = outcome.last_observation.result
        outcome.evidence = ro_data.get("evidence", [])
        outcome.uncertainty = {"confidence": 1.0,
            "side_effects_blocked": ro_data.get("side_effects_blocked", 0)}
        outcome.next_action = "Inspect via `paw beta inspect memory`."
    await db.close()
    return outcome.to_answer()


if __name__ == "__main__":
    result = asyncio.run(run_analyze_demo("/home/huythong/.hybridagent/workspaces/default"))
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
