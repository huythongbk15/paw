# PAW examples

## CLI chat demo

The default provider is deterministic and offline:

```bash
paw chat
```

Bind the session to the current workspace:

```bash
paw chat --provider local --workspace .
```

Inside the REPL:

```text
you> xin chào
paw> [local-standin] xin chào
you> tạo file demo.txt nội dung: xin chào PAW
paw> Cần phê duyệt ... Chưa gọi model hoặc executor. [proposed diff]
you> /approve
paw> Đã created `demo.txt` (14 bytes).
you> /why
you> /artifacts
you> /ledger
you> /status
you> /history
you> /exit
```

The structured write above is performed by `LocalFilesystemExecutor`. It is
confined to `--workspace`; the file is absent before approval, path traversal
is rejected, and a consumed operation is not repeated on resume. Unstructured
legacy requests such as “hãy tạo file demo.txt” remain a mock demonstration and
do not mutate the workspace.

To approve from another process, copy the session ID and use the same workspace:

```bash
paw chat --workspace . --session <session-id> --status
paw chat --workspace . --session <session-id> --approve
```

One-shot JSON mode is suitable for smoke tests:

```bash
paw chat --message "xin chào PAW" --json
```

Every inspection command also has a scriptable flag:

```bash
paw chat --workspace . --session <session-id> --plan --json
paw chat --workspace . --session <session-id> --why --json
paw chat --workspace . --session <session-id> --ledger --json
paw chat --workspace . --session <session-id> --checkpoint --json
paw chat --workspace . --session <session-id> --policy --json
paw chat --workspace . --session <session-id> --skills --json
paw chat --workspace . --session <session-id> --artifacts --json
```

## Library runtime

The following example uses only the canonical runtime and a deterministic step
function, so it is safe to run without a provider or network access.

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

For agent execution, inject `ContextCompiler`, `ModelRouter`, and
`ModelExecutor` into `PawRuntime` and call `run_agent`; do not call a provider
directly from a proposer. For a restart, pass the returned checkpoint ID as
`resume_from_checkpoint`; completed operation IDs are skipped durably.
