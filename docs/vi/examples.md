# Ví dụ PAW

## Demo CLI chat

Chạy offline và khóa thao tác file trong workspace hiện tại:

```bash
paw chat --provider local --workspace .
```

Trong REPL:

```text
you> xin chào
paw> [local-standin] xin chào
you> tạo file demo.txt nội dung: xin chào PAW
paw> Cần phê duyệt ... Chưa gọi model hoặc executor. [diff đề xuất]
you> /approve
paw> Đã created `demo.txt` (14 bytes).
you> /why
you> /artifacts
you> /ledger
you> /status
you> /history
you> /exit
```

Yêu cầu có cấu trúc trên được `LocalFilesystemExecutor` thực hiện thật. File chưa
tồn tại trước approval; traversal ra ngoài `--workspace` bị chặn và operation đã
consume không chạy lại khi resume. Yêu cầu legacy không có nội dung như "hãy tạo
file demo.txt" vẫn chỉ chạy mock và không sửa workspace.

**Hai approval cho một structured write.** Một structured write cần hai quyết
định của con người, và cái này không thay thế cái kia:

1. **Decision review** — người dùng chấp nhận bằng chứng implementation-readiness
   cho một snapshot `DecisionVersion` cụ thể (`ApprovalStore.request_decision_review`).
   Cái này cấp *chấp nhận bằng chứng*; không cấp quyền thực thi.
2. **Effect approval** — phê duyệt đúng operation được đề xuất (`/approve`).

Review mà không có effect approval thì không thực thi; effect approval mà
không có decision review tương ứng thì cũng không thực thi. Approval thô không
phải implementation authority. Luồng CLI/stream yêu cầu decision review FAST
có giới hạn trước, rồi mới đến effect approval chính xác.

Để approve từ process khác, dùng cùng workspace:

```bash
paw chat --workspace . --session <session-id> --status
paw chat --workspace . --session <session-id> --approve
```

Chế độ JSON một lần phù hợp smoke test:

```bash
paw chat --message "xin chào PAW" --json
```

Các lệnh inspect cũng có cờ JSON: `--plan`, `--why`, `--ledger`,
`--checkpoint`, `--policy`, `--skills` và `--artifacts`.

## Runtime qua library

Ví dụ sau chỉ dùng runtime canonical và step function xác định, an toàn khi chạy
không cần provider hoặc network:

```python
import asyncio
from pathlib import Path

from paw.core.autonomy import AutonomyBudget, AutonomyController
from paw.core.models import Capability, ExecutionObservation, ResourceUsage
from paw.core.policy import PolicyGuard
from paw.core.runtime import PawRuntime
from paw.core.session import SessionManager
from paw.core.storage import db, set_db_path
from paw.core.task import TaskManager


async def main() -> None:
    db_path = Path(".paw/example.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await set_db_path(db_path)
    await db.initialize()
    session = await SessionManager.create()
    task = await TaskManager.create(
        session.id,
        goal="Read a local status file",
        requested_capabilities=[Capability.FILESYSTEM_READ],
    )

    controller = AutonomyController(
        budget=AutonomyBudget(max_iterations=3),
        policy_guard=PolicyGuard(interactive=False),
    )
    runtime = PawRuntime(controller)

    async def step(task_id, action):
        return ExecutionObservation(
            step_id="status-read",
            action_id=action.operation_id,
            result={"done": True, "progress": 1.0, "summary": "status read"},
            resources_used=ResourceUsage(tool_calls=1),
            success=True,
        )

    outcome = await runtime.run(task.id, task_goal=task.goal, step_fn=step)
    assert outcome.reason.value == "task_completed"
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
```

Để chạy agent, inject `ContextCompiler`, `ModelRouter` và `ModelExecutor` vào
`PawRuntime`, rồi gọi `run_agent`; không gọi provider trực tiếp từ proposer. Khi
restart, truyền checkpoint ID trả về vào `resume_from_checkpoint`; operation ID
đã hoàn thành được bỏ qua một cách bền vững.
