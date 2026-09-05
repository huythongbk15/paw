"""PAW Knowledge — constraint records (E1-30).

``Constraint`` is a frozen dataclass that captures a
hard constraint, a goal, or a non-goal. See
``docs/benchmarks/e1/constraint_record.md`` for the
full contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Constraint:
    """A hard constraint, a goal, or a non-goal.

    ``kind`` is one of:
    - ``"constraint"``: a hard rule the runtime must
      respect.
    - ``"goal"``: a measurable target.
    - ``"non_goal"``: an out-of-scope item.

    ``description`` is the human-readable text the
    reviewer wrote. ``metric`` is the optional
    measurement (e.g. ``"30%"`` for a goal); ``None``
    for constraints and non-goals.
    """

    kind: str
    description: str
    metric: str | None = None


__all__ = ["Constraint"]
