# PAW Beta — Limitations and Release Decision

_Recorded: 2026-09-13, source HEAD `3e39ded` (clean + BETA B-01/B-02/B-11 committed)._

## Release decision

**Phase 10 Core Stabilization: VERIFIED** on the frozen revision `f3ad4ef`.
All S0–S6 acceptance items pass. (See `IMPLEMENTATION_MAP.md` for evidence.)

**BETA (daily engineering-partner slice): RELEASED for local-only daily use.**

The four beta profiles — `analyze`, `ideate`, `change`, `review` — run through
the canonical `PawRuntime` and share one `ExecutionProfile` + `SideEffectPolicy`
configuration model. They are configuration, not separate runtimes.

The BETA scope is intentionally narrow: **single-user, local-first, no remote
provider is required for the deterministic smoke path** (B-11 verified a wheel
that installs and runs entirely offline). B-04–B-07 demos and B-08 restart-safety
tests pass.

## Known limitations

### 1. No real model inference in the beta path
The beta demos use `LocalModelExecutor` (an offline stand-in that echoes input
as `[local-standin] <input>`). Real model inference (Ollama or cloud providers)
is gated behind the policy/privacy boundary and is **not** exercised by the beta
demos. The four daily profiles declare `privacy_preference` and `verifier_policy`
configuration, but no real provider call occurs in the beta test suite.

### 2. Single-user by design — no tenant isolation
PAW is explicitly single-user through BETA. `project_id` and `session_id` are
scoping keys for task organization and checkpoint/resume, **not** security
boundaries. There is no multi-user tenancy, authentication, or isolation
contract. Sharing the PAW database across users is unsupported and will not
provide isolation. See B-14 for the single-user verification proof.

### 3. Capabilities are advisory in the demo step functions
The beta demos inject evidence directly via `step_fn` rather than running real
skills through the full SkillFabric → ContextCompiler → ModelRouter → ModelExecutor
pipeline. The `ActionProposer` produces `ProposedAction` objects with declared
capabilities; the `_DemoGuard` (in `demo_change.py`) gates writes; but the
`analyze`/`ideate`/`review` demos use read-only step functions that do not
declare side-effect capabilities. This is safe for the beta because the profiles
are read-only or gated, but it means the demos are not full end-to-end runtime
tests of skill execution.

### 4. Restart safety is proven for denied and idempotent writes only
B-08 proves that denied writes produce zero side effects and that approved
idempotent writes do not repeat on restart. It does **not** prove atomicity
across arbitrary multi-step external effects. The canonical runtime has
`OperationRecord` for idempotency, but the beta demos use a single-step
`step_fn`, so crash-during-effect recovery is not exercised by the beta suite.

### 5. Privacy gate is configured, not exercised against real remote payloads
B-10 verifies that all beta demo code paths use `PolicyGuard` with local-only
preferences and declare no remote provider calls. The `RemoteDisclosureRefused`
runtime path (Phase 21) is unit-tested in `test_runtime_privacy_proof.py` but
is not triggered by any beta demo because no remote provider is invoked.

### 6. Limited evidence surface in beta
The beta `RuntimeOutcome.to_answer()` exposes `evidence`, `uncertainty`,
`next_action`, and `stop_reason` (B-03/B-13). This is a structured contract for
CLI/library consumers, but it is a **declared** answer contract over
demo-provided evidence — not a full E2 research-decision artifact with
provenance, alternatives, and readiness classification. The E2 decision lifecycle
is post-gate work.

### 7. No persistent workspace across beta profiles
Each beta demo writes to its own `/tmp/paw_beta_*/demo.db` path and cleans up
between runs via test fixtures. There is no shared persistent PAW workspace
wired into the beta demos. The `paw beta inspect` CLI (B-09) reads from the
database at `settings.db_path`, which is separate from the demo databases.

### 8. Wheel built from source, not a released artifact
B-11 builds and installs a wheel from the current source tree into a temporary
venv. This proves packaging works, but it is **not** a published release.
There is no signed artifact, no release channel, and no upgrade path.

## What the beta guarantees

| Guarantee | Evidence |
|---|---|
| A clean install supports all four profiles through one runtime | B-01, B-02 (shared `PawRuntime`) |
| analyze/ideate are read-only (zero side effects) | `SideEffectPolicy.READ_ONLY`, B-04/B-05, tests |
| change is explicitly gated; denied = zero effects, approved = idempotent | `_DemoGuard`, B-06, B-08 |
| review is non-mutating and detects regressions | B-07, `test_beta_demos.py::TestRestartSafety` |
| Answers expose evidence, uncertainty, next action | B-03, B-13, `to_answer()` |
| Single-user, local-first, no remote provider required | B-10, B-11, B-14 |
| Restart does not repeat completed side effects | B-08 tests |
| Wheel builds and runs outside the repository | B-11 |

## What the beta does NOT guarantee

- Tenant isolation or multi-user safety (see limitation 2, B-14)
- Real provider inference quality (see limitation 1)
- Atomicity of arbitrary multi-step external effects (see limitation 4)
- Full end-to-end skill execution through the production pipeline (see limitation 3)
- A published, upgradeable release artifact (see limitation 8)
