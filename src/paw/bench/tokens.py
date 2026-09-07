"""Budgeted token estimates against an explicit reviewed baseline."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paw.bench import CaseManifest
    from paw.core.context_compiler import ContextCompiler, ContextManifest

_E0_FROZEN_BASELINE: dict[str, int] = {}


@dataclass(frozen=True)
class TokenResult:
    case_id: str
    mode: str
    baseline_tokens: int
    measured_tokens: int
    reduction: float  # Signed: negative means increased usage.
    duration_ms: int


def set_baseline_tokens(case_id: str, tokens: int) -> None:
    """Compatibility registration; prefer explicit per-run baselines."""
    if type(tokens) is not int or tokens <= 0:
        raise ValueError("baseline tokens must be a positive integer")
    _E0_FROZEN_BASELINE[case_id] = tokens


async def measure_tokens(
    case: CaseManifest, *, compiler: ContextCompiler, repo_root: Path,
    mode: str, baseline_tokens: int | None = None,
    manifest: ContextManifest | None = None,
) -> TokenResult:
    """Measure manifest estimates, not billed cloud usage; never self-baseline."""
    if mode not in {"cold", "warm"}:
        raise ValueError("mode must be cold or warm")
    baseline = (
        baseline_tokens if baseline_tokens is not None
        else _E0_FROZEN_BASELINE.get(case.case_id)
    )
    if type(baseline) is not int or baseline <= 0:
        raise ValueError(f"missing or invalid baseline for {case.case_id}")
    start = time.perf_counter()
    if manifest is None:
        manifest = await compiler.compile_manifest(
            task_id=case.case_id, query=case.goal, session_id=None,
        )
    measured = manifest.final_tokens
    if type(measured) is not int or measured < 0:
        raise ValueError("manifest token estimate must be a nonnegative integer")
    return TokenResult(
        case_id=case.case_id, mode=mode, baseline_tokens=baseline,
        measured_tokens=measured, reduction=(baseline - measured) / baseline,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
