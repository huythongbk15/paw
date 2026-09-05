"""PAW Bench — token measurement (E1-24).

``measure_tokens`` measures the cold + warm cloud
input tokens of a single E0 case against the frozen
E0 baseline. The contract is documented in
``docs/benchmarks/e1/token_measurement.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.context_compiler import ContextCompiler
    from . import CaseManifest


@dataclass(frozen=True)
class TokenResult:
    case_id: str
    mode: str
    baseline_tokens: int
    measured_tokens: int
    reduction: float
    duration_ms: int


async def measure_tokens(
    case: CaseManifest,
    *,
    compiler: ContextCompiler,
    repo_root: Path,
    mode: str,
) -> TokenResult:
    """Measure the cloud input tokens of a single
    E0 case.

    The baseline is the sum of every expected-evidence
    ``value`` (the E0 frozen reference); the measured
    value is the post-E1 ``final_tokens`` of the
    manifest. The reduction is a fraction in
    ``[0.0, 1.0]``: ``(baseline - measured) / baseline``.
    """
    import time

    started = time.monotonic_ns()
    manifest = await compiler.compile_manifest(
        task_id=case.case_id,
        query=case.goal,
    )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000

    # The baseline token count is the sum of every
    # expected evidence's ``value`` length (3 chars per
    # token, the same heuristic the
    # ``TokenEstimator`` uses). The contract is the
    # comparison; the unit is "estimated tokens".
    baseline_tokens = sum(
        max(1, len(ev.value) // 3) for ev in case.expected_evidence
    )
    measured_tokens = manifest.final_tokens
    reduction = (
        (baseline_tokens - measured_tokens) / baseline_tokens
        if baseline_tokens > 0
        else 0.0
    )
    return TokenResult(
        case_id=case.case_id,
        mode=mode,
        baseline_tokens=baseline_tokens,
        measured_tokens=measured_tokens,
        reduction=reduction,
        duration_ms=duration_ms,
    )


__all__ = ["TokenResult", "measure_tokens"]
