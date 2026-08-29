# PAW Core — API Reference

> Generated for PAW 0.1.0 (Phase 0–17). All imports are from the `paw` package.
> PAW is local-first, pure-Python, zero vendor lock-in.

## Top-level layout (`src/paw/`)

```
paw/
  core/        Domain models + runtime services (Session, Task, Context, Policy,
               Autonomy, Model routing, Memory, Identity, Ledger, Checkpoint, …)
  knowledge/   Knowledge engine (chunk / index / citation / evidence / source)
  providers/   Provider Protocols + local adapters (ollama/, qwenpaw/, reme/, persona/)
  cli/         `paw` command-line entry points
```

## Session & Task lifecycle

### `SessionManager` — `paw.core.session`
```python
from paw.core.session import SessionManager

mgr = SessionManager()
await mgr.create(profile={"role": "default"})        # -> Session
await mgr.get(session_id)
await mgr.list()                                      # -> list[Session]
await mgr.update(session_id, profile={...})
await mgr.close(session_id)
```

### `TaskManager` — `paw.core.task`
```python
from paw.core.task import TaskManager

tm = TaskManager()
await tm.create(session_id, title="Do X", description="...")   # -> Task
await tm.get(task_id)
await tm.update(task_id, status=TaskStatus.IN_PROGRESS)
await tm.complete(task_id, result=TaskResult(...))
```

## Context Compiler (WHAT to know now)

### `ContextCompiler` — `paw.core.context_compiler`
```python
from paw.core.context_compiler import ContextCompiler, ContextBudget

compiler = ContextCompiler(
    budget=ContextBudget(max_tokens=4000, max_fragments=20),
    auto_attach_embeddings=True,        # auto-upgrade to hybrid if Ollama runs
)
context, plan = await compiler.compile(
    task_id, query, session_id=session_id,
    execution_profile=my_profile,        # optional budget override
)
# context.fragments -> list[ContextFragment]; plan has explain entries
report = format_explain_report(plan)     # human-readable selection report
```

* Hybrid retrieval (lexical + semantic) with re-ranking.
* Cross-source near-duplicate dedup; progressive Level-1 skill body loading.
* `auto_attach_embeddings=True` calls `try_ollama_embedding_provider()` lazily.

## Policy Guard (single authority — ASK/DENY = STOP)

### `PolicyGuard` — `paw.core.policy`
```python
from paw.core.policy import PolicyGuard, PolicyRule, PolicyDecision

guard = PolicyGuard()
guard.add_rule(PolicyRule(id="no_delete", capability=Capability.FILE_DELETE, decision="deny"))
detail = guard.check_detailed(capability=Capability.FILE_DELETE, action="rm")
# detail.decision in {allow, ask, deny}; detail.source == "rule:no_delete"
verdict = guard.evaluate_request([Capability.FILE_DELETE])   # go | ask | block
```
* `check_detailed()` is explainable (matched rule, conditions evaluated).
* `evaluate_request()` is the aggregate single-authority gate used by the autonomy loop.

## Autonomy Controller (SHOULD I keep going?)

### `AutonomyController` — `paw.core.autonomy`
```python
from paw.core.autonomy import AutonomyController, AutonomyBudget, StopReason

ctrl = AutonomyController(budget=AutonomyBudget(max_iterations=10, max_duration_s=300))
decision = await ctrl.decide(
    progress_detected=True,
    required_capabilities=[Capability.NETWORK_HTTP],   # consulted against Policy first
)
# decision.decision in {continue, replan, escalate, wait, stop}
# decision.stop_reason: Optional[StopReason] (typed)
```
Gated by Policy before budget: DENY → `stop(POLICY_DENIED)`, ASK non-interactive → `stop(POLICY_ASK_REQUIRED)`, ASK interactive → `ask`.

## Model routing & execution (provider-aware)

### `ModelRouter` / `ModelRegistry` — `paw.core.model_router`
```python
from paw.core.model_router import get_model_router, get_model_registry

registry = get_model_registry()
await registry.register_ollama_models()        # discover local Ollama models (graceful)
router = get_model_router()
selection = await router.route(role=ModelRole.REASONING, query="explain X")
# selection.model.provider only references *available* providers; falls back to "local"
```

### `ModelExecutor` — `paw.core.model_executor`
```python
from paw.core.model_executor import ModelExecutor

executor = ModelExecutor()
out = await executor.execute(selection, prompt="...")   # dispatches to provider
```

## Skills

### `SkillFabric` — `paw.core.skills`
```python
from paw.core.skills import get_skill_fabric, SkillManifest, Capability

fabric = get_skill_fabric()
await fabric.register_skill(SkillManifest(name="Search", trigger="search",
                                          capabilities=[Capability.NETWORK_HTTP]))
skills = fabric.list_skills(enabled_only=True)
```

### `AdvancedSkillSelector` — `paw.core.semantic`
```python
from paw.core.semantic import AdvancedSkillSelector

selector = AdvancedSkillSelector(fabric, auto_attach_embeddings=True)
results = await selector.select("search the web")   # hybrid lexical + semantic ranking
```

## Memory & Knowledge

### Memory — `paw.core.memory`
```python
from paw.core.memory import create_memory, MemoryRecord, MemoryType

store = await create_memory()
await store.add(MemoryRecord(content="fact", memory_type=MemoryType.SEMANTIC))
retriever = store.retriever()                       # AdvancedMemoryRetriever
hits = await retriever.score_records("fact", limit=5)
```

### Knowledge — `paw.knowledge`
```python
from paw.knowledge.index import KnowledgeIndex

idx = KnowledgeIndex()
await idx.add_document(path="doc.md", text="...")
chunks = await idx.search_chunks("query", limit=5)
```

### Embeddings — `paw.core.embeddings`
```python
from paw.core.embeddings import (
    OllamaEmbeddingProvider, LocalEmbeddingProvider, try_ollama_embedding_provider,
)

provider = await try_ollama_embedding_provider()    # None if Ollama down
if provider:
    vecs = await provider.embed(["hello", "world"])
```
* `LocalEmbeddingProvider` is an offline hashed bag-of-words fallback (lexical-equivalent).
* True semantic needs a local Ollama model (e.g. `nomic-embed-text`).

## Ledger & Checkpoint (observability + resumability)

### `TaskLedger` — `paw.core.ledger`
```python
from paw.core.ledger import TaskLedger, TaskEventType

ledger = TaskLedger()
await ledger.log_context_compiled(task_id, budget_used=1200, fragments=8)
events = await ledger.get_events(task_id, types=[TaskEventType.CONTEXT_COMPILED])
```

### `CheckpointManager` — `paw.core.checkpoint`
```python
from paw.core.checkpoint import CheckpointManager

mgr = CheckpointManager()
await mgr.checkpoint_task(task_id, state={"step": 3})
cp = await mgr.get_latest(task_id)
```

## Identity (Phase 4 spec)

### `IdentityManager` / `Identity` — `paw.core.identity`
```python
from paw.core.identity import IdentityManager, Identity

mgr = IdentityManager()
await mgr.bootstrap()                 # seed defaults (name=PAW, version, …)
await mgr.set("prefs", {"theme": "dark"})
name = await mgr.get("name")          # "PAW"
ident = await mgr.load()              # typed Identity
print(ident.name, ident.version, ident.persona)
```
* Backed by the key/value `identity` table (local SQLite).
* `get`/`set` transparently JSON-(de)serialize non-string values.

## Task Graph (what must happen)

### `TaskGraph` / `TaskScheduler` — `paw.core.task_scheduler`
```python
from paw.core.task_scheduler import TaskGraph, TaskScheduler

g = TaskGraph()
g.add_node("a"); g.add_node("b"); g.add_dependency("b", "a")
assert g.detect_cycles() == []        # cycle rejected
scheduler = TaskScheduler(g)
order = scheduler.topological_order() # ["a", "b"]
```
