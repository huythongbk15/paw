"""
PAW Demo — Full workflow demonstration
"""

import asyncio
from paw.core import (
    SessionManager, TaskManager, TaskLedger, MockExecutor,
    IntelligentPlanner, SemanticMatcher, MemoryStore, MemoryRetriever,
    MemoryType, create_memory, PolicyGuard, Capability, TaskStatus, PolicyDecision, TaskEventType,
    SkillFabric, get_skill_fabric,
    ExecutorPolicyEnforcer,
)
from paw.core.storage import set_db_path, db
from pathlib import Path
import tempfile

async def main():
    # Setup
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "demo.db"
    await set_db_path(db_path)
    await db.initialize()

    print("=" * 60)
    print("PAW Core — Full Workflow Demo")
    print("=" * 60)

    # 1. Session lifecycle
    print("\n--- 1. Session Lifecycle ---")
    session = await SessionManager.create("demo-project")
    print(f"Session created: {session.id}")

    # 2. Intelligent Planning
    print("\n--- 2. Intelligent Planning ---")
    planner = IntelligentPlanner()
    plan = await planner.plan("tinh 2 + 2 va tim kiem thong tin", session.id)
    print(f"Goal: {plan['goal']}")
    print(f"Intents: {plan['intents']}")
    print(f"Steps: {len(plan['nodes'])}")
    print(f"Confidence: {plan['confidence']:.2f}")
    for node in plan["nodes"]:
        print(f"  Step {node['order']}: {node['goal']} [{node['estimated_effort']}]")

    # 3. Memory
    print("\n--- 3. Memory Integration ---")
    m1 = await create_memory(MemoryType.EPISODIC, "Nguoi dung hoi tinh toan", project_id="demo-project")
    m2 = await create_memory(MemoryType.SEMANTIC, "Python programming is powerful", project_id="demo-project")
    print(f"Stored {m1.id}, {m2.id}")

    store = MemoryStore()
    recent = await store.get_recent(5)
    print(f"Recent memories: {len(recent)}")

    search_results = await store.search("Python")
    print(f"Search 'Python': {len(search_results)} results")
    for r in search_results:
        print(f"  Score {r['relevance_score']:.2f}: {r['record'].content[:40]}")

    # 4. Semantic Matching
    print("\n--- 4. Semantic Skill Matching ---")
    fabric = await get_skill_fabric()
    matcher = SemanticMatcher(fabric)
    scores = await matcher.match("hello world", max_results=5)
    print(f"Matched {len(scores)} skills for 'hello world'")
    for s in scores[:3]:
        print(f"  {s.skill_name}: {s.combined_score:.3f}")

    # 5. Policy Guard
    print("\n--- 5. Policy Guard ---")
    guard = PolicyGuard()
    await guard.add_rule(capability=Capability.DESTRUCTIVE, decision=PolicyDecision.DENY)
    decision = await guard.check_capabilities([Capability.FILESYSTEM_READ, Capability.DESTRUCTIVE])
    print(f"Policy check: filesystem.read={decision[Capability.FILESYSTEM_READ]}, destructive={decision[Capability.DESTRUCTIVE]}")

    # 6. Executor with Policy
    print("\n--- 6. Executor with Policy ---")
    enforcer = ExecutorPolicyEnforcer(guard)
    check = await enforcer.pre_execute_check("task-1", "test", [Capability.FILESYSTEM_READ])
    print(f"Pre-execute check: allowed={check.allowed}, decision={check.decision}")

    # 7. Full lifecycle with MockExecutor
    print("\n--- 7. Full Lifecycle (MockExecutor) ---")
    task = await TaskManager.create(session.id, "demo goal", "demo-project", requested_capabilities=[Capability.FILESYSTEM_READ])
    print(f"Task created: {task.id}")

    ledger = TaskLedger()
    await ledger.record(task.id, TaskEventType.TASK_CREATED, {"goal": "demo goal"})

    # Execute with policy
    from paw.core.executor_policy import PolicyEnforcedExecutor
    pe_executor = PolicyEnforcedExecutor(MockExecutor(), guard)
    result = await pe_executor.execute(task.id, "demo goal", [Capability.FILESYSTEM_READ], "test context")
    print(f"Execution result: success={result['result']['success']}, blocked={result['blocked']}")

    await ledger.record(task.id, TaskEventType.TASK_COMPLETED, {"result": "success"})
    task = await TaskManager.update_status(task.id, TaskStatus.COMPLETED)
    print(f"Task completed: {task.status}")

    await SessionManager.update(session)
    print(f"Session updated: {session.id}")

    # Summary
    print("\n" + "=" * 60)
    print("Demo Complete!")
    events = await ledger.get_events(task.id)
    print(f"Events in ledger: {len(events)}")
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())