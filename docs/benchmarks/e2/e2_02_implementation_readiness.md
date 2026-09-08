# E2-02 — Durable ImplementationReadiness Schema

**Date**: 2026-09-08
**HEAD**: `c28d679`
**Prerequisite**: E1 `VERIFIED`
**Scope**: `docs/benchmarks/e2/e2_02_implementation_readiness.md` (this file) — schema spec only. The implementation in `src/paw/core/` is scaffolded in docs pending Đại ca direction on code constraints.
**Status**: DRAFT (doc-only scaffolding; code to follow)

---

## 1. Purpose

This document specifies the durable `ImplementationReadiness` record that
closes the gap between E1 (source intelligence is deterministic and
source-backed) and E2-50 (model-assisted decision making). Every
implementation-purpose Plan must reference a current `READY` decision.

**Entry conditions met**:
- E0: `VERIFIED` (deterministic fixture-validation baseline on `f3ad4ef`)
- E1: `VERIFIED` (E1-27 gate PASS/VERIFIED on clean revision `c28d679`, dirty=false, recall=1.0, reduction=0.871)

---

## 2. Schema

```python
# src/paw/core/implementation_readiness.py  (scaffold location)

class ReadinessState(str, Enum):
    """State of a readiness decision record."""
    DRAFT = "draft"           # in-progress, not yet final
    FINAL = "final"           # approved, authoritative
    STALE = "stale"           # superseded by source revision or invalidation
    SUPERSEDED = "superseded" # replaced by a later FINAL record

class DecisionOutcome(str, Enum):
    """The documentary readiness outcome (carried from E0-28..35)."""
    NEEDS_RESEARCH = "needs_research"
    NEEDS_CLARIFICATION = "needs_clarification"
    SPIKE_REQUIRED = "spike_required"
    READY = "ready"
    REJECTED = "rejected"

@dataclass(frozen=True)
class ImplementationReadiness:
    """Durable record of an implementation-readiness decision.

    Invariants:
      - Only one FINAL record per (task_id, project_revision, scope_key).
      - A DRAFT record may be superseded by a FINAL record for the same key.
      - A FINAL record becomes STALE when project_revision changes.
      - A REJECTED record blocks all mutating proposals under the same scope_key.
    """
    id: str                        # deterministic hash of (task_id, project_revision, scope_key)
    task_id: str                   # existing Task.id (never create a parallel task)
    project_revision: str          # git SHA-1 (project revision at decision time)
    scope_key: str                 # e.g. "router_filter_availability" or "privacy_hard_gate"
    outcome: DecisionOutcome
    state: ReadinessState = ReadinessState.DRAFT
    plan_purpose: PlanPurpose | None = None  # see §3
    options_compared: list[str] = ()          # at least 2 for STANDARD/DEEP
    contrary_evidence: list[str] = ()
    research_stop_budget: str = "unbounded"   # default; must be explicit for STANDARD/DEEP
    verified_by: list[str] = ()              # test names / gate ids
    created_at: datetime = field(default_factory=datetime.utcnow)
    finalized_at: datetime | None = None
    invalid_at: datetime | None = None
    invalidation_reason: str = ""
    superseded_by: str = ""                   # id of the FINAL replacement (if STALE/SUPERSEDED)
    evidence_trace: list[str] = ()            # source_hash references / ledger event IDs
```

### 2.1 SQLite storage (migration from existing schema)

The `decision_events` table (already on `storage.py` schema) gains:
- `scope_key TEXT NOT NULL`
- `outcome TEXT NOT NULL` (enum string)
- `state TEXT NOT NULL DEFAULT 'draft'`
- `plan_purpose_json TEXT` (JSON-encoded `PlanPurpose`)
- `options_compared_json TEXT`
- `contrary_evidence_json TEXT`
- `research_stop_budget TEXT DEFAULT 'unbounded'`
- `finalized_at TEXT` (nullable)
- `invalid_at TEXT` (nullable)
- `invalidation_reason TEXT DEFAULT ''`
- `superseded_by TEXT DEFAULT ''`
- `evidence_trace_json TEXT`
- `project_revision TEXT`
- `task_id TEXT NOT NULL`

All columns are ADD COLUMN (additive, no row rewrite).

### 2.2 Readiness lookup

`ImplementationReadinessStore.get_current(task_id, project_revision, scope_key) -> ImplementationReadiness | None`
- Returns the latest FINAL record matching the key.
- If a FINAL record exists but `project_revision` differs from the current HEAD, returns STALE state.
- If only DRAFT records exist, returns None (no actionable decision yet).

---

## 3. PlanPurpose (extends existing Plan)

The existing `Plan` dataclass gains:
```python
class PlanPurpose(str, Enum):
    RESEARCH = "research"      # SPIKE / investigation; never mutates the project
    IMPLEMENTATION = "implementation"  # mutates; requires READY decision
    EVALUATION = "evaluation"  # benchmark / measurement; read-only
    VERIFICATION = "verification"     # gate check; read-only

# In Plan dataclass:
purpose: PlanPurpose = PlanPurpose.RESEARCH  # default: never implement without explicit purpose
```

**Constraint**: a Plan with `purpose=IMPLEMENTATION` MUST reference an
existing Task.id and a current `READY` decision for the same
`(task_id, project_revision, scope_key)`. This is enforced at
`Plan.__post_init__` and by `PawRuntime.run()` before dispatch.

---

## 4. Stop / Ask semantics

The runtime consumes readiness outcomes:
- `READY` → Autonomy may proceed to `CONTINUE` (subject to budget + Policy)
- `REJECTED` → `STOP(REJECTION)` — typed reason; never executes
- `NEEDS_RESEARCH` → `STOP(SPIKE_SCHEDULED)` — scheduling-only; no implementation
- `NEEDS_CLARIFICATION` → `ASK(CLARIFICATION_REQUIRED)` — user-facing question
- `SPIKE_REQUIRED` → `STOP(SPIKE_REQUIRED)` — bounded investigation first

These map directly to the existing `StopReason` enum; the runtime
checks `ImplementationReadinessStore.get_current()` before any
`Purpose=IMPLEMENTATION` plan is dispatched.

---

## 5. Acceptance criteria (E2-02)

| # | Criterion | Verification |
|---|-----------|--------------|
| A1 | `ImplementationReadiness` has 4 states (DRAFT/FINAL/STALE/SUPERSEDED) | `test_e2_02_readiness_schema.py` |
| A2 | `DecisionOutcome` carries 5 values (NEEDS_RESEARCH/CLARIFICATION/SPIKE_REQUIRED/READY/REJECTED) | same |
| A3 | STANDARD/DEEP decisions require ≥2 options + contrary_evidence | same |
| A4 | `PlanPurpose` enforces research vs implementation separation | `test_e2_02_plan_purpose.py` |
| A5 | REJECTED readiness blocks mutating proposals | `test_e2_02_rejected_blocks.py` |
| A6 | Stale (revision mismatch) readiness blocks execution | `test_e2_02_stale_blocks.py` |
| A7 | SQLite migration is additive (no DROP, no row rewrite) | `test_schema_migration.py` |
| A8 | `get_current()` returns STALE for revision mismatch | `test_e2_02_get_current.py` |

---

## 6. Boundary

- **Owns**: decision state machine, DRAFT→FINAL transition, STALE detection
- **Owned by** runtime: Plan dispatch gating (`PawRuntime.run()` checks readiness)
- **Owned by** E2-50 (future): model-assisted option scoring (E2-03) and novelty detection (E2-04)
- **Does NOT own**: Plan creation itself (that stays with the existing Plan dataclass); model provider selection (that's E2-31)

---

*Spec drafted 2026-09-08 on clean revision `c28d679`. Awaiting code
implementation window (Đại ca direction on src/ constraints).*
