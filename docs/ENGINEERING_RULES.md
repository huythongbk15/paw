# PAW engineering rules

These rules apply to humans and coding agents. Their purpose is to keep the
runtime convergent while it is being stabilized.

## Start every change with an ownership check

Before editing:

1. State the user-visible outcome and the architectural invariant affected.
2. Locate the canonical owner in `IMPLEMENTATION_MAP.md` and source.
3. Search for every definition, import, caller, persistence path and test.
4. Identify whether the change is a repair, contract migration, architecture
   decision or deferred feature.
5. List the smallest files that must change and the acceptance commands.

If no component clearly owns the behavior, clarify ownership in the map before
adding code. Lack of ownership is not permission to create a new manager.

## Scope control

- One change should solve one system problem.
- Do not mix baseline repair, contract refactor and new product behavior unless
  the behavior cannot be tested otherwise.
- Do not add a second runtime, planner, context builder, router, store or status
  enum as a shortcut.
- A compatibility layer must name its canonical target and removal condition.
- Any new core abstraction, production dependency, schema, adapter type or
  runtime entry point requires an architecture decision recorded in the change
  and reflected in canonical docs.
- Historical phase labels belong in history, not in module docstrings, API
  contracts or completion claims.

## Growth review triggers

These are review triggers, not automatic style failures:

- changing a production file already over 500 lines;
- adding more than 150 lines to a single existing production module;
- exporting another public symbol from the broad `paw.core` surface;
- touching more than three core subsystems for one behavior;
- adding global mutable state or another singleton;
- adding DDL, a provider call or a broad `except Exception` in core execution.

When triggered, explain why the owner remains cohesive, what could be extracted
or deleted, and how the change avoids another parallel path. Prefer reducing
or isolating responsibility over creating a generic framework.

## Runtime rules

- `PawRuntime` is the application orchestration authority. Other services
  return decisions/data and do not start hidden loops.
- Single-task and graph-node execution use the same proposal, gate, execution
  and observation pipeline.
- A provider/model call is an operation with capability, privacy and resource
  requirements; it is not a harmless planning helper.
- Policy produces a verdict once. Autonomy consumes it and evaluates whether
  work should continue.
- ASK persists a request and stops. Approval must reference the same proposal
  and cannot be inferred from interactive mode alone.
- Capability Router selects executors; Model Router selects models.
- No-op, echo or instruction loading must be labelled as such and cannot be
  reported as a completed external action.
- Every retry/resume uses a stable idempotency key.

## Domain and API rules

- One canonical enum/model per PAW-owned concept.
- Use typed proposal, observation, result, error and stop-reason boundaries.
- Normalize adapter dictionaries at the port boundary.
- Keep domain contracts independent of SQLite, Typer and provider packages.
- Avoid re-exporting internal helpers. Add a public symbol only with a supported
  use case and a contract test.
- Do not silently change a persisted enum value or serialized field; migrate it.

## Persistence rules

- Schema and migrations have one owner.
- Feature code never runs `CREATE`, `ALTER` or `DROP` in a normal request path.
- All writes use explicit transactions and are committed before success is
  returned.
- Test durability by closing and reopening the database.
- Initialization is non-destructive and repeatable.
- A checkpoint must contain or reference all state required to resume; hidden
  in-memory counters do not qualify.
- Ledger, task state and operation records must have documented atomic or
  recovery semantics.

## Testing rules

Use systematic debugging:

```text
REPRODUCE -> LOCALIZE -> ROOT CAUSE -> INVARIANT -> MINIMAL FIX -> REGRESSION PROOF
```

For important repairs, prove the regression fails before the fix and passes
after it. Required negative controls include:

- missing mandatory source/input makes a test fail;
- DENY and ASK cannot reach any side-effecting mock;
- process restart exposes uncommitted state;
- repeated idempotency key cannot repeat a completed operation;
- failed required graph node blocks dependents;
- context final payload cannot exceed its budget after skill-body loading;
- prohibited dependency/source scan examines a non-empty file set;
- package contents and CLI are tested outside the repository.

Minimum verification for a completed core change:

```bash
python -m pytest -q <focused tests>
python -m pytest -q
python -m ruff check .
python -m build
```

Then install the wheel into a clean environment and smoke-test the affected
CLI/import path. Until S0 supplies a project-only lock and setup command, report
environment setup failures as `BLOCKED`; do not fall back to the captured host
`requirements.lock.txt`.

## Documentation rules

- Source reality changes require an `IMPLEMENTATION_MAP.md` update.
- Contract changes require an `ARCHITECTURE.md` update.
- Scope and priority changes require charter/roadmap updates.
- API examples are documentation tests: a snippet cannot be called runnable
  until CI executes it.
- Do not add another overview or roadmap. Extend the canonical set.
- Do not claim `PASS` from code inspection, old logs or a subset of tests.

## Required handoff format

Every implementation handoff should include:

- **Outcome:** what behavior now exists.
- **Invariant:** which architecture rule was protected or repaired.
- **Scope:** files and contracts changed.
- **Verification:** exact commands and results on the current revision.
- **Status:** `PASS`, `PARTIAL`, `FAIL` or `BLOCKED`.
- **Known gaps:** remaining risk and the next safe task.

If a critical safety/durability gate remains failed, the status cannot be
presented as overall project success.
