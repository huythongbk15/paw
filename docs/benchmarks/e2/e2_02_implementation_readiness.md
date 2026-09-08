# E2-02..04 — Cognitive roles and task-signal contracts

**Review date:** 2026-09-08  
**Baseline:** `2c4a81f` plus the working tree  
**Prerequisite:** E0 + E1 `VERIFIED` before activation  
**Current result:** `PARTIAL` — value contracts are tested, E1 remains
unverified, and there is no E2 runtime wiring.

The historical filename is retained to avoid breaking references. This file
does **not** define `ImplementationReadiness`; that lifecycle belongs to
E2-25..E2-28 and E2-47. It also does not authorize routing, escalation,
persistence or provider calls.

## Ownership

| Concept | Canonical owner | Current boundary |
|---|---|---|
| Historical model-routing vocabulary | `paw.core.models.ModelRole` | Existing manifest compatibility; no new enum. |
| E2 cognitive role contract | `paw.core.reasoning_contracts.RoleContract` | One immutable registry, imported explicitly from its owner. |
| Privacy taxonomy | `paw.core.privacy.PrivacyClass` | Reused by task signals; there is no `PrivacyLevel`. |
| E2 task signals | `paw.core.reasoning_contracts.TaskSignals` | Immutable value input only; no decision method. |
| Research-depth classification | Future E2-29 owner | Not implemented by E2-04. |
| Escalation decision | Runtime/Autonomy/Model Router split in Architecture | Not implemented by E2-04. |

`paw.core.__all__` remains the ratified eleven-symbol runtime surface. E2
contracts are module-level expert APIs and do not widen the package root.

## E2-02: minimum cognitive roles

PAW reuses four existing `ModelRole` values for the minimum engineering loop:

| Role | Engineering use |
|---|---|
| `FAST` | Bounded classification and concise synthesis for low-risk work. |
| `REASONING` | Research, diagnosis and architecture option assessment. |
| `CODING` | Source-backed implementation or review proposals. |
| `TOOLS` | Structured operation proposals; never execution authority. |

`VISION` and `EMBEDDING` are modalities/capabilities, not separate cognitive
roles in this minimum set. `FALLBACK` is routing behavior, not a cognitive role.
They remain valid historical `ModelManifest.roles` values for compatibility.

## E2-03: output, evidence and uncertainty

Each selected role has one frozen `RoleContract` containing:

- role description and benchmark/application tags;
- typed output-schema identifier;
- whether evidence and citations are mandatory;
- allowed evidence categories;
- whether uncertainty is reported and a bounded minimum confidence;
- the required low-confidence disposition: `STOP`, `ASK` or `ESCALATE`.

The reasoning role returns a `reasoning_assessment`, not hidden chain-of-thought.
The assessment is expected to expose evidence references, option conclusions,
important uncertainty and a proposed next action. It cannot authorize a tool or
project mutation. Coding output is an `implementation_proposal` and requires
project/test/decision evidence plus citations.

The registry is a `MappingProxyType`, the contracts are frozen dataclasses, and
construction rejects invalid thresholds, citations without evidence, or an
evidence-requiring role without allowed evidence types.

## E2-04: task signals

`TaskSignals` records the inputs later E2 items may consume:

- novelty: `UNKNOWN`, `ROUTINE`, `FAMILIAR`, `NOVEL`, `UNPRECEDENTED`;
- impact: `UNKNOWN`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`;
- privacy: canonical `PrivacyClass`;
- context sufficiency: `UNKNOWN`, `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`;
- remaining budget: `UNKNOWN`, `WITHIN_LIMIT`, `NEAR_LIMIT`, `EXHAUSTED`;
- optional uncertainty score in `[0, 1]` and non-negative token estimate.

Unknown defaults are deliberate. Missing reconnaissance must not look like a
routine, public, low-impact task. `TaskSignals.complete` reports only whether
all inputs are present; it does not classify `FAST`/`STANDARD`/`DEEP`, request
escalation or select a model. Those behaviors remain E2-29, E2-11 and E2-06.

## Acceptance evidence

The focused contract set is:

```bash
python -m pytest -q \
  tests/test_e2_02_cognitive_roles.py \
  tests/test_e2_03_role_contracts.py \
  tests/test_e2_04_task_signals.py \
  tests/test_planning_contract.py \
  tests/test_e1_03_privacy_contract.py
python -m ruff check \
  src/paw/core/reasoning_contracts.py \
  src/paw/core/models.py src/paw/core/__init__.py \
  tests/test_e2_02_cognitive_roles.py \
  tests/test_e2_03_role_contracts.py \
  tests/test_e2_04_task_signals.py
```

Passing this set makes only the isolated value-contract repair `PASS`. E2-02,
E2-03 and E2-04 remain unchecked in the execution tracker until E1 is
`VERIFIED` and the contracts are re-approved on that revision.
