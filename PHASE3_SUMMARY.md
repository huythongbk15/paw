# PAW Core — Phase Summary & Roadmap

## Current State: Phase 0–3 Foundation Complete

**Prompt reference**: `media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`

**IMPORTANT**: The original prompt defines 16 phases (0–15). Implementation follows the prompt's phase structure with adaptations.

## ⚠️ CRITICAL CORRECTION

The initial project framing ("Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness") was **completely wrong**. PAW Core is a standalone system; external systems are only executor adapters at Phase 11+. All documentation has been corrected on 2026-08-28.

---

## Phases Complete (Foundation)

### Phase 0 — Repository Foundation ✅
- CLI entry point (`paw --help/--version/doctor/init/config`)
- Pydantic settings (`PawSettings`)
- Structured logging (structlog)
- SQLite + aiosqlite full schema (12+ tables)
- Typed domain models (ID, TimestampMixin, Result[T], Metadata)
- Tests: 10/10 ✅

### Phase 1 — Minimal End-to-End Agent ✅
- SessionManager, Session
- TaskManager, Task entity + CRUD
- TaskLedger (immutable append-only)
- MockExecutor (E2E without real LLM)
- SkillFabric (discover, index, load)
- Tests: 14/14 new ✅ (37/37 total)

### Phase 2 — Skill Fabric v1 ✅
- SkillManifest, SkillFabric, Skill
- Discover, index, search, load operations
- Builtin skills (echo, datetime) + filesystem discovery
- Tests: 25/25 ✅

### Phase 3 — Memory v1 ✅
- MemoryStore, MemoryRetriever, MemoryRecord
- Episodic, Semantic, Procedural, Factual memory types
- FTS5 search
- Tests: 31/31 ✅

### Phase 6 — Policy Engine ✅
- PolicyGuard, PolicyRule, PolicyDecision (ALLOW/DENY/ASK/SANDBOX)
- ExecutorPolicyEnforcer, PolicyEnforcedExecutor
- Tests included in Phase 3

---

## Architecture Gaps Fixed (2026-08-28)

| Gap | Fix Applied |
|-----|-------------|
| Missing Model Router | ✅ `paw/core/model_router.py` — ModelManifest, ModelRegistry, ModelRouter, ModelSelection |
| Missing Capability Router | ✅ `paw/core/capability_router.py` — CapabilityRouter with scoring |
| TaskResult wrong spec | ✅ `paw/core/models.py` — TaskResult with all spec fields |
| Skill Manifest wrong spec | ✅ `paw/core/skills.py` — executors field, metadata.paw/ nested structure |
| Missing Artifact/Decision/Evidence/Citation/Usage/ErrorInfo | ✅ Added to `paw/core/models.py` |
| Storage duplicate tables | ✅ Removed duplicate sessions, added skill_fts, model_registry, model_selections |

---

## Remaining Phases (Pending Implementation)

### Phase 4 — Model Router ⚠️ STUB
- [ ] Expand `paw/core/model_router.py` — improve scoring with full 10 factors
- [ ] Add `paw/core/routing/` subdirectory (currently flat)
- [ ] Add `model_registry` table population
- [ ] Add fallback chain logic
- [ ] Add `paw model list/route` CLI commands
- [ ] Tests: ≥ 5 new

### Phase 5 — Executor Fabric ⚠️ STUB
- [ ] Add `LocalExecutor` (execute local commands)
- [ ] Expand `CapabilityRouter` with full scoring (10 factors)
- [ ] Add `paw/executors/` subdirectory structure
- [ ] Add `paw executor list/doctor` CLI commands
- [ ] Tests: ≥ 5 new

### Phase 7 — Knowledge Engine ❌ NOT STARTED
- [ ] Create `paw/knowledge/` module — Source, Chunk, Evidence, Citation, KnowledgeIndex
- [ ] Add `paw knowledge add/search/source` CLI commands
- [ ] Add Source parsers, Chunk splitters
- [ ] Evidence extractors, Citation generators
- [ ] **Critical rule**: No hallucinated citations — if no evidence, say "insufficient evidence"
- [ ] Tests: ≥ 5 new

### Phase 8 — Context Builder ⚠️ BASIC
- [ ] Add `paw/core/context/` subdirectory
- [ ] Add `ContextItem.source`, `ContextItem.score`, `ContextItem.reason`, `ContextItem.token_estimate`
- [ ] Add `max_context_tokens = 12000` budget enforcement
- [ ] Add explain mode: `paw context explain <task-id>`
- [ ] Add `paw context explain` CLI command
- [ ] Tests: ≥ 5 new

### Phase 9 — Task Graph ⚠️ BASIC
- [ ] Create `TaskDependency` class
- [ ] Create `TaskGraph` class (DAG)
- [ ] Create `TaskScheduler` class
- [ ] Parallelize independent nodes only
- [ ] Dependency failure blocks downstream
- [ ] Add `paw task graph` CLI commands
- [ ] Tests: ≥ 5 new

### Phase 10 — QwenPaw Compatibility ❌ NOT STARTED
- [ ] Create `paw/providers/` subdirectory
- [ ] Add QwenPaw adapter (skills, ReMe, persona import)
- [ ] Adapter must not leak QwenPaw internals into core
- [ ] Tests: ≥ 5 new

### Phase 11 — Additional Executors ❌ NOT STARTED
- [ ] DeepSeek Harness adapter
- [ ] Antigravity adapter
- [ ] Codex adapter
- [ ] Claude Code adapter
- [ ] Aider adapter
- [ ] Tests: ≥ 5 new per adapter

### Phase 12–17 — Evaluation, Intelligent Routing, Tests ❌ NOT STARTED
- [ ] Evaluation system
- [ ] Skill evaluation
- [ ] Intelligent routing
- [ ] Contract tests
- [ ] Regression scenarios
- [ ] Security scanning
- [ ] mypy/pyright type checking

---

## Circular Dependency Risk (fix immediately)

**Problem**: `capability_router.py` imports `from .executor import executor_registry`, `model_router.py` may import from executor. If `executor.py` imports from either → circular import.

**Fix**: Use dependency injection (pass registry as parameter) instead of importing at module level.

---

## Directory Structure Decision (pending)

**Option A**: Keep flat `paw/core/*.py` (current state) — simpler, less refactoring
**Option B**: Organize into subdirectories (`paw/core/models/`, `paw/core/tasks/`, etc.) — more aligned with prompt spec, but requires refactoring

**Empty subdirectories already exist**: `paw/core/context/`, `paw/core/graph/`, `paw/core/identity/`, `paw/core/ledger/`, `paw/core/policy/`, `paw/core/routing/`, `paw/core/session/`, `paw/core/skills/`, `paw/core/tasks/`

---

## Tests Summary

- **93/93 pass**, zero warnings
- All tests self-contained with `tmp_path` fixture
- Demo (`demo_paw.py`) runs full lifecycle successfully

## Architecture constraints maintained
- Pure Python, local SQLite
- No QwenPaw/DeepSeek/NotebookLM/Antigravity imports
- Zero vendor lock-in
- Session + Task lifecycle preserved
- Policy Guard integration preserved