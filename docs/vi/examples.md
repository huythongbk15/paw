# Ví dụ PAW

## Demo CLI chat

Provider mặc định xác định và chạy offline:

```bash
paw chat
```

Trong REPL:

```text
you> xin chào
paw> [local-standin] xin chào
you> hãy tạo file demo.txt
paw> Cần phê duyệt ... Chưa gọi model hoặc executor.
you> /approve
paw> [local-standin] hãy tạo file demo.txt
you> /status
you> /history
you> /exit
```

Yêu cầu ghi file trên được bundled mock executor mô phỏng: demo chứng minh
authorization, routing, observation và resume nhưng không sửa file thật. Để tiếp
tục từ process khác, copy session ID rồi chạy:

```bash
paw chat --session <session-id> --status
paw chat --session <session-id> --approve
```

Chế độ JSON một lần phù hợp smoke test:

```bash
paw chat --message "xin chào PAW" --json
```

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
