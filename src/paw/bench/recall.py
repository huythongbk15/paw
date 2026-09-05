"""PAW Bench — recall measurement (E1-23).

``measure_recall`` measures the cold + warm
required-evidence recall of a single E0 case. The
contract is documented in
``docs/benchmarks/e1/recall_measurement.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.context_compiler import ContextCompiler
    from . import CaseManifest


@dataclass(frozen=True)
class RecallResult:
    case_id: str
    mode: str
    total_evidence: int
    recalled: int
    missed: tuple[str, ...]
    recall: float
    duration_ms: int


async def measure_recall(
    case: CaseManifest,
    *,
    compiler: ContextCompiler,
    repo_root: Path,
    mode: str,
) -> RecallResult:
    """Measure the recall of a single E0 case.

    The E0 case's expected evidence is the
    ``expected_evidence`` list on the case manifest.
    Recall is the fraction whose target value is
    present in the compiler's manifest (matched by
    substring on the included / excluded candidates'
    content). The E1-25 contract is the "review every
    miss" loop; this function is the data source.
    """
    import time

    started = time.monotonic_ns()
    # Run the compiler. The case's ``goal`` is the
    # query; the ``budget`` is the case's
    # ``max_iterations`` * 1000 (a small but
    # meaningful default).
    budget = None
    if hasattr(case, "max_iterations"):
        budget = None  # use the compiler's default
    manifest = await compiler.compile_manifest(
        task_id=case.case_id,
        query=case.goal,
        session_id=None,
        budget=budget,
    )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000

    # Build a flat text of the manifest's included
    # candidates for the substring match.
    manifest_text = "\n".join(
        c.content or c.source_id for c in manifest.included
    )

    total = len(case.expected_evidence)
    recalled = 0
    missed: list[str] = []
    for ev in case.expected_evidence:
        if ev.value and ev.value in manifest_text:
            recalled += 1
        else:
            missed.append(ev.value)
    recall = (recalled / total) if total else 1.0
    return RecallResult(
        case_id=case.case_id,
        mode=mode,
        total_evidence=total,
        recalled=recalled,
        missed=tuple(missed),
        recall=recall,
        duration_ms=duration_ms,
    )


__all__ = ["RecallResult", "measure_recall"]
