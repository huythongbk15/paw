## Architecture Gap Fixes Applied (2026-08-28)

**Trigger**: User flagged initial build was based on prompt spec (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`). Audit found implementation diverged from spec.

**Decision**: Fix all 5 critical architecture gaps immediately.

### Fixes Completed

1. **Model Router** (`paw/core/model_router.py`) — ModelManifest, ModelRegistry, ModelRouter, ModelSelection
2. **Capability Router** (`paw/core/capability_router.py`) — CapabilityRouter with scoring
3. **TaskResult contract** (`paw/core/models.py`) — Full spec fields: task_id, status, summary, artifacts, decisions, evidence, files_changed, executor, model, usage, error
4. **Skill Manifest** (`paw/core/skills.py`) — Added `executors` field, supports `metadata.paw/` nested structure
5. **Artifact/Decision/Evidence/Citation/Usage/ErrorInfo** (`paw/core/models.py`)
6. **Storage** (`paw/core/storage.py`) — Removed duplicate sessions, added skill_fts, model_registry, model_selections, executors column
7. **Exports** (`paw/core/__init__.py`) — All new modules exported, duplicate removed
8. **Documentation** — PROJECT.md and PHASE3_SUMMARY.md updated

### Remaining Gaps (pending discussion)

- Identity module (schema exists)
- Skill Fabric missing 6/10 operations
- Knowledge Engine (schema exists)
- Context Builder explain mode
- Task Dependency / Task Scheduler
- CLI commands (paw skill/memory/policy/executor/knowledge/context/stats)
- Working Memory module separation
- Contract/adversarial/regression tests
- mypy/pyright type checking
- Directory structure decision (flat vs subdirectories)

### All 93 tests pass, demo runs successfully.