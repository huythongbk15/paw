# Tham chiếu API PAW (Core Stabilization)

Đây là bề mặt nhỏ đã đối chiếu với mã nguồn. Hãy import từ module cụ thể; việc
re-export rộng qua `paw.core` chỉ để tương thích.

## Runtime

`paw.core.runtime.PawRuntime` là authority điều phối:

- `await runtime.run(task_id, task_goal=..., step_fn=..., initial_context=None, available_skills=None, resume_from_checkpoint=None)` chạy loop có kiểu `ProposedAction` → Policy/Autonomy gate → `ExecutionObservation`;
- `await runtime.run_agent(task_id, task_goal=..., session_id=..., brain_fn=None, resume_from_checkpoint=None)` dùng context/skill/model tích hợp. Tạo runtime với `context_compiler`, `model_router`, `model_executor`. Proposer không side effect; route và inference chỉ sau gate;
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
`ContextCompiler` (`paw.core.context_compiler`) sở hữu context assembly;
`ContextBuilder` chỉ là facade tương thích.

## Persistence

Gọi `await paw.core.storage.db.initialize()` một lần khi process bắt đầu.
Schema và migration tập trung ở `paw.core.storage`; feature module không tự tạo
bảng. Checkpoint/idempotency dùng `CheckpointStore`, `OperationRecordStore` và
`ResumeManager` trong `paw.core.checkpoint`.

## Approval bền vững

`paw.core.approval.ApprovalStore` sở hữu persistence của ASK. Các method chính là
`request`, `approve`, `deny`, `cancel`, `is_approved` và `consume`. Approval khớp
fingerprint JSON canonical đầy đủ của `ProposedAction`, không chỉ task hoặc
operation ID.

## Chat application service

`paw.application.chat.ChatService` là vertical slice cho CLI:

```python
service = ChatService(provider_mode="local")
session = await service.open()                 # hoặc open(existing_session_id)
reply = await service.send("xin chào")
status = await service.status()
history = await service.history()
reply = await service.approve(execute=True)    # operation đang chờ, phải exact
reply = await service.resume()                 # resume sau restart/approval
reply = await service.cancel()
await service.close()
```

`ChatReply` báo session/task ID, status, stop reason, checkpoint, approval, model/
executor đã chọn và việc context đã được compile hay chưa.
