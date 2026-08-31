# Bản đồ triển khai và audit ổn định PAW

Tài liệu này ghi lại thực tế mã nguồn hiện tại, không trao trạng thái hoàn thành
dựa trên ghi chú phase lịch sử. Mỗi thay đổi ownership hoặc wiring runtime phải
cập nhật tài liệu này.

## Baseline audit

| Mục | Giá trị quan sát được |
|---|---|
| Revision | `ffdd017` trên `main` + working tree Core Stabilization |
| Source root | `src/paw/` |
| File Python runtime | 44 |
| Dòng Python runtime | 15.774 |
| Core module cấp cao | 28 |
| Dòng Python test | 10.489 |
| Hàm test | 507; đây không phải số test pass |
| File runtime lớn nhất | `runtime.py` 1.659; `model_router.py` 789; `context_compiler.py` 758 |
| Packaging | `pyproject.toml`, setuptools, Python 3.12+ |

Working tree sạch ở thời điểm bắt đầu audit.

### Bằng chứng kiểm chứng

Môi trường project-only là `.venv`, tạo từ `pyproject.toml` bằng
`uv sync --extra dev` sau khi được cho phép. Kết quả revision hiện tại:

- `.venv/bin/python -m pytest -q`: **514 passed trong 270,53 giây**, gồm suite
  8 test chat/approval/process boundary;
- policy/runtime/chat regression tập trung: 47 passed;
- `.venv/bin/python -m ruff check .`: pass;
- `uv build --wheel` tạo `paw-0.1.0-py3-none-any.whl`; virtualenv sạch cài được
  wheel và chạy `paw --version`, `paw init`, `paw chat --message ... --json`
  ngoài repository;
- `requirements.lock.txt` vẫn là snapshot môi trường host, không phải project lock.

## Bản đồ component

| Khái niệm | Triển khai hiện tại | Dùng trong runtime | Trạng thái và khoảng trống |
|---|---|---|---|
| Identity | `core/identity/__init__.py`: `Identity`, `IdentityManager` | Chưa nằm trong loop chính | `OBSERVED`; có key/value service bền vững nhưng chưa ghép vào `PawRuntime`. |
| Session | `core/session.py`; projection chat trong `application/chat.py` | `ChatService` tạo/nạp trước mỗi task | `PASS` cho lifecycle chat và transcript bền vững. |
| Task | `core/task.py`; contract nền trong `core/models.py` | Runtime nhận `task_id`; ChatService tạo từng turn | `PASS` cho lifecycle runtime/CLI. |
| Plan | `core/planner.py`; `core/intelligent_planner.py` | Chưa wire vào `run_agent` | `PARTIAL`; có nhiều planning path, chưa có planner canonical. |
| Task Graph | `core/planner.py: TaskNode`; `core/task_scheduler.py` | `PawRuntime.run_graph` | `PASS` cho DAG, cycle, failure propagation và checkpoint resume. |
| Skill Fabric | `core/skills.py`; selector ở `selector.py`/`semantic.py` | Compiler retrieve, proposer chọn, executor thực thi | `PASS` cho runtime path; layered selector cần tiếp tục chuẩn hóa. |
| Context | `core/context.py`; `context_compiler.py` | Compiler dùng ở agent/graph | `PASS`; `ContextBuilder` là facade mỏng, không có thuật toán lắp ráp thứ hai. |
| Memory | `core/memory.py`, `core/embeddings.py` | `ContextCompiler` dùng retriever | `OBSERVED`; đường lexical/embedding có nhưng stress/restart chưa xác minh đầy đủ. |
| Knowledge | `knowledge/source.py`, `chunk.py`, `evidence.py`, `citation.py`, `index.py` | Compiler lấy candidate | `OBSERVED`; còn boundary trùng với Evidence/Citation ở result model. |
| Policy | `core/policy.py`; approval ở `core/approval.py` | `_gate_action` rồi `AutonomyController` | `PASS`; một verdict, DENY không chạy, ASK chỉ resume exact proposal. |
| Autonomy | `core/autonomy.py`; detector/profile tương ứng | Tất cả runtime path | `PASS` cho decision canonical và accounting restore. |
| Capability Router | `core/executor.py`: `CapabilityRouter`, `ExecutorRegistry` | `PawRuntime._execute_action` | `PASS`; action nào cũng chọn executor tương thích trước invoke. |
| Executor | `core/executor.py`; model provider ở `core/model_executor.py` | `_execute_action` invoke executor | `PASS` cho contract registry; skill body không tự tạo success. |
| Model Router | `core/model_router.py`; provider registry | Execution stage sau gate | `PASS`; một route/call ở execution stage được ghi nhận. |
| Ledger | `core/ledger.py`: `TaskLedger` và typed event | Dùng xuyên runtime | `OBSERVED`; atomicity hoàn toàn với checkpoint/operation còn cần chứng minh thêm. |
| Checkpoint/Resume | `core/checkpoint.py` | `run`/`run_agent`/`run_graph` restore | `PASS` cho store commit, autonomy/context restore và idempotency ổn định. |
| Storage | `core/storage.py` | Dùng chung hầu hết service | `PASS` cho DDL tập trung, migration không phá dữ liệu. |
| Runtime | `core/runtime.py`: `run`, `run_agent`, `run_graph` | Authority tích hợp | `PASS` cho core path đã sửa; graph vẫn là node loop riêng chờ hợp nhất. |
| CLI | `cli/__init__.py` và `application/chat.py` | Gọi cùng agent runtime canonical | `PASS` cho demo offline: history/status, approve/resume/cancel, JSON. Executor thật ngoài scope. |

## Contract cạnh tranh hoặc trùng lặp

| Khái niệm | Định nghĩa | Độ lệch |
|---|---|---|
| `AutonomyDecision` | `core/models.py`, re-export từ `core/autonomy.py` | Một enum canonical, có `STOP_SUCCESS`. |
| `StopReason` | `core/models.py`, re-export từ autonomy/policy | Một bộ giá trị canonical. |
| `ExtendedTaskStatus` | `core/models.py`, re-export từ checkpoint | Một bộ giá trị canonical. |
| Approval lifecycle | `ApprovalStatus` và `core/approval.py` | Một fingerprint exact-operation và owner transition. |
| `ExecutableTask` | `core/executor.py`, re-export từ `executor_policy.py` | Một dataclass wrapper canonical. |
| Context assembly | `ContextCompiler`; `ContextBuilder` facade | Builder ủy quyền Compiler, không retrieve lần hai. |
| Skill selection | `SkillSelector`, `SemanticSkillSelector`, `AdvancedSkillSelector` | Cần tiếp tục mô tả rõ layered call path. |
| Planning | `Planner`, `IntelligentPlanner`, `TaskScheduler`, runtime proposer | Decomposition/proposal/scheduling còn chồng ownership. |
| Evidence/Citation | result model trong `core/models.py` và stored model trong `paw.knowledge` | Cần boundary normalize rõ hơn. |

`core/__init__.py` vẫn re-export surface rộng, gồm cả type cũ và type thay thế;
đây là rủi ro coupling ngoài ý muốn.

## Đánh giá các vấn đề runtime

### Safety và authorization — đã sửa

1. `AgentActionProposer.propose()` không side effect; route/inference chỉ ở
   `_execute_action()` sau gate.
2. `_gate_action()` truyền một policy verdict vào Autonomy, không kiểm tra kép.
3. `ExecutorPolicyEnforcer.enforce()` coi ASK là quyết định không thực thi.

### Durability và resume — đã sửa

1. DDL runtime tập trung; checkpoint/operation dùng schema canonical.
2. Resume khớp operation ID đã hoàn tất và bỏ qua không chạy lại gate/executor.
3. Autonomy usage/decision và graph node status được restore.
4. Graph node ID là idempotency key ổn định qua restart.

### Execution và graph — đã sửa phần chính

1. `CapabilityRouter` và `ExecutorRegistry` nằm trong `_execute_action()`.
2. Nạp skill body chỉ là context; executor tương thích mới được trả success.
3. Observation lỗi đánh dấu node/task failed và return ngay; dependent không chạy.
4. Graph vẫn là loop node riêng nhưng dùng cùng policy/autonomy/executor/checkpoint boundary.

### Storage ownership — đã sửa

1. Runtime DDL tập trung ở `core/storage.py`; feature helper chỉ gọi `db.initialize()`.
2. `ensure_task_scheduler_tables()` không phá dữ liệu.
3. Mutation legacy commit an toàn khi không có explicit transaction.

## Kết luận gate

| Gate | Trạng thái | Bằng chứng |
|---|---|---|
| Core consistency | `PASS` cho contract/storage đã sửa | Enum canonical, facade tương thích, schema tập trung, router được wire. |
| Policy safety | `PASS` cho thứ tự gate runtime | Provider/model và executor chỉ chạy sau verdict; ASK/DENY không chạy. |
| Context quality | `PASS` | Full suite có stress 100 memory/100 knowledge/50 skill và budget/explain. |
| Autonomy | `PASS` cho accounting đã sửa | Decision canonical, usage restore, không double count. |
| Durable runtime | `PASS` cho store/resume | Checkpoint/operation commit; agent/graph restore và skip operation xong. |
| Task Graph | `PASS` cho semantics đã sửa | Node lỗi dừng graph/dependent; cycle vẫn bị từ chối. |
| Packaging | `PASS` | Wheel build, isolated install, import và CLI smoke pass. |
| Regression | `PASS` cho kiểm tra hiện tại | 514 test, regression tập trung và ruff xanh. |

Trạng thái tổng thể: **Core Stabilization đã sửa; CLI demo slice đã kiểm chứng**.
Khoảng trống còn lại là hợp nhất graph-node loop và executor thật ngoài mock; cả
hai không bị che giấu sau nhãn demo.

## Hai mục tiêu sửa tiếp theo

1. Đưa graph node qua cùng executable-unit implementation với single task nhưng
   không đổi semantics an toàn.
2. Chỉ định nghĩa real executor adapter hẹp sau exit gate; mock offline vẫn phải
   được ghi rõ là stand-in của demo.
