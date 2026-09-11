# E3 — Governed personal skills: lifecycle contract

**Created:** 2026-09-11  
**Owner:** `paw.core.skills` (SkillFabric, SkillManifest, SkillSelector)  
**Status:** IMPLEMENTING

## Goal

At least one repeated workflow becomes a reviewed, replayed, versioned and
reversible personal skill with a negative trigger case.

## Skill states

| State | Meaning | Transitions out |
|---|---|---|
| `CANDIDATE` | Draft, not yet reviewed. | → REVIEWED |
| `REVIEWED` | Review passed; not yet live. | → ACTIVE, → REJECTED |
| `ACTIVE` | Live, usable by the runtime. | → DEPRECATED, → SUPERSEDED |
| `REJECTED` | Review/acceptance failed. Cannot execute. | → CANDIDATE (re-submit with bump) |
| `DEPRECATED` | Retired, kept for audit. Cannot execute. | — |
| `SUPERSEDED` | Replaced by a newer ACTIVE version. Cannot execute. | — (prior version preserved for rollback) |

**Invariant:** Only `ACTIVE` skills pass through `SkillSelector` and
`SkillFabric.get_skill`. `enabled=True` alone does not make a skill executable.

## Legal transitions and required evidence

| Transition | Actor | Evidence required |
|---|---|---|
| CANDIDATE → REVIEWED | reviewer | Review record: diff, provenance, safety assessment |
| REVIEWED → ACTIVE | approver | Approval record: exact version, date, approver |
| REVIEWED → REJECTED | reviewer/approver | Rejection reason, prevents re-proposal of same version |
| ACTIVE → DEPRECATED | maintainer | Deprecation reason; skill stays in DB for audit |
| ACTIVE → SUPERSEDED | maintainer | New ACTIVE version that replaces it |
| REJECTED → CANDIDATE | author | Version bump; prior rejection is not erased |

## Provenance metadata (E3-04)

| Field | Type | Description |
|---|---|---|
| `skill_version` | str | Semantic version (`1.0.0`). Bumped on re-submit. |
| `source` | str | Where the skill came from: `installed`, `candidate`, `replay` |
| `review_record` | ReviewRecord | Who, when, what was reviewed |
| `approval_record` | ApprovalRecord | Who approved, when, exact version approved |
| `parent_version` | str | If superseded, the version it replaced |
| `rollback_to` | str | If superseded, which version to roll back to |

## Trigger and applicability (E3-05)

| Field | Type | Description |
|---|---|---|
| `trigger` | str | Natural-language trigger phrase |
| `non_applicable_when` | list[str] | Keywords/patterns that suppress the skill |
| `allowed_tools` | list[str] | Tools the skill is permitted to invoke |
| `input_schema` | dict | Expected input format |
| `output_schema` | dict | Expected output format |
| `risk` | SkillRisk | LOW / MEDIUM / HIGH |
| `network` | bool | Whether the skill may make network calls |
| `write` | bool | Whether the skill may write to disk |

## Evidence and checks (E3-06)

| Field | Type | Description |
|---|---|---|
| `success_criteria` | list[str] | Assertions that must pass after execution |
| `failure_criteria` | list[str] | Assertions that indicate failure |
| `expected_effect` | str | Human-readable description of expected outcome |
| `replay_trace_id` | str | Trace ID from positive replay |

## Persistence

New columns on `skills` table:
- `state` TEXT NOT NULL DEFAULT `candidate`
- `skill_version` TEXT NOT NULL DEFAULT `1.0.0`
- `review_record` TEXT (JSON)
- `approval_record` TEXT (JSON)
- `parent_version` TEXT
- `rollback_to` TEXT
- `allowed_tools` TEXT (JSON array)
- `non_applicable_when` TEXT (JSON array)
- `input_schema` TEXT (JSON)
- `output_schema` TEXT (JSON)
- `success_criteria` TEXT (JSON)
- `failure_criteria` TEXT (JSON)

Migration is **additive only**: existing rows get `state='active'`,
`skill_version='1.0.0'`, empty review/approval records. No data loss. No
column drops.

## Backward compatibility

- `SkillManifest.enabled` still exists but is **not sufficient** for execution.
  The `state` check gates execution.
- `list_skills(enabled_only=True)` filters on BOTH `enabled` AND `state='active'`.
- `get_skill(name)` returns only ACTIVE skills.
- Legacy skills (no `state` column) are treated as `ACTIVE` via migration.

## Single-authority gate

Skill execution requires ALL of:
1. Manifest `enabled == True`
2. Manifest `state == ACTIVE`
3. Policy allows required capabilities
4. Autonomy budget available
5. No `non_applicable_when` pattern matches

This is enforced in `PawRuntime._select_action` and `SkillSelector.select`.
