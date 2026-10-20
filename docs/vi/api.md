# Tham chiếu API PAW (Core Stabilization)

Đây là bề mặt nhỏ đã đối chiếu với mã nguồn. `paw.core` chỉ chứa runtime
contract 11 symbol; service, store và adapter phải import từ module owner cụ thể.

## Runtime

`paw.core.runtime.PawRuntime` là authority điều phối:

Mọi mode công khai đưa proposal qua cùng `_execute_unit`: Policy → Autonomy →
routing → execution → observation → operation record. `run_graph` chỉ sở hữu
dependency và node-state, không có pipeline side effect thứ hai.

- `await runtime.run(task_id, task_goal=..., step_fn=..., initial_context=None, available_skills=None, resume_from_checkpoint=None)` chạy loop có kiểu `ProposedAction` → Policy/Autonomy gate → `ExecutionObservation`;
- `await runtime.run_agent(task_id, task_goal=..., session_id=..., brain_fn=None, resume_from_checkpoint=None)` dùng context/skill/model tích hợp. Tạo runtime với `context_compiler`, `model_router`, `model_executor`. Proposer không side effect. **Routing và provider discovery diễn ra trong lúc đề xuất, trước gate** — `ModelRouter.route()` gọi `ensure_providers_ready()`, có thể khởi tạo và discover model. Gate kiểm soát *thực thi* (step function, lệnh gọi provider, side effect), không kiểm soát routing. Provider init/discovery trước gate được ghi là release blocker **F04** trong `BETA_LIMITATIONS.md`; trên đường remote, manifest được `gate_remote_disclosure` kiểm tra chưa được ràng buộc với đúng payload gửi đi — ghi là **F05**.
- `await runtime.run_graph(task_id, nodes=[...], task_goal=..., task_scheduler=..., resume_from_checkpoint=None)` chạy DAG đã validate. Node lỗi đánh dấu task failed và chặn dependent.

Kết quả là `RuntimeOutcome`. Thành công cuối có
`AutonomyDecision.STOP_SUCCESS` và `StopReason.TASK_COMPLETED`; Policy ASK/DENY
không gọi `step_fn` hoặc executor. Khi tạo với `approval_store=ApprovalStore`,
ASK ghi exact-operation request và fingerprint được approve có thể resume
proposal đó đúng một lần.

## Contract canonical

Enum và boundary dùng chung nằm trong `paw.core.models`:

```python
from paw.core.models import (
    ApprovalStatus, AutonomyDecision, Capability, ExecutionObservation,
    ExtendedTaskStatus, ProposedAction, ResourceUsage, StopReason,
)
```

`AutonomyController` (`paw.core.autonomy`) sở hữu budget/progress decision và
nhận policy verdict đã đánh giá để proposal không bị check hai lần.
`CapabilityRouter` và `ExecutorRegistry` (`paw.core.executor`) chọn tool.
`ExecutableTask` mang operation ID, idempotency key và metadata đã approve qua
executor port. `EffectIntent` là receipt trước execution dành cho executor có
external effect; runtime lưu nó trước khi invoke và gọi hook reconciliation nếu
completion commit bị ngắt.
`ContextCompiler` (`paw.core.context_compiler`) sở hữu context assembly;
`ContextBuilder` chỉ là facade tương thích.

`Planner` (`paw.core.planner`) là factory/store duy nhất cho `Plan`/`TaskNode`.
`await Planner().plan(task_id)` yêu cầu Task bền vững đã tồn tại và lấy goal/
session từ Task đó; Planner không tạo hoặc thay Task identity.
Default là research decomposition, không quyền implementation. Implementation
cần Planner cấu hình trusted `workspace_root`, `hard_constraints` structured,
`repo_filter`/`policy_guard` optional; gọi
`plan(task_id, purpose="implementation", decision_version_id=...)`. Yêu cầu
current FINAL READY, Task/session đúng, human review exact, content/constraints
fresh; ref version/revision/constraints sống qua reopen.
`ApprovalStore.request_decision_review(version_id)` tạo review pending; API
`approve`/`deny` hiện có quyết định explicit. Không auto-review; review decision
không thay executor ASK. Runtime revalidate Plan persisted ở shared unit, không
tin raw READY. Cấu hình `project_root`, `hard_constraints`, `repo_filter` optional
và PolicyGuard thật; truyền Plan persisted hoặc `metadata["plan_id"]`. Proposal
có scope read freshness trước approval effect exact. Recovery filesystem local
chỉ đối soát intent gốc, không lặp execute; private `_execute_action` mutating
không phải bypass hỗ trợ. CLI/stream write structured cần hai `/approve`: review
decision rồi approval operation. Approval đơn lẻ không cho mutation tự do báo
hoàn thành qua mock. Snapshot default có thể refuse project lớn/sâu, không tự
nâng bound; chỉ loại state PAW cấu hình, không loại mọi database.
`StructuredReasoner` (`paw.core.decomposition`) chỉ là strategy thuần. Runtime
proposer tạo `ProposedAction`; `TaskScheduler` (`paw.core.task_scheduler`) chỉ
sở hữu DAG readiness và node state.

`AdvancedSkillSelector` (`paw.core.semantic`) là implementation ranking skill
canonical. `SkillSelector` và `SemanticSkillSelector` chỉ là facade cho result
shape legacy; cả hai ủy quyền ranking và không chạy Policy. Authorization luôn
thuộc gate của proposal chính xác trong `PawRuntime`.

## Filesystem executor cục bộ

`paw.executors.filesystem.LocalFilesystemExecutor(workspace_root)` hỗ trợ
read/list/write có cấu trúc, chặn path ngoài workspace và symlink write, giới
hạn kích thước read/list và ghi qua temporary file cùng thư mục. Adapter không
sở hữu Policy/approval; `ChatService` compose nó phía sau runtime. Write intent
lưu path/mode/hash nội dung; restart công nhận final content khớp mà không ghi
lần hai và chặn trạng thái không khớp vì mơ hồ.

## Normalize knowledge/result

Dùng `paw.knowledge.normalize_knowledge_result(...)` để chuyển
`KnowledgeEvidence`, `KnowledgeChunk`, `KnowledgeCitation` đã lưu sang
`TaskResult.evidence` và `TaskResult.citations` canonical. Hàm giữ ID và source
provenance, sắp citation theo position và từ chối reference chéo bị hỏng.

## Persistence

Gọi `await paw.core.storage.db.initialize()` một lần khi process bắt đầu.
Schema và migration tập trung ở `paw.core.storage`; feature module không tự tạo
bảng. Checkpoint/idempotency dùng `CheckpointStore`, `OperationRecordStore` và
`ResumeManager` trong `paw.core.checkpoint`. Runtime commit group được điều phối
nội bộ bởi `paw.core.runtime_persistence`: operation evidence cùng commit; một
terminal checkpoint, task status và terminal ledger evidence là boundary nguyên
tử thứ hai. Executor có external effect còn dùng operation record `prepared`
trước invocation; đây là marker để reconciliation, không phải acknowledge thành
công.

## Approval bền vững

`paw.core.approval.ApprovalStore` sở hữu persistence của ASK. Các method chính là
`request`, `approve`, `deny`, `cancel`, `is_approved` và `consume`. Approval khớp
fingerprint JSON canonical đầy đủ của `ProposedAction`, không chỉ task hoặc
operation ID.

## Chat application service

`paw.application.chat.ChatService` là vertical slice cho CLI:

```python
service = ChatService(provider_mode="local", workspace_root=".")
session = await service.open()                 # hoặc open(existing_session_id)
reply = await service.send("xin chào")
status = await service.status()
history = await service.history()
plan = await service.plan()
explanation = await service.explain()
ledger = await service.ledger()
checkpoint = await service.checkpoint()
policy = await service.policy()
skills = await service.skills()
artifacts = await service.artifacts()
reply = await service.approve(execute=True)    # operation đang chờ, phải exact
reply = await service.resume()                 # resume sau restart/approval
reply = await service.cancel()
await service.close()
```

`ChatReply` báo session/task ID, status, stop reason, checkpoint, approval, model/
executor, artifact và việc context đã được compile hay chưa. Session được bind
với workspace; mở lại bằng workspace khác sẽ bị từ chối.
