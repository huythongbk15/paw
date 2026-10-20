# PAW system documents

## Current status — single source of truth (2026-10-20)

This section is the **only** place in the canonical set that states current
status. Other documents must link here instead of restating a verdict; the
historical records below are dated evidence, not current status.

Two different things have historically been called "E1/E2 VERIFIED". They are
separated below, because conflating them is the main source of contradiction
between the English and Vietnamese documents.

**Gate-level results** — a measured gate inside its own declared scope:

| Gate | Result | Scope and evidence |
|---|---|---|
| Core Stabilization | **`VERIFIED`** on `f3ad4ef` | S0–S6 acceptance passed the clean-revision D3 gate; the freeze commit is the tracked canonical evidence. |
| E0 fixture-validation baseline | **`VERIFIED`** for deterministic offline | 13 cases (8 minimum + 5 research-decision), deterministic runner, integration-pack record. 13/13 SUCCESS is **fixture-validation**, not an agent-quality gate. The runtime-driven agent-quality tier is post-gate work (E0-40). |
| E1-27 production measurement | **`VERIFIED`** | Clean revision `8d01d90`; `min_recall=1.00`, 12/12 samples (6 cases x cold/warm), real Ollama embeddings. **Evidence caveat:** the measurement report `benchmarks/e1/e1_production_report.md` is *gitignored*, so this verdict rests on the recorded documentation, not on a tracked artifact. Re-tracking it is a release prerequisite. |
| E2 prerequisite contract | **`RATIFIED`** on `8d01d90` | E2-25..28 and E2-45..47 implemented and passing (119 E2 contract tests). The cloud-baseline boundary is resolved by `InferenceClassification` / `evaluate_local_eligibility`. |

**Track-level (release) results** — whether a track may ship:

| Track | Result | Why |
|---|---|---|
| E1 (Local project intelligence) | **`PARTIAL`** | The E1-27 *measurement* gate is verified; the E1 *track* qualification is not. Quality, privacy and release acceptance for the track were never linked to the qualification revision. A verified measurement gate is not a qualified track. |
| E2, E3, BETA | **`BLOCKED`** | Their gate-level contracts exist, but the track-level release acceptance depends on E1 track qualification. Source wiring ahead of accepted prerequisites is `OBSERVED` implementation, not permission to expand. |
| E4 (controlled adaptation) | **`BLOCKED`**, optional | Requires E0–E3 and a verified dataset; not required for BETA. |

**Product release: `PARTIAL`.** The productization review is dated **2026-10-05**
(source `9fb893e` plus the preserved user index change), with a 2026-10-07
follow-up. B-18 shared-unit admission/recovery and two-approval CLI work carries
integrated working-tree D3 evidence (2026-10-07, 2262 passed, 3 skipped). That
evidence is **working-tree**, not clean-revision certification, and no clean
current-revision release is claimed. B-19 discovery/payload controls remain
outstanding. The
[productization audit and web contract](BETA_LIMITATIONS.md) records F01..F12,
feature parity, security, cases and acceptance; read it after the seven core
documents before taking B-15..B-36. The [Roadmap](ROADMAP.md) remains the
sequence authority. Web is a user-requested local presentation adapter, not a
new agent core. Training stays out of scope.

Vietnamese version: [đóng gói và web](vi/BETA_LIMITATIONS.md).

### Historical records (dated evidence — not current status)

Review — 2026-09-09, source HEAD `fd8a8c8` with an existing uncommitted
router change. The tracked report `benchmarks/e1/real_measurement_local.json`
records a clean **measurement-only** PASS/VERIFIED at `649ded9`: 71 source
files, 839,006 bytes, recall 1.0, estimated warm-context reduction 0.9847.
Its scope explicitly excludes overall E1 qualification. It is historical
measurement evidence, not a current-revision D3, engineering-quality or
provider-token claim. E2-06..11 code is already present, including runtime
routing/reconnaissance wiring; this is OBSERVED implementation ahead of
accepted prerequisites, not permission to expand. Preserve it for review.
See the 2026-09-09 decision in `IMPLEMENTATION_MAP.md`.

The English and Vietnamese Roadmap files describe the same 2026-09-09 review.
They previously stated *opposite* verdicts for it. Both now say the same
thing: measurement-only evidence at the stated revisions, E1 track
qualification not established.

This directory is the canonical documentation set for PAW. It exists to keep
the product boundary, architecture, implementation reality and work sequence
separate but consistent.

The recorded post-stabilization direction specializes PAW in code, systems and
software architecture: local control/context/memory supports selectively gated
cloud reasoning, and bounded source-backed research must produce a readiness
decision before implementation planning. This is a documented target, not
implemented status; the current gate and track results are the tables above.

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
