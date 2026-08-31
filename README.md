# PAW — Personal Agent Workstation

PAW is a local-first personal agent runtime: it turns a user goal into a
bounded, policy-authorized, observable and resumable sequence of actions while
keeping providers and executors replaceable.

## Current status

PAW is in **Core Stabilization** and now has one coherent CLI demo path. The
repository contains implemented tasks, skills, context, memory, knowledge,
policy, autonomy, routing, approvals, checkpoints and a runtime loop. The demo
is suitable for exercising those boundaries; its built-in model and executor
are deterministic stand-ins, not production automation.

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

Useful chat commands are `/status`, `/history`, `/approve`, `/resume`,
`/cancel`, and `/exit`. For a scriptable smoke test:

```bash
paw chat --message "xin chào PAW" --json
```

The default `local` provider is offline and deterministic. Use
`--provider ollama` to try the existing local Ollama adapter; PAW falls back to
the local stand-in if Ollama is unavailable.

## Install

PAW requires Python 3.12 or newer.

```bash
python -m pip install .
paw --help
```

For development, install the project-declared extras:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
```

`requirements.lock.txt` is currently a captured host-environment snapshot, not
a PAW-only lock. Do not use it to construct a project environment. Replacing it
with a reproducible project lock is the first roadmap task.

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
