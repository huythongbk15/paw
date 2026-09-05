"""E1-24 contract test: measure cold + warm cloud input tokens against the frozen baseline.

The contract is documented in
``docs/benchmarks/e1/token_measurement.md``.
The test pins:

- ``measure_tokens`` returns a ``TokenResult``;
- the baseline is the sum of every expected-evidence
  ``value`` length / 3 (the same heuristic the
  ``TokenEstimator`` uses);
- the measured is the manifest's ``final_tokens``;
- the reduction is ``(baseline - measured) / baseline``;
- the warm measurement is the same function with the
  same input (deterministic).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from paw.bench.tokens import TokenResult, measure_tokens
from paw.core.context import ContextBudget
from paw.core.context_compiler import ContextManifest


def _case_with_expected(expected: list[str]) -> MagicMock:
    case = MagicMock()
    case.case_id = "t1"
    case.goal = "hello"
    case.expected_evidence = [MagicMock(value=v) for v in expected]
    return case


def _manifest_with_tokens(final_tokens: int) -> ContextManifest:
    return ContextManifest(
        task_id="t1",
        budget=ContextBudget(max_tokens=12000),
        final_tokens=final_tokens,
    )


# --- 1. TokenResult shape -------------------------------------


def test_token_result_shape() -> None:
    r = TokenResult(
        case_id="t1",
        mode="cold",
        baseline_tokens=100,
        measured_tokens=70,
        reduction=0.3,
        duration_ms=10,
    )
    assert r.case_id == "t1"
    assert r.baseline_tokens == 100
    assert r.measured_tokens == 70
    assert abs(r.reduction - 0.3) < 1e-9


# --- 2. measure_tokens: baseline = sum(len/3) -----------------


async def test_baseline_uses_len_div_3() -> None:
    # Three expected values of length 30 each: baseline
    # = 10 + 10 + 10 = 30 tokens.
    case = _case_with_expected(["a" * 30, "b" * 30, "c" * 30])

    class _StubCompiler:
        async def compile_manifest(self, *, task_id, query, session_id=None, budget=None):
            return _manifest_with_tokens(15)

    compiler = _StubCompiler()
    result = await measure_tokens(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    assert result.baseline_tokens == 30
    assert result.measured_tokens == 15
    assert abs(result.reduction - 0.5) < 1e-9


# --- 3. measure_tokens: regression (measured > baseline) -----


async def test_regression_detected() -> None:
    case = _case_with_expected(["a" * 30])  # baseline 10

    class _StubCompiler:
        async def compile_manifest(self, *, task_id, query, session_id=None, budget=None):
            return _manifest_with_tokens(20)  # measured 20 > baseline 10

    compiler = _StubCompiler()
    result = await measure_tokens(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    assert result.reduction < 0  # regression


# --- 4. measure_tokens: empty expected evidence ------------


async def test_empty_expected_evidence() -> None:
    case = _case_with_expected([])

    class _StubCompiler:
        async def compile_manifest(self, *, task_id, query, session_id=None, budget=None):
            return _manifest_with_tokens(0)

    compiler = _StubCompiler()
    result = await measure_tokens(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    assert result.baseline_tokens == 0
    assert result.reduction == 0.0


# --- 5. Determinism --------------------------------------


async def test_deterministic() -> None:
    case = _case_with_expected(["a" * 30])

    class _StubCompiler:
        async def compile_manifest(self, *, task_id, query, session_id=None, budget=None):
            return _manifest_with_tokens(15)

    compiler = _StubCompiler()
    a = await measure_tokens(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    b = await measure_tokens(
        case, compiler=compiler, repo_root=Path(), mode="cold"
    )
    assert a == b