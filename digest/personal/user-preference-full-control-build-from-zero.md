---
actor: Đại ca
description: 'Đại ca ưu tiên kiểm soát hoàn toàn (full control) và build từ con số 0 thay vì tích hợp sẵn có. Đây là constraint mang tính nhận dạng: local-first, free-tier ready, no vendor lock-in ở core.'
kind: preference
name: 'User Preference: Full Control, Build from Zero'
scope: paw-core-architecture
---

**Rule**: Đại ca yêu cầu full control over core infrastructure — build from zero, reject external note-taking (NotebookLM) and search/analysis (Google Antigravity) dependencies, relegate LLM executors (QwenPaw, DeepSeek Harness) to adapter roles in Phase 11+ only.

**Why**: Identity-level constraint. Đại ca explicitly decided "muốn build từ 0, kiểm soát hoàn toàn" on 2026-08-27, rejecting an initial project framing of "Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness" which was **completely wrong**. The initial "integration" concept was fundamentally flawed — PAW Core is a standalone system, and external systems are only executor adapters at Phase 11+. The core must be local-first, free-tier ready, and free of vendor lock-in; adapters are pluggable and deferred.

**How to apply**:
- When proposing architecture or dependencies for `paw/core/`, default to self-built components.
- NotebookLM and Google Antigravity are **hard rejects** for core — replace with self-built Knowledge Engine (Phase 7) and Search Tool abstraction (Tavily/Google CSE).
- QwenPaw and DeepSeek Harness are **deferred to Phase 11+** as Executor Adapters only; they must not appear in `paw/core/` dependencies.
- Phase gates (Phase 0 foundation → Phase 1 Task Lifecycle E2E → ...) enforce this discipline; see [[digest/procedure/paw-development-phase-gated-approach.md|the phase-gated runbook]].
- This preference is the standing precedent behind [[digest/wiki/paw-core-architectural-pivot-build-from-zero.md|the architectural correction]].

## Sources

- This preference is directly stated in [[memory/2026-08-27/paw-core-phase0-complete-architecture-decision.md|the Phase 0 completion decision note]], where Đại ca decided "build từ 0, kiểm soát hoàn toàn" and explicitly rejected the initial "integration" framing as completely wrong.
- The original prompt spec (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`) confirms PAW Core as standalone architecture with provider isolation.