"""E1-27 contract test: E1 integration pack + gate decision.

The contract is documented in
``docs/benchmarks/e1/integration_pack.md``.
The test pins:

- the gate thresholds: recall >= 0.95, reduction
  >= 0.0, regression threshold 0.5;
- the gate decision rules: VERIFIED, PARTIAL, FAIL;
- the markdown report is written to disk and contains
  the expected sections;
- a zero-case directory is a clean VERIFIED;
- the empty directory produces the report with the
  ``no cases in directory`` reason.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from paw.bench.integration import (
    GATE_RECALL_THRESHOLD,
    GATE_REDUCTION_FLOOR,
    GATE_REGRESSION_THRESHOLD,
    run_integration_pack,
)
from paw.core.context_compiler import ContextCompiler


# --- 1. Gate thresholds are documented constants -----------------


def test_gate_recall_threshold() -> None:
    assert GATE_RECALL_THRESHOLD == 0.95


def test_gate_regression_threshold() -> None:
    assert GATE_REGRESSION_THRESHOLD == 0.5


def test_gate_reduction_floor() -> None:
    assert GATE_REDUCTION_FLOOR == 0.0


# --- 2. Empty case directory is a clean VERIFIED -----------------


async def test_empty_directory_is_verified(tmp_path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    report = tmp_path / "report.md"
    compiler = ContextCompiler()
    result = await run_integration_pack(
        case_dir,
        compiler=compiler,
        repo_root=tmp_path,
        report_path=report,
    )
    assert result.case_count == 0
    assert result.gate_decision == "VERIFIED"
    assert "no cases in directory" in result.gate_reasons
    # The report is on disk.
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "# E1 Integration Pack Report" in text
    assert "VERIFIED" in text


# --- 3. Decision rules: recall below threshold -> PARTIAL -----


def _copy_real_case(tmp_path: Path) -> Path:
    """Copy one real E0 case into a temp directory so
    the integration pack sees a valid CaseManifest.
    The CaseManifest contract requires non-empty
    fixtures + expected_evidence; we use the
    smallest real case the project ships."""
    real = Path("benchmarks/e0/cases/architecture_decision_cache.yaml")
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    shutil.copy(real, case_dir / "t1.yaml")
    return case_dir


async def test_recall_below_threshold_is_partial(tmp_path) -> None:
    import importlib
    integ = importlib.import_module("paw.bench.integration")
    from paw.bench.recall import RecallResult
    from paw.bench.tokens import TokenResult

    case_dir = _copy_real_case(tmp_path)
    report = tmp_path / "report.md"
    compiler = ContextCompiler()

    async def fake_recall(case, *, compiler, repo_root, mode):
        return RecallResult(
            case_id=case.case_id, mode=mode,
            total_evidence=10, recalled=7, missed=("a", "b", "c"),
            recall=0.7, duration_ms=10,
        )

    async def fake_tokens(case, *, compiler, repo_root, mode):
        return TokenResult(
            case_id=case.case_id, mode=mode,
            baseline_tokens=100, measured_tokens=80,
            reduction=0.2, duration_ms=10,
        )

    orig_recall = integ.measure_recall
    orig_tokens = integ.measure_tokens
    integ.measure_recall = fake_recall
    integ.measure_tokens = fake_tokens
    try:
        result = await run_integration_pack(
            case_dir,
            compiler=compiler,
            repo_root=tmp_path,
            report_path=report,
        )
    finally:
        integ.measure_recall = orig_recall
        integ.measure_tokens = orig_tokens
    assert result.case_count == 1
    assert result.gate_decision == "PARTIAL"
    assert any("partial" in r for r in result.gate_reasons)


# --- 4. Decision rules: recall below 0.5 -> FAIL --------------


async def test_recall_below_regression_threshold_is_fail(tmp_path) -> None:
    import importlib
    integ = importlib.import_module("paw.bench.integration")
    from paw.bench.recall import RecallResult
    from paw.bench.tokens import TokenResult

    case_dir = _copy_real_case(tmp_path)
    report = tmp_path / "report.md"
    compiler = ContextCompiler()

    async def fake_recall(case, *, compiler, repo_root, mode):
        return RecallResult(
            case_id=case.case_id, mode=mode,
            total_evidence=10, recalled=3,
            missed=("a", "b", "c", "d", "e", "g", "h"),
            recall=0.3, duration_ms=10,
        )

    async def fake_tokens(case, *, compiler, repo_root, mode):
        return TokenResult(
            case_id=case.case_id, mode=mode,
            baseline_tokens=100, measured_tokens=80,
            reduction=0.2, duration_ms=10,
        )

    orig_recall = integ.measure_recall
    orig_tokens = integ.measure_tokens
    integ.measure_recall = fake_recall
    integ.measure_tokens = fake_tokens
    try:
        result = await run_integration_pack(
            case_dir,
            compiler=compiler,
            repo_root=tmp_path,
            report_path=report,
        )
    finally:
        integ.measure_recall = orig_recall
        integ.measure_tokens = orig_tokens
    assert result.gate_decision == "FAIL"


# --- 5. Decision rules: all-recall-pass + reduction-pass = VERIFIED --


async def test_all_recall_and_reduction_pass_is_verified(tmp_path) -> None:
    import importlib
    integ = importlib.import_module("paw.bench.integration")
    from paw.bench.recall import RecallResult
    from paw.bench.tokens import TokenResult

    case_dir = _copy_real_case(tmp_path)
    report = tmp_path / "report.md"
    compiler = ContextCompiler()

    async def fake_recall(case, *, compiler, repo_root, mode):
        return RecallResult(
            case_id=case.case_id, mode=mode,
            total_evidence=10, recalled=10, missed=(),
            recall=1.0, duration_ms=10,
        )

    async def fake_tokens(case, *, compiler, repo_root, mode):
        return TokenResult(
            case_id=case.case_id, mode=mode,
            baseline_tokens=100, measured_tokens=50,
            reduction=0.5, duration_ms=10,
        )

    orig_recall = integ.measure_recall
    orig_tokens = integ.measure_tokens
    integ.measure_recall = fake_recall
    integ.measure_tokens = fake_tokens
    try:
        result = await run_integration_pack(
            case_dir,
            compiler=compiler,
            repo_root=tmp_path,
            report_path=report,
        )
    finally:
        integ.measure_recall = orig_recall
        integ.measure_tokens = orig_tokens
    assert result.gate_decision == "VERIFIED"
    text = report.read_text(encoding="utf-8")
    assert "VERIFIED" in text
    assert "all E0 cases meet the E1 acceptance targets" in text