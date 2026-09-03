# PAW system documents

This directory is the canonical documentation set for PAW. It exists to keep
the product boundary, architecture, implementation reality and work sequence
separate but consistent.

The recorded post-stabilization direction specializes PAW in code, systems and
software architecture: local control/context/memory supports selectively gated
cloud reasoning, and bounded source-backed research must produce a readiness
decision before implementation planning. This is a documented target, not
implemented status; Core Stabilization remains the only active track.

Current gate result: **`PARTIAL`**. S0–S6 repair behavior is observed in the
working tree, but SX has not yet qualified one reviewed clean revision. E0–E3,
BETA and optional E4 therefore remain `BLOCKED`; SX-01 through SX-03 have
focused evidence and the next item is `SX-04`.

Audit baseline: repository commit `c48a22e` plus the current Core Stabilization
working tree, inspected on 2026-08-31.

Vietnamese readers: see the synchronized [bộ tài liệu tiếng Việt](vi/README.md).
The English files remain the canonical contract text; the source code and tests
remain the final authority for implemented behavior.

## Read order

1. [Product charter](PRODUCT_CHARTER.md) — why PAW exists, what PAW owns and
   what is deliberately out of scope.
2. [Core architecture](ARCHITECTURE.md) — target runtime contract, dependency
   direction and invariants.
3. [Implementation map](IMPLEMENTATION_MAP.md) — where those concepts exist in
   the current source and where implementation diverges from the contract.
4. [Stabilization roadmap](ROADMAP.md) — repair order and binary exit gates.
5. [Engineering rules](ENGINEERING_RULES.md) — how humans and coding agents may
   change the system without creating another competing abstraction.
6. [Execution checklist](EXECUTION_CHECKLIST.md) — atomic, estimated work items
   derived from the roadmap. It tracks execution only and cannot change scope,
   order or acceptance gates.

`api.md` and `examples.md` are source-backed references for the stabilized core;
the offline example was executed against an isolated wheel install. They remain
secondary to current source and contract tests.

Reproducible developer setup uses the PAW-only lock:

```bash
uv lock --check
uv sync --locked --extra dev
```

## Authority order

When two sources disagree, use this order:

1. Reproducible behavior demonstrated by tests on the current revision.
2. Current source under `src/paw/`.
3. `IMPLEMENTATION_MAP.md` for interpretation of current behavior.
4. `ARCHITECTURE.md` for the intended contract.
5. `PRODUCT_CHARTER.md` and `ROADMAP.md` for scope and sequencing.
6. Historical phase notes, workspace memory and commit messages.

The intended contract does not make a missing behavior real. A mismatch means
the implementation is `PARTIAL` or `FAIL`, and the map must say so.

## Status vocabulary

Status has two separate dimensions. Do not substitute one for the other.

Evidence state:

| Label | Meaning |
|---|---|
| `OBSERVED` | Present in source by inspection; not necessarily exercised. |
| `VERIFIED` | A named command or test passed against the exact stated revision/tree. |

Gate or handoff result:

| Label | Meaning |
|---|---|
| `PASS` | Every acceptance condition for the named gate/change passed with current evidence. |
| `PARTIAL` | Some required behavior/evidence exists, but at least one acceptance item remains. |
| `FAIL` | Current evidence contradicts an acceptance condition or safety/durability invariant. |
| `BLOCKED` | Work or verification cannot proceed because a prerequisite is unavailable. |

`DONE` and bare `implemented` are not status labels. A feature may be observed
in a dirty working tree while its release gate remains `PARTIAL`. Never convert
an old test count, phase label or workspace note into `VERIFIED` or `PASS`.

## Documentation maintenance

Update the following in the same change:

- contract or dependency direction change: `ARCHITECTURE.md`;
- module ownership, public class or known-gap change: `IMPLEMENTATION_MAP.md`;
- priority or acceptance-gate change: `ROADMAP.md`;
- task atomization or completion evidence: `EXECUTION_CHECKLIST.md`, after any
  required roadmap change;
- product scope change: `PRODUCT_CHARTER.md` plus a recorded decision;
- developer workflow change: `ENGINEERING_RULES.md` and, when applicable,
  root `AGENTS.md`.
- user-facing documentation change: update the synchronized Vietnamese copy
  under `docs/vi/` in the same change.

Do not create another project overview, phase plan or architecture document.
Extend this set instead.
