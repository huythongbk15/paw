# E1-23 Measure Cold and Warm Required-Evidence Recall on Every E0 Case

This document is the **E1-23 deliverable**. It defines
the contract for the cold + warm recall measurement
the runtime runs on every E0 case.

## Why this contract exists

The E0 acceptance criterion for the benchmark is that
every case produces `outcome=SUCCESS` with the expected
evidence. The E1 acceptance criterion (from the
roadmap) is "at least 95% required-evidence recall on
the versioned benchmark". The E1-23 contract is the
*measurement*: the runtime produces a recall number
for every E0 case, in two modes:

- **cold** — the runtime's context cache is empty; the
  compiler starts from the source files.
- **warm** — the runtime's context cache is warm; the
  compiler reuses the cached derived records
  (E1-14 + E1-15).

The two numbers together tell the reviewer "how
effective is the cache + the budget + the gate
together, end-to-end".

## Canonical location

`measure_recall` is a new function in
`paw.bench.recall` (a new module under the existing
`paw/bench/` package). The function takes a case
manifest + the runtime's compiler + a `mode` flag
(`cold` or `warm`) and returns a `RecallResult`
record.

## Signature

```python
async def measure_recall(
    case: CaseManifest,
    *,
    compiler: ContextCompiler,
    repo_root: Path,
    mode: Literal["cold", "warm"],
) -> RecallResult:
    """Measure the recall of a single E0 case.

    Recall is the fraction of expected-evidence items
    the compiler's manifest can recall. A case with
    3 expected evidence items where the manifest
    includes 2 has recall = 2/3 = 0.667.

    ``mode`` is ``"cold"`` (no cache) or ``"warm"``
    (the E1-14 derived records are pre-loaded). The
    cold measurement is the harder of the two; the
    warm measurement is what the runtime achieves in
    a real session.
    """
```

## `RecallResult` shape

```python
@dataclass(frozen=True)
class RecallResult:
    case_id: str
    mode: str  # "cold" | "warm"
    total_evidence: int
    recalled: int
    missed: tuple[str, ...]  # the missed evidence targets
    recall: float  # recalled / total_evidence
    duration_ms: int
```

The ``missed`` list is the change-control surface: a
reviewer who sees a miss can decide whether the
heuristic is the cause or the manifest is the cause.
The E1-25 contract is the "review every miss" loop.

## Negative cases

| Case | Expected result |
|---|---|
| Case with 0 expected evidence | `recall=1.0` (vacuous). |
| Case where all evidence is recalled | `recall=1.0`, `missed=()`. |
| Cold vs warm | The warm measurement is `>=` the cold measurement for the same case. |

## Phase 4 sync contract

This document is the **source of truth** for E1-23.
The companion contract test
`tests/test_e1_23_recall_measurement_contract.py`
enforces the cases above.