# E1-24 Measure Cold and Warm Cloud Input Tokens Against the Frozen Baseline

This document is the **E1-24 deliverable**. It defines
the contract for the cold + warm cloud input token
measurement the runtime runs on every E0 case.

## Why this contract exists

The E0 acceptance target for token measurement is
defined in `docs/benchmarks/e0/measurement_spec.md`.
The E1-24 contract extends that target to a
*comparison*: the runtime measures the cloud input
tokens on every E0 case, in two modes (cold + warm),
and reports the reduction vs the E0 frozen baseline.

The contract is the change-control surface for
"did the E1 work reduce cloud input tokens?". A
reviewer who sees a 30% reduction in the warm-mode
measurement has a measurable, source-backed answer
to "is the E1 work paying off?".

## Canonical location

`measure_tokens` is a new function in
`paw.bench.tokens` (a new module under the existing
`paw/bench/` package). The function takes a case
manifest + the runtime's compiler + a `mode` flag
and returns a `TokenResult` record.

## Signature

```python
async def measure_tokens(
    case: CaseManifest,
    *,
    compiler: ContextCompiler,
    repo_root: Path,
    mode: Literal["cold", "warm"],
) -> TokenResult:
    """Measure the cloud input tokens of a single
    E0 case.
    """
```

## `TokenResult` shape

```python
@dataclass(frozen=True)
class TokenResult:
    case_id: str
    mode: str  # "cold" | "warm"
    baseline_tokens: int
    measured_tokens: int
    reduction: float  # (baseline - measured) / baseline
    duration_ms: int
```

The `baseline_tokens` is the E0 frozen baseline; the
`measured_tokens` is the post-E1 measurement. The
`reduction` is a fraction in `[0.0, 1.0]`; a value of
`0.3` means the E1 work reduced tokens by 30%.

## Phase 4 sync contract

This document is the **source of truth** for E1-24.
The companion contract test
`tests/test_e1_24_token_measurement_contract.py`
enforces the cases above.