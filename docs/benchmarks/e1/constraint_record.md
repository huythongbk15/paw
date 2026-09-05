# E1-30 Capture Hard Constraints, Goals and Non-Goals

This document is the **E1-30 deliverable**. It defines
the `Constraint` dataclass that captures a hard
constraint, a goal, or a non-goal — the three things
the E2 decision-evidence view needs to know about a
project.

## Why this contract exists

The E2 readiness criteria say: a decision must identify
which project evidence supports or contradicts it. To
make that judgment, the runtime needs to know the
project's hard constraints (e.g. "no shell exec"), the
goals (e.g. "reduce cold-start latency by 50%"), and
the non-goals (e.g. "the LLM is not retrained"). The
E1-30 contract is the typed surface for these three
kinds of statement.

The contract is the *type*; the *capture* is a future
item. E1-30 is the change-control surface for
"what kinds of decision inputs does the project
recognize".

## Canonical location

`Constraint` is a new frozen dataclass in
`paw.knowledge.constraints` (a new module). The
helper `make_constraint` constructs the record.

## `Constraint` shape

```python
@dataclass(frozen=True)
class Constraint:
    """A hard constraint, a goal, or a non-goal.

    ``kind`` is one of:
    - ``"constraint"``: a hard rule the runtime must
      respect (e.g. "no shell exec", "no
      NETWORK_HTTP without approval"). The kind maps
      to the existing ``Capability`` enum the policy
      gate already enforces.
    - ``"goal"``: a measurable target
      (e.g. "30% lower median cloud input tokens",
      "95% required-evidence recall").
    - ``"non_goal"``: an out-of-scope item
      (e.g. "the LLM is not retrained", "the
      runtime does not vendor a model").

    ``description`` is the human-readable text the
    reviewer wrote. ``metric`` is the optional
    measurement (e.g. ``"30%"`` for a goal); ``None``
    for constraints and non-goals.
    """
    kind: str
    description: str
    metric: str | None = None
```

## Phase 4 sync contract

This document is the **source of truth** for E1-30.
The companion contract test
`tests/test_e1_30_constraint_contract.py`
enforces the cases above.