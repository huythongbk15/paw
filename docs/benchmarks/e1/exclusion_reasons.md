# E1-18 / E1-19 / E1-20: Exclusion Reasons, Re-Budget, Over-Budget Rejection

This document covers three related items:

- **E1-18** — the closed set of exclusion / compression
  reasons the runtime records on every dropped
  candidate;
- **E1-19** — the re-budgeting that happens after a
  skill body is upgraded from Level 0 to Level 1;
- **E1-20** — the strict rejection of a final payload
  that still exceeds the approved budget after
  re-budgeting.

## Why these contracts exist

The pre-existing `_allocate_budget` already records an
`excluded_reason` on every dropped candidate (the
`token_budget_exceeded` / `max_sources_exceeded` /
`content_too_large` strings). The E1-18 contract pins
the *closed set* of those reasons: a reviewer who
inspects a manifest knows every possible reason the
runtime can give, no more. The E1-19 contract pins the
*post-skill-upgrade re-budget*: the runtime must
re-allocate after loading full skill bodies, not
before. The E1-20 contract pins the *strict* posture:
when the re-budget cannot bring the payload back under
the limit, the runtime raises `BudgetExceededError`
rather than silently dropping.

The three contracts share one shape: the closed set
of `EXCLUDED_REASONS`, the `BudgetExceededError`
exception, and the new `compile_manifest` method on
`ContextCompiler` that returns a `ContextManifest` (the
E1-16 type) and enforces the contract.

## Canonical location

- The closed set `EXCLUDED_REASONS` and the
  `BudgetExceededError` exception live in
  `paw.core.context_compiler` (the existing module
  that owns `ContextCompiler` and `ContextManifest`).
- The new `compile_manifest` method lives on
  `ContextCompiler` in the same module.

## Closed set of exclusion / compression reasons

```python
EXCLUDED_REASONS: frozenset[str] = frozenset(
    {
        # E1-18 hard reasons: the candidate was dropped
        # because the budget cannot accommodate it.
        "max_sources_exceeded",       # already in _allocate_budget
        "token_budget_exceeded",      # already in _allocate_budget
        "content_too_large",          # already in _allocate_budget
        # E1-19 soft reasons: the candidate was kept
        # but compressed so the budget can accommodate it.
        "body_skipped_exceeds_max_content_length",  # in _build_context
    }
)
```

The contract is the closed set; adding a new reason
is a change-control surface that requires updating
this spec and the contract test in the same change.

## `BudgetExceededError`

```python
class BudgetExceededError(Exception):
    """Raised by ``ContextCompiler.compile_manifest``
    when the final payload still exceeds the approved
    budget after re-budgeting.

    The exception carries the post-re-budget token
    total so the caller can decide whether to widen
    the budget or trim the query.
    """
    def __init__(self, final_tokens: int, max_tokens: int, task_id: str):
        super().__init__(
            f"context manifest for task {task_id!r} is "
            f"{final_tokens} tokens; budget is {max_tokens}"
        )
        self.final_tokens = final_tokens
        self.max_tokens = max_tokens
        self.task_id = task_id
```

The exception carries the numbers so a reviewer can
inspect the over-budget case without re-running the
compiler.

## `compile_manifest` signature

```python
async def compile_manifest(
    self,
    task_id: str,
    query: str,
    *,
    session_id: str | None = None,
    budget: ContextBudget | None = None,
    execution_profile: ExecutionProfile | None = None,
) -> ContextManifest:
    """Compile a ``ContextManifest`` for a task.

    The function is the E1-13 + E1-16 + E1-18 + E1-19 +
    E1-20 entry point: it runs the full compiler
    pipeline (candidate retrieval -> re-budgeting ->
    skill body upgrade -> final post-rebudget check)
    and returns the manifest.

    When the final payload still exceeds
    ``budget.max_tokens`` after re-budgeting, the
    function raises ``BudgetExceededError``; the
    caller is responsible for catching the exception
    and deciding whether to widen the budget or trim
    the query.
    """
```

The function reuses the existing ``_allocate_budget``
and ``_build_context`` internals; the new work is the
post-re-budget ``BudgetExceededError`` check and the
``ContextManifest`` return type.

## Phase 4 sync contract

This document is the **source of truth** for E1-18,
E1-19, and E1-20. The companion contract test
`tests/test_e1_18_19_20_budget_contract.py` enforces
the closed set, the exception, and the final
over-budget rejection.