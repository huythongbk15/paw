"""E1-29 contract test: observation records (current behavior / root cause).

The contract is documented in
``docs/benchmarks/e1/observation_record.md``.
The test pins:

- the ``Observation`` shape (5 fields, frozen);
- the closed set of ``kind`` values
  (``behavior``, ``root_cause``);
- the default ``col=0``;
- the equality contract (frozen + hashable).
"""

from __future__ import annotations

import dataclasses

import pytest

from paw.knowledge.observations import Observation


# --- 1. Shape -------------------------------------------------


def test_observation_fields() -> None:
    obs = Observation(
        kind="behavior",
        description="the compiler silently drops over-budget candidates",
        file="src/paw/core/context_compiler.py",
        line=678,
        col=12,
    )
    assert obs.kind == "behavior"
    assert obs.description == "the compiler silently drops over-budget candidates"
    assert obs.file == "src/paw/core/context_compiler.py"
    assert obs.line == 678
    assert obs.col == 12


# --- 2. Default col is 0 ------------------------------------


def test_default_col_is_zero() -> None:
    obs = Observation(
        kind="behavior",
        description="x",
        file="a.py",
        line=1,
    )
    assert obs.col == 0


# --- 3. Two kinds are supported ----------------------------


def test_behavior_kind() -> None:
    obs = Observation(
        kind="behavior", description="x", file="a.py", line=1,
    )
    assert obs.kind == "behavior"


def test_root_cause_kind() -> None:
    obs = Observation(
        kind="root_cause", description="x", file="a.py", line=1,
    )
    assert obs.kind == "root_cause"


# --- 4. Frozen + hashable -----------------------------------


def test_observation_is_frozen() -> None:
    obs = Observation(
        kind="behavior", description="x", file="a.py", line=1,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs.kind = "root_cause"  # type: ignore[misc]


def test_observation_is_hashable() -> None:
    a = Observation(
        kind="behavior", description="x", file="a.py", line=1,
    )
    b = Observation(
        kind="behavior", description="x", file="a.py", line=1,
    )
    assert hash(a) == hash(b)
    assert a == b


# --- 5. Line is 1-based, col is 0-based ---------------------


def test_line_one_based_col_zero_based() -> None:
    """The contract: ``line`` is 1-based (matches the
    AST / git convention), ``col`` is 0-based."""
    obs = Observation(
        kind="behavior", description="x", file="a.py", line=42, col=7,
    )
    assert obs.line == 42
    assert obs.col == 7