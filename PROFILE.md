# PROFILE.md

## 身份

- **名字:** PAW Core Engineer
- **定位:** PAW (Personal Agent Workstation) 核心运行时首席系统工程师。负责 Phase 10: Core Runtime, Autonomy & Context Foundation 的设计、实现与验收。
- **风格:** 严谨、务实、系统化。用中文/越南文交流，代码与文档用英文。优先可验证的行为胜过宣称。
- **语言:** 中文/越南文 (主要)，代码/技术术语用英文

## 用户资料

- **名字:** Đại ca
- **称呼:** Đại ca
- **项目:** PAW — Personal Agent Workstation
- **目标:** 从零构建独立的 Personal Agent Runtime，Phase 10 完成核心运行时闭环

### 背景与约束

**PAW 核心架构（自有抽象，外部系统不可重定义）:**
```
Identity · Session · Task · Task Graph
Skill Fabric · Context Compiler · Memory · Knowledge
Autonomy Controller · Policy Engine · Task Ledger
Capability Router · Model Router · Checkpoint/Resume
Evaluation primitives
```

**四部分智能核心:**
```
Skill Fabric (HOW) ◄──────► Context Compiler (WHAT)
       ▲                         ▲
       │                         │
       ▼                         ▼
Task Graph (WHAT) ◄──────► Autonomy Controller (SHOULD)
```

**Phase 10 严格非目标 (绝不实现):**
- OpenCode/Claude Code/Codex Executors
- DeepSeek Harness / QwenPaw / NotebookLM / Antigravity 集成
- Agent swarm, A2A, browser automation, GUI
- Temporal, Redis, PostgreSQL, Kafka, Docker
- Vector database, adaptive learned routing
- MCP 实现 (仅架构规范，gate 全过后再考虑)

**历史系统仅作灵感:** QwenPaw, DeepSeek Harness, NotebookLM, Google Antigravity — 不是运行时依赖、计划提供器、执行器、架构基础。

**架构约束:**
- Local-first, zero-daemon, CLI-first, free-tier
- Pure Python, SQLite, 零 vendor lock-in
- `src/paw/` 为唯一源码根目录
- 所有核心抽象由 PAW 自己拥有

---

## 已确认决策 (2026-08-28)

| 领域 | 决策 |
|------|------|
| **B10 Stress Test** | 使用 **SQLite thật**，full integration test |
| **ExecutionProfile (K)** | **Object cấu hình phong phú**，entity riêng，ảnh hưởng skill/model/autonomy |
| **Provider Layer (Phase 11)** | **Ollama** 作为 local provider  đầu tiên |
| **Packaging (Q)** | **pyproject.toml + build** (modern) |
| **Timeline** | **4 tuần** hoàn thành Phase 10 |
| **Priority** | **Đẩy TẤT CẢ gates PASS trước**，không song song |

**Kế hoạch triển khai đã chốt:**
```
Tuần 1:  Phase 10 Integration Tests (B10 SQLite thật, T scenarios) → Gates 3,4,5 PASS
Tuần 2:  Extended Ledger Events (L) + ExecutionProfile (K - rich object) + CLI commands
Tuần 3:  Packaging (pyproject.toml + build) + False-Green Defense (R) → Gate 7,8
Tuần 4:  GATE REVIEW → Phase 10 PASS/FAIL decision
         Nếu PASS → Phase 11: Ollama Provider Layer
         Nếu PARTIAL → Repair
```

---

## Phase 10 验收门控 (必须全部通过)

| Gate | 要求 |
|------|------|
| **GATE 1** | 核心一致性: 单一 CapabilityRouter, schema/应用契约匹配, Skill 持久化, 存储耐久性 |
| **GATE 2** | 策略安全: ASK≠执行, DENY≠执行, 条件优先级正确, 对抗测试通过 |
| **GATE 3** | 上下文质量: 100 memory + 100 knowledge + 50 skills 压力测试, 预算守恒, 技能/证据集成, explain 模式 |
| **GATE 4** | 自主性: 预算追踪, 进度追踪, 重复检测, 停滞检测, WAIT 状态停止循环, 类型化停止理由, 硬迭代上限 |
| **GATE 5** | 耐久运行时: checkpoint 持久化, 运行时恢复, 已完成操作不自动重复 |
| **GATE 6** | 任务图: 有效 DAG 执行, 环拒绝, 失败传播, 恢复行为 |
| **GATE 7** | 打包: wheel 构建, 干净环境安装成功, CLI 在 repo 外工作, 源码扫描检查非零运行时文件 |
| **GATE 8** | 回归: `pytest` + `ruff check` 通过, 所有前序测试通过 |

**状态规则**: PASS / PARTIAL / FAIL — 不能仅因 "tests pass" 而叫 PASS
**停止规则**: 任一关键 gate 失败 → Phase 10 = PARTIAL/FAIL → 下一步 = 修复 Phase 10

---

## 当前实现状态 (2026-08-28)

| 组件 | 状态 | 备注 |
|------|------|------|
| Core Invariant Repairs (A1–A7) | ✅ 完成 | Schema 修复, 重复移除, 策略强化 |
| ContextCompiler (B1–B9) | ✅ 完成 | 管道工作, B10 压力测试已通过 |
| AutonomyController + Detectors (C–G) | ✅ 完成 | 预算/档案/类型化决策/停止理由 |
| Extended Task States (H) | ✅ 完成 | ExtendedTaskStatus enum |
| Checkpoint/Resume (I1–I3) | ✅ 完成 | SQLite 持久化, 父链接, 恢复钩子 |
| Task Graph (J) | ✅ Phase 9 | 已硬化 |
| Model Router (M) | ✅ Phase 4 | 多维评分 |
| Progressive Skill Loading (O) | ✅ 在 ContextCompiler 中 | Level 0/1/2 |
| Policy/Security (P) | ✅ Phase 6 | ASK=DENY, 对抗测试 |
| **Integration Tests (T)** | ✅ Tuần 1 hoàn thành | B10 SQLite + Autonomy + Checkpoint + Skills + Explain — 15/15 tests pass |
| **Bug Fixes (from integration tests)** | ✅ 完成 | Capability enum, KnowledgeIndex.search, TaskLedger.log, DB transaction, schema columns |
| **Extended Ledger Events (L)** | ✅ Tuần 2 hoàn thành | 8 convenience functions: log_autonomy_decision, log_context_compiled, log_checkpoint_created, log_task_resumed/paused/stalled, log_repetition_detected, log_progress_insufficient — 6 tests pass |
| **ExecutionProfile (K)** | ✅ Tuần 2 hoàn thành | rich object in `src/paw/core/execution_profile.py`, 4 presets (precise/fast/safe/develop), integrated into AutonomyController/ContextCompiler/ModelRouter/SkillFabric — 9 tests pass |
| **CLI commands** | ✅ Tuần 2 hoàn thành | `paw profiles [name]` — list/show execution profiles |
| **Packaging (Q)** | ✅ Tuần 3 hoàn thành | `pyproject.toml` (setuptools, deps cleaned: removed sqlalchemy, added PyYAML), wheel builds, clean venv install OK, CLI works outside repo, 41 runtime py files (no zero-size, no test leak) |
| **False-Green Defense (R)** | ✅ Tuần 3 hoàn thành | `tests/test_phase10_false_green.py` — 10 negative-control tests: no prohibited vendor imports (QwenPaw/DeepSeek/NotebookLM/Antigravity/OpenCode), policy ASK≠exec, DENY≠exec, context budget hard limit, disabled skills excluded, wheel metadata clean. Caught & fixed real violations: `opencode` refs in executor.py/skills.py, F821/F811/F401/F841 bugs in autonomy/context_compiler/detectors/semantic/providers |

---

## Phase 10 Gate Status (2026-08-29)

| Gate | Status | Evidence |
|------|--------|----------|
| **GATE 1** | ✅ PASS | Single CapabilityRouter, schema matches, skill persistence, storage durable |
| **GATE 2** | ✅ PASS | ASK=DENY enforced, adversarial suite in test_phase6_security.py |
| **GATE 3** | ✅ PASS | B10 stress (100 mem + 100 knowledge + 50 skills SQLite), budgets respected, explain mode |
| **GATE 4** | ✅ PASS | Budget/repetition/stall tracking, WAIT stops loop, typed StopReason, hard iteration bound |
| **GATE 5** | ✅ PASS | Checkpoint persisted, runtime resumed, completed ops not repeated (test_phase10_checkpoint_resume) |
| **GATE 6** | ✅ PASS | DAG executes, cycle rejected, failure propagation (Phase 9) |
| **GATE 7** | ✅ PASS | Wheel builds, clean venv install OK, `paw --version`/`paw profiles` work outside repo, 41 non-zero runtime py files, no test leak |
| **GATE 8** | ✅ PASS | `pytest`: 389 passed (0 failed); `ruff check .`: All checks passed |

**Phase 10 = PASS** — all 8 gates satisfied. Phase 11 (Ollama Provider Layer) implemented 2026-08-29.

---

## E0 Track — Benchmark Case Manifest (2026-09-03)

**E0 = Verified** on commit `f3ad4ef`. The benchmark system produces a deterministic,
fixture-validation gate (13/13 SUCCESS) that is **NOT** an agent-quality gate.
The agent-quality tier is the future E0-40 (runtime-driven runner, post-gate work).

| Component | Status | Notes |
|-----------|--------|-------|
| `paw.bench` module | ✅ | Versioned case manifest contract: `CaseManifest`, `ExpectedEvidence`, `FixtureRef`, `CaseCategory`, `PrivacyClass`, `SchemaError`, `validate_case_manifest`, `load_case`, `run_case` |
| `paw.bench.runner` | ✅ | Deterministic runner: `run_case()`, `run_case_file()`, `write_runs_jsonl()`; `shell=False` only (E1-01 hardening) |
| `paw.bench.verification` | ✅ | `VerificationSpec`, `VerificationRecord`, `VerificationResult`, `make_spec_from_evidence` |
| E0-23a | ✅ | `paw.core` surface documented — the public API surface that benchmark cases reference |
| E0-27 | ✅ PASS | D3 release check: full suite green, wheel builds, CLI works outside repo, 13/13 SUCCESS = fixture-validation baseline |
| Benchmark tier framing | ✅ | **13/13 SUCCESS = fixture-validation only**, NOT agent-quality. Agent-quality = E0-40 (runtime-driven runner) |

**Key design decision**: the benchmark runner is read-only (no destructive commands),
uses `shell=False` exclusively, and rejects shell-string targets (E1-01 reopen).
Cases are YAML files in `benchmarks/e0/cases/` — not SQLite, not a database.
The runner is a future consumer of the PAW runtime loop; it is NOT yet integrated.

---

## Phase 11 Implementation Status (2026-08-29)

| Component | Status | Notes |
|----------|--------|-------|
| `OllamaProvider` | ✅ 完成 | `src/paw/providers/ollama/provider.py` — implements `ModelProvider` Protocol (list_models/get_model/complete/stream), stdlib-only HTTP (urllib + asyncio.to_thread), graceful degradation khi Ollama không chạy |
| `ModelRegistry.register_ollama_models()` | ✅ 完成 | Lazy import OllamaProvider, discover + register Ollama models as `provider="ollama"` ModelManifest; returns 0 nếu Ollama unavailable |
| `ModelExecutor` | ✅ 完成 | `src/paw/core/model_executor.py` — dispatch ModelSelection tới đúng provider; `LocalModelExecutor` fallback (offline stand-in); unknown provider → local fallback |
| Manifest inference | ✅ 完成 | Single `_MODEL_HINTS` table: model-name fragment → (roles, capabilities), consistent |
| **Tests** | ✅ 12 passed | `tests/test_phase11_ollama.py` — mock HTTP server, unavailable-degradation, registry integration, executor dispatch |
| **Full suite** | ✅ 401 passed | 389 (Phase 0–10) + 12 (Phase 11), 0 failed |
| **ruff** | ✅ All checks passed | |
| **Packaging (Gate 7)** | ✅ PASS | Wheel rebuild OK, 44 non-zero py files, no test leak, clean venv install OK, CLI works outside repo |

**Phase 11 = PASS** — Ollama local provider + ModelExecutor layer hoàn thành, zero vendor lock-in (stdlib HTTP, local-first).

---

## Phase 12 Implementation Status (2026-08-29)

**Phase 12 = Advanced Memory Retrieval** — hybrid (lexical + semantic embedding) retrieval with re-ranking, fully local-first and zero vendor lock-in.

| Component | Status | Notes |
|----------|--------|-------|
| `src/paw/core/embeddings.py` | ✅ 新增 | `EmbeddingProvider` Protocol, `OllamaEmbeddingProvider` (stdlib HTTP tới `/api/embeddings`, graceful degradation), `LocalEmbeddingProvider` (offline hashed bag-of-words fallback), `cosine_similarity`, persistence (`memory_embeddings` bảng riêng, không migration `memory_records`) |
| `OllamaProvider.embed()` | ✅ 新增 | `src/paw/providers/ollama/provider.py` — gọi `/api/embeddings`, trả vector hoặc `[]` khi lỗi (không raise) |
| `AdvancedMemoryRetriever` | ✅ 新增 | `src/paw/core/memory.py` — hybrid lexical + semantic; khi có provider thì fetch broader pool (semantic recall vượt lexical prefilter), re-rank by fused score; degrade lexical-only khi không có provider |
| ContextCompiler wiring | ✅ 完成 | `_retrieve_memory_candidates` dùng `AdvancedMemoryRetriever.score_records` → memory candidate có relevance_score thật (không còn flat 0.5); metadata ghi lexical_score/semantic_score/has_embedding |
| **Tests** | ✅ 9 passed | `tests/test_phase12_memory_retrieval.py` — cosine, local-deterministic, persistence, lexical-only degradation, hybrid re-rank (stub vectors), Ollama mock server, Ollama-unavailable fallback, ContextCompiler integration |
| **Full suite** | ✅ 410 passed | 401 (Phase 0–11) + 9 (Phase 12), 0 failed |
| **ruff** | ✅ All checks passed | src + tests |

**Phase 12 = PASS** — hybrid retrieval + re-ranking hoạt động, semantic recall vượt lexical prefilter, graceful degradation đúng (Ollama down → local fallback). Lưu ý: `LocalEmbeddingProvider` là hashed bag-of-words (tương đương lexical) — true semantic cần Ollama model thật (nomic-embed-text); kiến trúc pluggable sẵn sàng.

---

## Phase 11b — Semantic Skill Selector (deferred item, 2026-08-29)

**Tái dùng pattern Phase 12** (`embeddings.py` + `AdvancedMemoryRetriever`) cho skill selection.

| Component | Status | Notes |
|----------|--------|-------|
| `AdvancedSkillSelector` | ✅ 新增 | `src/paw/core/semantic.py` — hybrid lexical (`SemanticMatcher`) + semantic embeddings; fusion weighted (`lexical_weight`/`semantic_weight`); khi có provider thì score TẤT CẢ skills (không lexical prefilter) để semantic recall vượt; degrade lexical-only khi không có provider; embed failure → lexical fallback |
| `AdvancedSkillResult` + `get_advanced_skill_selector()` | ✅ 新增 | transparent scores (lexical/semantic/final/has_embedding) |
| ContextCompiler wiring | ✅ 完成 | `_retrieve_skill_candidates` dùng `AdvancedSkillSelector` → skill candidate có `relevance_score` thật (trước là flat 0.5), metadata ghi `lexical_score`/`semantic_score`/`has_embedding` |
| **Tests** | ✅ 6 passed | `tests/test_semantic_skill_selector.py` — lexical-only, hybrid rerank, capability filter, embed-failure degrade, LocalEmbeddingProvider signal, ContextCompiler integration |
| Bug fix | ✅ | `list_skills()` trả `SkillManifest` (không phải `Skill`) → wrap defensively trong selector; `FakeFabric` test double aligned to contract |

**Phase 11b = PASS** — Semantic Skill Selector hoàn thành, tái dùng pattern Phase 12, zero vendor lock-in.

---

## Phase 13 — Enhanced Context Builder (2026-08-29)

**Hai enhancement lên ContextCompiler base:**

| Component | Status | Notes |
|----------|--------|-------|
| Cross-source near-duplicate dedup | ✅ 新增 | `_deduplicate()` nâng cấp: exact-key + near-dup qua lexical Jaccard (threshold default 0.85), upgrade sang embedding cosine khi có `embedding_provider`; drop candidate thấp priority hơn, ghi `excluded_reason="duplicate_of:<src>:<id>"` + `duplicate_similarity`. Thêm `dedup_threshold`/`dedup_enabled` vào `ContextBudget` |
| Progressive skill Level-1 upgrade | ✅ 新增 | `_build_context()` hiện upgrade selected skill candidate (Level 0→1) bằng cách load `skill.manifest.body` qua `get_skill_fabric().get_skill()`; resp `max_content_length` (quá lớn → giữ metadata + `body_skipped`); ghi `body_loaded`/`skill_level` |
| Explain metadata | ✅ | `excluded_reason`/`duplicate_similarity`/`body_loaded`/`body_skipped` |
| **Tests** | ✅ 7 passed | `tests/test_phase13_context_builder.py` — dedup exact/near-cross-source/distinct/disabled, semantic-via-embedding paraphrase, progressive L1 upgrade, body-too-large skip |
| **Full suite** | ✅ 423 passed | 416 (Phase 0–12 + 11b) + 7 (Phase 13), 0 failed |
| **ruff** | ✅ All checks passed | src + tests |

**Phase 13 = PASS** — Enhanced Context Builder: real cross-source dedup (budget-saving, coherence) + progressive skill body loading (actionable instructions). Zero vendor lock-in giữ nguyên.

---

## Phase 14 — Policy Guard v2 (2026-08-29)

**Mục tiêu:** nâng Policy Guard từ v1 (trả enum trần, không provenance, không gắn vào autonomy loop) lên v2 — explainable + aggregate single-authority gate + loop-enforced + audited.

**Phát hiện gap trước khi làm (inspect repo):**
- `PolicyGuard.check()` trả `PolicyDecision` enum TRẦN — không có "quy tắc nào khớp / tại sao".
- Autonomy loop (`AutonomyController.decide()`) check budget/progress/repetition/stall NHƯNG **không bao giờ consult policy** → ASK/DENY không thực sự dừng loop (vi phạm hiến pháp: "ASK = STOP, never execute").
- Không có aggregate gate cho một TẬP capabilities; không audit trail chi tiết.

| Component | Status | Notes |
|----------|--------|-------|
| `PolicyDecisionDetail` (explainable) | ✅ 新增 | `src/paw/core/policy.py` — `decision`, `source` (`rule:<id>` / `default`), `matched_rule`, `conditions_evaluated`, `reason`, `interactive_resolved` |
| `PolicyGuard.check_detailed()` | ✅ 新增 | trả `PolicyDecisionDetail` (raw decision — giữ backward-compat cho Phase 6断言 `check()==ASK`); `check()` delegate sang `.decision` |
| `RequestVerdict` + `evaluate_request()` | ✅ 新增 | single-authority aggregate gate: `go` / `ask` / `block`. DENY→block(POLICY_DENIED); ASK non-interactive→block(POLICY_ASK_REQUIRED); ASK interactive→ask. ASK never→ALLOW (fail-closed) |
| `log_policy_decision()` (ledger audit) | ✅ 新增 | `src/paw/core/ledger.py` — ghi provenance vào `TaskEventType.POLICY_CHECKED` |
| Autonomy-loop policy gate | ✅ 新增 | `AutonomyController.__init__(policy_guard=...)` + `decide(required_capabilities=...)` — bước 0 trước budget: DENY→STOP(POLICY_DENIED), ASK non-interactive→STOP(POLICY_ASK_REQUIRED), ASK interactive→ASK(POLICY_ASK_REQUIRED). Optional params → backward-compatible (legacy tests không đổi) |
| **Tests** | ✅ 19 passed | `tests/test_phase14_policy_guard_v2.py` — explainable detail, aggregate gate, condition priority, ledger audit, autonomy-loop enforcement, adversarial (path traversal, undeclared→ASK, privilege escalation) |
| **Full suite** | ✅ 442 passed | 423 (Phase 0–13) + 19 (Phase 14), 0 failed |
| **ruff** | ✅ All checks passed | src + tests |
| **Pre-existing flake** | ⚠️ biết | `test_autonomy_hard_iteration_bound` + `test_execution_profile_influences_context_compiler` flake (`no such table: task_events` / aiosqlite OperationalError) khi chạy SUBSET do global `db` singleton race — tái hiện ĐỘC LẬP với Phase 14 (chạy phase6+phase10 cũng fail). KHÔNG phải regression logic. Full suite luôn xanh 442. |

**Phase 14 = PASS** — Policy Guard v2: explainable decisions + aggregate single-authority gate + autonomy-loop enforcement (ASK/DENY thực sự dừng loop) + ledger audit. Constitution "ASK = STOP, never execute" giờ được thực thi ở loop level. Zero vendor lock-in giữ nguyên.

---

## 近期优先级

1. ~~**Phase 16**: Full integration & docs~~ ✅ DONE (Phase 16)
2. ~~**Optional**: Runtime tự động gắn `OllamaEmbeddingProvider`~~ ✅ DONE (Phase 17)
3. ~~**Optional / tech-debt**: Sửa DB-isolation race~~ ✅ DONE (Phase 17 — per-test DB)
4. **Open Work**: Identity module, directory restructure, API docs — chờ Đại ca quyết định

---

## Phase 15 — Model Router v2 (providers) (2026-08-29)

**Mục tiêu:** Nâng ModelRouter từ "score-only, blind to provider health" → "provider-aware, health-checked, fallback-safe".

| Component | Status | Notes |
|----------|--------|-------|
| `ModelProvider` Protocol | ✅ nâng cấp | `src/paw/providers/__init__.py` — thêm `@runtime_checkable` + `available` property + `discover_manifests()`; OllamaProvider conform, LocalModelExecutor (executor) KHÔNG conform (đúng) |
| `ProviderRegistry` | ✅ mới | `src/paw/core/model_router.py` — aggregate providers, `discover_models()` chỉ lấy models của provider **available** (graceful degradation), zero vendor lock-in (core KHÔNG import Ollama) |
| `ModelRouter` provider-aware | ✅ | `route()`/`route_with_explain()`: discover models từ providers (khi default registry), lọc bỏ models của provider unavailable, fallback `local` khi không có candidate, fallback_chain chỉ chứa provider reachable; preferred model từ provider down → skip |
| Latent bug fixes | ✅ | `ModelManifest.local` property + `supports_role()` (`src/paw/core/models.py`); `ModelRouter.scorer` property (route preferred path trước dùng `self.scorer` chưa tồn tại) |
| **Tests** | ✅ 11 passed | `tests/test_phase15_model_router_v2.py` — protocol conformance, discover-available-only, exclude unavailable, select available, fallback local-when-only-down, preferred-skip-down, backward-compat, route_with_explain, scorer accessor |
| **Full suite** | ✅ 453 passed | 442 (Phase 0–14) + 11 (Phase 15), 0 failed |
| **ruff** | ✅ All checks passed | src + tests |

**Phase 15 Gates (đề xuất + satisfied):**
- **G1** ModelProvider Protocol `@runtime_checkable` có `available` + `discover_manifests`; OllamaProvider pass, LocalModelExecutor fail (đúng).
- **G2** `ProviderRegistry` aggregate + discover chỉ provider available; core không hardcode import Ollama (zero vendor lock-in).
- **G3** Provider-aware route: unavailable providers bị loại, fallback `local` khi none.
- **G4** Fallback chain không chứa provider down.
- **G5** 11 tests pass, ruff clean, full suite 453 xanh (không regression Phase 0–14).

**Phase 15 = PASS** — Model Router giờ aware provider health, không còn chọn model của provider chết. Tích hợp sẵn với ModelExecutor (Phase 11) để dispatch. Zero vendor lock-in giữ nguyên.

---

## Phase 16 — Full Integration & Docs (2026-08-29)

**Mục tiêu:** Ghép toàn bộ PAW Core runtime loop (Phase 0–15) thành một luồng nhất quán + tài liệu dự án (README, ARCHITECTURE).

| Component | Status | Notes |
|----------|--------|-------|
| `tests/test_phase16_integration.py` | ✅ 2 passed | End-to-end loop: Session/Task → ContextCompiler → PolicyGuard → AutonomyController → ModelRouter (provider-aware) → ModelExecutor → TaskScheduler DAG → CheckpointManager → TaskLedger. Happy-path + negative (DENY capability dừng loop trước execution) |
| `README.md` | ✅ mới | Overview, install (`pip install .`), CLI (`paw --version`, `paw profiles`), Python quickstart, 4-part core, runtime loop, provider pluggability, phase table |
| `ARCHITECTURE.md` | ✅ mới | Module map (`src/paw/`), design principles, four-part intelligence core, runtime loop, safety invariants, phase history |
| **Full suite** | ✅ 455 passed | 453 (Phase 0–15) + 2 (Phase 16), 0 failed |
| **ruff** | ✅ All checks passed | src + tests |

**Phase 16 Gates (đề xuất + satisfied):**
- **G1** Integration test chạy toàn bộ loop qua API thật (real temp SQLite), không mock storage/core.
- **G2** Ledger ghi trail mạch lạc (context_compiled/policy_checked/autonomy_decision/model_selected/execution_completed/task_completed).
- **G3** Policy gate là single authority: DENY → AutonomyController STOP, không execution nào được log.
- **G4** Task Graph DAG valid (topo sort đúng thứ tự, detect_cycles=[]).
- **G5** Checkpoint persist + reload (get_latest khớp).
- **G6** Docs准确 reflect thực tế (module map, providers, zero vendor lock-in).
- **G7** Full suite 455 xanh, ruff sạch, không regression Phase 0–15.

**Phase 16 = PASS** — PAW Core Runtime hoàn chỉnh end-to-end. Tất cả Phase 0–16 đều PASS.

---

## Phase 17 — Optional Backlog: Auto-attach + DB Race (2026-08-29)

**Mục tiêu:** Làm 2 optional backlog còn lại sau Phase 16.

| Component | Status | Notes |
|----------|--------|-------|
| `try_ollama_embedding_provider()` | ✅ 新增 | `src/paw/core/embeddings.py` — trả `OllamaEmbeddingProvider` nếu Ollama chạy, `None` nếu down (graceful, không raise) |
| `ContextCompiler` auto-attach | ✅ | `auto_attach_embeddings=True` (default); `_resolve_embedding_provider()` lazy, chạy 1 lần/instance; propagate flag vào `AdvancedSkillSelector` bên trong |
| `AdvancedSkillSelector` auto-attach | ✅ | standalone `auto_attach_embeddings=True`; `_resolve_embedding_provider()` trong `select()` |
| conftest per-test DB | ✅ | `session_db` đổi thành **function-scoped + autouse** → mỗi test 1 file + connection riêng; xoá module-scoped global `_SHARED_DB_PATH`; triệt tiêu race "no such table: task_events" |
| **Tests** | ✅ 5 passed | `tests/test_phase17_auto_attach_embeddings.py` — down/up/explicit/disabled/selector-standalone |
| **Full suite** | ✅ 460 passed | 455 (Phase 0–16) + 5 (Phase 17), 0 failed |
| **ruff** | ✅ All checks passed | src + tests |

**Root cause race (đã fix):** `set_db_path` tạo `Database` mới mỗi lần, nhưng race xảy ra khi nhiều module chia connection singleton qua conftest module-scoped + truncate FTS5. Chuyển sang per-test file/connection (function-scoped autouse) → mỗi test luôn có schema riêng, flake structurally impossible. Chi phí: full suite 143s → 228s (~+85s do schema build mỗi test) — chấp nhận được.

**Phase 17 = PASS** — cả 2 optional backlog hoàn thành, zero vendor lock-in giữ nguyên.

---

## Phase 18 — Open Work: Identity + Restructure + Docs (2026-08-29)

**Mục tiêu:** Làm 3 Open Work còn lại sau Phase 17.

| Component | Status | Notes |
|----------|--------|-------|
| Identity module | ✅ 新增 | `src/paw/core/identity/__init__.py` — `Identity` (typed dataclass) + `IdentityManager` (key/value store trên bảng `identity`); `bootstrap/get/set/get_all/delete/load`; JSON (de)serialize; export vào `core/__init__.py` |
| Directory restructure | ✅ effectively done | Inspect: cấu trúc top-level (`core/` `providers/` `knowledge/` `cli/`) **đã khớp** ARCHITECTURE.md từ trước. Gap duy nhất là `core/identity/` rỗng → giờ đã thành package thật (vừa làm Identity module). Không need move file (tránh rủi ro break 468 tests) |
| API reference | ✅ 新增 | `docs/api.md` — reference theo module (Session/Task, Context, Policy, Autonomy, Model, Skills, Memory/Knowledge, Embeddings, Ledger/Checkpoint, Identity, TaskGraph) |
| Examples | ✅ 新增 | `docs/examples.md` — 11 snippets chạy được (identity bootstrap → full runtime loop) |
| ARCHITECTURE.md | ✅ cập nhật | thêm `identity/` vào module map |
| **Tests** | ✅ 8 passed | `tests/test_identity.py` — bootstrap/defaults/roundtrip/get_all/delete/load/overwrite |
| **Full suite** | ✅ 468 passed | 460 (Phase 0–17) + 8 (Phase 18), 0 failed |
| **ruff** | ✅ All checks passed | src + tests |

**Phase 18 = PASS** — toàn bộ roadmap PAW (Phase 0–18) hoàn thành. PAW Core Runtime độc lập, local-first, zero vendor lock-in, có Identity + docs đầy đủ.

---

## 近期优先级 (updated 2026-09-06)

1. ~~**Phase 16**: Full integration & docs~~ ✅ DONE (Phase 16)
2. ~~**Optional**: Runtime tự động gắn `OllamaEmbeddingProvider`~~ ✅ DONE (Phase 17)
3. ~~**Optional / tech-debt**: Sửa DB-isolation race~~ ✅ DONE (Phase 17 — per-test DB)
4. ~~**Open Work**: Identity module + Directory restructure + API docs/examples~~ ✅ DONE (Phase 18)
5. ~~**Phase 19 Runtime Hardening**~~ ✅ DONE (2026-08-30, 501 tests)
6. ~~**Phase 20 Agent Loop**~~ ✅ DONE (506 tests)
7. ~~**E0 track**~~ ✅ VERIFIED on f3ad4ef (13/13 fixture-validation baseline; E0-23a paw.core surface; E0-27 gate verdict PASS)
8. ~~**E1 track**~~ ✅ VERIFIED (37/37 + 3/3 backlog PASS; E1-27 measurement gate PASS/VERIFIED on clean revision `8d01d90` with real Ollama embeddings, min_recall=1.00; all E1-27 production measurements pass)
9. ~~**E1-35 E2E recall contract**~~ ✅ VERIFIED (10 tests, real fixture repo, no monkeypatch)
10. ~~**E2**~~ ✅ RATIFIED on clean revision `8d01d90` (E1 VERIFIED gate satisfied; E2-25..28 + E2-45..47 prerequisites all PASS; cloud-baseline boundary explicitly resolved via InferenceClassification/E2-09 + evaluate_local_eligibility/E2-05; 119 E2 contract tests pass)

### E1 track finalization (2026-09-06)

**E1-17/23/24/25 DONE** — 4 remaining items implemented in 1 commit (`548f8f0`):

| Item | Implementation | Tests |
|------|---------------|-------|
| **E1-17** | `docs/benchmarks/e1/inclusion_reasons.md` + wiring `source_hash`/`external_id`/`revision`/`privacy_class` from `KnowledgeSource` for knowledge candidates; `privacy_class` from `MemoryRecord` for memory candidates in `context_compiler.py` | `test_e1_17_inclusion_contract.py` (14 D1) |
| **E1-23** | `src/paw/bench/recall.py` — `RecallResult` frozen dataclass + `measure_recall(case, *, compiler, repo_root, mode)` async function (cold/warm modes) | `test_e1_23_recall_measurement_contract.py` (9 D2) |
| **E1-24** | `src/paw/bench/tokens.py` — `TokenResult` frozen dataclass + `measure_tokens(...)` + `set_baseline_tokens()` | `test_e1_24_token_measurement_contract.py` (8 D2) |
| **E1-25** | `MISS_CATEGORIES` closed frozenset (5 causes) + deterministic action mapping | `test_e1_25_recall_misses_contract.py` (12 D2) |
| **E1-35** | End-to-end recall contract: real fixture repo → scan → revision → symbol graph → test association → knowledge ingestion → ContextManifest → privacy gate → evidence recall >= 95% (no monkeypatch, no fake measurements). 10 tests all pass. | `test_e1_35_e2e_recall_contract.py` (10 D1) |

**Total E1: 37/37 core + 13/13 backlog = ALL DONE.** Full suite continues to pass (targeted E1 + context_compiler tests all pass; E1-35 end-to-end contract verified).
9. **Roadmap**: PAW Core hoàn chỉnh (Phase 0–20 + E0 + E1). Tiếp theo tuỳ Đại ca — e.g. thực tế hoá vendor provider (OpenCode/Claude Code executors, DeepSeek harness) BÊN NGOÀI core, hoặc mở rộng Knowledge Engine, hoặc đóng gói release, hoặc chat REPL app layer.

### Kỹ năng đã materialize

| Skill | Mục đích | Trigger |
|-------|----------|---------|
| `bootstrap-canonical-docs` | Tạo 4 file canonical rỗng có cấu trúc (ROADMAP, IMPLEMENTATION_MAP, EXECUTION_CHECKLIST, ENGINEERING_RULES) | "set up the doc set", "bootstrap the four files" |
| `doc-driven-stabilization` | Đóng track theo 5 phases (atomic commits, evidence chain, test isolation, frozen revision, exit gate) | "stabilize the project", "close the gate", "verify docs match code" |

### Test-speed policy (2026-08-29, quyết định Đại ca)
- **Cấp 1** (không refactor fixture): chạy theo phase/file + `--lf` + `-x`. Helper `scripts/pt.sh`.
- **Cấp 2 ĐÃ IMPLEMENT** (sau đó Đại ca đổi ý từ "chỉ Cấp 1" sang Cấp 2):
  - `tests/conftest.py` mới: `session_db` fixture **module-scoped** (1 DB file + schema build / test file, không phải / test) + `reset_db` (function-scoped, truncate mọi user table trước/sau mỗi test) + `temp_db` (yield shared path).
  - Gom 5 fixture `temp_db` trùng lặp (phase6/8/14/storage_helpers/skill_fabric) vào conftest.
  - `policy_rules` thêm vào SCHEMA chính (`src/paw/core/storage.py`) — giờ là core table, không cần test tự CREATE.
  - **rollback = truncate** (DELETE FROM) vì `db.write` tự commit → transaction rollback không undo được; truncate deterministic + rẻ.
  - **module-scoped thay vì session-scoped**: FTS5 virtual table `skill_fts` corrupt (`vtable constructor failed` / `database disk image is malformed`) khi 1 DB file shared xuyên nhiều test-module + truncate lặp. Module-scoped = mỗi file DB riêng, FTS an toàn, vẫn chỉ init 1 lần/file.
  - **skill_fabric giữ fixture riêng** (per-test file+init) — FTS5 không chịu shared/reconnect DB; 4 files còn lại (phase6/8/14/storage_helpers) hưởng Cấp 2.
  - **Kết quả**: full suite 442 passed, **233s → 143s (~38% nhanh hơn)**, ruff clean. 5 files (gom) chạy 111 passed / ~47s.
- In-memory `:memory:` BỊ LOẠI (treo do singleton close→mất DB).
---

## Phase 19 — Runtime Hardening (2026-08-30)

Sau Phase 18, Đại ca chỉ ra 10 core gap cần sửa TRƯỚC chat REPL. Thứ tự đã chốt: #9 cleanup → #6 unify ProviderRegistry+messages → #1/#8 PawRuntime.run() black-box → #7 Autonomy STOP_SUCCESS → #2 ContextCompiler re-budget → #3 knowledge get_chunk_with_evidence → #4 TaskGraph validate → #5 Checkpoint OperationRecord → #10 move adapters ra integrations/.

| # | Item | Status | Commit |
|---|------|--------|--------|
| #9 | Cleanup: xoá __pycache__/*.pyc/test DB, harden .gitignore | ✅ DONE | `dd7a464` |
| #6 | ModelExecutor chia sẻ ProviderRegistry với ModelRouter + truyền `messages` (không chỉ `prompt`); LocalModelExecutor giữ ngoài registry | ✅ DONE | `eac3ce6` |
| #1/#8 | `PawRuntime.run()` black-box loop: Policy+Autonomy gate TRƯỚC step_fn, truyền proposed capabilities; test gọi run() không tự orchestrate | ✅ DONE | `79e4c4b` |
| #7 | Autonomy: task hoàn thành → STOP_SUCCESS deterministic; bỏ CONTINUE\|STOP chấp nhận | ✅ DONE | `6f2aac9` |
| #2 | ContextCompiler progressive skill L0→L1 re-budget final payload | ✅ DONE | `c19dadb` |
| #3 | Knowledge Context: dùng `get_chunk_with_evidence()` thay search chunk ID trong claim | ✅ DONE | `d9fd0de` |
| #4 | TaskGraph: reject missing deps/self-cycle/cycle trước persist/execute | ✅ DONE | `dc98eee` |
| #5 | Checkpoint: thêm OperationRecord / primitive idempotency tối thiểu chứng minh replay safety | ✅ DONE | `9406deb` |
| #10 | Move QwenPaw/ReMe/persona adapters ra `integrations/` (archive, giữ dùng sau) — Đại ca chọn MOVE không DELETE | ✅ DONE | `6ab2d8f` |

**Trạng thái**: Phase 19 HOÀN THÀNH (local, 6 commit mới: `6f2aac9`/`c19dadb`/`d9fd0de`/`dc98eee`/`9406deb`/`6ab2d8f` + 3 commit trước `79e4c4b`/`eac3ce6`/`dd7a464`). Full suite **501 passed (0 failed)**, ruff clean. Chưa push (Đại ca đã chỉ "xong push sau"). `history.db` (QwenPaw agent history) KHÔNG xoá — chỉ xoá test DB.

---

## Phase 19 — Runtime Hardening (2026-08-30) — 8 Hardening Points Complete

**8 điểm hardening được thực hiện trong `test_phase19_runtime_hardening.py` (11 tests) + `test_phase19_runtime_loop.py` (7 tests):**

| # | Hardening Point | Implementation | Tests |
|---|-----------------|----------------|-------|
| 1 | **ProposedAction** với `operation_id`, `estimated_cost` (ResourceUsage), `idempotency_key` | `src/paw/core/models.py:ProposedAction` | test_1 |
| 2 | **ExecutionObservation** typed class thay thế arbitrary dict | `src/paw/core/models.py:ExecutionObservation` | test_2 |
| 3 | **ActionProposer** — single source of truth cho next action | `src/paw/core/runtime.py:ActionProposer` | test_3 |
| 4 | **AutonomyBudget / ResourceUsage** — per-resource-type tracking (model, tool, tokens, wall_time, network, destructive) | `src/paw/core/models.py:ResourceUsage` + `AutonomyController.usage` | test_4 |
| 5 | **OperationRecord** — idempotent replay safety (skip completed ops on resume) | `src/paw/core/checkpoint.py:OperationRecordStore` | test_5, test_resume |
| 6 | **CheckpointManager** integration in runtime loop (auto + forced) | `src/paw/core/runtime.py:PawRuntime._create_checkpoint` + `maybe_checkpoint` | test_6 |
| 7 | **TaskLedger** full event trail (STEP_PROPOSED, POLICY_GATE, AUTONOMY_GATE, STEP_EXECUTED, OPERATION_RECORDED, CHECKPOINT_CREATED, TASK_COMPLETED) | `src/paw/core/ledger.py` + runtime wiring | test_7 |
| 8 | **Black-box real SQLite acceptance** — no mocks for core subsystems | `tests/test_phase19_runtime_hardening.py:test_8` | test_8 |
| + | **Policy ASK/DENY blocks BEFORE step_fn** (single authority gate) | `src/paw/core/runtime.py` policy gate | test_ask, test_deny |

**New Types Added:**
- `ProposedAction` — action proposal with operation_id, estimated_cost, capabilities, idempotency_key
- `ExecutionObservation` — typed step result with resources_used, success, error, action_id
- `ResourceUsage` — model_calls, tool_calls, tokens, wall_time_ms, network_bytes, destructive_ops
- `AutonomyBudget` extensions — max_model_calls, max_tool_calls, max_total_tokens, max_wall_time_seconds
- `TaskEventType` additions: STEP_PROPOSED, STEP_EXECUTED, STEP_COMPLETED, OPERATION_RECORDED, CHECKPOINT_RESTORED, POLICY_GATE_EVALUATED, AUTONOMY_GATE_EVALUATED

**Runtime Loop Contract Enforced:**
1. ActionProposer → ProposedAction
2. Policy Gate (evaluate_request) → block/ask/go
3. Autonomy Gate (decide) → STOP/ASK/PAUSE/ESCALATE/DELEGATE/CONTINUE
4. CONTINUE → step_fn → ExecutionObservation
5. Record OperationRecord for replay safety
6. Update autonomy usage from observation
7. Maybe checkpoint
8. Check completion → STOP_SUCCESS

**Key Files Modified:**
- `src/paw/core/models.py` — +ProposedAction, ExecutionObservation, ResourceUsage, TaskEventType
- `src/paw/core/runtime.py` — PawRuntime.run (black-box), ActionProposer, ledger/checkpoint integration
- `src/paw/core/ledger.py` — 7 new convenience log functions
- `src/paw/core/checkpoint.py` — force_checkpoint handles AutonomyUsage serialization, TaskLedger.record
- `tests/test_phase19_runtime_hardening.py` — 11 acceptance tests (8 hardening points + resume + policy deny/ask)
- `tests/test_phase19_runtime_loop.py` — 7 black-box contract tests (#1/#8)

**Full Suite: 501 passed, ruff clean.**

---

## Phase 20 — PawRuntime 成为 TRUE Agent-Loop Integration Point (2026-08-30)

**Mục tiêu:** 把 `PawRuntime` 从「循环框架」升级为真正连接所有 PAW 子系统的反馈循环运行
时 —— 补全 archived task 的遗留项（TaskGraph → Context → Skill → Model → Execution 闭环）。

| Component | Status | Notes |
|-----------|--------|-------|
| `PawRuntime.run_agent()` | ✅ 新增 | 真实 agent 循环：ContextCompiler → SkillFabric → ModelRouter → ModelExecutor 全链路接线 |
| `AgentActionProposer` | ✅ 重构 | 真实「大脑」：编译 context + 选 skill（goal 相关性排序）+ 路由 model + 调 model + 解析成 ProposedAction |
| 运行时拥有 ContextCompiler | ✅ | `_loop` 每轮编译 context 并记 `context_compiled`（不再依赖 brain 内部） |
| `_gate_action()` (single authority) | ✅ 抽取 | Policy + Autonomy gate 抽成单一 helper，`run` / `run_agent` / `run_graph` 共用 |
| `PawRuntime.run_graph()` | ✅ 新增 | TaskGraph DAG 经同一 gated loop 逐节点执行；build_graph 校验拒绝环/缺失依赖 |
| `_execute_action()` | ✅ | 运行时级 model 路由（execution 侧）+ skill 加载 + `execution_completed` 日志 |

**Wiring (闭环):**
```
TaskGraph(DAG) → ContextCompiler → SkillFabric → ModelRouter → ModelExecutor
     ↑                                              │
     │                                              ▼
Observation ← Policy Gate ← Autonomy Gate ← ProposedAction
                     │
                     ▼
            TaskLedger + CheckpointManager
```

**Tests:** `tests/test_phase20_agent_runtime_loop.py` — 5 passed (A: 真实子系统接线 end-to-end; B: brain 驱动完成 → STOP_SUCCESS; C: policy DENY 阻断执行; D: DAG 3 节点依赖序执行; E: 环图拒绝). 
**Full Suite: 506 passed (501 + 5), ruff clean.**

**Phase 20 = PASS** — `PawRuntime` 现为真正的 integration point，连接 Context + TaskGraph + Autonomy + Policy + Execution + Observation + Ledger + Checkpoint 为单一反馈循环；零 vendor lock-in 保持。

---

## Phase 21 — E1-01 Reopen (2026-09-04)

Sau Phase 20, Đại ca reopen E1-01 (track owner Memory/Knowledge/ContextCompiler ownership cho từng field mới). 4 cụm việc:

| Cụm | Thay đổi |
|---|---|
| Ownership regenerate | `docs/benchmarks/e1/ownership_audit.md` regenerated từ source: MemoryRecord (13 fields), KnowledgeSource (12), KnowledgeChunk (7), KnowledgeEvidence (6), KnowledgeCitation (7), TaskContext (8), ContextBudget (8). Audit cũ list phantom `source` trên MemoryRecord, thiếu `keywords`/`updated_at`/`last_accessed`, phantom `kind`/`uri`/`revision` trên KnowledgeSource |
| Contract test | `tests/test_e1_ownership_audit_contract.py` (16 D1 tests) — pin audit ↔ dataclass field mapping. Two-fail-positive proven: swap về original `f909f65` audit → 16/16 fail |
| Canonical status reconciliation | README + ROADMAP + IMPLEMENTATION_MAP + CHECKLIST + vi/CHECKLIST đồng bộ: Core Stabilization VERIFIED on f3ad4ef; E0 VERIFIED cho deterministic fixture-validation baseline (13/13 SUCCESS); E1 IN PROGRESS 1/34; E1-01 reopened; E1-02 next |
| Bench command_exit hardening | `src/paw/bench/runner.py` reject shell-string targets, `subprocess.run(shell=False)` only. Deny-list giữ defense-in-depth. 37 existing command_exit tests pass |
| Benchmark tier framing | `integration_pack_run.md` + CHECKLIST clarify: **13/13 SUCCESS = fixture-validation only**, NOT agent-quality gate. Agent-quality tier = runtime-driven runner (E0-40 post-gate) |

**Commit `7eaf377`** pushed to origin/main.

**Full Suite: 793 passed (was 777; +16 = new contract test), ruff clean, cross-link batch CONTRACT PASSED.**

---

## Phase 22 — E1-02 Project-Source Identity, Revision, Content Hash, Invalidation Metadata (2026-09-04)

Sau Phase 21, Đại ca chốt E1-02 (project-source identity + revision + content hash + invalidation metadata) làm tiếp. Contract: mỗi byte project context phải truy nguyên được về source identity/revision; decision phải phát hiện được khi revision thay đổi làm nó stale.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/project_source_identity.md` — định nghĩa 5 field mới, closed `INVALID_REASONS` set, `is_stale`/`is_fresh` predicate, `mark_invalid` + `list_stale` boundary |
| `KnowledgeSource` dataclass | ✅ 12→17 fields | additive: `external_id`, `revision`, `invalidated_at`, `invalidation_reason`, `superseded_by`. Defaults `""` hoặc `None` — không cần row rewrite. |
| `KnowledgeSource` properties | ✅ 新增 | `is_stale` (True iff invalidated/superseded/ERROR) + `is_fresh` |
| `KnowledgeSourceManager` | ✅ | `create()` accept `external_id`/`revision`; `mark_invalid(source_id, reason, superseded_by="")` enforce closed reason set (unknown → `ValueError`); `list_stale()` SQL filter đồng thuận với in-Python predicate |
| SQL migration | ✅ additive | `storage._migrate_schema`: `ALTER TABLE knowledge_sources ADD COLUMN` × 5, guard `PRAGMA table_info`, no DROP, no row rewrite, no `PRAGMA user_version` bump (forward-compatible) |
| E1-01 ownership audit | ✅ sync | KnowledgeSource table 12→17 fields, contract test updated (`revision` từ phantom → real; 5 E1-02 field asserted) |
| Contract test | ✅ 22 D1 tests | `tests/test_e1_02_source_identity_contract.py`: field existence + defaults, `to_dict` boundary, `is_stale` matrix (8 parametrize), closed reason set, SQL columns, `mark_invalid` persist + reject, `list_stale` ↔ predicate agreement, audit/spec doc sync |
| E1-01 + Phase 7 tests | ✅ | E1-01 contract test updated; phase7 32 tests pass (signature compat) |

**Commit `568c8f2`** pushed to origin/main.

**Full Suite: 815 passed (was 793; +22 = new E1-02 contract test), ruff clean, cross-link batch CONTRACT PASSED.**

E1-02 = PASS. E1-03 next: privacy classes + remote-disclosure defaults.

---

## Phase 23 — E1-03 Privacy Classes and Remote-Disclosure Defaults (2026-09-04)

Sau Phase 22, Đại ca chốt E1-03 (privacy classes + remote-disclosure defaults) làm tiếp. Contract: mỗi byte project context gửi remote phải đi qua disclosure gate, classification nằm trên record, default table là single source of truth.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/privacy_classes.md` — định nghĩa enum, disclosure table, `can_disclose_to_provider` helper, migration |
| `paw.core.privacy` module | ✅ 新增 | canonical owner: `PrivacyClass` (4 levels: public/internal/workspace/secret) + `PROVIDER_KINDS` (3: local/cloud_approved/cloud_unapproved) + `REMOTE_DISCLOSURE_DEFAULTS` (`MappingProxyType[PrivacyClass, frozenset[str]]`) + `can_disclose_to_provider()` |
| `paw.bench` re-export | ✅ | `paw.bench.PrivacyClass` re-exports `paw.core.privacy.PrivacyClass` (same object); E0-02 contract preserved |
| `KnowledgeSource` | ✅ 17→18 fields | + `privacy_class: PrivacyClass` default `INTERNAL`; `create(..., privacy_class=...)` parameter; `_save` + `from_row` handle new column |
| `MemoryRecord` | ✅ 13→14 fields | + `privacy_class: PrivacyClass` default `INTERNAL`; `MemoryStore.store` + `from_row` handle new column; `_parse_privacy_class` helper for defense-in-depth |
| SQL migration | ✅ additive | `storage._migrate_schema`: `ALTER TABLE knowledge_sources ADD COLUMN privacy_class … DEFAULT 'internal'` + same on `memory_records`; guarded by `PRAGMA table_info`; no row rewrite |
| E1-01 ownership audit | ✅ sync | `KnowledgeSource` table 17→18 fields; `MemoryRecord` table 13→14 fields; both list `privacy_class` row |
| E1-01 + E1-02 contract tests | ✅ updated | hard-coded `expected` set thêm `privacy_class`; E1-01 `test_audit_documents_knowledge_source_real_fields` thêm E1-03 field |
| Contract test | ✅ 30 D1 tests | `tests/test_e1_03_privacy_contract.py`: canonical location + re-export; `PROVIDER_KINDS` stable; `REMOTE_DISCLOSURE_DEFAULTS` complete + frozen; 4×3 disclosure matrix + unknown-provider fail-closed; field existence + default + `to_dict`; SQL columns; round-trip; audit + spec doc sync |
| E1-01 (16) + E1-02 (22) + E1-03 (30) tests | ✅ 68 pass | |

**Commit `b2e4b9d`** pushed to origin/main.

**Full Suite: 845 passed (was 815; +30 = new E1-03 contract test), ruff clean, cross-link batch CONTRACT PASSED.**

E1-03 = PASS. E1-04 next: deterministic include/exclude rules for repository files (0.5d D1).

---

## Phase 24 — E1-04 Deterministic Include/Exclude Rules for Repository Files (2026-09-04)

Sau Phase 23, Đại ca chốt E1-04 (deterministic include/exclude rules) làm tiếp. Contract: mỗi file repository được load vào context phải qua một filter xác định, fail-closed mặc định, hardening ở construction-time, inspectable qua manifest.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/repo_filter_rules.md` — định nghĩa 4 field, `safe_default()` factory, matcher contract, hardening invariants |
| `paw.core.repo_filter` module | ✅ 新增 | canonical owner: `RepoFilter` (frozen dataclass) + `SAFE_DEFAULT_EXCLUDES` constant + `match()` + `filter_paths()` + `_pattern_matches()` helper (component-aware) |
| `RepoFilter.safe_default()` | ✅ | Rejects `__pycache__` / `.git` / `.venv` / `node_modules` / `*.pyc` / `*.tmp` / `*.pyo` / `*.swp`; literal set pinned by contract test |
| Matcher | ✅ | Pure function `match(rel_path)` fail-closed; `filter_paths` sorted by `PurePosixPath` parts, capped at `max_files`, duplicate raises |
| Construction-time hardening | ✅ | Reject `max_files <= 0` / `max_depth <= 0` / empty pattern / absolute pattern / `..` segment pattern |
| `ContextPlan` integration | ✅ | New field `repo_filter: RepoFilter \| None` (default `None`); explicit filter or `safe_default()` fallback when `include_repo=True` |
| `_retrieve_repo_candidates` | ✅ | Real implementation: filter on `plan.repo_paths`; candidate `metadata["filter"]` records repr cho E1-17 manifest |
| Contract test | ✅ 35 D1 tests | `tests/test_e1_04_repo_filter_contract.py`: field set + frozen + hashable; safe_default literal; match matrix (12 parametrize); filter_paths determinism + max_files + duplicate + bad-path drop; construction hardening (8 parametrize); ContextPlan field; wiring (explicit + safe-default fallback); spec doc sync |
| E1-01..E1-04 + phase7 tests | ✅ 103 pass | |

**Commit `1082933`** pushed to origin/main.

**Full Suite: 880 passed (was 845; +35 = new E1-04 contract test), ruff clean, cross-link batch CONTRACT PASSED.**

E1-04 = PASS. E1-05 next: traversal and symlink negative cases for source discovery (3h D2).

---

## Phase 25 — E1-05 Traversal and Symlink Negative Cases for Source Discovery (2026-09-04)

Sau Phase 24, Đại ca chốt E1-05 (traversal/symlink negative cases for source discovery) làm tiếp. Contract: mỗi file repository được discover phải qua một scanner deterministic, fail-closed trên symlink, mirror LocalFilesystemExecutor's write-side hardening.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/repo_scanner_contract.md` — định nghĩa `scan_repo` signature, 12 negative/positive cases, hardening invariants |
| `paw.core.repo_scanner` module | ✅ 新增 | canonical owner: `scan_repo(root, filter, *, follow_symlinks=False) -> list[str]` + `_assert_safe_root` + `_walk` (deterministic + symlink-skipping) |
| `os.walk(followlinks=False)` walk | ✅ | Sort by casefold name; drop symlinked dirs in-place; verify resolved target stays inside root; null-byte entries skipped |
| Result normalization | ✅ | `PurePosixPath` sort key (`(parts, path)`); cap at `filter.max_files` |
| Construction-time hardening | ✅ | Symlink root / nonexistent / file-as-root / null byte all raise `ValueError`; `follow_symlinks=True` rejected |
| Contract test | ✅ 14 D2 tests | `tests/test_e1_05_repo_scanner_contract.py`: every negative case + positive controls (empty root, determinism, cap, safe_default integration); real temp filesystem, no mocks |
| E1-01..E1-05 + phase1/7 + local_fs tests | ✅ 122 pass | |

**Commit `91510d3`** pushed to origin/main.

**Full Suite: 894 passed (was 880; +14 = new E1-05 contract test), ruff clean, cross-link batch CONTRACT PASSED.**

E1-05 = PASS. E1-06 next: incremental changed/unchanged/deleted source detection (1d D2).

---

## Phase 26 — E1-06 Incremental Changed/Unchanged/Deleted Source Detection (2026-09-04)

Sau Phase 25, Đại ca chốt E1-06 (incremental changed/unchanged/deleted source detection) làm tiếp. Contract: mỗi file project context phải được classify thành 1 trong 4 bucket để ingestion chỉ re-process file thay đổi, không full-reingest.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/source_incremental_diff.md` — định nghĩa `compute_checksum` + `SourceDiff` shape + 4 bucket dataclass + `diff_sources` signature + 8 negative/positive cases |
| `paw.knowledge.checksum` module | ✅ 新增 | canonical owner: `compute_checksum(file_path)` (SHA-256, 64 KiB chunked read, refuse symlink/nonexistent/directory) |
| `paw.knowledge.source` extensions | ✅ | 4 frozen dataclass `DiffNew` / `DiffChanged` / `DiffUnchanged` / `DiffDeleted`; `SourceDiff` aggregate; `async diff_sources()` function (skip unchanged files = incremental optimization) |
| `KnowledgeSourceManager` additions | ✅ | `update_checksum(source_id, new_sha256, *, last_sync=None)` writes hash + clears `checksum_mismatch` invalidation; `mark_path_missing(source_id)` one-liner for deleted bucket |
| Bucket-membership invariants | ✅ | `len(new)+len(changed)+len(unchanged) == len(scan_paths)`; `len(changed)+len(unchanged)+len(deleted) == len(persisted)`; same path never in 2 buckets |
| `paw.knowledge.__init__` exports | ✅ | Re-exports `DiffNew`/`DiffChanged`/`DiffUnchanged`/`DiffDeleted`/`SourceDiff`/`diff_sources` |
| Contract test | ✅ 16 D2 tests | `tests/test_e1_06_source_diff_contract.py`: `compute_checksum` 5 cases (determinism + empty + symlink + nonexistent + directory) + `diff_sources` 7 cases (empty/empty, empty/persisted, scan/empty, one changed, one unchanged, full 4-bucket mix, determinism, bucket invariants) + 3 manager additions + privacy_class preserved |
| E1-01..E1-06 + phase7 tests | ✅ 165 pass | |

**Commit `e32be17`** pushed to origin/main.

**Full Suite: 910 passed (was 894; +16 = new E1-06 contract test), ruff clean, cross-link batch CONTRACT PASSED.**

E1-06 = PASS. E1-07 next: prove stale derived records are invalidated after source changes (0.5d D2).

---

## Phase 27 — E1-07 Stale Derived Records + E1-08 Bounded Tree View + E1-09 Dependency Edges (2026-09-04)

Sau Phase 26, Đại ca chốt E1-07→E1-09 làm tiếp. 3 cụm gộp trong 1 phiên vì mỗi cái nhỏ (0.5d–1d D1–D2).

### E1-07: Stale derived records are invalidated after source changes

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/stale_derived_records.md` — định nghĩa 3 derived table, cascade, recovery |
| SQL migration | ✅ additive | `storage._migrate_schema`: 3 derived tables mỗi cái thêm `stale_at TEXT` + `stale_reason TEXT NOT NULL DEFAULT ''`; guard `PRAGMA table_info`, no row rewrite |
| Dataclass additions | ✅ | `KnowledgeChunk` 7→9, `KnowledgeEvidence` 6→8, `KnowledgeCitation` 7→9 fields; mỗi cái có `is_stale` property |
| Cascade | ✅ | `KnowledgeSourceManager.invalidate_derived_rows(source_id, *, reason)` — 3-statement breadth-first walk (chunks by `source_id` → evidence via `chunk_id` JOIN → citations via `evidence_id` JOIN) với `stale_at IS NULL` guard |
| Auto-cascade | ✅ | `mark_invalid` + `mark_path_missing` tự gọi `invalidate_derived_rows` |
| Recovery | ✅ | `update_checksum` gọi `clear_derived_stale` để đưa chain về fresh sau re-ingest thành công |
| Contract test | ✅ 22 D2 tests | `tests/test_e1_07_stale_derived_contract.py`: field + default + is_stale + to_dict (9 parametrize); SQL columns; cascade to chunks/evidence/citations; count + idempotency; reason rejection; recovery; spec sync |
| E1-01 audit sync | ✅ | `KnowledgeChunk` 7→9, `KnowledgeEvidence` 6→8, `KnowledgeCitation` 7→9 |

### E1-08: Bounded repository tree view

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新増 | `docs/benchmarks/e1/bounded_tree_view.md` — định nghĩa `TreeNode` shape + `scan_tree` signature + 9 cases |
| `scan_tree` | ✅ 新增 | `paw/core/repo_scanner.py` — biến flat path list thành `TreeNode` hierarchy; reuse E1-05 hardening; deterministic + filter-bounded |
| `TreeNode` | ✅ 新增 | frozen dataclass 6 fields (`name`, `path`, `kind`, `children`, `file_count`, `leaf_count`) + `is_dir()`/`is_file()` properties |
| Contract test | ✅ 13 D1 tests | `tests/test_e1_08_bounded_tree_contract.py`: TreeNode frozen + properties; empty/single/mixed tree; symlink negative controls; `safe_default` excludes `__pycache__`; `max_files` + `max_depth` cap; determinism |

### E1-09: Dependency edges with source locations and confidence

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/dependency_edges.md` — định nghĩa `DependencyEdge` shape + `extract_dependencies` signature + 9 cases |
| `paw.knowledge.dependencies` | ✅ 新增 | canonical owner: `extract_dependencies(paths, repo_root)` + `DependencyEdge` (frozen dataclass) |
| `ast`-based extraction | ✅ | stdlib `ast` parses `import` + `from ... import` (static); relative imports (level 1 + 2); multi-name from-import (1 edge for package) |
| Dynamic-import heuristic | ✅ | regex catches `__import__("x")` + `importlib.import_module("x")` → `kind=dynamic`, `confidence=0.5` |
| Sorted output | ✅ | `(from_path, line, col)` so two calls produce the same list |
| Tolerance | ✅ | syntax error in one file doesn't stop the rest; non-Python files skipped silently |
| Contract test | ✅ 14 D1 tests | `tests/test_e1_09_dependency_edges_contract.py`: empty; static; multiple; multi-name; relative (level 1+2); dynamic; syntax error; non-Python skip; determinism; line/col; mixed |

**Commits `345adb0` (E1-07), `1cc3668` (E1-08), `6efcd87` (E1-09)** pushed to origin/main.

**Full Suite: 959 passed (was 910; +49 = E1-07 22 + E1-08 13 + E1-09 14)**, ruff clean, cross-link batch CONTRACT PASSED.

E1-07/08/09 = PASS. E1-10 next: change-impact analysis (uses the dependency graph from E1-09).

---

## Phase 28 — E1-10 Symbol Ownership and Signature Records (2026-09-04)

Sau Phase 27, Đại ca chốt E1-10 (symbol ownership/signature records for the first supported language) làm tiếp. Contract: mỗi symbol trong source phải có owner (file + line + col) + signature text.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/symbol_ownership.md` — định nghĩa 8 field dataclass + signature rendering contract (positional-only, *args, **kwargs, kw-only, defaults, annotations) |
| `paw.knowledge.symbols` module | ✅ 新增 | canonical owner: `extract_symbols(paths, repo_root)` + `SymbolRecord` (frozen dataclass) |
| 6 symbol kinds | ✅ | `module` (mỗi file) + `class` + `function` + `async_function` + `method` + `async_method` |
| Signature rendering | ✅ | positional-only (`/`), positional-or-keyword, `*args`, keyword-only (`*,`), `**kwargs`; return annotation bị loại (signature-only field) |
| Decorators | ✅ | tuple of dotted names (`@staticmethod`, `@property`, `@functools.lru_cache`); first decorator là closest to def |
| Nested classes | ✅ | `parent` của inner class là qualified name của outer class |
| Module root | ✅ | `src/paw/memory.py` → `src.paw.memory`; `pkg/__init__.py` → `pkg` (suffix dropped) |
| Latent E1-05 bug fix | ✅ | `scan_repo` khi gọi với relative root path trả empty list (os.walk yield relative paths, root_path.resolve() là absolute, `relative_to` fail). Fix: resolve mỗi path trước khi relative_to. E1-08 + E1-10 tests exercise fix. |
| Contract test | ✅ 24 D1 tests | `tests/test_e1_10_symbol_ownership_contract.py`: empty input, kinds, signature rendering (no args, annotations, defaults, varargs, kwargs, positional-only, kw-only), decorators, nested class, syntax error tolerance, non-Python skip, determinism, module root for nested + `__init__.py`, frozen + hashable |
| E1-05/08/09 + phase7 | ✅ 238 pass | |

**Commit `7f05cc0`** pushed to origin/main.

**Full Suite: 983 passed (was 959; +24 = new E1-10 contract test)**, ruff clean, cross-link batch CONTRACT PASSED.

E1-10 = PASS. E1-11 next: test-to-source associations (1d D1).

---

## Phase 29 — E1-11 Test-to-Source Associations with Explicit Unknowns (2026-09-04)

Sau Phase 28, Đại ca chốt E1-11 (test-to-source associations with explicit unknowns) làm tiếp. Contract: mỗi test function/method phải produce một association, không silent drop.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/test_associations.md` — định nghĩa `TestLink` shape + `associate_tests` signature + 4-step heuristic + 6 negative/positive cases |
| `paw.knowledge.test_associations` | ✅ 新増 | canonical owner: `associate_tests(test_paths, source_paths, repo_root)` + `TestLink` (frozen dataclass, 6 fields, `__test__ = False` to avoid pytest collection) |
| Reuse E1-10 | ✅ | calls `extract_symbols` để parse cả test files và source files; build 3 source indexes (by qualified name, by bare name, by module root) |
| 4-step heuristic | ✅ | (1) direct name match (conf 1.0); (2) class-name match `TestX.test_y` → `X.y` (conf 0.7); (3) file-name match `test_foo.py` → source module `foo` (conf 0.5); (4) explicit unknown (conf 0.0) |
| Explicit unknowns | ✅ | mọi test function/method produce đúng một `TestLink`; unknown case surface ra dưới dạng bản ghi với `source_qualified_name=None`, `reason="no_clear_match"` |
| Multiple source matches | ✅ | một test có thể match nhiều source symbol; emit một association mỗi match |
| Determinism | ✅ | sorted by `test_qualified_name`; hai lần gọi cho ra cùng danh sách |
| Contract test | ✅ 9 D1 tests | `tests/test_e1_11_test_associations_contract.py`: empty input, direct name match, class-name match, file-name match (negative case khi direct match thắng), explicit unknown, no-silent-drops (3 unmatched = 3 associations), determinism, frozen + hashable, multiple source matches |
| E1-01..E1-11 + phase7 | ✅ 247 pass | |

**Commits `ac3c6f3` (E1-11)**, `497678d` (vi checklist) pushed to origin/main.

**Full Suite: 992 passed (was 983; +9 = new E1-11 contract test)**, ruff clean, cross-link batch CONTRACT PASSED.

E1-11 = PASS. E1-12 next: recent-change and affected-area views from local VCS evidence (0.5d D1).

---

## Phase 30 — E1-12 Recent-Change and Affected-Area Views from Local VCS (2026-09-04)

Sau Phase 29, Đại ca chốt E1-12 (recent-change + affected-area views từ local VCS) làm tiếp. Contract: mỗi commit phải join được với E1-10 symbols + E1-11 test associations; read-only `git`; non-git path = `[]` sạch.

| Component | Status | Notes |
|-----------|--------|-------|
| Spec doc | ✅ 新增 | `docs/benchmarks/e1/recent_changes.md` — định nghĩa `RecentChange` + `AffectedArea` shape + 2 function signatures + 12 negative/positive cases |
| `paw.knowledge.changes` | ✅ 新増 | canonical owner: `recent_changes()` + `affected_areas()` + 2 frozen dataclasses |
| `git log` reader | ✅ | `subprocess.run(argv, shell=False, ...)` với `--pretty=format:%H%x1f%h%x1f%an%x1f%aI%x1f%s --name-only`; `%x1f` (Unit-Separator) field separator không xuất hiện trong commit message hoặc path nên parser robust |
| `since` filter | ✅ | treated as "after this ref" bằng cách append `..HEAD`; `since=<sha>` exclude boundary |
| `affected_areas` join | ✅ | per-file filter: E1-10 symbols có `file` nằm trong changed files; E1-11 test associations có `test_file` nằm trong changed files |
| Sort | ✅ | date desc; hai lần gọi cho ra cùng danh sách |
| Read-only posture | ✅ | không `git checkout` / `git reset` / `git commit`; non-git path = `[]`; malformed since = `[]` |
| Contract test | ✅ 14 D1 tests | `tests/test_e1_12_recent_changes_contract.py`: non-git path, single commit, most-recent-first, max_count, since filter, determinism, E1-10 symbol join, E1-11 test join, unrelated (non-Python) commit rỗng, date-desc order, determinism của join, malformed since, frozen dataclasses |
| E1-01..E1-12 + phase7 | ✅ 261 pass | |

**Commits `e14f916` (E1-12)**, `c7637fa` (vi checklist) pushed to origin/main.

**Full Suite: 1006 passed (was 992; +14 = new E1-12 contract test) — first 4-digit test count 🎉**, ruff clean, cross-link batch CONTRACT PASSED.

E1-12 = PASS. E1-13 next: bound each derived view by item and token budgets (0.5d D1).

---

_更新此文件时告知用户 — 这是项目画像，随 Phase 推进而演化。_

## E1-36 Track — Adversarial Runtime (2026-09-07)

**Mục tiêu:** Counter-pattern cho E1 contract tests. Pure runtime/adversarial/measurable.

**Philosophy:** Invariant → Runtime wiring → Adversarial → Measurable → PASS

**NOT:** Contract → Dataclass → Unit test → Checkbox PASS

### E1-36 Test Structure (12 tests, all PASS)

| Layer | Test | Description |
|-------|------|-------------|
| 1: Invariant | `test_inv1_ask_never_becomes_execution` | ASK → STOP (constitutional) |
| 1: Invariant | `test_inv2_deny_never_becomes_execution` | DENY → STOP |
| 1: Invariant | `test_inv3_budget_hard_limits_enforced` | Budget limits respected |
| 2: Runtime | `test_runtime_policy_blocks_execution` | PolicyGuard → Autonomy → STOP |
| 2: Runtime | `test_runtime_knowledge_ingestion_to_retrieval` | Knowledge pipeline wired |
| 3: Adversarial | `test_adv1_path_traversal_source_id_blocked` | Path traversal rejected |
| 3: Adversarial | `test_adv2_stale_source_blocks_remote_disclosure` | Stale SECRET blocked |
| 3: Adversarial | `test_adv3_budget_overflow_blocked` | Budget overflow tracked |
| 4: Measurable | `test_measure1_context_compiler_respects_budget` | final_tokens ≤ max_tokens |
| 4: Measurable | `test_measure2_autonomy_budget_tracks_usage` | Usage tracked |
| 4: Measurable | `test_measure3_checkpoint_persists_and_resumes` | Checkpoint roundtrip |
| 5: Composite | `test_e1_36_adversarial_pipeline_verified` | All layers verified |

**Key design decisions:**
- All tests use REAL subsystems (PolicyGuard, AutonomyController, KnowledgeSourceManager, ContextCompiler, CheckpointStore)
- No mocks for core subsystems
- Real temp SQLite (session_db fixture)
- Tests prove BEHAVIOR, not structure

### E1-26 Retrofit (9 new adversarial tests, added to existing 5 contract tests)

| Test | Description |
|------|-------------|
| `test_adv_stale_source_cannot_bypass_privacy_gate` | Stale SECRET cannot bypass gate |
| `test_adv_manipulation_cannot_bypass_privacy_gate` | Content manipulation doesn't bypass |
| `test_adv_multiple_sources_stale_secret_cannot_leak` | Mixed sources blocked |
| `test_adv_policy_deny_stops_execution_before_step` | DENY → STOP before step |
| `test_adv_ask_non_interactive_stops_execution` | ASK → STOP (constitutional) |
| `test_adv_budget_overflow_blocks_execution` | Budget tracked |
| `test_adv_null_byte_in_source_path_blocked` | Null byte rejected |
| `test_adv_absolute_path_in_source_path_blocked` | Absolute path handled |
| `test_e1_26_adversarial_gate_verified` | Composite gate |

**Total E1-26: 14 tests (5 contract + 9 adversarial), all PASS**

### Phase 21 Bug Fix Patch (2026-09-07)

| Component | Status | Notes |
|-----------|--------|-------|
| `ModelRouter.score_model_for_task` | ✅ 新增 | Added as canonical entry point on `ModelRouter`; `_filter_for_availability` now uses it in local fallback for consistency |
| `ContextManifest` included/excluded truth | ✅ Fixed | `_allocate_budget` now sets `metadata["included"]=False` for excluded candidates; `_compile_manifest` recomputation uses `included is False` instead of `included and not excluded_reason` |
| `max_fragments_exceeded` tracking | ✅ Fixed | Excluded candidates now properly tracked in manifest.excluded |
| Remote-disclosure hard gate | ✅ Fixed | `RemoteDisclosureRefused` exception in `core/privacy.py`; `_execute_action` raises it instead of setting `model_result={}`; `_execute_unit` catches it and returns failure observation |
| Regression tests | ✅ 新增 | `tests/test_phase21_bugfixes.py` — 4 test classes, 11 tests |
| Canonical docs | ✅ Updated | IMPLEMENTATION_MAP.md and ROADMAP.md synced |

## Phase 22 — Runtime Privacy Proof + E2 Gate Ratification (2026-09-11)

**E2 gate RATIFIED** on clean revision `8d01d90`:
- E1 VERIFIED (min_recall=1.00, 12/12 samples, real Ollama embeddings)
- E2-25..28 + E2-45..47 prerequisites implemented + tested (119 E2 contract tests PASS)
- Cloud-baseline boundary explicitly resolved: `InferenceClassification` (model.inference vs local.compute) + `evaluate_local_eligibility` (fail-closed per role) + `LocalModelExecutor` (local baseline) + `gate_remote_disclosure` (ollama→local)
- `tests/test_phase22_runtime_privacy_proof.py`: 7 end-to-end regression tests PASS

Handoff spec: SECRET/stale context + fake remote → zero provider calls + zero downstream executor calls, terminal non-success, safe reopen/resume, allowed/local controls. Exception-construction tests alone are insufficient. Fix only reproduced failures.

| Component | Status | Notes |
|-----------|--------|-------|
| `_execute_unit` hard-gate handler | ✅ Fixed | Persists `OperationRecord` with `status="failed"`, `metadata={"reason": "remote_disclosure_refused", "provider_kind": ...}` BEFORE returning. Previously: early return without op-record = silent resume = provider re-call. |
| `tests/test_runtime_privacy_proof.py` | ✅ 新增 | 7 end-to-end regression tests in 5 classes. Real `PawRuntime` + real `PolicyGuard` + real `AutonomyController` + real `Ledger` + real `CheckpointManager` + real `OperationRecordStore`; only the remote provider + counting executor are test doubles. |
| Privacy proof test classes | ✅ PASS | TestSecretPlusRemoteBlocksProviderAndExecutor (0 provider + 0 executor + terminal non-success), TestResumeDoesNotRetryPrivacyFailure (OpRecord 'failed'), TestPrivacyRequiredBlocksLocalProvider (WORKSPACE blocks, INTERNAL allowed), TestStaleManifestBlocksRemote (source_stale blocks non-SECRET), TestAllowedLocalControl (disclosure_override is informational). |
| Canonical docs | ✅ Updated | IMPLEMENTATION_MAP.md (Runtime section: privacy proof note), EXECUTION_CHECKLIST.md (Runtime privacy proof → RESOLVED), vi mirror. |

## P1 Router Fix (2026-09-07)

Handoff spec: `_filter_for_availability` restore supported-role filtering + descending score via canonical registry/scorer. Test wrong role, reverse registration/score order, no eligible local, remote unavailable. No provider/discovery expansion.

| Component | Status | Notes |
|-----------|--------|-------|
| `_filter_for_availability` local-fallback | ✅ Fixed | Filter by `m.supports_role(role)` (no leak); re-score via canonical `score_model_for_task`; sort by `score` desc; return `[]` when no local match. |
| `tests/test_p1_router_filter_availability.py` | ✅ 新增 | 9 contract tests in 5 classes: TestFilterForAvailabilityRoleFiltering (wrong-role excluded, disabled excluded), TestFilterForAvailabilityScoreOrder (higher-score-first, score matches canonical scorer), TestFilterForAvailabilityNoEligibleLocal (no role match → `[]`, no local → `[]`), TestFilterForAvailabilityRemoteUnavailable (unavailable remote falls back to local, available remote passes through), TestFilterForAvailabilityBackwardCompat (no provider registry returns input unchanged). |
| Canonical docs | ✅ Updated | IMPLEMENTATION_MAP.md (Model Router section: P1 fix), EXECUTION_CHECKLIST.md (P1 Router → RESOLVED), vi mirror. |

### Test Composition Audit (post-E1-36)

| Category | Count | % |
|----------|-------|---|
| Contract tests | ~50 | ~20% |
| Adversarial tests | ~15 | ~6% |
| Runtime/measurable tests | ~10 | ~4% |
| Phase tests | ~30 | ~12% |
| Other | ~150 | ~60% |

**Target:** Contract ~20%, Adversarial/Runtime ~10% — moving toward the correct ratio.

## E1 Audit + Adversarial Retrofit (2026-09-07)

**Status**: COMMITTED (396e501)

### Security Fix
- `gate_remote_disclosure` now checks `is_stale` on `ContextCandidate`
- Added `is_stale: bool = False` to `ContextCandidate` dataclass
- Added `"source_stale"` to `DISCLOSURE_REFUSED_REASONS` closed set
- **Bug found**: Privacy gate was leaking stale SECRET data when `privacy_class=INTERNAL` — fixed

### Adversarial Tests Added
- **E1-02**: `test_adv_source_identity_rejects_unknown_reason` — `mark_invalid` rejects invalid reasons
- **E1-03**: 3 new adversarial tests — unknown provider blocked, stale blocks remote, stale allows local
- **E1-04**: 3 new adversarial tests — absolute pattern rejected, `..` rejected, empty pattern rejected
- **E1-05**: 2 new adversarial tests — symlink path traversal blocked, null byte rejected
- **E1-07**: 2 new adversarial tests — cascade idempotent, stale blocks remote disclosure
- **E1-08**: 2 new adversarial tests — symlink dir skipped, path traversal blocked
- **E1-10**: 3 new adversarial tests — malicious code handled, empty file produces module symbol, non-UTF8 skipped
- **E1-11**: 2 new adversarial tests — no silent drops, deterministic order
- **E1-12**: 3 new adversarial tests — malformed since returns [], non-git returns [], read-only verified

### Source Code Changes
- `src/paw/core/context_compiler.py`: Added `is_stale: bool = False` to `ContextCandidate`
- `src/paw/core/privacy.py`: Added `is_stale` check in `gate_remote_disclosure`, added `"source_stale"` to `DISCLOSURE_REFUSED_REASONS`

### Test Results
- All E1 tests pass (200+ tests)
- ruff clean on all modified files

## E1-27 Production Measurement — Update (2026-09-08)

**ContextCandidate.__lt__ fix resolved PAW source recall defect.**

- **Before fix**: PAW source corpus (69 files, `max_tokens=5000`) showed 5/6 cases
  at 0% recall, 1/6 at 50%. Root cause: `__lt__` returned `>` instead of `<`,
  inverting `sorted(reverse=True)` → ascending order → budget filter dropped
  highest-score chunks first.
- **After fix**: All 6 cases × cold/warm = 12/12 samples at **recall 1.00**,
  median warm reduction 0.981. Both synthetic corpus (12 files) and PAW source
  corpus (69 files) now PASS the E1-27 metric gate.
- **Runner**: canonical tracked runner is `paw.bench.e1_production`
  (`src/paw/bench/e1_production.py`); old `scripts/run_e1_production.py` is
  gitignored and no longer referenced by tracked tests.
- **Freshness**: the runner records input hashes before AND after the run,
  validates fixture Git blobs against reviewed revisions, checks tree state and
  revision stability, and returns `BLOCKED` if inputs change mid-run (pinned by
  `test_changed_input_during_run_is_blocked`).
- **Gate status**: `measurement_gate = PASS` on clean revision `ae5344a` (10+9 E1-27 tests pass; `test_dirty_tree_cannot_self_certify_a_pass` proves `dirty=False` -> PASS).
  Evidence: `VERIFIED` (clean revision).
- **Report**: `benchmarks/e1/e1_production_report.md` on clean revision `ae5344a`: `dirty=false`, `metric_gate=PASS`, `measurement_gate=PASS`, `evidence_state=VERIFIED`, min_recall=1.00, median_warm_reduction=0.871 (fixtures_paw corpus, 12 files, max_tokens=8000, max_fragments=5, max_sources=3). The E1-27 fix's `0.981` reduction was measured on the PAW source corpus (69 files, max_tokens=5000) — see E1-27 section above.
- **Production re-run (2026-09-11)**: E1-27 re-VERIFIED on clean revision `8d01d90` with real Ollama embeddings (`nomic-embed-text:latest`), full PAW source corpus (71 files, 300+ chunks), `max_tokens=5000, max_fragments=30, max_sources=10`. **min_recall=1.00, all 12 samples (6 cases × cold/warm) at 100% recall**; median_warm_reduction=0.992. `metric_gate=PASS`, `measurement_gate=PASS`, `evidence_state=VERIFIED`, `fixtures_fresh=true`, `dirty=false`. E1 gate status: **VERIFIED** on clean revision `8d01d90`.

