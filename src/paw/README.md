# PAW — Personal Agent Workstation

**PAW** is an independent Personal Agent Runtime: a local-first, zero-vendor-lock-in
core that owns its own abstractions for skills, context, memory, knowledge, autonomy,
policy, and task orchestration.

## Phase 10 — Core Runtime, Autonomy & Context Foundation

PAW delivers a coherent runtime loop:

```
User Request → Task → Skill Discovery → Context Compilation → Task Plan/Graph
    → Autonomy Budget → Policy Authorization → Executor/Model Routing → Execution
    → Observation → Progress Evaluation → Autonomy Decision
    → CONTINUE / REPLAN / ESCALATE / WAIT / STOP → Checkpoint → Task Ledger
```

## Architecture (owned by PAW)

```
Identity · Session · Task · Task Graph
Skill Fabric · Context Compiler · Memory · Knowledge
Autonomy Controller · Policy Engine · Task Ledger
Capability Router · Model Router · Checkpoint/Resume
Evaluation primitives
```

Four-part intelligence core:

```
Skill Fabric (HOW) ◄──────► Context Compiler (WHAT)
       ▲                         ▲
       │                         │
       ▼                         ▼
Task Graph (WHAT) ◄──────► Autonomy Controller (SHOULD)
```

## Design principles

- **One canonical implementation** of each core abstraction
- **Typed boundaries** between subsystems
- **Small core**, deterministic-first (LLM only where uncertainty requires)
- **Minimum sufficient context** — compile, don't dump
- **Policy before side effects** — ASK means STOP, never execute
- **Durable state before long autonomy** — checkpoint before unbounded loops
- **Bounded autonomy** — hard limits, typed decisions, classified stop reasons
- **Observable decisions** — every choice logged to Task Ledger
- **Replaceable providers/executors** — no vendor lock-in

## Install

```bash
pip install paw
```

## CLI

```bash
paw init        # initialize database + directories
paw doctor      # verify installation
paw config      # show configuration
paw profiles    # list execution profiles (Phase 10 K)
paw profiles fast  # show details for a profile
```

## License

Internal / prototype.
