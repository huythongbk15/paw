"""BETA B-07: Review demo - identify invariant regression without writing."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from paw.core.autonomy import AutonomyController
from paw.core.beta_profiles import REVIEW, is_side_effect_capability
from paw.core.model_executor import LocalModelExecutor
from paw.core.model_router import ModelRouter
from paw.core.models import ExecutionObservation, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path


async def _bootstrap(task_id, goal):
    await db.initialize()
    await db.execute(
        "INSERT OR REPLACE INTO tasks (id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, "s1", goal, "pending",
         datetime.now(UTC).isoformat(),
         datetime.now(UTC).isoformat()),
    )


async def run_review_demo(repo_root=".") -> dict:
    repo_root = Path(repo_root)
    paw_db = Path("/tmp/paw_beta_review/demo.db")
    paw_db.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_db)
    await _bootstrap("beta-review-01", f"Review {repo_root} for invariant regressions")

    profile = REVIEW.execution_profile
    guard = PolicyGuard(interactive=False)
    autonomy = AutonomyController(policy_guard=guard, budget=profile.resolved_autonomy_budget())
    runtime = PawRuntime(
        autonomy=autonomy, context_compiler=None, model_router=ModelRouter(),
        model_executor=LocalModelExecutor(), execution_profile=profile,
        readiness="READY", current_revision="HEAD",
        checkpoint_interval=100, auto_checkpoint=False,
    )

    regressions = []
    py_files = [f for f in repo_root.rglob("*.py") if ".git" not in f.parts]
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(py_file.relative_to(repo_root)) if py_file.is_relative_to(repo_root) else str(py_file)
        if "open(" in content and "'w'" in content:
            regressions.append({"type": "potential_write", "file": rel, "finding": "open() with write mode"})
        if "os.remove(" in content or "os.unlink(" in content:
            regressions.append({"type": "potential_delete", "file": rel, "finding": "os.remove/unlink"})

    async def review_step(task_id, proposed) -> ExecutionObservation:
        evidence = [
            {"type": "review_scope", "files_scanned": len(py_files), "regressions_found": len(regressions)},
            {"type": "regressions", "items": regressions[:5]},
        ]
        side_effects = [c for c in proposed.capabilities if is_side_effect_capability(c)]
        return ExecutionObservation(
            step_id=proposed.operation_id, action_id=proposed.operation_id,
            result={"done": True, "progress": 1.0, "evidence": evidence,
                    "side_effects_blocked": len(side_effects), "regressions": regressions,
                    "files_scanned": len(py_files)},
            success=True, resources_used=ResourceUsage(),
        )

    outcome = await runtime.run("beta-review-01",
        task_goal="Scan source tree for invariant regressions.",
        step_fn=review_step)
    if outcome.last_observation and outcome.last_observation.result:
        ro = outcome.last_observation.result
        outcome.evidence = ro.get("evidence", [])
        outcome.uncertainty = {"confidence": 0.8, "regressions_found": len(regressions),
            "side_effects_blocked": ro.get("side_effects_blocked", 0)}
        if regressions:
            outcome.next_action = f"Review {len(regressions)} potential invariant regressions found."
        else:
            outcome.next_action = "No invariant regressions detected. Source tree is clean."
    await db.close()
    return outcome.to_answer()


if __name__ == "__main__":
    result = asyncio.run(run_review_demo("/home/huythong/.hybridagent/workspaces/default"))
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
