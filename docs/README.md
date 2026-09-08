# PAW system documents

Latest verification (2026-09-08, `74b563e` + working tree): **PARTIAL**.
This supersedes the earlier numeric/status snapshot below. The current
71-file source run has recall 1.0, median reduction 0.981366, fresh fixtures
and unchanged inputs/tree; measurement remains PARTIAL because the tree is
dirty. Local inference with a manifest is repaired: 41 affected tests pass,
full Ruff passes, and a source-matched installed wheel passes local CLI chat.
Full D3 has not passed on this revision; E2 activation remains blocked.
See the latest verification record in `IMPLEMENTATION_MAP.md`.

Earlier audit (2026-09-08, `2c4a81f` plus the working tree): **PARTIAL**.
The real `src/paw` E1 observation meets its numeric targets, but E1 is not
`VERIFIED`: the clean report previously used for that claim measured the small
`benchmarks/e1/fixtures_paw` corpus, while the current real-source run is dirty
and has stale reviewed-fixture provenance. E2 remains blocked. The isolated
E2 role/task-signal value contracts are pre-gate repair work, not active router
or readiness implementation. See the current decision and evidence record in
`IMPLEMENTATION_MAP.md`.

This directory is the canonical documentation set for PAW. It exists to keep
the product boundary, architecture, implementation reality and work sequence
separate but consistent.

The recorded post-stabilization direction specializes PAW in code, systems and
software architecture: local control/context/memory supports selectively gated
cloud reasoning, and bounded source-backed research must produce a readiness
decision before implementation planning. This is a documented target, not
implemented status; Core Stabilization has a verified freeze, E0 has shipped
its fixture-validation baseline, E1 qualification is active, and E2–E4 / BETA
remain gated by the ordered roadmap.

Current gate result:

| Track | Result | Meaning |
|---|---|---|
| Core Stabilization | **`VERIFIED`** on `f3ad4ef` | S0–S6 acceptance passed the clean-revision D3 gate; the freeze commit is the canonical evidence. |
| E0 (fixture-validation baseline) | **`VERIFIED`** for deterministic offline | The contract, 13 cases (8 minimum + 5 research-decision), the deterministic evidence runner, and the integration-pack record are in place. The 13/13 SUCCESS line is **fixture-validation**, not an agent-quality gate; the runtime-driven agent-quality tier is post-gate work (E0-40). |
| E1 (Local project intelligence) | `PARTIAL`; real-source metric `PASS` is `OBSERVED` | The current 70-file `src/paw` run has cold/warm recall 1.00 and median warm context reduction 0.981. The clean 12-file synthetic-fixture report at `c28d679` is not representative-project evidence. A reviewed real-source freeze plus the remaining quality/privacy D3 gate is required. |
| E2, E3, BETA | `BLOCKED` | E2 requires E0 + E1 `VERIFIED`. The E2-01 audit and isolated E2-02..05 value contracts (`RoleContract`, `TaskSignals`, `OODCondition`/`EligibilityRule`) are provisional and have no runtime authority. |
| E4 (controlled adaptation) | `BLOCKED`, optional | Requires E0–E3 and a verified dataset; not required for BETA. |

Audit baseline: Core Stabilization freeze `f3ad4ef`, current HEAD `2c4a81f`, and
the working tree inspected on 2026-09-08. Historical counts are not current
gate evidence.

Vietnamese readers: see the synchronized [bộ tài liệu tiếng Việt](vi/README.md).
The English files remain the canonical contract text; the source code and tests
remain the final authority for implemented behavior.

## Read order

1. [Product charter](PRODUCT_CHARTER.md) — why PAW exists, what PAW owns and
   what is deliberately out of scope.
2. [Core architecture](ARCHITECTURE.md) — target runtime contract, dependency
   direction and invariants. Paragraphs are marked `[CURRENT]` / `[RATIFIED TARGET]` /
   `[FUTURE]`; the status legend at the top explains how to read them.
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

The benchmarks themselves are the read-only, deterministic tier of E0;
`docs/benchmarks/e0/integration_pack_run.md` records the 13/13 SUCCESS result
as a **fixture-validation** gate, not an agent-quality gate.

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
