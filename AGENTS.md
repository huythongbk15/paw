# PAW repository instructions

## Mission

PAW is a local-first personal agent runtime. The current work track is **Core
Stabilization**. Historical phase numbers are not a license to add features and
must not be advanced automatically.

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

If a document conflicts with source behavior, tests and source win. Update the
implementation map in the same change; never silently reinterpret the code.

## Current scope lock

Until the Core Stabilization exit gate passes, do not add:

- new model providers or external executor integrations;
- MCP, browser automation, GUI/TUI, swarm or A2A features;
- distributed infrastructure, background workers or a vector database;
- a new planner/router/context abstraction that overlaps an existing one;
- a new numbered phase or a claim that an old phase is complete.

The next safe work is repair work listed in `docs/ROADMAP.md`. A request from
the user may deliberately change this scope, but the expansion and its impact
must be stated before implementation.

## Mandatory workflow

Before implementation:

1. Inspect `git status` and preserve unrelated user changes.
2. Locate the owning contract and all call sites under `src/paw/`.
3. Reproduce the behavior or establish a failing regression test.
4. Record the affected invariant from `docs/ARCHITECTURE.md`.
5. Write a small implementation map: files, boundary changes and acceptance
   checks.

During implementation:

1. Make one canonical implementation; migrate callers before deleting aliases.
2. Gate every side effect, including network/model-provider calls, before it
   occurs.
3. Keep schema definition and migration ownership centralized.
4. Preserve typed stop/failure reasons and idempotency keys across resume.
5. Do not turn ASK into execution without a recorded approval artifact.

After implementation:

1. Run the focused regression test, then the full suite.
2. Run `ruff check .`, package build and isolated CLI smoke checks when the
   change can affect them.
3. Inspect the diff for duplicated contracts, provider leakage and stale docs.
4. Report `PASS`, `PARTIAL`, `FAIL` or `BLOCKED` with command evidence from the
   current revision. A historical test count is not evidence.

## Safety and data handling

- Never expose credentials, workspace memory or private user data.
- Ask before destructive operations or external communication.
- Production initialization and migration code must never drop user tables.
- Prefer reversible changes and explicit transactions.
- Do not use `requirements.lock.txt` as a PAW project environment lock; it is a
  captured host environment and is tracked as technical debt until replaced.

## Definition of done

A change is done only when its behavior, persistence semantics, tests and
canonical documents agree. If verification cannot run, report `BLOCKED` or
`PARTIAL`; do not infer green status from implementation or old logs.
