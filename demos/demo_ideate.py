"""BETA B-05: Ideate demo - architecture-idea exploration with alternatives."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from paw.core.autonomy import AutonomyController
from paw.core.beta_profiles import IDEOATE, is_side_effect_capability
from paw.core.model_executor import LocalModelExecutor
from paw.core.model_router import ModelRouter
from paw.core.models import ExecutionObservation, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.storage import db, set_db_path

ALTERNATIVES = [
    {"name": "A1: SQLite-first embedded", "description": "Single SQLite file, local-only.",
     "pros": ["Zero daemon", "ACID", "Single file portable"], "cons": ["No horizontal scaling"], "score": 0.85},
    {"name": "A2: SQLite + optional cloud", "description": "SQLite primary, cloud behind privacy gate.",
     "pros": ["Zero vendor lock-in", "Local-first default", "Optional cloud"], "cons": ["Complexity"], "score": 0.92},
    {"name": "A3: In-memory + sync", "description": "All state in dict, explicit sync.",
     "pros": ["Fastest", "Simple"], "cons": ["Data loss on crash"], "score": 0.45},
]


async def _bootstrap(task_id, goal):
    await db.initialize()
    await db.execute(
        "INSERT OR REPLACE INTO tasks (id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, "s1", goal, "pending",
         datetime.now(UTC).isoformat(),
         datetime.now(UTC).isoformat()),
    )


async def run_ideate_demo(question="What storage strategy maximizes local-first?") -> dict:
    paw_db = Path("/tmp/paw_beta_ideate/demo.db")
    paw_db.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_db)
    await _bootstrap("beta-ideate-01", f"Explore alternatives for: {question}")

    profile = IDEOATE.execution_profile
    guard = PolicyGuard(interactive=False)
    autonomy = AutonomyController(policy_guard=guard, budget=profile.resolved_autonomy_budget())
    runtime = PawRuntime(
        autonomy=autonomy, context_compiler=None, model_router=ModelRouter(),
        model_executor=LocalModelExecutor(), execution_profile=profile,
        readiness="READY", current_revision="HEAD",
        checkpoint_interval=100, auto_checkpoint=False,
    )

    async def ideate_step(task_id, proposed) -> ExecutionObservation:
        evidence = [{"type": "question", "text": question},
                     {"type": "alternatives", "items": ALTERNATIVES}]
        best = max(ALTERNATIVES, key=lambda a: a["score"])
        evidence.append({"type": "decision", "best": best["name"], "score": best["score"]})
        side_effects = [c for c in proposed.capabilities if is_side_effect_capability(c)]
        return ExecutionObservation(
            step_id=proposed.operation_id, action_id=proposed.operation_id,
            result={"done": True, "progress": 1.0, "evidence": evidence,
                    "side_effects_blocked": len(side_effects)},
            success=True, resources_used=ResourceUsage(),
        )

    outcome = await runtime.run("beta-ideate-01",
        task_goal=f"Explore architecture alternatives for: {question}",
        step_fn=ideate_step)
    if outcome.last_observation and outcome.last_observation.result:
        ro = outcome.last_observation.result
        outcome.evidence = ro.get("evidence", [])
        outcome.uncertainty = {"confidence": 0.92, "alternatives_evaluated": len(ALTERNATIVES),
            "side_effects_blocked": ro.get("side_effects_blocked", 0)}
        outcome.next_action = "Document decision in an ADR. Proceed with A2: SQLite + optional remote."
    await db.close()
    return outcome.to_answer()


if __name__ == "__main__":
    result = asyncio.run(run_ideate_demo())
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
