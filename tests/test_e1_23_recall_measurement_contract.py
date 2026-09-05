"""E1-23 contract test: measure cold + warm required-evidence recall on E0 cases.

The contract is documented in
``docs/benchmarks/e1/recall_measurement.md``.
The test pins:

- ``measure_recall`` returns a ``RecallResult``;
- the recall is the fraction of expected-evidence
  values present in the manifest;
- a case with 0 expected evidence has ``recall=1.0``;
- the warm measurement is the same function with the
  same input (deterministic).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from paw.bench.recall import RecallResult, measure_recall
from paw.core.context_compiler import (
    ContextCandidate,
    ContextCompiler,
    ContextManifest,
)


def _case_with_expected(expected: list[str]) -> MagicMock:
    """A minimal E0 case mock: ``expected_evidence`` is
    a list of objects with a ``.value`` attribute."""
    case = MagicMock()
    case.case_id = "t1"
    case.goal = "hello"
    case.expected_evidence = [MagicMock(value=v) for v in expected]
    return case


def _manifest_with(text: str) -> ContextManifest:
    from paw.core.context import ContextBudget

    return ContextManifest(
        task_id="t1",
        budget=ContextBudget(max_tokens=12000),
        included=(
            ContextCandidate(
                source="x", source_id="a", content=text, token_estimate=10,
            ),
        ),
    )


# --- 1. RecallResult shape ---------------------------------------


def test_recall_result_shape() -> None:
    from paw.core.context import ContextBudget

    r = RecallResult(
        case_id="t1",
        mode="cold",
        total_evidence=3,
        recalled=2,
        missed=("c",),
        recall=2/3,
        duration_ms=10,
    )
    assert r.case_id == "t1"
    assert r.mode == "cold"
    assert r.total_evidence == 3
    assert r.recalled == 2
    assert r.missed == ("c",)
    assert abs(r.recall - 2/3) < 1e-9


# --- 2. measure_recall: vacuous case (0 expected) -----------------


async def test_recall_vacuous_case() -> None:
    case = _case_with_expected([])
    compiler = ContextCompiler()
    result = await measure_recall(case, compiler=compiler, repo_root=Path(), mode="cold")
    assert result.recall == 1.0
    assert result.missed == ()


# --- 3. measure_recall: full recall -----------------------------


async def test_recall_full_match() -> None:
    case = _case_with_expected(["hello", "world"])
    # Monkey-patch the compiler: the test compiles
    # a real ContextCompiler but the case's goal is
    # a non-matching string; the manifest will be
    # empty. So we wrap the compiler.
    captured: dict = {}

    class _StubCompiler:
        async def compile_manifest(self, *, task_id, query, session_id=None, budget=None):
            captured["query"] = query
            return _manifest_with("hello world")

    compiler = _StubCompiler()
    result = await measure_recall(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    assert result.recalled == 2
    assert result.recall == 1.0
    assert result.missed == ()


# --- 4. measure_recall: partial recall --------------------------


async def test_recall_partial() -> None:
    case = _case_with_expected(["hello", "world"])

    class _StubCompiler:
        async def compile_manifest(self, *, task_id, query, session_id=None, budget=None):
            return _manifest_with("hello")

    compiler = _StubCompiler()
    result = await measure_recall(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    assert result.recalled == 1
    assert abs(result.recall - 0.5) < 1e-9
    assert result.missed == ("world",)


# --- 5. measure_recall: cold vs warm consistency --------------


async def test_recall_deterministic() -> None:
    case = _case_with_expected(["hello"])

    class _StubCompiler:
        async def compile_manifest(self, *, task_id, query, session_id=None, budget=None):
            return _manifest_with("hello")

    compiler = _StubCompiler()
    a = await measure_recall(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    b = await measure_recall(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    assert a == b