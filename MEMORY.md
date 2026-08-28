# MEMORY.md

## 偏好与决策

- Ngôn ngữ chính: tiếng Việt
- Agent identity: NAD - sự kết hợp NotebookLM + Google Antigravity + DeepSeek Harness
- Gọi người dùng: Đại ca

## 经验与教训

_（后续积累）_

## 项目与关注点

### Dự án: Tích hợp QwenPaw + NotebookLM + Google Antigravity + DeepSeek Harness
- **Ngày bắt đầu thảo luận:** 2026-08-27
- **Trạng thái:** Đang thảo luận tính khả thi
- **Mục tiêu:** Tạo một hệ thống AI trợ lý cá nhân tích hợp quản lý tri thức, tìm kiếm thông minh và suy luận sâu
- **Thách thức chính:** Tích hợp API, đồng bộ hóa ngữ cảnh, chi phí và độ trễ
- **Ghi chú:** Cần làm rõ kiến trúc tổng thể và thành phần nào sẽ đóng vai trò gì

### Dự án PAW (Personal Agent Workstation) - Phase 0 Hoàn thành
- **Ngày bắt đầu:** 2026-08-27
- **Trạng thái:** Phase 0 Foundation - HOÀN THÀNH ✅
- **Kiến trúc:** PAW Core (tự xây) + QwenPaw/DeepSeek/Search làm Executor Adapters
- **Stack:** Python 3.12, SQLite, Typer CLI, Rich, Pydantic, structlog, aiosqlite
- **Free-tier:** Local-first, zero-daemon, $0/month

### Phase 0 Acceptance Criteria - ĐẠT TẤT CẢ
- ✅ Project installs cleanly (`pip install -e .`)
- ✅ CLI launches (`paw --help`, `paw --version`, `paw doctor`, `paw init`, `paw config`)
- ✅ SQLite initializes with full schema (tasks, task_nodes, task_events, skills, memory_records, memory_fts, knowledge_sources, knowledge_chunks, knowledge_fts, evidence, citations, identity, sessions)
- ✅ Tests pass (23/23)
- ✅ Ruff passes (0 errors)
- ✅ No prohibited dependencies (QwenPaw, DeepSeek Harness, NotebookLM, Google Antigravity absent from paw/core/)