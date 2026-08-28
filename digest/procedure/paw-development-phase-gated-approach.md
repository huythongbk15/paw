---
description: 'Runbook for strict phase-gated development of PAW Core components: each
  phase has objective acceptance criteria that must be fully met before advancing.
  Phase 0 establishes foundation (CLI, Config, Logging, Storage, Models) with measurable
  gates; Phase 1 implements Task Lifecycle E2E. Pattern is reusable for other core
  components.'
kind: procedure
name: PAW Development Phase-Gated Approach
---

## Trigger / When to Use
Use this runbook when building a new core component from zero and you need a disciplined, measurable phase structure that prevents scope creep and ensures each layer is solid before the next begins.

## Pre-conditions / Inputs
- Clear architectural spec for the component (what it owns, what it delegates)
- Identified prohibited dependencies that must stay out of the core
- Local-first toolchain (Python, SQLite, Ruff, pytest) available

## Steps
1. **Define Phase 0 acceptance criteria upfront** — write objective, binary gates (install, CLI surface, DB schema, test count, lint, prohibited deps absent).
2. **Implement Phase 0 Foundation** — CLI entry point, config system, structured logging, storage layer with full schema, typed domain models, unit + integration tests.
3. **Verify all Phase 0 gates** — run install, CLI smoke, DB init, full test suite, Ruff, dependency audit. **Do not proceed until every gate passes.**
4. **Record the architectural pivot / decision** — document what the core owns, what is deferred to adapters, what external systems are rejected. Link to [[digest/wiki/paw-core-architectural-pivot-build-from-zero.md|the precedent]].
5. **Define Phase 1 acceptance criteria** — measurable E2E goals (SessionManager, Task CRUD, TaskLedger, MockExecutor, minimal skill registry).
6. **Implement Phase 1 Task Lifecycle E2E** — build only what the criteria demand; defer LLM integrations to adapter layers (Phase 11+).
7. **Repeat for subsequent phases** — each phase adds one cohesive capability with its own binary gates; never blend phases.

## Failure Modes / Caveats
- **Gate slippage**: advancing with "mostly passing" tests or lint warnings undermines the whole pattern. Treat gates as hard stops.
- **Scope creep in Phase 0**: resist adding Phase 1 features (e.g., real executors) to foundation. Adapters belong in later phases.
- **External dependency bleed**: prohibited deps (NotebookLM, Antigravity, QwenPaw, DeepSeek Harness) must stay out of `paw/core/`; verify via dependency audit each phase.
- **Test debt**: Phase 0's 23/23 tests are the baseline; every phase must maintain or increase coverage, never decrease.
- **Circular dependency risk**: `capability_router.py` and `model_router.py` must not import from each other or from `executor.py` at module level. Use dependency injection (pass registry as parameter) instead.
- **Directory structure decision**: subdirectories (`core/models/`, `core/tasks/`, etc.) already exist empty; decide whether to refactor flat code into subdirectories or keep flat structure.

## Sources
- This runbook is distilled from [[memory/2026-08-27/paw-core-phase0-complete-architecture-decision.md|the Phase 0 completion decision note]], which records the actual Phase 0 gates, their measured results, and the architectural role assignments that motivated the phase structure.
- The architectural correction [[digest/wiki/paw-core-architectural-pivot-build-from-zero.md|PAW Core Architectural Correction: Build from Zero, Not Integration]] captures the correction that the initial "integration" framing was completely wrong.
- The overall architecture [[paw/docs/ARCHITECTURE.md|PAW Architecture & Structure]] documents the complete project structure and phase roadmap.
