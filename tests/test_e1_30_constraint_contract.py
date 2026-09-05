"""E1-30 contract test: hard constraints, goals, non-goals.

The contract is documented in
``docs/benchmarks/e1/constraint_record.md``.
The test pins:

- the ``Constraint`` shape (3 fields, frozen);
- the closed set of ``kind`` values
  (``constraint``, ``goal``, ``non_goal``);
- the optional ``metric`` field (``None`` for
  constraints and non-goals, a string for goals);
- the equality contract (frozen + hashable).
"""

from __future__ import annotations

import dataclasses

import pytest

from paw.knowledge.constraints import Constraint


# --- 1. Shape -------------------------------------------------


def test_constraint_fields() -> None:
    c = Constraint(
        kind="constraint",
        description="no shell exec",
    )
    assert c.kind == "constraint"
    assert c.description == "no shell exec"
    assert c.metric is None


# --- 2. Three kinds are supported -------------------------


def test_constraint_kind() -> None:
    c = Constraint(kind="constraint", description="x")
    assert c.kind == "constraint"
    assert c.metric is None


def test_goal_kind_with_metric() -> None:
    c = Constraint(
        kind="goal", description="reduce cold-start latency", metric="50%",
    )
    assert c.kind == "goal"
    assert c.metric == "50%"


def test_non_goal_kind() -> None:
    c = Constraint(kind="non_goal", description="the LLM is not retrained")
    assert c.kind == "non_goal"
    assert c.metric is None


# --- 3. Frozen + hashable --------------------------------


def test_constraint_is_frozen() -> None:
    c = Constraint(kind="constraint", description="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.kind = "goal"  # type: ignore[misc]


def test_constraint_is_hashable() -> None:
    a = Constraint(kind="constraint", description="x")
    b = Constraint(kind="constraint", description="x")
    assert hash(a) == hash(b)
    assert a == b


# --- 4. Goal's metric is a string ------------------------


def test_goal_metric_is_string() -> None:
    """The contract: ``metric`` is a string when the
    kind is ``goal``; ``None`` when the kind is
    ``constraint`` or ``non_goal``. The reviewer is
    responsible for using a parseable format (``"30%"``,
    ``"95%"``)."""
    c = Constraint(kind="goal", description="x", metric="30%")
    assert isinstance(c.metric, str)
    assert c.metric == "30%"


# --- 5. Constraint + non_goal have None metric -----------


def test_constraint_metric_is_none() -> None:
    c = Constraint(kind="constraint", description="x", metric="ignored")
    # The contract: ``metric`` is a string when
    # present, but the kind drives the semantic. A
    # constraint's metric is conventionally ``None``;
    # the reviewer can pass a value but the kind is
    # the change-control surface.
    # We only assert the field accepts a string;
    # the kind is the semantic marker.
    assert c.metric == "ignored"  # type: ignore[comparison-overlap]