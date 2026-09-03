# PAW — Personal Agent Workstation

PAW is an alpha, local-first engineering agent runtime for understanding,
changing and verifying software projects through bounded, policy-gated,
observable and resumable task execution. PAW owns its task, context, policy,
autonomy, routing, ledger and checkpoint contracts; external model providers
and executors are replaceable adapters.

PAW requires Python 3.12 or newer.

```bash
python -m pip install paw
paw --help
```

The current CLI provides setup, inspection and a durable chat demo:

```text
paw init
paw doctor
paw config
paw profiles [name]
paw chat
```

`paw chat` runs each turn through Task → Context/Skills → Policy/Autonomy →
Model/Capability routing → Executor → Observation → Ledger/Checkpoint. Use
`/status`, `/history`, `/plan`, `/why`, `/ledger`, `/checkpoint`, `/policy`,
`/skills`, `/artifacts`, `/approve`, `/resume`, `/cancel`, and `/exit`.
General chat retains a deterministic stand-in; structured filesystem commands
use a workspace-scoped local executor and writes require exact approval.

Project source and canonical architecture documents:
[github.com/huythongbk15/paw](https://github.com/huythongbk15/paw)

Tài liệu tiếng Việt được đồng bộ tại
[`docs/vi/README.md`](../../docs/vi/README.md). Mã nguồn và test vẫn là nguồn
thẩm quyền cuối cùng khi có khác biệt.
