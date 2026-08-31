# PAW architecture

The canonical architecture is maintained in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Use the paired [implementation map](docs/IMPLEMENTATION_MAP.md) to distinguish
the intended contract from current source behavior. The short version is:

```text
Task/TaskGraph -> Context + Skills -> Operation Proposal
-> Policy -> Autonomy -> Capability Router / Model Router
-> Executor -> Observation -> Progress -> Ledger + Checkpoint
```

PAW owns every contract and state transition in that flow. Providers and
executors are inward-facing adapters. Every side effect is gated before it
occurs, ASK is a durable wait state, and resume is keyed by completed operation
identity rather than an in-memory counter.

Historical architecture and phase documents were consolidated on 2026-08-31
because their status claims and module maps no longer matched the repository.
