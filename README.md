# PAW — Personal Agent Workstation

PAW is a local-first engineering agent runtime for understanding, designing,
changing and verifying complex software projects. It turns a technical goal
into a bounded, policy-authorized, observable and resumable sequence of actions
while keeping providers and executors replaceable.

## Current status

PAW is in **Core Stabilization** and now has one coherent CLI workflow. The
repository contains implemented tasks, skills, context, memory, knowledge,
policy, autonomy, routing, approvals, checkpoints and a runtime loop. The demo
is suitable for exercising those boundaries. General chat still has a
deterministic stand-in, while explicit read/list/write commands can use the
workspace-scoped local filesystem executor after Policy and exact approval.

Current gate result is **`PARTIAL`**: S0–S6 repair behavior is present, but the
14-item SX qualification has not yet produced one reviewed clean revision with
current D3 evidence. SX-01 through SX-03 have focused evidence, including the
canonical Task/Plan identity repair. E0–E3, BETA and optional E4 remain
`BLOCKED`; the next authorized item is `SX-04`. This is not a `DONE` or
release-ready claim.

The recorded post-stabilization direction is an engineering agent in which
local state, project context, memory and evaluated narrow inference reduce
cloud context, while difficult architecture and debugging work may use gated
cloud reasoning. That direction is documented but is not yet implemented.

The 2026-08-31 audit found safety, durability and ownership gaps, including
duplicated core contracts, pre-policy model calls, disconnected capability
routing, incomplete graph failure/resume behavior and scattered schema
ownership. Historical “Phase complete” claims are not current status evidence.

Start with the [canonical system documents](docs/README.md):

Nếu bạn đọc tiếng Việt, bắt đầu từ [bộ tài liệu tiếng Việt](docs/vi/README.md).

- [Product charter](docs/PRODUCT_CHARTER.md)
- [Core architecture](docs/ARCHITECTURE.md)
- [Implementation map and audit](docs/IMPLEMENTATION_MAP.md)
- [Core Stabilization roadmap](docs/ROADMAP.md)
- [Engineering rules](docs/ENGINEERING_RULES.md)

## What exists today

```text
src/paw/
  core/        Task/runtime services, policy, autonomy, routing and persistence
  knowledge/   Source, chunk, evidence, citation and search primitives
  providers/   Provider ports and the optional Ollama adapter
  executors/   Built-in local adapters composed by applications
  cli/         Typer commands for setup, inspection and execution profiles
```

The CLI currently exposes:

```bash
paw --version
paw init
paw doctor
paw config
paw profiles [name]
paw chat
```

Start an interactive durable session:

```bash
paw chat
```

Useful chat commands include `/status`, `/history`, `/plan`, `/why`, `/ledger`,
`/checkpoint`, `/policy`, `/skills`, `/artifacts`, `/approve`, `/resume`,
`/cancel`, and `/exit`. For a scriptable smoke test:

```bash
paw chat --message "xin chào PAW" --json
```

Try a real workspace-bounded write (the file does not exist until approval):

```bash
paw chat --provider local --workspace . \
  --message "tạo file demo.txt nội dung: xin chào PAW" --json
paw chat --provider local --workspace . --session <session-id> --approve --json
```

The default `auto` provider tries the existing local Ollama adapter and falls
back to the deterministic stand-in. Use `--provider local` for a fully offline
smoke path.

## Install

PAW requires Python 3.12 or newer.

```bash
python -m pip install .
paw --help
```

For development, install the project-declared extras:

```bash
uv sync --locked --extra dev
python -m pytest -q
python -m ruff check .
```

`uv.lock` is generated only from `pyproject.toml` and is the canonical PAW
dependency lock. `uv lock --check` verifies that the manifest and lock agree.

## Architectural core

PAW owns:

```text
Identity  Session  Task  Plan/TaskGraph  Skill Fabric
Context Compiler  Memory  Knowledge  Policy  Autonomy
Capability Router  Model Router  Executor ports
Observation  Task Ledger  Checkpoint/Resume
```

External systems implement ports only. They do not own or redefine these
concepts.

The intended unit loop is:

```text
Task/ready node -> context + skills -> operation proposal
-> Policy -> Autonomy -> Capability/Model selection -> execute
-> observation -> progress/state -> ledger/checkpoint -> next decision
```

Every side effect, including a remote or billable model call, must be authorized
before it occurs. ASK waits for a recorded approval; it never means execute.

## Contribution direction

New provider, GUI, MCP, swarm and distributed-runtime work is intentionally
deferred. The next safe work is the ordered repair plan in
[docs/ROADMAP.md](docs/ROADMAP.md). Root [AGENTS.md](AGENTS.md) gives coding
agents the same scope and verification rules.
