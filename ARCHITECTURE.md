# PAW Architecture

PAW is a **Personal Agent Runtime** built as a small, explicit, deterministic
core that owns its abstractions. External systems (QwenPaw, Ollama, OpenCode,
NotebookLM, Antigravity, …) are adapters — they convert formats, they never
own or redefine PAW's concepts.

## Design principles (constitutional)

```
one canonical implementation · typed boundaries · small core · explicit state
deterministic first (LLM only where uncertainty requires it)
minimum sufficient context · policy before side effects
durable state before long autonomy · bounded autonomy · observable decisions
replaceable providers · replaceable executors · zero vendor lock-in
```

## Module map (`src/paw/`)

```
core/
  models.py          Identity/task/model/policy types (ModelManifest, Capability, …)
  storage.py         SQLite schema + DB singleton (one canonical store)
  session.py         SessionManager      (session lifecycle)
  task.py            TaskManager         (task lifecycle)
  skills.py          SkillFabric        (skill registry + discovery)
  context.py         ContextBudget/ContextFragment/TaskContext
  context_compiler.py ContextCompiler   (WHAT to know — hybrid retrieval + dedup)
  semantic.py        AdvancedSkillSelector (lexical + semantic skill match)
  memory.py          AdvancedMemoryRetriever (hybrid memory retrieval)
  embeddings.py      EmbeddingProvider + Local/Ollama embeddings
  planner.py         TaskNode / plan representation
  task_scheduler.py  TaskGraph + TaskScheduler (DAG, topo sort, cycle detect)
  identity/         Identity module (Identity / IdentityManager — key/value self-identity store)
  policy.py          PolicyGuard v2 (explainable, aggregate gate, fail-closed)
  autonomy.py        AutonomyController + detectors (budget/progress/repetition/stall)
  execution_profile.py ExecutionProfile (precise/fast/safe/develop presets)
  model_router.py    ModelRegistry + ModelRouter + ProviderRegistry (provider-aware)
  model_executor.py  ModelExecutor (dispatch to provider, local fallback)
  executor.py        Executor abstraction + policy
  executor_policy.py Executor policy glue
  checkpoint.py      CheckpointStore + CheckpointManager (durable resume)
  ledger.py          TaskLedger + typed event loggers (full observability)
  intelligent_planner.py Advanced planner
providers/
  __init__.py        ModelProvider / SkillProvider / MemoryProvider / PersonaProvider Protocols
  ollama/            OllamaProvider (local models, stdlib HTTP, graceful degradation)
  qwenpaw/ reme/ persona/  Format adapters only (no behavior ownership)
knowledge/           Knowledge engine (chunk / index / citation / evidence / source)
cli/                 `paw` command-line entry points
```

## The four-part intelligence core

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

- **Skill Fabric** — *how* to act (selected skills + instructions).
- **Context Compiler** — *what* to know now (memory + knowledge + session +
  ledger + skills, budget-limited, deduped, progressively loaded).
- **Task Graph** — *what* must happen (validated DAG; cycles rejected, failure
  propagates, resumable).
- **Autonomy Controller** — *should* I continue? Bounded by budget, progress,
  repetition and stall detectors, and **always gated by Policy first**.

## Runtime loop

```
User Request
  → Task
  → Skill Discovery
  → Context Compilation
  → Task Plan / Task Graph
  → Autonomy Budget
  → Policy Authorization        ← single authority; ASK/DENY = STOP
  → Executor / Model Routing    ← provider-aware, health-checked
  → Execution
  → Observation
  → Progress Evaluation
  → Autonomy Decision (CONTINUE / REPLAN / ESCALATE / WAIT / STOP)
  → Checkpoint
  → Task Ledger
```

Every transition is recorded in the **Task Ledger** (16+ event types) so the
runtime is fully observable and resumable. Checkpoints persist the loop state;
on resume, completed steps are not re-executed.

## Safety invariants

1. `Policy.ASK` must **not** execute — ASK → STOP → `WAITING_APPROVAL`.
2. `ASK ≠ ALLOW`, `DENY ≠ ALLOW`.
3. Policy is the **single authority**; skills/executors only *request* capability.
4. Autonomous loops are **bounded** (hard iteration limit, typed stop reasons).
5. Durable state is written **before** any long autonomy runs.

## Phase history

Phases 0–16 are complete (all gates PASS). See `PROFILE.md` for the per-phase
implementation log and `README.md` for the quick start.
