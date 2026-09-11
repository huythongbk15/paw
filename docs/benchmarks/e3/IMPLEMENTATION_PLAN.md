# E3 Implementation Plan — 2026-09-11

## Current state

**Already implemented (D1/D2):**
- `SkillState` enum (candidate/reviewed/active/rejected/deprecated/superseded) — E3-02
- `ReviewRecord` / `ApprovalRecord` dataclasses — E3-04
- `SkillManifest` E3 fields: `allowed_tools`, `non_applicable_when`,
  `input_schema`, `output_schema`, `success_criteria`, `failure_criteria`,
  `expected_effect`, `review_record`, `approval_record`, `parent_version`,
  `rollback_to` — E3-05, E3-06
- `SkillFabric` lifecycle methods: `approve_skill` (E3-18), `reject_skill`
  (E3-13), `deprecate_skill` (E3-21), `rollback_skill` (E3-19) — E3-18/19/21
- Database schema: `skills` table with all E3 columns + triggers — storage.py

**Missing (the gaps):**
- E3-03: Legal transitions table (no formal definition; implicit in lifecycle methods)
- E3-07: Proof that facts/preferences cannot be normalized into active skills
- E3-08: Select one repeated workflow from verified E0-E2 traces
- E3-09: Trace → candidate draft with source links
- E3-10: Redact secrets and private payloads before persistence
- E3-11: Detect duplicate and overlapping trigger candidates
- E3-12: Present candidate diff, provenance and expected effect for approval
- E3-14: Replay path that cannot mutate reviewed benchmark fixtures
- E3-15: Positive replay against source workflow
- E3-16: Negative applicability case
- E3-17: Compare verified outcome, tokens, intervention with no-skill baseline
- E3-20: Record selection precision, failures and maintenance cost per version
- E3-22: Expose skill state, source, replay and version in inspect output
- E3-23: E3 integration pack
- E3-24: Prove candidate trace preserves research, decision, implementation, verification links
- E3-25: Migrate governance; prove `enabled` and legacy registry cannot bypass reviewed ACTIVE

## E3 build plan (ordered by dependency)

### Phase A: Legal transitions + governance (D1)
1. E3-03: Define `LEGAL_SKILL_TRANSITIONS` in `reasoning_contracts.py` + enforce in `SkillFabric.approve_skill/reject_skill/deprecate_skill`
2. E3-07: Add `normalize_fact_to_skill` guard — explicitly refuse facts/memory → skill conversion

### Phase B: Candidate creation pipeline (D2)
3. E3-08: `SkillCandidate.from_trace()` — create a candidate from a verified task trace
4. E3-09: Source links preserved (trace task_id, trace revision, source files)
5. E3-10: `redact_payload()` — redact secrets/private paths from skill body
6. E3-11: `detect_duplicate_candidates()` — exact dup + overlap detection by trigger
7. E3-12: `generate_skill_diff()` — candidate diff + provenance summary

### Phase C: Replay + evaluation (D2)
8. E3-14: Replay path uses read-only test double (cannot mutate benchmark)
9. E3-15: Positive replay against source workflow
10. E3-16: Negative applicability case
11. E3-17: Compare with no-skill baseline

### Phase D: Integration + migration (D3)
12. E3-20: Selection precision per version (E3-08 trace → measurement)
13. E3-22: Inspect output shows skill state, source, replay, version
14. E3-24: Trace links preserved through candidate → review → approval chain
15. E3-25: Prove `enabled` and legacy registry table cannot bypass reviewed ACTIVE
16. E3-23: E3 integration pack (1 D3 test)

## E4 — Controlled local model adaptation

E4 entry conditions require E0–E3 pass + non-trained local baseline + cloud teacher baseline.
The cloud teacher baseline (E4-11) requires provider integration (out of scope per AGENTS.md).
However, the **dataset governance foundation (E4-01..09)** and **local baseline measurement (E4-10)**
are feasible and useful independently.

### E4 feasible work (D0–D2)
- E4-01: Verify E0–E3 gates, identify one repeated narrow role
- E4-03: Record dataset scope, consent, retention, deletion
- E4-04: Versioned example schema with full lineage
- E4-05: Export successful reviewed traces through deterministic filter
- E4-06: Redact credentials, private paths, raw conversation
- E4-09: Freeze dataset hash, version, build manifest
- E4-10: Measure deterministic and non-trained local baselines

### E4 out of scope (blocked)
- E4-02: Can be documented (theoretical)
- E4-07: Manual audit (feasible but optional)
- E4-08: Train/validation/test split (feasible)
- E4-11 onward: Requires cloud training infrastructure (explicitly out of scope)

## Test plan

Each phase produces contract tests (~20% of items):
- Phase A: `test_e3_transitions.py` (D1)
- Phase B: `test_e3_candidate_pipeline.py` (D2)
- Phase C: `test_e3_replay.py` (D2)
- Phase D: `test_e3_integration_pack.py` (D3)

Total: ~40 E3 tests expected.
