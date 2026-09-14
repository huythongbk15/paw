# PAW Project Map & Capability Diagram

> **Status**: VERIFIED on clean revision after all phases.
> This document is a human-readable map of the PAW codebase — what exists, what each piece does, and how everything connects.

## 1. Repository Layout

```
src/paw/
├── __init__.py              # Version, package entrypoint
├── cli/
│   └── __init__.py          # Typer CLI: `paw chat`, `paw beta profiles`, `paw bench`, `paw doc`
├── core/                    # 🧠 Core runtime — all domain contracts owned by PAW
│   ├── models.py            # Pydantic dataclasses: TaskStatus, Capability, ModelManifest, ModelSelection,
│   │                        #   ProposedAction, ExecutionObservation, ResourceUsage,
│   │                        #   AutonomyDecision, StopReason, ExtendedTaskStatus, TaskEventType, etc.
│   ├── storage.py           # SQLite database, schema migrations (additive only), transaction context
│   ├── config.py            # Pydantic BaseSettings: paths, provider prefs, knowledge dir
│   ├── logging.py           # structlog configuration (stderr-separated)
│   ├── session.py           # SessionManager — durable session lifecycle
│   ├── task.py              # Task + TaskManager — primary unit of work, persists to SQLite
│   ├── planner.py           # Plan + Planner + TaskNode — decomposes goals into DAG nodes
│   ├── task_scheduler.py    # TaskGraph, TaskScheduler, TaskDependency — validates DAGs (no cycles, no missing deps)
│   ├── executor.py          # Executor protocol, ExecutorRegistry, CapabilityRouter, MockExecutor
│   ├── executor_policy.py   # ExecutorPolicyEnforcer — policy-before-execution
│   ├── model_router.py      # ModelRouter — selects best model by role/cost/latency/complexity/privacy
│   ├── model_executor.py    # ModelExecutor — dispatches to ModelProvider (shared ProviderRegistry)
│   ├── autonomy.py          # AutonomyController — budget/progress/repetition/stall tracking, decisions
│   ├── policy.py            # PolicyGuard — capability evaluation, ASK/DENY/ALLOW/SANDBOX, single authority
│   ├── privacy.py           # PrivacyClass enum, REMOTE_DISCLOSURE_DEFAULTS, gate_remote_disclosure
│   ├── context.py           # ContextBudget, ContextFragment, TaskContext, ContextBuilder (facade)
│   ├── context_compiler.py  # ContextCompiler — assembles context from memory/knowledge/skills/ledger/session/repo
│   ├── checkpoint.py        # CheckpointStore, ResumeManager, OperationRecord, OperationRecordStore
│   ├── reasonering_contracts.py  # ReconnaissanceResult, TaskSignals, OODCondition, classify_inference
│   ├── runtime.py           # PawRuntime — the ONE orchestration loop (run / run_agent / run_graph)
│   ├── runtime_persistence.py    # RuntimePersistence — commit_operation, commit_checkpoint
│   ├── skills.py            # SkillManifest, SkillFabric, get_skill_fabric — progressive loading (L0/L1/L2)
│   ├── memory.py            # MemoryStore — episodic/semantic memory with hybrid retrieval
│   ├── memory_index.py      # MemoryIndex — lexical + semantic embedding retrieval
│   ├── beta_profiles.py     # BetaProfile, SideEffectPolicy, ExecutionProfile integration
│   └── identity/
│       └── __init__.py      # Identity, IdentityManager — user/agent identity key-value store
├── knowledge/               # 📚 Knowledge Engine — local-first, SQLite-backed
│   ├── __init__.py          # Package exports
│   ├── index.py             # KnowledgeIndex — search chunks/evidence/citations
│   ├── source.py            # KnowledgeSource, KnowledgeSourceManager
│   ├── chunk.py             # KnowledgeChunk dataclass
│   ├── evidence.py          # KnowledgeEvidence dataclass
│   ├── citation.py          # KnowledgeCitation dataclass
│   ├── checksum.py          # SHA-256 checksum for incremental diff (E1-06)
│   ├── dependencies.py      # extract_dependencies — AST-based import graph (E1-09)
│   ├── symbols.py           # extract_symbols — AST-based symbol ownership (E1-10)
│   ├── associations.py      # associate_tests — test-to-source links (E1-11)
│   ├── changes.py           # recent_changes — git log reader (E1-12)
│   ├── normalization.py     # Knowledge normalization helpers
│   ├── observations.py      # Knowledge observation extraction
│   ├── history.py           # Knowledge history/persistence
│   └── constraints.py       # Knowledge constraint checking
├── providers/
│   ├── __init__.py          # ModelProvider Protocol, ProviderRegistry, register_ollama_models
│   └── ollama/
│       └── provider.py      # OllamaProvider — stdlib HTTP (urllib + asyncio), graceful degradation
├── adapters/                # 🗃️ Archived integrations (QwenPaw, ReMe, personas) — not active
├── bench/                   # 🧪 Benchmark & verification system
│   ├── __init__.py          # CaseManifest, ExpectedEvidence, FixtureRef, validate_case_manifest
│   ├── runner.py            # Deterministic runner: run_case, run_case_file, write_runs_jsonl
│   ├── verification.py      # VerificationSpec, VerificationRecord, VerificationResult
│   ├── recall.py            # RecallResult, measure_recall (E1-23)
│   ├── tokens.py            # TokenResult, measure_tokens (E1-24)
│   ├── e1_production.py     # E1-27 production measurement runner (tracked, canonical)
│   ├── cases.py             # Canonical case registry
│   └── E0/                  # Case manifest files (YAML)
└── executors/               # Legacy executor implementations (kept for compat)
```

## 2. Architecture: Four-Part Intelligence Core

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PAW Core Runtime                            │
│                              (PawRuntime)                           │
│                                                                     │
│  Skill Fabric (HOW) ◄──────────────► Context Compiler (WHAT)        │
│         │                                     │                      │
│         ▼                                     ▼                      │
│   Task Graph (WHY) ◄────────► Autonomy Controller (SHOULD)          │
│                                                                     │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐ │
│  │ Policy  │  │ Model    │  │ Executor │  │ Skill   │  │ Memory / │ │
│  │ Guard   │  │ Router   │  │ Router   │  │ Fabric  │  │ Knowledge│ │
│  │ (ASK=   │  │ (score   │  │ (cap     │  │ (load   │  │ Engine   │ │
│  │ DENY)   │  │ models)  │  │ match)   │  │ skills) │  │          │ │
│  └─────────┘  └──────────┘  └──────────┘  └─────────┘  └──────────┘ │
│         │           │             │           │            │         │
│         ▼           ▼             ▼           ▼            ▼         │
│    Task Ledger  ModelExec   ExecutorExec  SkillExec   DB (SQLite)   │
│    (audit trail)(provider)  (filesystem)  (markdown)               │
└─────────────────────────────────────────────────────────────────────┘
```

### The Four Quadrants (Per PROFILE.md)

| Quadrant | Module | Role | Key Files |
|----------|--------|------|-----------|
| **Skill Fabric (HOW)** | `core/skills.py` | Loads and provides skills; progressive L0/L1/L2 loading | `SkillManifest`, `SkillFabric`, `get_skill_fabric()` |
| **Context Compiler (WHAT)** | `core/context_compiler.py` | Assembles context from 6 sources within budget | `ContextCompiler`, `ContextPlan`, `ContextCandidate`, `ContextManifest` |
| **Task Graph (WHY)** | `core/task_scheduler.py` | DAG decomposition with cycle/missing-dep validation | `TaskGraph`, `TaskScheduler`, `TaskNode` |
| **Autonomy Controller (SHOULD)** | `core/autonomy.py` | Budget tracking, progress/repetition/stall detection, typed StopReason | `AutonomyController`, `AutonomyBudget`, `AutonomyDecision`, `StopReason` |

## 3. The Runtime Loop (PawRuntime)

### Single Authority Gate + Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PAW Runtime Loop                               │
│                    (runtime.py — _loop)                             │
└─────────────────────────────────────────────────────────────────────┘

 Each iteration:

  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
  │   1. Compile      │  │   2. Propose      │  │   3. Single       │
  │   Context         │  │   Action          │  │   Authority       │
  │   ContextCompiler │  │   (propose_fn)    │  │   Gate (_gate_)   │
  │   memory+knowledge│  │   → ProposedAction│  │   action          │
  │   +skills+ledger  │  │                   │  │                   │
  └─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
            │                      │                      │
            │              ┌───────▼───────┐       ┌───────▼───────┐
            │              │ 4. Policy     │       │ 5. Autonomy   │
            │              │    Guard      │       │   Controller  │
            │              │ evaluate_     │       │ decide()      │
            │              │  request()    │       │ budget/       │
            │              │  → go/block/  │       │ progress/     │
            │              │  ask          │       │ repet/stal    │
            └──────────────┼───┬───────────┘       └───────┬───────┘
                           │ ALLOW                 CONTINUE │
                           │                              │
                  ┌────────▼────────┐            ┌────────▼────────┐
                  │ DENY → STOP     │            │ ASK → STOP      │
                  │ (POLICY_DENIED) │            │ (POLICY_ASK)    │
                  │ Never executes  │             │                 │
                  └─────────────────┘            └────────┬────────┘
                                                          │
                                                 ┌────────▼────────┐
                                                 │ CONTINUE →      │
                                                 │ 6. Execute      │
                                                 │    step_fn()    │
                                                 │    → Observ'cn │
                                                 └────────┬────────┘
                                                          │
                                                 ┌────────▼────────┐
                                                 │ 7. Record Op    │
                                                 │    (idempotency)│
                                                 │ 8. Update Usage │
                                                 │ 9. Maybe        │
                                                 │    Checkpoint    │
                                                 └────────┬────────┘
                                                          │
                                                 ┌────────▼────────┐
                                                 │ 10. Log to      │
                                                 │    TaskLedger   │
                                                 │ 11. Check       │
                                                 │    Completion   │
                                                 │ → stop | loop   │
                                                 └─────────────────┘
```

### Three Execution Entry Points

| Method | Purpose | Step Function | Brain |
|--------|---------|--------------|-------|
| `PawRuntime.run()` | Generic black-box loop | User-supplied `step_fn` | `ActionProposer` (simple) |
| `PawRuntime.run_agent()` | True agent loop | `_execute_action` (self-wired) | `AgentActionProposer` or injected `brain_fn` |
| `PawRuntime.run_graph()` | TaskGraph DAG execution | `_execute_action` per node | `AgentActionProposer` or injected `brain_fn` |

### The Execution Stage (`_execute_action`)

When the gate passes (policy ALLOW + autonomy CONTINUE), `_execute_action` runs:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    _execute_action (the "do" stage)                 │
└─────────────────────────────────────────────────────────────────────┘

  1. READINESS CHECK
     If action.is_mutating:
       - readiness != READY → reject (unless research/spike/clarification)
       - readiness_revision != current_revision → reject (stale)

  2. RESEARCH BUDGET CHECK (E2-30)
     If task_signals.research_budget set → check_research_budget()

  3. MODEL EXECUTION (if MODEL_INFERENCE in capabilities)
     ├─ If canonical proposal has cached selection → use it
     ├─ Else: ModelRouter.route() → re_evaluate_routing()
     ├─ E1-21: gate_remote_disclosure(manifest, provider_kind)
     │   ├─ SECRET/WORKSPACE → refuse non-local → RemoteDisclosureRefusedError
     │   └─ Stop loop (hard gate, no provider call)
     └─ ModelExecutor.complete(selection, messages) → model_result

  4. SKILL LOADING (if skill_name)
     └─ SkillFabric.get_skill(name) → skill.manifest.body (instruction only)

  5. EXECUTOR ROUTING
     ├─ CapabilityRouter.route_detailed() → best executor
     ├─ ExecutorRegistry.get(best) → Executor instance
     └─ (preferred_executor honored)

  6. EFFECT INTENT (prepare/reconcile pattern)
     ├─ If op record exists with status="prepared":
     │   └─ executor.reconcile_effect() (resume after interruption)
     ├─ Else:
     │   └─ executor.prepare_effect() → persist EffectIntent
     │   └─ executor.execute() → ExecutorResult

  7. OBSERVATION
     └─ ExecutionObservation(
         step_id, action_id, result={done, progress, skill, model_response, ...},
         resources_used, success, thinking, error
       )
```

## 4. Subsystem Deep-Dives

### 4.1 ContextCompiler (The Assembly Line)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   ContextCompiler.compile()                         │
└─────────────────────────────────────────────────────────────────────┘

 Input: task_id, query, session_id, execution_profile, privacy_class
 Output: (ContextManifest, list[ContextCandidate])

  SOURCE 1: Ledger Events ──→ _retrieve_ledger_candidates()
    - TaskEventType.CONTEXT_COMPILED, SKILL_CANDIDATES_FOUND,
      MODEL_SELECTED, EXECUTION_COMPLETED, TASK_COMPLETED
    - Priority: 0.3

  SOURCE 2: Memory Records ──→ _retrieve_memory_candidates()
    - MemoryStore.search_records() with hybrid retrieval
    - Lexical + semantic embedding (OllamaEmbeddingProvider or LocalFallback)
    - Priority: 0.25

  SOURCE 3: Knowledge Chunks ──→ _retrieve_knowledge_candidates()
    - KnowledgeIndex.search_chunks() with relevance scoring
    - Priority: 0.2

  SOURCE 4: Skills ──→ _retrieve_skill_candidates()
    - SkillFabric.list_skills() → semantic selector
    - Lexical + embedding re-rank (fallback if no provider)
    - Priority: 0.15

  SOURCE 5: Session History ──→ _retrieve_session_candidates()
    - Chat transcript from current session
    - Priority: 0.1

  SOURCE 6: Repository ──→ _retrieve_repo_candidates()
    - RepoScanner (E1-05) + SourceDiff (E1-06) + Symbols (E1-10)
    - Optional, only if project_root configured
    - Priority: 0.05

  ↓
  _score_candidates() — relevance_score (real, from semantic/lexical)
  ↓
  _deduplicate() — exact key + near-dup (Jaccard/emdedding cosine, threshold=0.85)
  ↓
  _allocate_budget() — hard budget constraint (max_tokens, max_fragments, max_sources)
  ↓
  _compile_manifest() — ContextManifest with included[] + excluded[] partition
  ↓
  _upgrade_selected_skills() — Level 0→1 (load skill body)
```

### 4.2 AutonomyController (The Brakes & Accelerator)

```
┌─────────────────────────────────────────────────────────────────────┐
│              AutonomyController.decide()                           │
└─────────────────────────────────────────────────────────────────────┘

 Input: task_id, context, required_capabilities, policy_verdict
 Output: (AutonomyDecision, StopReason | None)

  1. CHECK BUDGET (AutonomyBudget)
     - max_model_calls: count from ledger STEP_EXECUTED events
     - max_tool_calls: count from STEP_EXECUTED events
     - max_total_tokens: sum of STEP_EXECUTED token counts
     - max_wall_time_seconds: elapsed time
     - max_iterations: loop count
     → BUDGET_EXHAUSTED → STOP

  2. CHECK PROGRESS (ProgressTracker)
     - progress_history: list of progress values per iteration
     - If progress < threshold for N iterations → INSUFFICIENT_PROGRESS → ASK/PAUSE
     - If no progress at all → STALLED → ASK/PAUSE

  3. CHECK REPETITION (RepetitionDetector)
     - Track tool calls by name
     - If same tool called > MAX_REPETITIONS → REPETITION_DETECTED → ASK/PAUSE

  4. CHECK ITERATION LIMIT
     - iterations >= max_iterations → MAX_ITERATIONS_REACHED → STOP

  5. Decision Matrix
     ┌──────────────┬──────────────────────────────────────┐
     │ Budget/      │ Decision                             │
     │ Progress     │                                      │
     ├──────────────┼──────────────────────────────────────┤
     │ Exhausted    │ STOP + BUDGET_*_EXHAUSTED           │
     │ Stalled      │ PAUSE/ASK + STALLED                 │
     │ Repetition   │ ASK/PAUSE + REPETITION_DETECTED     │
     │ Max iter     │ STOP + MAX_ITERATIONS_REACHED       │
     │ Normal       │ CONTINUE                            │
     │ Task done    │ STOP_SUCCESS + TASK_COMPLETED       │
     └──────────────┴──────────────────────────────────────┘
```

### 4.3 ModelRouter + Model Executor (Phase 11-15)

```
┌─────────────────────────────────────────────────────────────────────┐
│                ModelRouter.route() + Phase 15 Provider-Aware       │
└─────────────────────────────────────────────────────────────────────┘

  1. discover_models()
     ├─ For each provider in registry: if provider.available → discover_manifests()
     └─ Graceful degradation: unavailable provider → 0 models (no error)

  2. _filter_for_availability()
     ├─ Remove models from unavailable providers
     └─ Local fallback: filter by supports_role(role), re-score via canonical scorer

  3. score_models() — multi-dimensional scoring
     ├─ Capability fit (ModelCapability scores)     weight: variable
     ├─ Cost (free/low/variable → lower is better)   weight: variable
     ├─ Latency (low/med/high → lower is better)     weight: variable
     ├─ Complexity match (task complexity)          weight: variable
     ├─ Privacy (local preferred if privacy_required) weight: variable
     ├─ Role ceiling (E2-04: role ceiling check)    weight: variable
     └─ Reassessment (E2-10: re-evaluate after reconnaissance) weight: hard gate

  4. Selection with Fallback Chain
     ├─ Pick highest score that supports role
     ├─ Build fallback_chain (descending score, provider available only)
     └─ If no candidate → local fallback

  5. _select_model_for_proposal() (E2-49)
     ├── Gather Recon (E1 evidence pipeline)
     ├── Route → Classify inference (local.compute vs model.inference)
     ├── Build CanonicalProposal (exact proposal before gates)
     └── Gates receive the exact proposal → single authority

  ModelExecutor.complete():
  ├─ Resolve provider from ModelSelection.model_manifest.provider
  ├─ If provider in registry → provider.complete(request)
  └─ Else → LocalModelExecutor (offline echo stand-in)
```

### 4.4 Skill Fabric (Progressive Loading L0/L1/L2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SkillFabric + Progressive Loading                 │
└─────────────────────────────────────────────────────────────────────┘

  L0 (registry-level):
    - SkillManifest: name, trigger, category, risk, capabilities
    - No body loaded
    - Used for selection/scoring

  L1 (body-level):
    - Load skill.manifest.body (instruction text)
    - Triggered by _upgrade_selected_skills() in ContextCompiler
    - max_content_length guard (skip if too large)

  L2 (execution-level):
    - Executor-level: skill body passed to executor as instructions
    - Not loaded into context memory

  Selection pipeline:
    ContextCompiler._retrieve_skill_candidates()
    ├─ SkillFabric.list_skills() → all skill manifests
    ├─ AdvancedSkillSelector (hybrid lexical + semantic)
    │   ├─ Lexical: SemanticMatcher (keyword/BM25)
    │   └─ Semantic: EmbeddingProvider (Ollama or Local) → cosine similarity
    ├─ Re-rank by fused score (lexical_weight + semantic_weight)
    ├─ Capability filter (must support required capabilities)
    └─ Return top-N with relevance_score

  Discovery:
    - Filesystem-based: scans `skills/` directory for .md files
    - _parse_skill_file(): extracts manifest metadata via regex
    - _CANDIDATE → _ACTIVE state transition (E3 governance)
```

### 4.5 Checkpoint & Resume (Phase 10)

```
┌─────────────────────────────────────────────────────────────────────┐
│                CheckpointManager + OperationRecordStore              │
└─────────────────────────────────────────────────────────────────────┘

  Checkpoint (TaskCheckpoint):
  ├─ task_id, checkpoint_id, status, progress_ratio
  ├─ context (compiled context dict)
  ├─ autonomy_usage (budget state)
  ├─ progress_history, repetition_state, stall_state
  ├─ loop_iteration, loop_decision_history
  └─ tags, parent_checkpoint_id, created_at

  OperationRecord:
  ├─ task_id, op_id, op_type, status
  ├─ checkpoint_id, result_ref
  ├─ metadata (effect_intent, etc.)
  └─ Idempotency: same op_id → skip on resume

  Resume flow (run_agent/run_graph/run):
  1. ResumeManager.resume(task_id, checkpoint_id)
     ├─ Load TaskCheckpoint from DB
     ├─ Restore autonomy state (budget, decision_history)
  2. OperationRecordStore.get_completed_op_ids(task_id)
     ├─ Return set of op_ids with status="completed"
  3. In _loop(): skip any proposed.action.operation_id in completed_op_ids
     ├─ Log OPERATION_RECORDED skipped
     └─ continue (no re-execution)

  Auto-checkpoint: every N iterations (default 5) or on terminal state
```

### 4.6 Knowledge Engine (sqlite + source-of-truth)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Knowledge Engine Data Flow                         │
└─────────────────────────────────────────────────────────────────────┘

  Tables (in storage.py schema):
  knowledge_sources
    ├─ source_id, kind, uri, title, description
    ├─ privacy_class (PUBLIC/INTERNAL/WORKSPACE/SECRET)
    ├─ revision, invalidated_at, invalidation_reason, superseded_by
    └─ created_at, updated_at

  knowledge_chunks
    ├─ chunk_id, source_id, content, chunk_index
    ├─ embedding_model, stale_at
    └─ created_at

  knowledge_evidence
    ├─ evidence_id, chunk_id, source_line, snippet
    ├─ license, license_url, external_id

  knowledge_citations
    ├─ citation_id, evidence_id, source_id, context, position

  knowledge_chunk_embeddings (optional cache)
    ├─ chunk_id, vector, model

  Flow:
  1. Source ingestion (KnowledgeSourceManager.create)
     ├─ Checksum computation (SHA-256, E1-06)
     ├─ Incremental diff (E1-06: new/changed/unchanged/deleted)
     └─ Stale derived records cascade (E1-07: chunks → evidence → citations)

  2. Chunk creation (KnowledgeChunk)
     ├─ Content extraction (chunk.py)
     └─ Symbol extraction (E1-10: functions, classes, methods)

  3. Search (KnowledgeIndex.search_chunks)
     ├─ Lexical scoring (BM25/token overlap)
     ├─ Semantic re-rank (if embedding provider available)
     └─ Stale filtering (stale_at IS NULL)
```

### 4.7 Benchmark System (bench/)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PAW Benchmark System                             │
│                      (E0-E1 tracks)                                 │
└─────────────────────────────────────────────────────────────────────┘

  E0 (Fixture Validation Baseline):
  ├─ CaseManifest: case_id, category, expected_evidence, fixture_ref
  ├─ ExpectedEvidence: kind, value, min_count
  ├─ FixtureRef: type, path, sha256
  ├─ validate_case_manifest() — structural validation
  ├─ run_case() — deterministic execution (shell=False only)
  ├─ VerificationSpec/Record — pass/fail criteria
  └─ 13/13 SUCCESS = fixture-validation only (NOT agent-quality)

  E1 (Source Context & Recall):
  ├─ E1-01: Ownership audit (MemoryRecord, KnowledgeSource, etc.)
  ├── E1-02: Source identity (revision, external_id, invalidation)
  ├── E1-03: Privacy classes (PrivacyClass, REMOTE_DISCLOSURE_DEFAULTS)
  ├── E1-04: Repo filter rules (RepoFilter, safe_default)
  ├── E1-05: Repo scanner (scan_repo, follow_symlinks=False)
  ├── E1-06: Source incremental diff (diff_sources, 4 buckets)
  ├── E1-07: Stale derived records (cascade, recovery)
  ├── E1-08: Bounded tree view (scan_tree, TreeNode)
  ├── E1-09: Dependency edges (extract_dependencies, AST + dynamic)
  ├── E1-10: Symbol ownership (extract_symbols, 6 kinds)
  ├── E1-11: Test associations (associate_tests, 4-step heuristic)
  ├── E1-12: Recent changes (recent_changes, git log reader)
  ├── E1-17: Inclusion reasons (source_hash, external_id, privacy_class)
  ├── E1-23: Recall measurement (measure_recall, cold/warm modes)
  ├── E1-24: Token measurement (measure_tokens, baseline)
  ├── E1-25: Recall miss categories (MISS_CATEGORIES closed set)
  ├── E1-26: Adversarial runtime (policy blocks, budget, privacy)
  ├── E1-27: Production measurement (e1_production.py runner)
  ├── E1-35: E2E recall contract (real fixture repo, no monkeypatch)
  ├── E1-36: Adversarial runtime (12 invariant/runtime/adversarial/measurable tests)
  └── Runner: paw.bench.e1_production (tracked, canonical)

  E2 (Inference Classification — RATIFIED):
  ├─ E2-05: evaluate_local_eligibility (fail-closed per role)
  ├─ E2-07: routing provenance (MODEL_SELECTED ledger)
  ├─ E2-08: ReconnaissanceResult (symbols/changes/tests/knowledge)
  ├─ E2-09: classify_inference (InferenceClassification)
  ├─ E2-11: OOD conditions (OODCondition, fail-closed)
  ├─ E2-25: budget signals
  ├─ E2-27: model routing contract (provider health awareness)
  ├─ E2-28: model executor dispatch
  ├─ E2-45: effect constraints flow
  ├─ E2-46: effect constraints enforcement
  ├─ E2-47: model router re-evaluation after recon
  └─ CanonicalProposal: exact proposal before gates
```

### 4.8 Providers (Phase 11-15)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Provider Architecture                            │
└─────────────────────────────────────────────────────────────────────┘

  ModelProvider Protocol (providers/__init__.py):
  ├─ @runtime_checkable
  ├─ list_models() → list[ModelManifest]
  ├─ get_model(name) → ModelManifest
  ├─ complete(request: dict) → dict (async)
  ├─ stream(request: dict) → AsyncGenerator (async)
  ├─ available: bool (property)
  └─ discover_manifests() → list[ModelManifest]

  ProviderRegistry:
  ├─ Aggregates multiple providers
  ├─ discover_models() → only from available providers
  ├─ get(name) → provider by name
  └─ Core does NOT hardcode import Ollama (zero vendor lock-in)

  OllamaProvider (providers/ollama/provider.py):
  ├─ stdlib HTTP (urllib + asyncio.to_thread)
  ├─ list_models: GET /api/tags
  ├─ complete: POST /api/generate
  ├─ stream: POST /api/chat (SSE)
  ├─ available: checks GET /api/tags health
  └─ Graceful degradation: if Ollama down → 0 models (no error)

  LocalModelExecutor (core/model_executor.py):
  ├─ NOT a ModelProvider (executor only)
  ├─ Offline echo/placeholder
  └─ Used as fallback when no provider matches

  EmbeddingProvider Protocol (core/embeddings.py):
  ├─ OllamaEmbeddingProvider (POST /api/embeddings)
  ├─ LocalEmbeddingProvider (hashed bag-of-words, offline)
  ├─ cosine_similarity()
  └─ Auto-attach: try_ollama_embedding_provider() → None if down
```

### 4.9 Memory Engine (core/memory.py)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Memory Engine                                     │
└─────────────────────────────────────────────────────────────────────┘

  Tables:
  memory_records: id, type, content, relevance_score, privacy_class,
    created_at, updated_at, last_accessed, metadata

  memory_embeddings (optional): record_id, vector, model

  MemoryStore:
  ├─ store(type, content, privacy_class) → record_id
  ├─ search_records(query, limit, embedding_provider)
  │   └─ AdvancedMemoryRetriever: hybrid lexical + semantic + re-rank
  ├─ get(record_id) → MemoryRecord
  ├─ get_all(limit) → list[MemoryRecord]
  └─ delete(record_id)

  Memory Types:
  - EPISODIC: conversation turns
  - SEMANTIC: facts/knowledge
  - PROCEDURAL: how-to instructions
  - FACTUAL: discrete facts
```

### 4.10 Chat Application (application/)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Chat Application Layer                            │
└─────────────────────────────────────────────────────────────────────┘

  ChatService:
  ├─ provider_mode: "local" | "auto" | "ollama"
  ├─ workspace_root: filesystem boundary
  ├─ _providers: ProviderRegistry (shared)
  ├─ _model_router: ModelRouter
  ├─ _model_executor: ModelExecutor (shared registry)
  ├─ _executor_registry: ExecutorRegistry
  │   ├─ LocalFilesystemExecutor (filesystem ops)
  │   └─ MockExecutor (offline echo)
  ├─ _capability_router: CapabilityRouter

  send(message):
  1. Parse filesystem intent (read_file/write_file/edit_file)
  2. Infer capabilities (conservative deterministic)
  3. Create Task (TaskManager.create)
  4. Build ProposedAction (goal, capabilities, context, metadata)
  5. Build PawRuntime with full wiring
  6. runtime.run_agent() → RuntimeOutcome
  7. Map outcome → ChatReply (content, status, thinking, artifacts)

  /approve [id]:
  1. ApprovalStore.approve(id) → mark APPROVED
  2. resume() → re-run action from checkpoint

  /resume:
  1. Load pending approval
  2. runtime.run_agent(resume_from_checkpoint=checkpoint_id)

  Inspection commands (/status, /plan, /why, /ledger, /checkpoint,
                        /policy, /skills, /artifacts):
  ├─ All projections in chat_inspection.py
  └─ /why uses explain_projection (RuntimeOutcome.to_answer + evidence)

  ChatStateStore (persistent projection):
  ├─ chat_sessions: session_id, status, current_task_id, pending_approval_id
  ├─ chat_messages: id, session_id, task_id, role, content, metadata
  └─ All durable in SQLite
```

## 5. Data Flow Diagrams

### 5.1 Agent Task Execution (run_agent → run → _loop → _execute_unit → _execute_action)

```
                    ┌─────────────────────────────────────┐
                    │        ChatService.send()           │
                    │  1. Parse intent + capabilities      │
                    │  2. TaskManager.create()             │
                    │  3. ProposedAction                  │
                    │  4. PawRuntime.run_agent()          │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │       PawRuntime.run_agent()        │
                    │  1. Pre-compile manifest (E1-16)    │
                    │  2. AgentActionProposer             │
                    │  3. _loop()                         │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │          _loop()                    │
                    │  Each iteration:                    │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   1. ContextCompiler.compile()      │
                    │   (memory/knowledge/skills/ledger/  │
                    │    session/repo)                    │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   2. AgentActionProposer.propose()  │
                    │   → ProposedAction (no side effects)│
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   3. _select_model_for_proposal()   │
                    │   (E2-49: recon → route → classify) │
                    │   → CanonicalProposal               │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   4. _gate_action() (Single Auth.)  │
                    │   Policy Guard: evaluate_request()  │
                    │   Autonomy Gate: decide()            │
                    │   → BLOCK/ASK/PAUSE/STOP or CONTINUE│
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   CONTINUE: _execute_unit()         │
                    │   5. _execute_action():             │
                    │   ├─ Readiness check                 │
                    │   ├─ Research budget (E2-30)         │
                    │   ├─ Model routing (if MODEL_INF)  │
                    │   │  └─ gate_remote_disclosure()    │
                    │   ├─ Skill loading                   │
                    │   ├─ Executor routing                │
                    │   ├─ Effect intent (prepare/execute) │
                    │   └─ ExecutionObservation            │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   6. RuntimePersistence             │
                    │   ├─ commit_operation()              │
                    │   └─ maybe_checkpoint()              │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   7. TaskLedger events               │
                    │   STEP_PROPOSED/OUTPUT/COMPLETED     │
                    │   + model_selected, etc.             │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │   8. Completion check                 │
                    │   → STOP_SUCCESS | continue loop     │
                    └──────────────────────────────────────┘
```

### 5.2 Context Assembly (ContextCompiler.compile → compile_manifest)

```
                    ┌─────────────────────────────────────┐
                    │    ContextCompiler.compile()        │
                    │  Input: task_id, query, profile     │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  1. _score_candidates()              │
                    │  ┌─ Ledger candidates (0.3 weight)  │
                    │  ├─ Memory candidates (0.25 weight)  │
                    │  ├─ Knowledge candidates (0.20)      │
                    │  ├─ Skill candidates (0.15)         │
                    │  ├─ Session candidates (0.10)       │
                    │  └─ Repository candidates (0.05)    │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  2. _deduplicate()                    │
                    │     - exact key match                 │
                    │     - near-dup: Jaccard / cosine      │
                    │       threshold=0.85                 │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  3. _allocate_budget()               │
                    │     - max_tokens: hard cap           │
                    │     - max_fragments: hard cap        │
                    │     - max_sources: hard cap          │
                    │     → ContextManifest.included[]    │
                    │     → ContextManifest.excluded[]    │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  4. _compile_manifest()              │
                    │     - Set privacy_class per candidate │
                    │     - Set is_stale per candidate      │
                    │     - Build ManifestRef               │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  5. _upgrade_selected_skills()       │
                    │     - Level 0 → Level 1               │
                    │     - Load skill body (max_content) │
                    └──────────────────────────────────────┘
```

### 5.3 Privacy Gate (E1-21) — Before Any Remote Model Call

```
                    ┌─────────────────────────────────────┐
                    │  _execute_action()                  │
                    │  When MODEL_INFERENCE needed:       │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  ModelRouter.route() → selection     │
                    │  + Recon (E1 evidence pipeline)      │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  gate_remote_disclosure(manifest,   │
                    │  provider_kind)  ← E1-21              │
                    │                                       │
                    │  For each included candidate:        │
                    │  ├─ if is_stale AND provider≠local  │
                    │  │   → refuse: ("source_stale")      │
                    │  ├─ if privacy_class=SECRET & remote │
                    │  │   → refuse: ("class_secret_remote")│
                    │  ├─ if privacy_class=WORKSPACE & remote│
                    │  │   → refuse: ("class_workspace_remote")│
                    │  └─ if allowed → included             │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────┐
                    │  allowed=True → ModelExecutor.complete()│
                    │  allowed=False → RemoteDisclosureRefusedError│
                    │  → ExecutionObservation(success=False)     │
                    │  → OperationRecord(status="failed")       │
                    └──────────────────────────────────────┘
```

## 6. Test Suite Composition

| Track | Tests | Purpose |
|-------|-------|---------|
| Phase tests | ~200 | Phases 0-22 integration tests |
| E0 tests | ~13 | Fixture validation baseline |
| E1 tests | ~200+ | Source context, ownership, privacy, recall (contract + adversarial) |
| E2 tests | ~440+ | Inference classification, model routing, effect constraints |
| Beta tests | ~36 | Daily profiles, single-user, chat REPL |
| Runtime tests | ~30 | Run loop, checkpoint/resume, black-box acceptance |
| **Total** | **~1000+** | All pass on clean revision |

### Test Isolation Strategy

| Strategy | Implementation |
|----------|----------------|
| Per-test DB | `session_db` fixture (module-scoped, 1 SQLite file per test file) |
| Schema reset | `reset_db` (function-scoped, truncates all user tables) |
| FTS5 safety | Module-scoped (not session-scoped) to avoid corruption |
| skill_fabric | Separate per-test fixture (FTS5 fragile with shared DB) |
| Speed | ~38% faster than per-test init (~143s for full suite) |

## 7. Component Ownership Matrix

| Domain | Component | Module | Owner | Tests |
|--------|-----------|--------|-------|-------|
| Types | Task, TaskStatus, Capability | `core/models.py` | PAW | phase tests |
| Storage | SQLite, schema, migrations | `core/storage.py` | PAW | test_storage |
| Session | SessionManager | `core/session.py` | PAW | phase tests |
| Task | TaskManager | `core/task.py` | PAW | phase tests |
| Plan | Planner, TaskNode, Plan | `core/planner.py` | PAW | phase tests |
| Graph | TaskGraph, TaskScheduler | `core/task_scheduler.py` | PAW | phase tests |
| Executor | Executor protocol, CapabilityRouter | `core/executor.py` | PAW | phase tests |
| Policy | PolicyGuard, RequestVerdict | `core/policy.py` | PAW | test_phase6_security |
| Autonomy | AutonomyController, StopReason | `core/autonomy.py` | PAW | test_phase10_autonomy |
| Privacy | PrivacyClass, gate_remote_disclosure | `core/privacy.py` | PAW | E1-03, E1-21, E1-26 |
| Context | ContextCompiler, ContextBudget | `core/context_compiler.py` | PAW | phase tests, B10, E1-27 |
| Checkpoint | CheckpointStore, OperationRecord | `core/checkpoint.py` | PAW | test_phase10_checkpoint |
| Skills | SkillFabric, SkillManifest | `core/skills.py` | PAW | phase tests |
| Memory | MemoryStore, MemoryIndex | `core/memory.py` | PAW | phase tests, phase12 |
| Knowledge | KnowledgeIndex, KnowledgeSource | `knowledge/` | PAW | E1 tests |
| Model Router | ModelRouter, ProviderRegistry | `core/model_router.py` | PAW | phase tests, E2 |
| Model Executor | ModelExecutor, LocalModelExecutor | `core/model_executor.py` | PAW | phase tests, phase11 |
| Providers | ModelProvider, OllamaProvider | `providers/` | PAW | phase11, E2-27 |
| Embeddings | EmbeddingProvider, OllamaEmbedding | `core/embeddings.py` | PAW | phase12, phase11b |
| Runtime | PawRuntime, RuntimeOutcome | `core/runtime.py` | PAW | phase19, phase20, E1-36 |
| Ledger | TaskLedger, TaskEvent | `core/ledger.py` | PAW | phase tests |
| Approval | ApprovalStore, ApprovalRequest | `core/approval.py` | PAW | phase tests |
| Identity | Identity, IdentityManager | `core/identity/` | PAW | test_identity |
| Benchmark | CaseManifest, Runner | `bench/` | PAW | E0, E1 |
| CLI | Typer app, chat commands | `cli/__init__.py` | PAW | phase tests |
| Chat | ChatService, ChatStateStore | `application/chat.py` | PAW | beta tests |
| Inspection | Projections | `application/chat_inspection.py` | PAW | beta tests |
| Intents | Intent parsing | `application/chat_intents.py` | PAW | beta tests |
| Beta Profiles | BetaProfile, SideEffectPolicy | `core/beta_profiles.py` | PAW | beta tests |
| Config | Settings | `core/config.py` | PAW | phase tests |
| Logging | structlog config | `core/logging.py` | PAW | phase tests |
| Reasoning | Contracts | `core/reasoning_contracts.py` | PAW | E2 |
| Runtime Persistence | commit_operation, commit_checkpoint | `core/runtime_persistence.py` | PAW | phase19 |

## 8. Key Design Decisions

1. **Local-first, zero-daemon**: Everything runs in-process. SQLite is the only external dependency.
2. **Zero vendor lock-in**: All provider contracts are PAW-owned Protocols. External systems (Ollama) are pluggable adapters.
3. **Single authority gate**: Policy + Autonomy gates run BEFORE any side effect (model call, executor call, effect). ASK/DENY never execute.
4. **Schema migrations are additive only**: `ALTER TABLE ADD COLUMN`, never DROP or rewrite rows.
5. **CLI-first**: All functionality exposed via `paw` CLI commands. No GUI/TUI (scope-locked).
6. **CLI-first, zero-daemon, SQLite-backed**: Pure Python, no background workers, no distributed infrastructure.
7. **Thinking/reasoning captured**: `thinking: str | None` on ProposedAction, ExecutionObservation, and ChatReply for full observability.
8. **Logs to stderr**: INFO/WARNING/DEBUG go to stderr by default; REPL user-facing output stays on stdout. `--quiet`/`--debug` flags available.
