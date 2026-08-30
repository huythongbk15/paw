# PAW — Personal Agent Workstation

**Independent Personal Agent Runtime.** Local-first, zero vendor lock-in, CLI-first.
PAW owns its core abstractions (Identity, Session, Task, Skill Fabric, Context
Compiler, Autonomy Controller, Policy Engine, Model Router, Task Ledger) — external
systems are adapters, never owners.

> Status: **Phases 0–16 complete.** All 16 acceptance gates pass; full test suite green.

---

## Install

```bash
pip install .          # builds paw-0.1.0 wheel (root pyproject.toml, setuptools)
paw --version          # prints the installed version
```

Pure-Python, SQLite-backed. No external services required to run the runtime loop.

## CLI

```bash
paw --version                 # version
paw profiles [name]           # list execution profiles or show one (precise/fast/safe/develop)
```

## Quick start (Python API)

```python
import asyncio
from pathlib import Path
from paw.core.storage import db, set_db_path
from paw.core.session import SessionManager
from paw.core.task import TaskManager
from paw.core.context_compiler import ContextCompiler
from paw.core.policy import PolicyGuard
from paw.core.autonomy import AutonomyController, AutonomyDecision
from paw.core.model_router import ModelRouter
from paw.core.model_executor import ModelExecutor

async def run():
    # 1. Storage
    await set_db_path(Path(".paw/paw.db"))
    await db.initialize()

    # 2. Session + Task
    session = await SessionManager.create()
    task = await TaskManager.create(session.id, goal="Summarize the project")

    # 3. Context
    compiler = ContextCompiler()
    context, _ = await compiler.compile(task.id, "Summarize", session_id=session.id)

    # 4. Policy -> Autonomy (single authority, fail-closed: ASK/DENY = STOP)
    guard = PolicyGuard(interactive=False)
    ac = AutonomyController(policy_guard=guard)
    decision, stop = await ac.decide(task.id, required_capabilities=[])
    assert decision == AutonomyDecision.CONTINUE

    # 5. Model routing + execution (provider-aware, local fallback)
    router = ModelRouter()                      # discovers local + any provider models
    selection = await router.route(task.id, "Summarize", role="fast")
    executor = ModelExecutor()                  # local stand-in (shares router's ProviderRegistry)
    result = await executor.complete(selection, [{"role": "user", "content": "Summarize now"}])
    return result

asyncio.run(run())
```

## Architecture — the four-part intelligence core

```
                 Skill Fabric (HOW)
                     /\
                    /  \
                   /    \
          Context Compiler (WHAT) ─── Task Graph (WHAT to do)
                   \             /
                    \           /
                     \         /
                 Autonomy Controller (SHOULD I keep going?)
```

| Component | Answers |
|-----------|---------|
| **Skill Fabric** | HOW should I do it? |
| **Context Compiler** | WHAT should I know right now? |
| **Task Graph** | WHAT needs to happen (DAG of steps)? |
| **Autonomy Controller** | SHOULD I keep going — and when must I stop? |

Every side-effecting action is gated by the **Policy Engine** (the single
authority). `ASK` and `DENY` halt the loop before execution — never after
(constitution: *ASK = STOP, never execute*).

### Runtime loop

```
User Request → Task → Skill Discovery → Context Compilation → Task Plan/Graph
    → Autonomy Budget → Policy Authorization → Model Routing → Execution
    → Observation → Progress Evaluation → Autonomy Decision
    → CONTINUE / REPLAN / ESCALATE / WAIT / STOP → Checkpoint → Task Ledger
```

State is persisted to SQLite continuously, so long autonomous runs can be
**checkpointed and resumed** without repeating completed steps.

## Providers (pluggable, zero lock-in)

- `OllamaProvider` — local models via stdlib HTTP, graceful degradation when
  the Ollama server is down.
- `ModelExecutor` — dispatches a `ModelSelection` to the right provider, falling
  back to a local stand-in when no model server is available.
- Adapters for external systems (`qwenpaw`, `reme`, `persona`) are format
  converters only — they never redefine PAW's core abstractions.

## Testing

```bash
pytest                 # full suite (SQLite-backed, no network)
ruff check .           # lint
```

Each phase ships its own integration test; `tests/test_phase16_integration.py`
exercises the entire runtime loop end-to-end against a real temp SQLite DB.

## Phase status

| Phase | Scope | Gate |
|-------|-------|------|
| 0–9 | Core lifecycle, planner, policy, memory, task graph | PASS |
| 10 | Core Runtime Foundation (context, autonomy, policy, checkpoint) | PASS |
| 11 | Ollama Provider Layer | PASS |
| 12 | Advanced Memory Retrieval (hybrid lexical + semantic) | PASS |
| 13 | Enhanced Context Builder (dedup + progressive skill load) | PASS |
| 14 | Policy Guard v2 (explainable, loop-enforced) | PASS |
| 15 | Model Router v2 (provider-aware, health-checked) | PASS |
| 16 | Full integration & docs | PASS |

See `PROFILE.md` for the detailed per-phase implementation log.
