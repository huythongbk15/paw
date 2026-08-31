# PAW — Personal Agent Workstation

PAW is an alpha, local-first personal agent runtime for bounded, policy-gated,
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
`/status`, `/history`, `/approve`, `/resume`, `/cancel`, and `/exit`. The
default model/executor are deterministic local stand-ins for safe offline
verification; they are not production automation.

Project source and canonical architecture documents:
[github.com/huythongbk15/paw](https://github.com/huythongbk15/paw)

Tài liệu tiếng Việt được đồng bộ tại
[`docs/vi/README.md`](../../docs/vi/README.md). Mã nguồn và test vẫn là nguồn
thẩm quyền cuối cùng khi có khác biệt.
