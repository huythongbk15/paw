## Phase 2 & Phase 3 — paw Project (Architecture Gap Fixes Applied)

### 2026-08-28 — Architecture Gap Fixes Complete

User flagged that the initial build was based on `media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt` (prompt spec). Audit found 16 phases defined in spec but only 3 implemented. **All 5 critical architecture gaps have been fixed today.**

#### ✅ Critical Architecture Gaps — ALL FIXED

| # | Gap | Fix Applied |
|---|-----|-------------|
| 1 | **Missing Model Router** | ✅ `paw/core/model_router.py` — ModelManifest, ModelRegistry, ModelRouter, ModelSelection, ensure_model_selections_table, get_model_router, get_model_registry |
| 2 | **Missing Capability Router** | ✅ `paw/core/capability_router.py` — CapabilityRouter with capability-fit scoring, ensure_executors_table, get_capability_router |
| 3 | **TaskResult wrong spec** | ✅ `paw/core/models.py` — TaskResult with all spec fields: task_id, status, summary, artifacts, decisions, evidence, files_changed, executor, model, usage, error |
| 4 | **Skill Manifest wrong spec** | ✅ `paw/core/skills.py` — Added `executors` field, supports nested `metadata.paw/` structure (paw/version, paw/category, paw/capabilities, paw/executors, paw/network, paw/write) |
| 5 | **Missing Artifact/Decision/Evidence/Citation/Usage/ErrorInfo** | ✅ Added to `paw/core/models.py` |

#### ✅ Storage & Schema Fixes

| Fix | Detail |
|-----|--------|
| Removed duplicate `sessions` table | Schema now has each table once |
| Added `skill_fts` virtual table | FTS5 for skill search |
| Added `model_registry` table | For ModelRouter persistence |
| Added `model_selections` table | For model selection tracking |
| Added `executors` column to `skills` table | Supports prompt spec executors field |

#### ✅ Exports Fixed

- `paw/core/__init__.py` — Exports all new modules (ModelRouter, ModelRegistry, CapabilityRouter, TaskResult, Artifact, Decision, Evidence, Citation, Usage, ErrorInfo, etc.)
- Removed duplicate `get_semantic_selector` from `__all__`

#### ✅ Documentation Updated

- `paw/docs/PROJECT.md` — Added architecture fixes section reflecting current state
- `PHASE3_SUMMARY.md` — Updated status table

---

### Remaining Gaps (not fixed today — pending discussion)

| Gap | Status | Notes |
|-----|--------|-------|
| Identity module | ❌ Schema table exists, no module | Prompt lists Identity as PAW Core component |
| Skill Fabric operations | ⚠️ 4/10 done | Missing: rank, validate, enable, disable, version, evaluate |
| Knowledge Engine | ❌ Schema exists, no implementation | Source → Chunk → Evidence → Claim → Citation |
| Context Builder | ⚠️ Basic | Missing explain mode, token estimate, budget enforcement |
| Task Graph | ⚠️ Basic | Missing TaskDependency, TaskScheduler |
| CLI commands | ❌ Severely incomplete | Missing: paw skill/memory/policy/executor/knowledge/context/stats |
| Working Memory module | ❌ | Spec requires 4 memory types separated |
| Test coverage gaps | ❌ | Missing contract tests, adversarial tests, regression scenarios |
| mypy/pyright type checking | ❌ | Prompt requires type checking |
| Directory structure | ⚠️ Flat | Prompt suggests subdirectories: core/models/, core/tasks/, etc. |

---

### Key Expert Analysis (from prompt review)

The prompt (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`) defines:

- **16 phases** (Phase 0–15), not 3
- **Architecture review gates** at phases 5, 8, 10, 15
- **Phase 0 CLI acceptance**: `paw --help`, `paw doctor`, `paw version` (NOT `paw init`)
- **CURRENT_PHASE=<number>** pattern — each session implements one phase only
- **Do not auto-advance** — stop at current phase, report, next phase started explicitly
- **Working Memory** must be a separate module from Episodic/Semantic/Project Knowledge
- **Memory writes must be explicit/deterministic** — no LLM auto-writing to long-term memory initially
- **No multi-agent swarm before Task Graph**
- **No ML-based routing before evaluation history**
- **Directory structure suggestion**: `core/models/`, `core/tasks/`, `core/context/`, `core/skills/`, `core/routing/`, `core/policy/`, `core/ledger/`, plus top-level `memory/`, `knowledge/`, `executors/`, `providers/`

### Tests
- **93/93 pass**, zero warnings
- All tests self-contained with `tmp_path` fixture
- Demo (`demo_paw.py`) runs full lifecycle successfully

### Architecture constraints maintained
- Pure Python, local SQLite
- No QwenPaw/DeepSeek/NotebookLM/Antigravity imports
- Zero vendor lock-in
- Session + Task lifecycle preserved
- Policy Guard integration preserved