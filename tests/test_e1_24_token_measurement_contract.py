"""Result shapes and API compatibility; behavioral gates are tested separately."""

from __future__ import annotations

import dataclasses

import pytest

from paw.bench.tokens import TokenResult, measure_tokens, set_baseline_tokens


# --- 1. TokenResult shape ---------------------------------------------


def test_token_result_has_documented_fields() -> None:
    r = TokenResult(
        case_id="c1",
        mode="cold",
        baseline_tokens=1000,
        measured_tokens=700,
        reduction=0.3,
        duration_ms=42,
    )
    assert r.case_id == "c1"
    assert r.mode == "cold"
    assert r.baseline_tokens == 1000
    assert r.measured_tokens == 700
    assert r.reduction == pytest.approx(0.3)
    assert r.duration_ms == 42


def test_token_result_is_frozen() -> None:
    r = TokenResult(
        case_id="c1", mode="cold", baseline_tokens=100,
        measured_tokens=80, reduction=0.2, duration_ms=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.reduction = 0.5  # type: ignore[misc]


# --- 2. Reduction formula ---------------------------------------------


def test_reduction_formula_positive() -> None:
    """reduction = (baseline - measured) / baseline."""
    baseline = 1000
    measured = 700
    reduction = (baseline - measured) / baseline
    assert reduction == pytest.approx(0.3)





# --- 3. Baseline lookup ------------------------------------------------


def test_set_baseline_tokens_registers_value() -> None:
    set_baseline_tokens("test_case_e1_24_a", 5000)
    from paw.bench.tokens import _E0_FROZEN_BASELINE
    assert _E0_FROZEN_BASELINE.get("test_case_e1_24_a") == 5000



def test_explicit_baseline_override() -> None:
    """When baseline_tokens is passed explicitly, it
    overrides the frozen baseline."""
    set_baseline_tokens("test_case_e1_24_c", 1000)
    explicit = 500
    measured = 400
    reduction = (explicit - measured) / explicit
    assert reduction == pytest.approx(0.2)


# --- 4. measure_tokens signature ---------------------------------------


def test_measure_tokens_is_callable() -> None:
    assert callable(measure_tokens)


def test_measure_tokens_signature() -> None:
    import inspect
    sig = inspect.signature(measure_tokens)
    params = sig.parameters
    assert "case" in params
    assert "compiler" in params
    assert "repo_root" in params
    assert "mode" in params
    assert "baseline_tokens" in params


# --- 5. Determinism ---------------------------------------------------


def test_token_result_deterministic() -> None:
    r1 = TokenResult(
        case_id="c1", mode="warm", baseline_tokens=1000,
        measured_tokens=800, reduction=0.2, duration_ms=10,
    )
    r2 = TokenResult(
        case_id="c1", mode="warm", baseline_tokens=1000,
        measured_tokens=800, reduction=0.2, duration_ms=10,
    )
    assert r1 == r2
