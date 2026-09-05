# E1-27 E1 Integration Pack + Gate Decision

This document is the **E1-27 deliverable**. It records
the integration pack that runs every E0 case through
the E1 compiler pipeline (recall + token measurement
+ gate) and produces a gate decision.

## Why this contract exists

The E1 acceptance target lists several measurable
properties (≥95% recall, ≥30% token reduction, no
unauthorized actions, every byte attributable to a
manifest). The E1-27 contract is the *integration*:
a single invocation that runs the recall + token
measurement + gate pipeline against every E0 case and
records a `VERIFIED` / `PARTIAL` / `FAIL` gate
decision.

The decision is the change-control surface: a reviewer
who sees `VERIFIED` knows the E1 work is done; a
reviewer who sees `PARTIAL` knows which contracts
fell short and which case the runtime failed on.

## Canonical location

`run_integration_pack` is a new function in
`paw.bench.integration` (a new module under
`paw/bench/`). The function takes the E0 case
directory + a `ContextCompiler` and returns an
`IntegrationResult` record + a markdown report.

## `IntegrationResult` shape

```python
@dataclass(frozen=True)
class IntegrationResult:
    case_count: int
    recall_results: tuple[RecallResult, ...]
    token_results: tuple[TokenResult, ...]
    gate_decision: str  # "VERIFIED" | "PARTIAL" | "FAIL"
    gate_reasons: tuple[str, ...]
    report_path: Path  # the markdown report on disk
```

The ``gate_decision`` is:

- ``"VERIFIED"`` when every E0 case has
  ``recall >= 0.95`` and ``reduction >= 0.0`` (the
  warm measurement is not worse than the baseline)
  and every manifest passes the E1-21 gate (no
  refused items on a `cloud_unapproved` provider).
- ``"PARTIAL"`` when at least one contract is met but
  not all.
- ``"FAIL"`` when at least one E0 case has
  ``recall < 0.5`` (the runtime is regressing vs the
  E0 frozen baseline).

The contract test pins the gate thresholds; the
*actual* numbers are recorded in
`docs/benchmarks/e1/integration_pack_run.md`.

## Phase 4 sync contract

This document is the **source of truth** for E1-27.
The companion contract test
`tests/test_e1_27_integration_pack_contract.py`
enforces the gate decision rules.