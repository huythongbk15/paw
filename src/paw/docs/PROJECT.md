# PAW — Personal Agent Workstation

## ⚠️ LỖI PHẢN CHỈNH — Ý tưởng ban đầu hoàn toàn sai

**CẢNH BÁO**: Ý tưởng ban đầu "Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness" là **HOÀN TOÀN SAI**.

Đây không phải là dự án "tích hợp" các hệ thống bên ngoài. PAW Core là một **Personal Agent Core độc lập**, tự xây toàn bộ infrastructure. Các hệ thống bên ngoài (QwenPaw, NotebookLM, Antigravity, DeepSeek Harness) chỉ có thể là **executor adapter** ở Phase 11+, không bao giờ là "thành phần tích hợp."

**Prompt gốc** (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`) xác nhận kiến trúc PAW Core tách biệt với mọi provider.

**Đã sửa**: 2026-08-28.

## Dự án ban đầu

**Khởi tạo:** 2026-08-27  
**Chủ sở hữu:** Đại ca  
**Trợ lý:** NAD (mã đại diện — NotebookLM + Antigravity + DeepSeek Harness là tên mã cũ, không còn ý nghĩa tích hợp)  
**Prompt gốc:** `media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`

**Note**: Tên "NAD" là viết tắt của NotebookLM + Antigravity + DeepSeek Harness — đây là tên mã của trợ lý AI, không phải statement về kiến trúc dự án. Kiến trúc thực tế: PAW Core độc lập, không tích hợp bất kỳ hệ thống nào.

## Mục tiêu sản phẩm

PAW không phải là một wrapper quanh một agent framework có sẵn.

PAW phải là một **Personal Agent Core độc lập**, có thể sử dụng các dự án bên ngoài như provider/executor nhưng không phụ thuộc chặt vào bất kỳ provider nào.

Triết lý:

1. CLI first, GUI optional.
2. Local first, cloud only when useful.
3. Cheap model first, expensive model only when justified.
4. One personal identity, many replaceable workers.
5. Task Graph first, agent swarm second.
6. Context must be selected, never blindly dumped.
7. Skills are first-class capabilities.
8. Memory records knowledge; Task Ledger records actions.
9. Every external integration must be replaceable.
10. Zero-daemon mode must be the default.

## Kiến trúc mục tiêu

```
                         USER
                          │
                        $ paw
                          │
                ┌─────────▼─────────┐
                │     PAW CORE      │
                │                   │
                │ Identity          │
                │ Session Manager   │
                │ Task Graph        │
                │ Context Builder   │
                │ Skill Fabric      │
                │ Policy Engine     │
                │ Model Router      │
                │ Capability Router │
                │ Task Ledger       │
                └─────────┬─────────┘
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
        ▼                 ▼                  ▼
      MEMORY          KNOWLEDGE          EXECUTION
        │                 │                  │
 SQLite/FTS5        LlamaIndex-like      OpenCode
 optional ReMe      components            local tools
 optional Mem0      citations             future DSH
                    evidence              future AGY
                                          future Codex
                                          future Claude
```

PAW Core sở hữu: Identity, Session, Task Graph, Context Builder, Skill Fabric, Model Router, Capability Router, Policy Engine, Task Ledger.

Các provider không được sở hữu các abstraction trên.

## Công nghệ mặc định

| Thành phần | Công nghệ |
|---|---|
| Language | Python 3.12+ |
| Models | Pydantic v2 |
| Agent | PydanticAI (nếu cần) |
| CLI | Typer |
| Database | SQLite + aiosqlite |
| Search | FTS5 |
| Concurrency | asyncio |
| Tests | pytest + pytest-asyncio |
| Linting | ruff |
| Type check | mypy/pyright |

**Không thêm nếu chưa có nhu cầu:** Redis, PostgreSQL, Kafka, Docker, Kubernetes, Qdrant, Weaviate, Celery, web server, background daemon.

## Nguyên tắc kiến trúc bắt buộc

### Provider isolation
Không import trực tiếp internal implementation của QwenPaw, OpenCode, DeepSeek Harness, Antigravity, NotebookLM vào domain layer. Mọi integration đi qua adapter/interface.

```python
class Executor(Protocol):
    async def execute(self, task: Task, context: TaskContext) -> TaskResult: ...
```

### Typed contracts
Các boundary phải dùng typed models. Object cốt lõi tối thiểu: Task, TaskResult, TaskContext, TaskPlan, TaskNode, ExecutionResult, ModelRequest, ModelSelection, CapabilityManifest, SkillManifest, MemoryRecord, Evidence, Citation, Artifact, PolicyDecision, TaskEvent.

### TaskResult contract
Tất cả executor phải normalize về cùng một structure:
```python
class TaskResult(BaseModel):
    task_id: str
    status: Literal["completed", "failed", "partial", "blocked"]
    summary: str
    artifacts: list[Artifact] = []
    decisions: list[Decision] = []
    evidence: list[Evidence] = []
    files_changed: list[str] = []
    executor: str | None = None
    model: str | None = None
    usage: Usage | None = None
    error: ErrorInfo | None = None
```

## Skill Fabric

Skills là first-class abstraction. Canonical directory: `~/.paw/skills/`

```
skill-name/
├── SKILL.md
├── references/
├── scripts/
└── tests/
```

SKILL.md metadata:
```yaml
---
name: architecture-review
description: Review software architecture and propose improvements.
metadata:
  paw/version: "1.0"
  paw/category: coding
  paw/risk: low
  paw/capabilities:
    - filesystem.read
    - git.read
    - reasoning
  paw/executors:
    - local
    - opencode
  paw/network: false
  paw/write: false
---
```

Skill Fabric hỗ trợ: discover, index, search, rank, load, validate, enable, disable, version, evaluate.

Flow: all skills → metadata index → candidate retrieval → top N → selection → lazy load.

## Memory architecture

Tách rõ:
- **Working Memory** — Current task/session only.
- **Episodic Memory** — Những gì đã xảy ra. Append-oriented.
- **Semantic Personal Memory** — Preferences, long-term facts, recurring decisions.
- **Project Knowledge** — Documentation, research, repository knowledge, evidence.

Không trộn personal facts với external knowledge.

## Knowledge Engine

Không clone NotebookLM. Chỉ xây các primitive: SOURCE → CHUNK → EVIDENCE → CLAIM → CITATION.

v0.x: SQLite, FTS5, metadata, optional embeddings.

## Capability Router

Executor không được hard-code theo kiểu `if coding: use_opencode()`.

CapabilityManifest ví dụ:
```yaml
name: opencode
capabilities:
  coding: 10
  filesystem: 9
  git: 9
  shell: 8
  architecture: 7
cost:
  compute: medium
  monetary: variable
features:
  resumable: true
  subagents: true
```

Router tính score từ: capability fit, quality requirement, task complexity, context size, privacy, permissions, latency, monetary cost, machine cost, historical success.

## Model Router

Model Router và Capability Router phải hoàn toàn tách biệt.
- Capability Router: **Ai hoặc runtime nào nên thực thi?**
- Model Router: **Model nào nên reasoning?**

Model roles tối thiểu: fast, reasoning, coding, tools, vision, embedding, fallback.

Model provider: local, Ollama, OpenRouter, direct APIs. Không hard-code vendor trong domain layer.

## Policy Engine

Policy Engine là authority duy nhất. Capability examples: filesystem.read, filesystem.write, shell.execute, network.http, git.read, git.write, process.spawn, secrets.read, destructive, financial.

Decision: ALLOW, DENY, ASK, SANDBOX.

Executor không được tự ý bypass policy.

## Task Ledger

Mỗi action đáng kể phải có event. Event types:
TASK_CREATED, PLAN_CREATED, SKILL_SELECTED, CONTEXT_BUILT, EXECUTOR_SELECTED, MODEL_SELECTED, EXECUTION_STARTED, TOOL_CALLED, ARTIFACT_CREATED, EXECUTION_COMPLETED, MEMORY_PROPOSED, MEMORY_ACCEPTED, TASK_COMPLETED.

Ledger trả lời: **What happened?**  
Memory trả lời: **What should be remembered?**

## Task Graph

Không xây multi-agent swarm trước. Task phải compile thành DAG/tree.

Mỗi node có: goal, inputs, dependencies, skills, context requirements, capability requirements, policy requirements, executor, model, result.

## Context Builder

Context Builder là critical subsystem. Mục tiêu: **minimum sufficient context**.

Sources: current user request, working conversation, personal memory, project memory, repository files, relevant skills, parent task results, research evidence, policy constraints.

Không gửi full history mặc định. Mỗi TaskContext phải giải thích được **why this context item was included**.

Mỗi context item có: source, score, reason, token estimate.

Context budget configurable: `max_context_tokens = 12000`.

## Phát triển theo phase

| Phase | Nội dung |
|---|---|
| Phase 0 | Repository Foundation — skeleton, config, logging, typed IDs, SQLite, base domain models, CLI entry point |
| Phase 1 | Minimal End-to-End Agent — task → context → local executor → TaskResult → ledger |
| Phase 2 | Skill Fabric v1 — SkillManifest, SkillRegistry, SkillLoader, SkillValidator, SkillSearch, lazy loading |
| Phase 3 | Memory v1 — working memory, episodic memory, semantic memory abstraction |
| Phase 4 | Model Router — ModelManifest, ModelRegistry, ModelRouter, fallback chain |
| Phase 5 | Executor Fabric — Executor protocol, ExecutorRegistry, CapabilityManifest, CapabilityRouter |
| Phase 6 | Policy Engine — policies (read, write, network, shell, process, destructive, secrets) |
| Phase 7 | Knowledge Engine — Source, Chunk, Evidence, Citation, KnowledgeIndex |
| Phase 8 | Context Builder — context selection, budget, explain mode |
| Phase 9 | Task Graph — TaskNode, TaskDependency, TaskGraph, TaskScheduler |
| Phase 10 | QwenPaw Compatibility — adapter cho QwenPaw skills, ReMe, persona import |
| Phase 11 | Additional Executors — DeepSeek Harness, Antigravity, Codex, Claude Code, Aider |
| Phase 12 | Evaluation System — task success, latency, token usage, monetary cost |
| Phase 13 | Skill Evaluation — skill metrics, optimizer |
| Phase 14 | Intelligent Routing — rules + weighted scoring, learned ranking |
| Phase 15 | Personal Agent v1 — kết hợp tất cả subsystem |

## Quy tắc code

Không: over-engineer, premature abstraction, add infrastructure without demonstrated need, implement speculative features, tightly couple providers, silently swallow errors, modify unrelated code, add network dependencies.

Ưu tiên: simple, typed, tested, observable, replaceable.

## Quy trình mỗi phase

Before coding: Inspect repository, summarize architecture, identify scope, identify files, define acceptance tests.

After implementation: Run unit/integration/contract/failure/security tests, lint, type checks, phase acceptance scenarios, inspect git diff, check architecture leakage, check backward compatibility.

Return: PHASE, STATUS (PASS/PARTIAL/FAIL), IMPLEMENTED, TESTS, ACCEPTANCE CRITERIA, ARCHITECTURAL DECISIONS, KNOWN LIMITATIONS, TECHNICAL DEBT, NEXT SAFE PHASE.

**Critical rule:** Khi CURRENT_PHASE hoàn thành, dừng. Report results. Phase tiếp theo phải được start explicitly.

## Architectural review gate

Tại phases 5, 8, 10, 15: đánh giá coupling, cohesion, dependency direction, provider leakage, testability, replaceability, performance, security, complexity. Nếu chất lượng kiến trúc giảm: STOP feature expansion, Refactor trước khi tiếp tục.

## Definition of success

PAW is successful khi user có thể chạy `paw` và nhận được một coherent personal agent:
- nhớ thông tin cá nhân liên quan,
- discovery & load relevant skills,
- chọn appropriate context,
- chọn appropriate model,
- chọn appropriate executor,
- research với evidence,
- execute coding/tool tasks,
- tôn trọng permissions,
- ghi lại những gì đã xảy ra,
- học long-term knowledge hữu ích,
- tránh model đắt đỏ không cần thiết,
- chạy chủ yếu từ terminal,
- độc lập với bất kỳ vendor AI/agent framework nào.

## Architecture fixes applied (2026-08-28)

Per review against original prompt spec (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`):

| Fix | Module | Status |
|---|---|---|
| Added Model Router | `paw/core/model_router.py` | ✅ ModelManifest, ModelRegistry, ModelRouter, ModelSelection |
| Added Capability Router | `paw/core/capability_router.py` | ✅ CapabilityRouter with scoring |
| Added TaskResult contract | `paw/core/models.py` | ✅ Full fields: task_id, status, summary, artifacts, decisions, evidence, files_changed, executor, model, usage, error |
| Added ModelManifest/ModelSelection | `paw/core/models.py` | ✅ |
| Added CapabilityManifest/CapabilityScore | `paw/core/models.py` | ✅ |
| Added Artifact/Decision/Evidence/Citation/Usage/ErrorInfo | `paw/core/models.py` | ✅ |
| Fixed SkillManifest to include executors field | `paw/core/skills.py` | ✅ |
| Fixed SkillManifest metadata.paw/ parsing | `paw/core/skills.py` | ✅ Supports nested metadata.paw/ structure |
| Added skill_fts virtual table | `paw/core/storage.py` | ✅ |
| Added model_registry table | `paw/core/storage.py` | ✅ |
| Added model_selections table | `paw/core/storage.py` | ✅ |
| Added executors column to skills table | `paw/core/storage.py` | ✅ |
| Removed duplicate sessions table | `paw/core/storage.py` | ✅ |
| Exported new modules from core/__init__.py | `paw/core/__init__.py` | ✅ |
| Added PolicyDecision.SANDBOX support | `paw/core/models.py` | ✅ (already existed) |