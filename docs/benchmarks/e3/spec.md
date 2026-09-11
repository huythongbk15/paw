# E3 — Governed personal-skill accumulation

## Goal

Turn repeated, verified engineering work into reusable personal procedures
without converting raw activity or model output into authority.

## Entry conditions

- E0–E2 pass and verified traces identify at least one repeated workflow
- The Skill Fabric remains the sole owner of skill lifecycle and selection
- Memory facts, user preferences and procedural skills have distinct records
  and correction rules

## Contract

### States (E3-02)

`SkillState` enum with closed set:
- `CANDIDATE` — derived from trace, not yet reviewed
- `REVIEWED` — passed safety + applicability review
- `ACTIVE` — reviewed and explicitly approved
- `REJECTED` — reviewed and denied; same version cannot be re-proposed
- `DEPRECATED` — was ACTIVE, now superseded by newer version
- `SUPERSEDED` — was ACTIVE, replaced by a newer ACTIVE version

### Legal transitions (E3-03)

| From          | To            | Required evidence          |
|---------------|---------------|----------------------------|
| CANDIDATE     | REVIEWED      | `review_record`            |
| REVIEWED      | ACTIVE        | `approval_record`          |
| CANDIDATE     | REJECTED      | `rejection_record`         |
| REVIEWED      | REJECTED      | `rejection_record`         |
| ACTIVE        | DEPRECATED    | `deprecation_record`       |
| ACTIVE        | SUPERSEDED    | `supersession_record`      |
| DEPRECATED    | ACTIVE        | `rollback_record`          |
| SUPERSEDED    | ACTIVE        | `rollback_record`          |

All transitions are enforced in `SkillFabric` via `validate_skill_transition()`.

### Facts/preferences guard (E3-07)

`normalize_fact_to_skill()` is a negative function — it always raises
`ValueError`. Memory facts and user preferences are context records (KnowledgeChunk
/ MemoryRecord), never executable skill bodies.

### Candidate creation (E3-08/09)

`SkillCandidate.from_trace(SkillTrace)` produces a deterministic candidate
with full `TraceLink` provenance: `task_id`, `task_version`, `source_files`,
`evidence_sha`, `derived_at`.

### Secret redaction (E3-10)

`redact_payload(text)` redacts API keys, bearer tokens, AWS keys, and absolute
private paths before candidate persistence. Never raises.

### Deduplication (E3-11)

`detect_duplicate_candidates(candidates)` detects exact duplicates (same
trigger + normalized body) and trigger-word overlap (identical word sets).

### Diff & approval (E3-12)

`generate_skill_diff(candidate, existing)` produces a unified diff plus
provenance summary for human review before approval.

### Replay (E3-14/15/16/17)

Replay uses read-only mode — no skill files are written to disk. Positive
replay validates the candidate on the source workflow. Negative replay
validates the `non_applicable_when` conditions. Results are compared against
a no-skill baseline (tokens, duration, outcome).

### Lifecycle methods (E3-13/18/19/21)

- `submit_candidate_from_trace()` — CANDIDATE
- `review_skill()` — CANDIDATE → REVIEWED
- `approve_skill()` — REVIEWED → ACTIVE (supersedes prior ACTIVE)
- `reject_skill()` — → REJECTED
- `deprecate_skill()` — ACTIVE → DEPRECATED
- `rollback_skill()` — DEPRECATED/SUPERSEDED → ACTIVE

### ACTIVE gate (E3-25)

`SkillFabric.list_skills(enabled_only=True)` returns only ACTIVE skills.
The `enabled` flag alone does NOT grant selectability — a CANDIDATE or
REVIEWED skill with `enabled=True` is invisible to selection.

## Acceptance

- No raw conversation, failed attempt or unreviewed model output becomes an
  active skill
- Every active personal skill has reviewed replay evidence and an accountable
  source/version
- Activation, rejection, deprecation and rollback are durable and inspectable
- Skill selection improves at least one named E0 case without lowering safety
  or required-evidence recall, and a negative case proves the skill does not
  trigger outside its scope
