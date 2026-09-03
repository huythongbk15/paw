# Bản đồ triển khai và audit ổn định PAW

Tài liệu này ghi lại thực tế mã nguồn hiện tại, không trao trạng thái hoàn thành
dựa trên ghi chú phase lịch sử. Mỗi thay đổi ownership hoặc wiring runtime phải
cập nhật tài liệu này.

## Baseline audit

| Mục | Giá trị quan sát được |
|---|---|
| Revision | `c48a22e` trên `main` + working tree Core Stabilization |
| Source root | `src/paw/` |
| File Python runtime | 50 |
| Dòng Python runtime | 16.798 |
| Core module cấp cao | 30 |
| Dòng Python test | 11.843 |
| Hàm test | 536; đây không phải số test pass |
| File runtime lớn nhất | `runtime.py` 1.797; `model_router.py` 814; `storage.py` 792 |
| Packaging | `pyproject.toml`, setuptools, Python 3.12+ |

Working tree đã có thay đổi của người dùng khi bắt đầu audit; phần triển khai
giữ nguyên các thay đổi đó và bản đồ này mô tả cây mã nguồn kết hợp hiện tại.

## Nhật ký qualification SX

### SX-01/SX-02: ghi và phân loại working tree

Ngày ghi: 2026-09-02. Base revision:
`c48a22edc70c585f45dbabb0f1f25743e472aac7`. Cây đã ghi có 69 path thay đổi.
Tracked diff tại thời điểm ghi gồm 50 file, 3.696 dòng thêm và 2.245 dòng xóa;
path untracked có trong phân loại dưới đây nhưng không nằm trong thống kê diff.

| Owner ổn định hóa chính | Path đã ghi | Số lượng |
|---|---|---:|
| Governance SX, packaging S0 và tài liệu S6 | `.gitignore`, `AGENTS.md`, README root/package, `docs/*.md`, `docs/vi/*.md`, `tests/test_project_lock.py` | 24 |
| Contract và ownership S1 | `core/__init__.py`, `models.py`, `planner.py` (owner duy nhất sau khi loại bỏ module dual-planner cũ), `decomposition.py` mới, `selector.py`, `semantic.py`, `knowledge/__init__.py`, `knowledge/normalization.py` mới và test tương thích planning/knowledge/selector/skill | 17 |
| Storage và durability S2 | `core/storage.py`, `task.py`, `checkpoint.py`, `ledger.py`, `runtime_persistence.py` mới, `test_runtime_atomicity.py`, `test_phase1.py`, `test_phase5.py` | 8 |
| Authorization và thứ tự model call S3 | `core/model_router.py`, `providers/ollama/provider.py`, `test_phase11_ollama.py`, `test_phase14_policy_guard_v2.py`, `test_phase4.py` | 5 |
| Execution và routing độc lập S4 | `core/executor.py`, `executors/__init__.py` mới, `executors/filesystem.py` mới, `test_local_filesystem_executor.py`, `test_phase6_security.py` | 5 |
| Execution/resume thống nhất S5 | `core/runtime.py`, `test_external_effect_reconciliation.py`, `test_runtime_unit_pipeline.py`, `test_phase9.py` | 4 |
| Application slice CLI S6 | `application/chat.py`, `chat_inspection.py` mới, `chat_intents.py` mới, `cli/__init__.py`, `test_chat_cli_demo.py`, `test_cli_utf8.py` | 6 |
| User work không liên quan | Không thấy qua mục đích path/diff; đây là record phân loại, không phải quyền xóa bất kỳ thay đổi nào. | 0 |

Tổng số là 69, bao phủ mọi path từ
`git status --short --untracked-files=all` tại thời điểm ghi. Các edit sau trong
working tree này vẫn thuộc cùng candidate tới khi SX-11 đóng băng revision.

### Decision record đang hoạt động: sửa identity Task/Plan canonical

Phân loại quyết định: `STANDARD`. Readiness: `READY` chỉ cho sửa chữa cục bộ
này. Quyết định không cho phép Plan purpose E2, research readiness hoặc schema
project-revision.

- **Vấn đề:** `Planner.plan(goal, session_id, project_id)` tạo Plan ID rồi gán
  nó vào `Plan.task_id`, nên Plan đã persist không tham chiếu Task bền vững do
  `TaskManager` tạo.
- **Ràng buộc:** giữ một Planner và một Task owner; không thêm schema hoặc
  abstraction cạnh tranh; lấy goal/session từ Task bền vững; giữ nguyên user
  work trong dirty tree; không bịa Task cho Plan row legacy.
- **Bằng chứng:** `TaskManager.create()` là đường tạo Task hiện tại duy nhất;
  trong repository, chỉ test planning gọi `Planner.plan()`; node Plan và
  scheduler đã hiểu `task_id` là key Task canonical.
- **Phương án A — chọn:** bắt buộc `task_id` hiện hữu, nạp Task bền vững rồi lấy
  goal/session từ đó. Cách này bỏ input caller trùng lặp và làm Task không tồn
  tại fail trước khi ghi Plan/node.
- **Phương án B — loại:** nhận object `Task` từ caller. Dễ cho một số caller
  nhưng object có thể stale/chưa bền vững và vẫn phải lookup persistence.
- **Phương án C — loại:** giữ argument cũ rồi để Planner tạo hoặc suy ra Task.
  Cách này giữ syntax nhưng trùng ownership TaskManager và che mismatch metadata.
- **Bằng chứng ngược và chi phí tương thích:** phương án A cố ý phá call
  signature Planner cũ vốn không public. Plan row legacy có thể vẫn mang shape
  lịch sử `plan.id == task_id`; repair này vẫn đọc được nhưng không rewrite/xóa
  chúng. Migration/disposition được review riêng trong SX-10.
- **Budget và điều kiện dừng nghiên cứu:** chỉ dùng source, schema, test và mọi
  caller trong repository; dừng khi đã localize owner, call graph, persistence
  path và negative case. Nghiên cứu ngoài không thể đổi contract identity do PAW
  sở hữu.
- **Nghiệm thu bác bỏ được:** Task không tồn tại không tạo row Plan/node; Plan
  mới có `plan.id != plan.task_id == task.id`; mọi node giữ Task ID đó; goal/
  session lấy từ Task; close/reopen giữ quan hệ; không thêm Planner/Task factory.

## Hướng tiếp theo đã ghi nhận — chưa triển khai

Quyết định sản phẩm ngày 2026-09-01 thu hẹp PAW vào code, hệ thống và kiến trúc
phần mềm. Phía local sở hữu durable control, project context, memory, retrieval,
verification và inference hẹp đã đánh giá; suy luận khó hoặc mới được dành cho
cloud đã qua gate. Quyết định cũng đặt thích nghi memory/context và vòng đời
personal skill có quản trị trước mọi training model local, đồng thời bắt buộc
cắt bỏ feature và có benchmark trước khi mở rộng. Trước triển khai, loop đích
nghiên cứu có giới hạn, ghi phương án có nguồn và tạo readiness decision có kiểu.

Mục này chỉ ghi hướng đích. Source hiện tại chưa triển khai benchmark hậu gate,
context manifest, escalation đã đánh giá, vòng đời candidate/replay/promotion
cho personal skill hoặc training pipeline. Source cũng chưa có research
decision artifact hoặc gate `ImplementationReadiness`; tài liệu không đánh dấu
các phần này là `OBSERVED` hay `VERIFIED`. Core Stabilization vẫn là track triển
khai duy nhất đang hoạt động.

### Khoảng trống bằng chứng trước triển khai

Planner hiện tại phân rã ngay goal được cung cấp rồi lưu `Plan`.
`StructuredReasoner` là strategy keyword/template xác định; nó không đọc bằng
chứng dự án, so sánh phương án hoặc xác lập readiness. Với decomposition ghi
file hiện tại, task graph được tạo có thể chứa action `filesystem.write` trước
khi có quyết định nghiên cứu dựa trên nguồn.

Vì vậy source chưa có decision artifact canonical, độ sâu nghiên cứu, record
bằng chứng ngược, so sánh phương án hoặc readiness outcome có kiểu. Đây là
khoảng trống sản phẩm hậu gate đã được phê duyệt, không phải safety failure S0–S6
mới phát hiện. Phần sửa phải mở rộng boundary runtime/Planner/Knowledge/Context
hiện có; không được tạo research planner hoặc store cạnh tranh.

### Audit boundary đã làm rõ

Làm rõ kiến trúc cho thấy các sự thật source sau. Đây không phải claim rằng đích
hậu gate đã được triển khai:

| Boundary | Thực tế source hiện tại | Hướng xử lý bắt buộc |
|---|---|---|
| Identity Task/Plan | `Planner.plan(task_id)` giờ yêu cầu Task bền vững hiện hữu, lấy goal/session từ Task, persist Plan ID riêng và gán Task ID canonical cho mọi node. Task không tồn tại fail trước khi ghi Plan/node. | Repair identity SX hiện tại có proof close/reopen. Project revision, constraint fingerprint và migration/disposition row legacy là việc E2/SX-10 riêng. |
| Purpose công việc | `Plan`/`TaskNode` chưa có purpose research/spike/implementation có kiểu. | Mở rộng Plan hiện có bằng `PlanPurpose`; không thêm `ResearchTask`. |
| Lifecycle decision | Chưa có decision-artifact store, record state, constraint fingerprint hoặc transition staleness. | E2 sở hữu lifecycle versioned `DRAFT`/`FINAL`/`STALE`/`SUPERSEDED` qua schema tập trung. |
| Engineering verification | `ExecutionObservation.success` và `TaskResult.status` báo state execution/result; chưa có `VerificationSpec` khai báo trước hoặc `VerificationRecord` bền vững. | E0 định nghĩa evaluation contract; E2 tích hợp operation verification đã gate. Observation không tự tạo verified trace. |
| Escalation | Có `AutonomyDecision.ESCALATE`, nhưng controller chưa có routing assessment đích để phát và runtime xử lý như stopped outcome. `ModelRouter.route()` có thể initialize/discover provider, dù execution path hiện gọi nó sau proposal gate. | E2 làm escalation non-terminal; selection trước proposal chỉ dùng cache, mọi provider discovery là operation riêng đã gate. |
| Governance skill | `SkillFabric` là registry runtime; manifest có `enabled`, schema có `skill_registry`, nhưng chưa owner nào dùng nó cho transition candidate/review/activation. | E3 mở rộng SkillFabric và persistence tập trung; không tạo registry thứ hai hoặc suy trust từ `enabled`. |
| Tenancy | Task có scope project/session nhưng không có contract tenant/authentication/isolation. | Đây là chủ ý tới BETA: single-user local authority; multi-user là product decision riêng. |
| Bootstrap benchmark | Roadmap yêu cầu fixture do người review nhưng E0 runner/evaluation record chưa triển khai. | E0 phải đánh giá runtime hiện tại độc lập E1–E3, phá vòng benchmark/trace/skill tưởng tượng. |

Mismatch identity Task/Plan là dòng duy nhất cần sửa behavior SX hiện tại. Các
dòng khác là gap hậu gate tường minh và không hồi tố mở rộng completion scenario
S0–S6.

### Baseline verification đã ghi — không phải proof exit hiện tại

Môi trường project-only là `.venv`, tái lập từ `pyproject.toml` và `uv.lock`
bằng `uv sync --locked --extra dev`. Evidence D3 dưới đây được ghi trên dirty
working tree Core Stabilization trước delta tài liệu/contract-test mới nhất. Nó
hỗ trợ audit implementation nhưng không tạo trạng thái `VERIFIED` cho một clean
candidate đã đóng băng:

- `.venv/bin/python -m pytest -q`: **543 passed trong 303,33 giây** trên working
  tree đó, gồm proof
  normalization, prepared-effect reconciliation, unit-pipeline, filesystem,
  selector ownership, lock/ownership và CLI process;
- nhóm compatibility/ownership selector tập trung: **69 passed trong 46,45
  giây**. Nhóm knowledge/runtime/filesystem/atomicity trước đó **116 passed**;
  toàn bộ cũng nằm trong lượt full 543 test cuối;
- `uv run ruff check .`: pass;
- `uv build --wheel` tạo `paw-0.1.0-py3-none-any.whl`; virtualenv sạch cài được
  wheel. Ngoài repository, `--version`, `--help`, `init`, `doctor` và một JSON
  chat turn xác định đều pass. Package đã cài export đúng 11 symbol `paw.core`
  và import được decomposition/transaction coordinator mới;
- staging setuptools bị ignore đã được dọn trước build cuối; kiểm tra wheel có
  `decomposition.py`, `runtime_persistence.py`, `knowledge/normalization.py` và
  không còn module planner cũ;
- `uv lock --check`, regression cho lock contract và locked sync đều pass;
  snapshot freeze của host đã được xóa.
- Sau delta tài liệu/status research,
  `.venv/bin/python -m pytest -q tests/test_project_lock.py` pass **5 test** và
  Ruff tập trung pass. Đây là check contract tài liệu D0/D1, không thay SX-12.
- Repair Task/Plan được tái hiện bằng hai contract test fail, sau đó working tree
  hiện tại chạy
  `.venv/bin/python -m pytest -q tests/test_planning_contract.py tests/test_phase2.py tests/test_phase3.py`:
  **61 passed trong 45,75 giây**. Đây là evidence identity/persistence tập trung,
  không phải kết quả SX-12 trên revision sạch.

## Bản đồ component

| Khái niệm | Triển khai hiện tại | Dùng trong runtime | Trạng thái và khoảng trống |
|---|---|---|---|
| Identity | `core/identity/__init__.py`: `Identity`, `IdentityManager` | Primitive preference PAW-owned độc lập; không inject vào execution loop | `PASS` cho typed/local store. Compose persona vào runtime được defer theo product change test vì không core scenario nào cần. |
| Session | `core/session.py`; projection chat trong `application/chat.py` | `ChatService` tạo/nạp trước mỗi task | `PASS` cho lifecycle chat và transcript bền vững. |
| Task | `core/task.py`; contract nền trong `core/models.py` | Runtime nhận `task_id`; ChatService tạo từng turn | `PASS` cho lifecycle runtime/CLI. |
| Plan | `core/planner.py`: `Plan`, `TaskNode`, `Planner` canonical; strategy thuần ở `core/decomposition.py` | Application/library gọi tường minh trước `run_graph` | `PASS` cho identity Task/Plan hiện tại, sole owner và write mới atomic: Planner yêu cầu Task bền vững và giữ Plan ID riêng. Disposition row legacy chờ SX-10; project revision, purpose và readiness vẫn là việc hậu gate. |
| Task Graph | `core/planner.py: TaskNode`; `core/task_scheduler.py` | `PawRuntime.run_graph` | `PASS` cho DAG, cycle, failure propagation và checkpoint resume. |
| Skill Fabric | `core/skills.py`; selector ở `selector.py`/`semantic.py` | Compiler retrieve, proposer chọn, executor thực thi | `PASS` cho registry/selection runtime hiện tại; lifecycle state, version bất biến và activation đã review hậu gate chưa có. |
| Context | `core/context.py`; `context_compiler.py` | Compiler dùng ở agent/graph | `PASS`; `ContextBuilder` là facade mỏng, không có thuật toán lắp ráp thứ hai. |
| Memory | `core/memory.py`, `core/embeddings.py` | `ContextCompiler` dùng `AdvancedMemoryRetriever` | `PASS` cho product slice: lexical fallback, hybrid ranking có kiểm soát, embedding lưu bền vững, compiler integration và stress 100 memory trên SQLite thật đều có test. |
| Knowledge | record lưu trong `knowledge/source.py`, `chunk.py`, `evidence.py`, `citation.py`, `index.py`; boundary ở `knowledge/normalization.py` | Compiler lấy candidate; caller normalize record được chọn sang `TaskResult` | `PASS` cho ownership: persistence type tách khỏi result type, một normalizer nghiêm ngặt giữ provenance. |
| Policy | `core/policy.py`; approval ở `core/approval.py` | `_gate_action` rồi `AutonomyController` | `PASS`; một verdict, DENY không chạy, ASK chỉ resume exact proposal. |
| Autonomy | `core/autonomy.py`; detector/profile tương ứng | Tất cả runtime path | `PASS` cho accounting budget/continue/stop hiện tại. Protocol assessment/reroute `ESCALATE` hậu gate chưa có và runtime hiện coi enum này là stopped outcome. |
| Capability Router | `core/executor.py`: `CapabilityRouter`, `ExecutorRegistry` | `PawRuntime._execute_action` | `PASS`; action nào cũng chọn executor tương thích trước invoke. |
| Executor | port/registry và `EffectIntent` ở `core/executor.py`; adapter file ở `executors/filesystem.py` | `_execute_action` invoke hoặc reconcile executor đã chọn | `PASS` cho adapter built-in; write prepare intent bền vững và restart không replay mù effect. |
| Model Router | `core/model_router.py`; provider registry | Execution stage sau gate | `PASS` cho gate ordering hiện tại. Escalation hậu gate cần selection cached không side effect; live init/discovery không được ẩn trước proposal gate mới. |
| Ledger | `core/ledger.py`; coordinator ở `core/runtime_persistence.py` | Dùng xuyên runtime | `PASS`; observation/artifact/execution event và operation record commit cùng nhau; terminal task/checkpoint/event rollback cùng nhau. |
| Checkpoint/Resume | `core/checkpoint.py` | Các mode restore state; restart executor đọc prepared effect | `PASS` cho checkpoint atomic, state/idempotency restore và filesystem reconciliation sau close/reopen. |
| Storage | `core/storage.py`; transaction group ở `core/runtime_persistence.py` | Dùng chung hầu hết service | `PASS` cho DDL tập trung, migration không phá dữ liệu và multi-record boundary tường minh. |
| Runtime | `core/runtime.py`: `run`, `run_agent`, `run_graph`, `_execute_unit` | Authority tích hợp | `PASS` cho executable proposal pipeline hiện tại. Decision admission, escalation non-terminal và derivation `VerificationRecord` hậu gate chưa có. |
| CLI | `cli/__init__.py`; `application/chat.py` điều phối; `application/chat_intents.py` và `chat_inspection.py` tạo projection quyết định | Gọi cùng agent runtime canonical | `PASS` cho lifecycle và plan/why/ledger/checkpoint/policy/skills/artifact inspect. |
| Filesystem adapter | `executors/filesystem.py` | `ChatService` compose bằng registry riêng | `PASS` cho containment, exact approval, atomic write, effect-intent hash, restart reconciliation và chặn trạng thái mơ hồ. |

## Contract cạnh tranh hoặc trùng lặp

| Khái niệm | Định nghĩa | Độ lệch |
|---|---|---|
| `AutonomyDecision` | `core/models.py`, re-export từ `core/autonomy.py` | Một enum canonical, có `STOP_SUCCESS`. |
| `StopReason` | `core/models.py`, re-export từ autonomy/policy | Một bộ giá trị canonical. |
| `ExtendedTaskStatus` | `core/models.py`, re-export từ checkpoint | Một bộ giá trị canonical. |
| Approval lifecycle | `ApprovalStatus` và `core/approval.py` | Một fingerprint exact-operation và owner transition. |
| `ExecutableTask` | `core/executor.py`, re-export từ `executor_policy.py` | Một dataclass wrapper canonical. |
| Context assembly | `ContextCompiler`; `ContextBuilder` facade | Builder ủy quyền Compiler, không retrieve lần hai. |
| Skill selection | `AdvancedSkillSelector` canonical; `SkillSelector` và `SemanticSkillSelector` tương thích | Một owner ranking lexical/semantic. API legacy chỉ delegate/đổi shape, không gọi Policy; chỉ xóa ở major release sau migrate caller. |
| Planning | `Planner`; `StructuredReasoner` thuần; runtime proposer; `TaskScheduler` | Đã tách rõ tạo/lưu Plan, đề xuất action và DAG readiness/state. |
| Evidence/Citation | result model trong `core/models.py`, stored record trong `paw.knowledge`, boundary ở `knowledge/normalization.py` | `normalize_knowledge_result()` map source/provenance, sắp citation và từ chối link hỏng. |

`core/__init__.py` chỉ export 11 symbol của runtime contract. Planner, scheduler,
store, adapter và helper tương thích phải import từ module sở hữu; contract test
giữ cố định surface này.

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
5. `RuntimePersistence` commit nguyên tử evidence của operation và, ở boundary
   riêng, checkpoint/task-status/terminal evidence. Failure injection sau từng
   loại write chứng minh rollback sau đóng-mở database thật.
6. Write filesystem lưu `EffectIntent` và record `prepared` trước execution.
   Restart xác nhận final content khớp mà không gọi executor lần hai; mismatch
   trả ambiguous và không ghi đè.

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
| Core consistency | `PASS` cho slice identity/ownership S1 đã kiểm tra | Enum canonical và facade tương thích có một owner; Planner giờ yêu cầu Task ID bền vững, dùng Plan ID riêng và persist node theo Task identity. Review SX còn lại vẫn có thể tìm ra finding riêng. |
| Policy safety | `PASS` cho thứ tự gate runtime | Provider/model và executor chỉ chạy sau verdict; ASK/DENY không chạy. |
| Context quality | `PASS` | Full suite có stress 100 memory/100 knowledge/50 skill và budget/explain. |
| Autonomy | `PASS` cho accounting đã sửa | Decision canonical, usage restore, không double count. |
| Durable runtime | `PASS` cho transition cục bộ và filesystem effect built-in | Atomic rollback đã test; prepared effect được reconcile sau close/reopen không lặp, mismatch bị chặn. |
| Task Graph | `PASS` cho semantics đã sửa | Node lỗi dừng graph/dependent; cycle vẫn bị từ chối. |
| Packaging | `PASS` | Wheel build, isolated install, import và CLI smoke pass. |
| Regression | `PARTIAL` cho exit evidence | Repair Task/Plan có proof persistence/caller tập trung 61 test hiện tại. Lượt D3 543 test thuộc dirty tree trước và SX-12 chưa chạy trên clean candidate. |

Trạng thái tổng thể: **`PARTIAL`**. Các sửa normalization, gate, atomicity,
graph, crash-window filesystem và identity Task/Plan đã được quan sát và có
evidence tập trung hoặc working-tree trước đó. SX-04 tới SX-10 vẫn cần review;
sau đó clean candidate cần release check SX-12 trước mọi claim Core
Stabilization `PASS`.

## Các mục tiêu sửa tiếp theo

1. Làm SX-04 tới SX-09 cho schema, gate ordering, unit pipeline, durability,
   filesystem reconciliation và tài liệu CLI/API.
2. Trong SX-10, sửa mọi finding phát sinh và quyết định cách phát hiện hoặc
   migrate Plan row legacy trước repair mà không dùng destructive initialization.
3. Đóng băng một revision sạch và chạy SX-12 tới SX-14; chỉ exit decision pass
   mới unblock E0.
