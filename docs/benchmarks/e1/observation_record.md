# E1-29 Capture Current Behavior or Reproduced Root Cause with Source Locations

This document is the **E1-29 deliverable**. It defines
the `Observation` dataclass that pins a "current
behavior" or "reproduced root cause" record to
file + line + column.

## Why this contract exists

The E1-09 / E1-10 / E1-11 / E1-12 views tell the runtime
*what* the code looks like; E1-29 is the contract for
*what was true at a particular moment*. A reviewer who
writes an E2 analysis says "the bug was here: src/foo.py:42";
the E1-29 record is the typed surface for that statement.

The contract is small: one dataclass, one helper
function. The point is the change-control surface:
a reviewer who sees an `Observation` knows the schema
without re-reading the source.

## Canonical location

`Observation` is a new frozen dataclass in
`paw.knowledge.observations` (a new module). The
helper `make_observation` constructs the record from
a free-form description, a file path, a line, and a
column.

## `Observation` shape

```python
@dataclass(frozen=True)
class Observation:
    """A pinned "current behavior" or "reproduced root
    cause" record.

    ``kind`` is one of:
    - ``"behavior"``: what the code does today
      (e.g. "the compiler silently drops over-budget
      candidates").
    - ``"root_cause"``: the cause of a bug
      (e.g. "missing branch in
      _allocate_budget: tokens > max_content_length
      with empty reference is dropped silently").

    ``description`` is the human-readable text the
    reviewer wrote. ``file`` + ``line`` + ``col`` is
    the source location the observation is about
    (the line is 1-based; the column is 0-based).
    """
    kind: str
    description: str
    file: str
    line: int
    col: int = 0
```

## Phase 4 sync contract

This document is the **source of truth** for E1-29.
The companion contract test
`tests/test_e1_29_observation_contract.py`
enforces the cases above.