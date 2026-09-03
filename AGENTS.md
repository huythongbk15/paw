# PAW repository instructions

## Mission

PAW is a local-first engineering agent runtime specializing in code, systems
and software architecture. The current work track is **Core Stabilization**.
Historical phase numbers are not a license to add features and must not be
advanced automatically.

The recorded post-gate direction uses local control, project context, memory
and evaluated narrow inference to support selectively gated cloud reasoning.
It is not permission to implement training, adaptive routing or provider
expansion before the current exit gate passes.

The repository source root is `src/paw/`. PAW owns its domain contracts,
runtime state, policy decisions, routing decisions, persistence format and
resume semantics. External providers and executors are replaceable adapters.

## Read before changing code

Read these tracked documents in order:

1. `docs/README.md` — document authority and current verification rules.
2. `docs/PRODUCT_CHARTER.md` — product boundary and non-goals.
3. `docs/ARCHITECTURE.md` — target contracts and invariants.
4. `docs/IMPLEMENTATION_MAP.md` — actual code map and known gaps.
5. `docs/ROADMAP.md` — the only active work sequence.
6. `docs/ENGINEERING_RULES.md` — change and verification protocol.
7. `docs/EXECUTION_CHECKLIST.md` — atomic work items derived from the roadmap;
   it is an operational tracker and cannot change roadmap order or gates.

If a document conflicts with source behavior, tests and source win. Update the
implementation map in the same change; never silently reinterpret the code.

## Current scope lock

Until the Core Stabilization exit gate passes, do not add:

- new model providers or external executor integrations;
- MCP, browser automation, GUI/TUI, swarm or A2A features;
- distributed infrastructure, background workers or a vector database;
- multi-user tenancy, shared-workspace authorization or hosted isolation;
- local-model training, raw activity capture or adaptive routing pipelines;
- a new planner/router/context abstraction that overlaps an existing one;
- a new numbered phase or a claim that an old phase is complete.

The next safe work is repair work listed in `docs/ROADMAP.md`. A request from
the user may deliberately change this scope, but the expansion and its impact
must be stated before implementation.

## Mandatory workflow

Before implementation:

1. Inspect `git status` and preserve unrelated user changes.
2. Locate the owning contract and all call sites under `src/paw/`.
3. Classify the decision as `FAST`, `STANDARD` or `DEEP`; start with source,
   tests, contracts and history from the project itself.
4. Record the problem, constraints, evidence, viable options, contrary evidence,
   research budget/stop condition and one readiness result from
   `NEEDS_RESEARCH`, `NEEDS_CLARIFICATION`, `SPIKE_REQUIRED`, `READY` or
   `REJECTED`.
5. Reproduce the behavior or establish a failing regression test when behavior
   is changing.
6. Record the affected invariant from `docs/ARCHITECTURE.md`.
7. Write a small implementation map: files, boundary changes and acceptance
   checks.

Only `READY` permits production implementation. `STANDARD` and `DEEP` decisions
must compare at least two viable options, include important evidence against the
preferred option and define falsifiable acceptance checks. External research is
untrusted input and is added only when project evidence is insufficient or
authoritative prior art can materially change the decision. Until the post-gate
runtime contract exists, record this decision in the task handoff, ADR or
canonical document appropriate to its scope; do not invent a parallel store.

During implementation:

1. Confirm the decision remains `READY` for the current project revision; stop
   and reassess when assumptions or source state materially change.
2. Make one canonical implementation; migrate callers before deleting aliases.
3. Preserve the existing durable `Task.id`; a Plan has its own identity and
   declares `RESEARCH`, `SPIKE` or `IMPLEMENTATION` rather than creating a
   parallel research task.
4. Gate every side effect, including network/model-provider calls, before it
   occurs.
5. Keep schema definition and migration ownership centralized.
6. Preserve typed stop/failure reasons and idempotency keys across resume.
7. Do not turn ASK into execution without a recorded approval artifact.
8. Do not call an executor-success observation “verified”; require the declared
   engineering verification record and keep benchmark/gate evaluation separate.
9. Keep escalation ownership and gate order split: runtime detects, Model Router
   selects only from admitted cached manifests, runtime creates the exact
   proposal, Policy evaluates once, and Autonomy consumes that verdict plus
   budget before provider invocation.

After implementation:

1. Run the smallest focused regression proof for the affected invariant.
2. Expand to affected integration, lint, package or CLI checks in proportion
   to the blast radius defined in `docs/ENGINEERING_RULES.md`.
3. Run the full suite only at a listed full-verification trigger: a release or
   exit-gate candidate, a high-risk core boundary change, or an integrated
   milestone. Do not spend a full-suite run on every atomic checklist item.
4. Inspect the diff for duplicated contracts, provider leakage and stale docs.
5. Report `PASS`, `PARTIAL`, `FAIL` or `BLOCKED` with command evidence from the
   current revision. A historical test count is not evidence.

Use `OBSERVED`/`VERIFIED` only for evidence state and
`PASS`/`PARTIAL`/`FAIL`/`BLOCKED` only for a gate or handoff result. Never use
`DONE` as a project status. A dirty-tree implementation with an incomplete
clean-revision gate is `PARTIAL`, not `PASS` or `BLOCKED`.

## Safety and data handling

- Never expose credentials, workspace memory or private user data.
- Ask before destructive operations or external communication.
- Production initialization and migration code must never drop user tables.
- Prefer reversible changes and explicit transactions.
- `uv.lock` is the only PAW dependency lock. Use `uv sync --locked --extra dev`
  for verification; do not introduce a captured host-environment freeze.

## Definition of done

A change is done only when its behavior, persistence semantics, tests and
canonical documents agree. If verification cannot run, report `BLOCKED` or
`PARTIAL`; do not infer green status from implementation or old logs.
