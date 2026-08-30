# PAW Core — Examples

Runnable snippets for PAW 0.1.0. All snippets are async; run inside `async def main():`.

## 0. Install & CLI
```bash
pip install .
paw --version
paw profiles            # list execution-profile presets (precise/fast/safe/develop)
```

## 1. Bootstrap the agent's identity
```python
from paw.core.identity import IdentityManager

async def main():
    mgr = IdentityManager()
    await mgr.bootstrap()                 # seeds name=PAW, version, persona, …
    ident = await mgr.load()
    print(ident.name, ident.version, ident.persona)
    await mgr.set("prefs", {"theme": "dark", "verbose": True})
    print(await mgr.get("prefs"))
```

## 2. Create a session + task
```python
from paw.core.session import SessionManager
from paw.core.task import TaskManager, TaskStatus

async def main():
    sm, tm = SessionManager(), TaskManager()
    session = await sm.create(profile={"role": "default"})
    task = await tm.create(session.id, title="Summarize doc", description="...")
    await tm.update(task.id, status=TaskStatus.IN_PROGRESS)
    print(session.id, task.id)
```

## 3. Compile context (hybrid retrieval)
```python
from paw.core.context_compiler import ContextCompiler, ContextBudget
from paw.core.context import ContextFragment

async def main():
    compiler = ContextCompiler(budget=ContextBudget(max_tokens=4000, max_fragments=15))
    context, plan = await compiler.compile(task.id, "summarize the key points",
                                            session_id=session.id)
    for frag in context.fragments:
        print(f"[{frag.source}] {frag.priority} {frag.content[:60]}")
    print(format_explain_report(plan))
```

## 4. Policy gate before any side effect
```python
from paw.core.policy import PolicyGuard, PolicyRule, Capability

async def main():
    guard = PolicyGuard()
    guard.add_rule(PolicyRule(id="protect", capability=Capability.FILE_DELETE,
                              decision="deny"))
    verdict = guard.evaluate_request([Capability.FILE_DELETE])
    assert verdict.verdict == "block"          # DENY -> never execute
```

## 5. Autonomy loop (policy-gated)
```python
from paw.core.autonomy import AutonomyController, AutonomyBudget
from paw.core.policy import PolicyGuard, Capability

async def main():
    ctrl = AutonomyController(budget=AutonomyBudget(max_iterations=8))
    guard = PolicyGuard()
    decision = await ctrl.decide(
        progress_detected=True,
        required_capabilities=[Capability.NETWORK_HTTP],
    )
    print(decision.decision, decision.stop_reason)
```

## 6. Route + execute a model (provider-aware)
```python
from paw.core.model_router import get_model_router, get_model_registry
from paw.core.model_executor import ModelExecutor
from paw.core.models import ModelRole

async def main():
    registry = get_model_registry()
    await registry.register_ollama_models()        # graceful if Ollama absent
    router = get_model_router()
    selection = await router.route(role=ModelRole.REASONING, query="explain recursion")
    out = await ModelExecutor().complete(selection, [{"role": "user", "content": "explain recursion"}])
    print(out.text[:120])
```

## 7. Select skills (hybrid match)
```python
from paw.core.semantic import AdvancedSkillSelector

async def main():
    selector = AdvancedSkillSelector(fabric=None, auto_attach_embeddings=True)
    results = await selector.select("search the web for prices")
    for r in results[:3]:
        print(r.manifest.name, round(r.final_score, 3))
```

## 8. Memory add + retrieve
```python
from paw.core.memory import create_memory, MemoryRecord, MemoryType

async def main():
    store = await create_memory()
    await store.add(MemoryRecord(content="Paris is the capital of France",
                                 memory_type=MemoryType.SEMANTIC))
    hits = await store.retriever().score_records("capital of France", limit=5)
    for h in hits:
        print(h.record.content, round(h.relevance_score, 3))
```

## 9. Task graph (DAG)
```python
from paw.core.task_scheduler import TaskGraph, TaskScheduler

async def main():
    g = TaskGraph()
    g.add_node("fetch"); g.add_node("parse"); g.add_node("write")
    g.add_dependency("parse", "fetch")
    g.add_dependency("write", "parse")
    assert g.detect_cycles() == []
    print(TaskScheduler(g).topological_order())
```

## 10. Ledger + checkpoint (resumable runtime)
```python
from paw.core.ledger import TaskLedger, TaskEventType
from paw.core.checkpoint import CheckpointManager

async def main():
    ledger = TaskLedger()
    await ledger.log_context_compiled(task.id, budget_used=900, fragments=6)
    await CheckpointManager().checkpoint_task(task.id, state={"step": 1})
    cp = await CheckpointManager().get_latest(task.id)
    print(cp.state)
```
