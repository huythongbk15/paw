---
description: 'Đại ca quyết định build PAW Core từ 0, kiểm soát hoàn toàn — bỏ NotebookLM
  & Google Antigravity, QwenPaw/DeepSeek Harness chỉ làm Executor Adapter cho Phase
  11+. Phase 0 Foundation hoàn thành: CLI, Config, Logging, SQLite full schema, Models,
  Tests (23/23 pass), Ruff clean, 0 prohibited deps. Phase 1 Task Lifecycle E2E hoàn
  thành: Session, Task, Ledger, MockExecutor, Skill Fabric — 14 new tests, 37/37 total
  pass, zero vendor lock-in. Sẵn sàng Phase 2 — Planner + Skill Selector + Context
  Builder + Policy Guard.'
name: paw-core-phase0-complete-architecture-decision
session_id: qpsid_sha256_01ffac971663b5b0d0d19e7ec34e7e36d8cb3e4b223ce6518ceeb8794d4b790b
source_conversation: '[[mem_session/dialog/qpsid_sha256_01ffac971663b5b0d0d19e7ec34e7e36d8cb3e4b223ce6518ceeb8794d4b790b.jsonl]]'
---

## ⚠️ LỖI PHẢN CHỈNH — Ý tưởng ban đầu hoàn toàn sai

**Nhận định**: Ý tưởng ban đầu "Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness" là HOÀN TOÀN SAI. Đây không phải là dự án "tích hợp" mà là dự án XÂY PAW CORE ĐỘC LẬP.

**Sự thật theo prompt gốc** (`media/fe44a522b3c14e6f8caa22be450b4850_New_Text_Document__2_.txt`):
- PAW Core là hệ thống **độc lập**, tự xây toàn bộ core infrastructure
- QwenPaw, NotebookLM, Google Antigravity, DeepSeek Harness **không bao giờ là "thành phần tích hợp"** — chúng chỉ có thể là **executor adapter** ở Phase 11+
- Prompt spec nêu rõ: "PAW Core sở hữu: Identity, Session, Task Graph, Context Builder, Skill Fabric, Model Router, Capability Router, Policy Engine, Task Ledger"
- "Các provider không được sở hữu các abstraction trên" — provider bị cách ly hoàn toàn khỏi core
- Không import trực tiếp internal implementation của bất kỳ provider nào vào domain layer

**Cơ sở**: Prompt gốc định nghĩa kiến trúc PAW Core tách biệt với mọi provider. Không có concept "tích hợp" — chỉ có "adapter cho executor". Việc đặt tên dự án là "Tích hợp..." đã gây hiểu lầm nghiêm trọng về hướng đi kiến trúc.

**Đã sửa**: 2026-08-28. Cập nhật toàn bộ tài liệu project, memory, và PHASE3_SUMMARY.md để phản ánh đúng.

---

## Cấu hình lần đầu — NAD

- **Tên người dùng**: Đại ca (gọi là "Đại ca" / "anh")
- **Tên trợ lý**: **NAD** (NotebookLM + Antigravity + DeepSeek Harness)
- **Ngôn ngữ**: Tiếng Việt
- **Phong cách**: Thông minh, chính xác, có cấu trúc, thân thiện
- **File đã tạo**: `PROFILE.md` lưu danh tính và sở thích

## Chủ đề dự án — Đang chờ triển khai

Đại ca đề xuất thảo luận tính khả thi dự án tích hợp:
1. **QwenPaw** — (chưa rõ vai trò cụ thể)
2. **NotebookLM** — quản lý ghi chú / tài liệu
3. **Google Antigravity** — tìm kiếm / phân tích thông tin thông minh
4. **DeepSeek Harness** — suy luận sâu, logic mạnh

### Thông tin cần bổ sung trước khi phân tích
- Mục tiêu tổng thể của dự án
- Thứ tự ưu tiên thành phần (trái tim hệ thống là gì?)
- Giới hạn thực tế: API access, chi phí token, độ trễ, bảo mật, offline vs online

### Kế hoạch phân tích (đã đề xuất)
- Kiến trúc đề xuất
- Rủi ro kỹ thuật
- Lộ trình triển khai khả thi

## Trạng thái
✅ **ĐÃ CHỌT KIẾN TRÚC & HOÀN THÀNH PHASE 0 & PHASE 1** — Đại ca quyết định: **"Muốn build từ 0, kiểm soát hoàn toàn"**. Không dùng NotebookLM, không dùng Google Antigravity. QwenPaw & DeepSeek Harness chỉ là **Executor Adapter** cho Phase 11+. Trái tim hệ thống = **PAW Core** tự xây.

### 🎯 Phase 1 — Task Lifecycle E2E ✅ (2026-08-27)

| Criteria | Status |
|---|---|
| Phase 1 tests | 14/14 new ✅ |
| Total tests (Phase 0 + Phase 1) | 37/37 ✅ |
| New core modules | `session.py`, `task.py`, `ledger.py`, `executor.py`, `skills.py` ✅ |
| Zero prohibited deps | Still clean ✅ |

---

## 🎉 PHASE 0 HOÀN THÀNH — PAW FOUNDATION (2026-08-27)

Đã xây xong nền tảng **PAW Core từ con số 0** theo đúng kiến trúc PAW Spec.

### ✅ Phase 0 Acceptance Criteria — TẤT CẢ ĐẠT

| Criteria | Status |
|---|---|
| Project installs cleanly | `pip install -e .` ✅ |
| CLI launches | `paw --help`, `paw --version`, `paw doctor`, `paw init`, `paw config` ✅ |
| SQLite initializes | Full schema: tasks, task_nodes, task_events, skills, memory_records, memory_fts, knowledge_sources, knowledge_chunks, knowledge_fts, evidence, citations, identity, sessions ✅ |
| Tests pass | 23/23 ✅ |
| Ruff passes | 0 errors ✅ |
| No prohibited deps | QwenPaw, DeepSeek Harness, NotebookLM, Antigravity **vắng mặt hoàn toàn** trong `paw/core/` ✅ |

### 📁 Cấu trúc Phase 0

```
paw/
├── pyproject.toml           # deps, ruff, pytest config
├── paw/
│   ├── __init__.py          # version 0.1.0
│   ├── __main__.py          # entry point
│   ├── cli/__init__.py      # Typer CLI: help, version, doctor, init, config
│   ├── core/
│   │   ├── models.py        # Typed IDs, Enums (StrEnum), Result[T], Metadata, Identified
│   │   ├── config.py        # Pydantic Settings (PAW_HOME, DB, skills, knowledge paths)
│   │   ├── logging.py       # structlog (JSON/console, secret filtering)
│   │   └── storage.py       # aiosqlite + full schema (WAL, FK, FTS5 triggers)
│   └── tests/
│       ├── test_phase0.py   # 10 CLI integration tests
│       └── test_models.py   # 13 unit tests
```

### 🎯 Kiến trúc đã chốt (theo PAW Spec)

| Thành phần | Vai trò trong PAW | Trạng thái |
|---|---|---|
| **PAW Core** | **Trái tim** — Identity, Session, Task Graph, Context Builder, Skill Fabric, Policy Engine, Model Router, Capability Router, Task Ledger | Phase 0 foundation ✅ |
| **QwenPaw** | Executor Adapter (Phase 11+) — coding, tool calling | Chưa tích hợp (sẽ làm adapter) |
| **DeepSeek Harness** | Executor Adapter (Phase 11+) — reasoning | Chưa tích hợp (sẽ làm adapter) |
| **NotebookLM** | **KHÔNG DÙNG** — thay bằng Knowledge Engine tự xây (Phase 7) | Bỏ hoàn toàn |
| **Google Antigravity** | **KHÔNG DÙNG** — thay bằng Search Tool abstraction (Tavily/Google CSE) | Bỏ hoàn toàn |
| **Free-tier** | Local models (Ollama), SQLite, Tavily free | ✅ Sẵn sàng |

### ✅ Phase 1 HOÀN THÀNH — Task Lifecycle E2E (2026-08-27)

Đã xây xong đầy đủ lifecycle Task + Session + Ledger + Executor + Skills.

#### Các module mới tạo:

| Module | Purpose |
|--------|---------|
| `paw/core/session.py` | Session management (create, get, list, update, delete) |
| `paw/core/task.py` | Task entity + CRUD with status transitions |
| `paw/core/ledger.py` | Immutable append-only Task Ledger cho audit/debugging |
| `paw/core/executor.py` | Executor protocol + MockExecutor cho testing |
| `paw/core/skills.py` | Skill Fabric — discovery, validation, loading |

#### Tính năng chính:
- **Session + Task lifecycle**: Create session → Create task → Execute với MockExecutor → Record trong ledger → Complete
- **Task Ledger**: 16 event types cho full observability (TASK_CREATED, PLAN_CREATED, SKILL_SELECTED, EXECUTION_STARTED, TOOL_CALLED, EXECUTION_COMPLETED, MEMORY_PROPOSED, TASK_COMPLETED, ...)
- **Executor Registry**: Pluggable executors với capability matching
- **Skill Fabric**: Builtin skills (echo, datetime) + filesystem discovery từ `.md` files
- **Zero external dependencies**: Pure Python, local SQLite, không QwenPaw/DeepSeek/NotebookLM/Antigravity imports

#### Tests Passing (14 new):
```
test_session_create_and_get ✅
test_task_create_and_get ✅
test_task_status_transitions ✅
test_task_ledger_recording ✅
test_mock_executor_execution ✅
test_executor_registry ✅
test_skill_fabric_builtin ✅
test_skill_fabric_find_candidates ✅
test_full_task_lifecycle_e2e ✅
test_paw_task_help (CLI) ✅
4 prohibited dependency checks ✅
```

#### Files Modified:
- `paw/core/__init__.py` — exports all new modules
- `paw/core/storage.py` — added `error` column to tasks table, lazy DB initialization
- `paw/tests/test_phase1.py` — comprehensive Phase 1 test suite

### 🔜 Next: Phase 2 — Planner + Skill Selector + Context Builder + Policy Guard

Cần implement:
- **Planner** — phân tích mục tiêu, decompose thành tasks
- **Skill Selector** — chọn skill phù hợp cho từng task
- **Context Builder** — xây dựng context cho execution
- **Policy Guard** — kiểm tra chính sách trước khi thực thi

---

## Lịch sử quyết định quan trọng

| Thời điểm | Quyết định | Ghi chú |
|---|---|---|
| Ban đầu | **❌ Ý tưởng sai**: Đề xuất "Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness" | Không phải dự án tích hợp — phải là dự án xây PAW Core độc lập |
| 2026-08-27 | **✅ Đại ca quyết định: build từ 0, kiểm soát hoàn toàn** | Tự xây PAW Core, các hệ thống bên ngoài chỉ là executor adapter ở Phase 11+ |
| 2026-08-28 | **⚠️ Sửa lỗi**: Cập nhật toàn bộ memory và digest để phản ánh ý tưởng ban đầu là SAI | Đã sửa tất cả memory files, digest files, PROJECT.md, PHASE3_SUMMARY.md |
| 2026-08-27 | **Phase 1 — Task Lifecycle E2E hoàn thành** | 14 new tests, 37/37 total pass. Session, Task, Ledger, MockExecutor, Skill Fabric. Zero vendor lock-in. |