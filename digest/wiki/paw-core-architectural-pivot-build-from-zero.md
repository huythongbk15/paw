---
description: Precedent recording that the initial concept "Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness" was completely wrong. PAW Core must be built standalone; external systems are only executor adapters at Phase 11+. Phase 0 Foundation completed with hard quality gates.
name: 'PAW Core Architectural Correction: Build from Zero, Not Integration'
---

PAW Core Architectural Correction records the critical correction that the initial project concept was fundamentally flawed and has been rectified.

## The Error

The initial project framing — "Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness" — was **completely wrong**. This was not an "integration" project. The correct framing, confirmed by the original prompt spec (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`), is:

**PAW Core is a standalone Personal Agent Core built from zero.** External systems (QwenPaw, NotebookLM, Google Antigravity, DeepSeek Harness) are at most executor adapters in Phase 11+, never "integrated components."

## Why It Was Wrong

| Wrong framing | Correct framing |
|---|---|
| "Tích hợp" (integrate) 4 external systems | Build PAW Core standalone, with optional adapter layer |
| QwenPaw/NotebookLM/Antigravity/DSH as co-equal components | These are only executor adapters, deferred to Phase 11+ |
| Core depends on external architectures | Core owns all abstractions: Identity, Session, Task Graph, Context Builder, Skill Fabric, Model Router, Capability Router, Policy Engine, Task Ledger |
| Provider internals could leak into core | "Các provider không được sở hữu các abstraction trên" — strict isolation |

## The Correction (2026-08-28)

- All memory files updated to state the initial idea was **wrong**, not merely "pivoted from"
- `memory/2026-08-27/paw-core-phase0-complete-architecture-decision.md` — added explicit correction section
- `memory/2026-08-27.md` — added ⚠️ correction marker
- `memory/2026-08-28.md` — updated to reflect corrected state
- `PHASE3_SUMMARY.md` — updated to reference corrected understanding
- `paw/docs/PROJECT.md` — updated architecture fixes section

## Architectural Roles (Corrected)

| Component | Role | Status |
|---|---|---|
| **PAW Core** | Heart — Identity, Session, Task Graph, Context Builder, Skill Fabric, Policy Engine, Model Router, Capability Router, Task Ledger | Standalone, self-built |
| **QwenPaw** | Executor Adapter (Phase 11+) — coding, tool calling | Deferred adapter only |
| **DeepSeek Harness** | Executor Adapter (Phase 11+) — reasoning | Deferred adapter only |
| **NotebookLM** | **Rejected entirely** — replaced by self-built Knowledge Engine (Phase 7) | Never integrated |
| **Google Antigravity** | **Rejected entirely** — replaced by Search Tool abstraction | Never integrated |

## Core Principle

**core first, adapter later; local-first, zero external dependencies.** PAW Core is the trunk; adapters are branches that can be added or removed without affecting the trunk.

## Sources

- This correction is recorded from [[memory/2026-08-27/paw-core-phase0-complete-architecture-decision.md|the Phase 0 completion decision note]], updated 2026-08-28 with explicit correction of the initial wrong framing.
- The original prompt spec (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`) confirms PAW Core as standalone architecture with provider isolation.