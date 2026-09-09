# PAW system documents

Review — 2026-09-09, source HEAD `fd8a8c8` with an existing uncommitted
router change: **E1 PARTIAL; E2–E3/BETA BLOCKED at the acceptance gate**.
The tracked report `benchmarks/e1/real_measurement_local.json` records
a clean **measurement-only** PASS/VERIFIED at `649ded9`: 71 source files,
839,006 bytes, recall 1.0, estimated warm-context reduction 0.9847.
Its scope explicitly excludes overall E1 qualification. It is historical
measurement evidence, not a current-revision D3, engineering-quality or
provider-token claim. E2-06..11 code is already present, including runtime
routing/reconnaissance wiring; this is OBSERVED implementation ahead of
accepted prerequisites, not permission to expand. Preserve it for review.
See the 2026-09-09 decision in `IMPLEMENTATION_MAP.md`.

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
| E1 (Local project intelligence) | `PARTIAL` | Historical source measurement at `649ded9` passes its own scope. Remaining quality/privacy/release acceptance must be linked on the qualification revision. |
| E2, E3, BETA | `BLOCKED` | E2 source wiring exists ahead of accepted prerequisites; no overall E1 gate evidence is established by the measurement report. |
| E4 (controlled adaptation) | `BLOCKED`, optional | Requires E0–E3 and a verified dataset; not required for BETA. |

Audit baseline: historical Core freeze `f3ad4ef`; source review `fd8a8c8`
on 2026-09-09. Historical counts are not current gate evidence.

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
