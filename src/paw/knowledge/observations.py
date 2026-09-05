"""PAW Knowledge — observation records (E1-29).

``Observation`` is a frozen dataclass that pins a
"current behavior" or "reproduced root cause" record
to file + line + column. See
``docs/benchmarks/e1/observation_record.md`` for the
full contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    """A pinned "current behavior" or "reproduced root
    cause" record.

    ``kind`` is one of:
    - ``"behavior"``: what the code does today.
    - ``"root_cause"``: the cause of a bug.

    ``description`` is the human-readable text the
    reviewer wrote. ``file`` + ``line`` + ``col`` is
    the source location the observation is about
    (line is 1-based; col is 0-based).
    """

    kind: str
    description: str
    file: str
    line: int
    col: int = 0


__all__ = ["Observation"]
