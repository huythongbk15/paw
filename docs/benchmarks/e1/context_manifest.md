# E1-16 Context Manifest through Existing Context Contracts

This document is the **E1-16 deliverable**. It defines
the `ContextManifest` aggregate that the E1-17 per-item
record, the E1-18 exclusion reasons, the E1-19
re-budgeting, and the E1-20 over-budget rejection all
read from / write to. The aggregate is a *snapshot* of
the E1-09 / E1-10 / E1-11 / E1-12 views, clipped to a
budget, with the per-item provenance a reviewer
needs to explain why a file / symbol / test is in
the final manifest.

## Why this contract exists

The existing `TaskContext` is the *runtime* view: the
fragments a `PawRuntime` carries into a step. The
*manifest* is a different object: a structured snapshot
a reviewer can inspect *before* the context is used,
with the per-item source / hash / score / privacy /
reason fields the runtime needs to gate a remote
inference. E1-21 (gate remote disclosure) and the
future change-impact analysis read the manifest, not
the `TaskContext`.

The aggregate is the change-control surface for the
E1-17 / E1-18 / E1-19 / E1-20 items: every later item
in the cluster reads from or writes to the same
`ContextManifest` shape. A reviewer who sees a
manifest knows the *full* contract: what is in it, what
is excluded, why each item is there.

## Canonical location

`ContextManifest` is a new dataclass in
`paw.core.context_compiler` (the existing module that
owns `ContextCandidate`, `ContextPlan`, and
`ContextCompiler`). The dataclass is the canonical
manifest shape; the E1-16 contract is the "what is the
shape" and the E1-17 contract is the "what is the
per-item record".

## `ContextManifest` shape

```python
@dataclass(frozen=True)
class ContextManifest:
    """A snapshot of the items a context compiler
    selected for a task, clipped to a budget.

    Every field is the change-control surface for a
    later E1 item: ``included`` is the E1-17 per-item
    record, ``excluded`` is the E1-18 reason, the budget
    fields are the E1-13 ceiling, the snapshot fields
    are the E1-09 / E1-10 / E1-11 / E1-12 inputs.
    """
    task_id: str
    budget: ContextBudget
    included: tuple[ContextCandidate, ...] = ()
    excluded: tuple[ContextCandidate, ...] = ()
    # E1-09 / E1-10 / E1-11 / E1-12 snapshots.
    recent_changes: tuple[RecentChange, ...] = ()
    affected_areas: tuple[AffectedArea, ...] = ()
    symbols: tuple[SymbolRecord, ...] = ()
    test_links: tuple[TestLink, ...] = ()
    dependency_edges: tuple[DependencyEdge, ...] = ()
    # Provenance: the inputs the compiler used to
    # build the manifest. ``scan_paths`` is the
    # E1-05 / E1-08 input; ``repo_filter`` is the
    # E1-04 input.
    scan_paths: tuple[str, ...] = ()
    repo_filter_repr: str = ""
    # E1-20: a payload whose token total exceeds
    # ``budget.max_tokens`` after re-budgeting raises
    # ``BudgetExceededError``; the manifest records
    # ``final_tokens`` so the exception message is
    # inspectable.
    final_tokens: int = 0
```

The dataclass is frozen; a new manifest is a new
dataclass instance.

## Phase 4 sync contract

This document is the **source of truth** for E1-16.
The companion contract test
`tests/test_e1_16_context_manifest_contract.py`
enforces the shape.