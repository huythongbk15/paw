# PAW — Personal Agent Workstation
## Tổng thể kiến trúc & Cấu trúc dự án

> **Cập nhật**: 2026-08-28  
> **Nhà phát triển**: Đại ca  
> **Trợ lý**: NAD  
> **Prompt gốc**: `media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`

---

## ⚠️ LỖI PHẢN CHỈNH — Ý tưởng ban đầu hoàn toàn sai

**CẢNH BÁO**: Ý tưởng ban đầu "Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness" là **HOÀN TOÀN SAI**.

Đây không phải là dự án "tích hợp" các hệ thống bên ngoài. PAW Core là một **Personal Agent Core độc lập**, tự xây toàn bộ infrastructure. Các hệ thống bên ngoài (QwenPaw, NotebookLM, Antigravity, DeepSeek Harness) chỉ có thể là **executor adapter** ở Phase 11+, không bao giờ là "thành phần tích hợp."

**Prompt gốc** xác nhận kiến trúc PAW Core tách biệt với mọi provider:
> "PAW Core sở hữu: Identity, Session, Task Graph, Context Builder, Skill Fabric, Model Router, Capability Router, Policy Engine, Task Ledger"
> "Các provider không được sở hữu các abstraction trên"

---

## Mục tiêu sản phẩm

PAW Core là **Personal Agent Core độc lập**, có thể sử dụng các provider/executor bên ngoài nhưng **không phụ thuộc chặt** vào bất kỳ provider nào.

### Triết lý (không thỏa hiệp)

1. **CLI first**, GUI optional
2. **Local first**, cloud only when useful
3. **Cheap model first**, expensive model only when justified
4. **One personal identity, many replaceable workers**
5. **Task Graph first, agent swarm second**
6. **Context must be selected, never blindly dumped**
7. **Skills are first-class capabilities**
8. **Memory records knowledge; Task Ledger records actions**
9. **Every external integration must be replaceable**
10. **Zero-daemon mode must be the default**

---

## Cấu trúc dự án mục tiêu

```
paw/
├── cli/                           # Typer CLI entry point
│   └── __init__.py               # paw: help, version, doctor, init, config, + phase commands
├── core/                          # Core domain layer — owns all abstractions
│   ├── __init__.py               # Public exports
│   ├── models/                   # Typed domain models
│   │   ├── __init__.py
│   │   ├── base.py               # ID, TimestampMixin, Identified, Metadata, Result[T]
│   │   ├── task.py               # Task, TaskStatus, TaskEventType, TaskResult
│   │   ├── memory.py             # MemoryRecord, MemoryType, MemoryQuery
│   │   ├── skill.py              # SkillManifest, SkillRisk, Capability
│   │   ├── routing.py            # ModelManifest, ModelSelection, ModelRole, CapabilityManifest
│   │   ├── policy.py             # PolicyDecision, PolicyRule, Capability
│   │   └── artifact.py           # Artifact, Decision, Evidence, Citation, Usage, ErrorInfo
│   ├── session/                  # SessionManager, Session
│   │   └── __init__.py
│   ├── tasks/                    # TaskManager, Task entity
│   │   └── __init__.py
│   ├── context/                  # ContextBuilder, TaskContext, ContextItem
│   │   └── __init__.py
│   ├── skills/                   # SkillFabric, Skill, SkillLoader, SkillValidator
│   │   └── __init__.py
│   ├── routing/                  # ModelRouter, ModelRegistry, CapabilityRouter
│   │   └── __init__.py
│   ├── policy/                   # PolicyGuard, PolicyEngine, PolicyCheckResult
│   │   └── __init__.py
│   ├── ledger/                   # TaskLedger, TaskEvent
│   │   └── __init__.py
│   ├── memory/                   # MemoryStore, MemoryRetriever, WorkingMemory, EpisodicMemory
│   │   └── __init__.py
│   ├── knowledge/                # KnowledgeEngine primitives (Phase 7+)
│   │   └── __init__.py
│   ├── config.py                 # Pydantic PawSettings
│   ├── storage.py                # aiosqlite + full schema
│   ├── logging.py                # structlog
│   └── __init__.py
├── memory/                        # Top-level memory subsystem (Working/Episodic/Semantic/Project)
├── knowledge/                     # Top-level knowledge subsystem
├── executors/                     # Executor adapters (local, opencode, etc.)
│   ├── base.py                   # Executor protocol, ExecutorRegistry
│   ├── local/                    # LocalExecutor
│   └── opencode/                 # OpenCodeExecutor (Phase 11+)
├── models/                        # Model configs/manifests
├── providers/                     # Provider adapters (QwenPaw, DSH, etc.) — Phase 10+
├── storage/                       # Database layer
├── docs/
│   ├── PROJECT.md                # This file (project overview)
│   ├── ARCHITECTURE.md           # Detailed architecture (this file)
│   └── PHASES.md                 # Phase-by-phase roadmap
├── tests/
│   ├── test_phase0.py            # Phase 0: CLI, Config, Logging, Storage, Models
│   ├── test_phase1.py            # Phase 1: Task Lifecycle E2E
│   ├── test_phase2.py            # Phase 2: Skill Fabric v1
│   ├── test_phase3.py            # Phase 3: Memory v1
│   └── ...                       # Phase 4+ as implemented
├── README.md
└── pyproject.toml
```

---

## Kiến trúc PAW Core

```
                         USER
                          │
                        $ paw
                          │
                ┌─────────▼─────────┐
                │     PAW CORE      │
                │  (domain layer)   │
                │                   │
                │ ┌───────────────┐ │
                │ │   Identity    │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │ Session Mgr   │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │  Task Graph   │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │ Context Bldr  │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │  Skill Fabric │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │ Model Router  │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │Capability Rtr │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │ Policy Engine │ │
                │ └───────────────┘ │
                │ ┌───────────────┐ │
                │ │ Task Ledger   │ │
                │ └───────────────┘ │
                └─────────┬─────────┘
                          │ Protocol/Adapter
        ┌─────────────────┼──────────────────┐
        │                 │                  │
        ▼                 ▼                  ▼
      MEMORY          KNOWLEDGE          EXECUTION
        │                 │                  │
   Working Memory    Source→Chunk     LocalExecutor
   Episodic Memory   Evidence→Cite    OpenCodeExecutor
   Semantic Personal  KnowledgeIndex  (Phase 11+: DSH, AGY, NLM)
   Project Knowledge
```

**Core rule**: Provider không được sở hữu abstraction của PAW Core. Mọi integration đi qua Protocol/adapter.

---

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Language | Python 3.12+ |
| Models | Pydantic v2 |
| CLI | Typer |
| Database | SQLite + aiosqlite |
| Search | FTS5 |
| Concurrency | asyncio |
| Tests | pytest + pytest-asyncio |
| Linting | ruff |
| Type check | mypy/pyright |

**Không thêm nếu chưa cần**: Redis, PostgreSQL, Kafka, Docker, K8s, Qdrant, Weaviate, Celery, web server, daemon.

---

## Phát triển theo Phase

| Phase | Nội dung | Status |
|---|---|---|
| **Phase 0** | Repository Foundation — CLI, Config, Logging, Storage, Models | ✅ DONE (10 tests) |
| **Phase 1** | Minimal End-to-End Agent — Session, Task, Ledger, MockExecutor, Skill Fabric | ✅ DONE (14 tests) |
| **Phase 2** | Skill Fabric v1 — discover, index, search, rank, load, validate, enable, disable, version, evaluate | ✅ DONE (25 tests) |
| **Phase 3** | Memory v1 — working memory, episodic memory, semantic memory, FTS5 search | ✅ DONE (31 tests) |
| **Phase 4** | Model Router — ModelManifest, ModelRegistry, ModelRouter, fallback chain | ⚠️ STUB — needs expansion |
| **Phase 5** | Executor Fabric — Executor protocol, ExecutorRegistry, CapabilityRouter | ⚠️ STUB — needs expansion |
| **Phase 6** | Policy Engine — policies, adversarial tests | ✅ DONE |
| **Phase 7** | Knowledge Engine — Source, Chunk, Evidence, Citation, KnowledgeIndex | ❌ NOT STARTED |
| **Phase 8** | Context Builder — context selection, budget, explain mode | ⚠️ BASIC — needs explain mode |
| **Phase 9** | Task Graph — TaskNode, TaskDependency, TaskGraph, TaskScheduler | ⚠️ BASIC — needs TaskDependency/Scheduler |
| **Phase 10** | QwenPaw Compatibility — adapter cho QwenPaw skills, ReMe, persona import | ❌ NOT STARTED |
| **Phase 11** | Additional Executors — DeepSeek Harness, Antigravity, Codex, Claude Code, Aider | ❌ NOT STARTED |
| **Phase 12** | Evaluation System — task success, latency, token usage, monetary cost | ❌ NOT STARTED |
| **Phase 13** | Skill Evaluation — skill metrics, optimizer | ❌ NOT STARTED |
| **Phase 14** | Intelligent Routing — rules + weighted scoring, learned ranking | ❌ NOT STARTED |
| **Phase 15** | Personal Agent v1 — kết hợp tất cả subsystem | ❌ NOT STARTED |
| **Phase 16-17** | Tests — contract tests, regression scenarios, security scanning | ❌ NOT STARTED |

**Total**: 93 tests pass (Phase 0: 10, Phase 1: 14, Phase 2: 25, Phase 3: 31)

---

## Quy tắc Phase

1. **Mỗi phase có acceptance criteria rõ ràng** — binary pass/fail gates
2. **Phase 0-3 Foundation** — đã hoàn thành. Core infrastructure solid.
3. **CURRENT_PHASE=<number>** — mỗi session implement một phase
4. **Do not auto-advance** — stop at current phase, report results, next phase started explicitly
5. **Architecture review gates** at phases 5, 8, 10, 15
6. **Phase gate slippage**: advancing with "mostly passing" tests undermines the whole pattern

---

## Tiêu chí Phase Gate (ví dụ)

### Phase Gate Requirements (cho mỗi phase):
- [ ] Unit tests: ≥ X new tests
- [ ] Integration tests: end-to-end scenario passes
- [ ] Contract tests: Protocol compliance verified
- [ ] Failure tests: graceful degradation confirmed
- [ ] Security scan: no prohibited dependencies
- [ ] Lint: ruff clean
- [ ] Type check: mypy/pyright pass (Phase 8+)
- [ ] Architecture review: no provider leak into core

---

## Quy trình mỗi Phase

### Before coding:
1. Inspect repository
2. Summarize architecture
3. Identify scope
4. Identify files
5. Define acceptance tests

### After implementation:
1. Run unit/integration/contract/failure/security tests
2. Run lint (ruff)
3. Run type checks (mypy/pyright)
4. Run phase acceptance scenarios
5. Inspect git diff
6. Check architecture leakage
7. Check backward compatibility

### Return format:
```
PHASE: <phase number>
STATUS: PASS/PARTIAL/FAIL
IMPLEMENTED: <list>
TESTS: <count> new, <total> total
ACCEPTANCE CRITERIA: <binary gates met>
ARCHITECTURAL DECISIONS: <key decisions>
KNOWN LIMITATIONS: <list>
TECHNICAL DEBT: <list>
NEXT SAFE PHASE: <phase number>
```

---

## Định nghĩa thành công

PAW is successful khi user có thể chạy `paw` và nhận được một coherent personal agent:
- nhớ thông tin cá nhân liên quan
- discovery & load relevant skills
- chọn appropriate context
- chọn appropriate model
- chọn appropriate executor
- research với evidence
- execute coding/tool tasks
- tôn trọng permissions
- ghi lại những gì đã xảy ra
- học long-term knowledge hữu ích
- tránh model đắt đỏ không cần thiết
- chạy chủ yếu từ terminal
- độc lập với bất kỳ vendor AI/agent framework nào