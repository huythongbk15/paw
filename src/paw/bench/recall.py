"""Source-bound recall in the actual budgeted context."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paw.bench import CaseManifest
    from paw.core.context_compiler import ContextCompiler, ContextManifest


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
    case: CaseManifest, *, compiler: ContextCompiler, repo_root: Path,
    mode: str, manifest: ContextManifest | None = None,
) -> RecallResult:
    """Score file evidence; the caller prepares the corpus and cache state.

    Warm means repeated compilation, not automatic cache hydration. Unsupported
    runtime evidence requires a dedicated evaluator, never a text-match proxy.
    """
    if mode not in {"cold", "warm"}:
        raise ValueError("mode must be cold or warm")
    if not case.expected_evidence:
        raise ValueError("recall requires expected evidence")
    for ev in case.expected_evidence:
        if ev.kind not in {"file_contains", "file_exists"}:
            raise ValueError(f"unsupported context recall evidence: {ev.kind}")
        if not ev.target or (ev.kind == "file_contains" and not ev.value):
            raise ValueError("file evidence requires a target and matching value")
    start = time.perf_counter()
    if manifest is None:
        manifest = await compiler.compile_manifest(
            task_id=case.case_id, query=case.goal, session_id=None,
        )
    root = repo_root.resolve()
    missed = []
    for ev in case.expected_evidence:
        target = (root / ev.target).resolve()
        if not target.is_relative_to(root):
            raise ValueError("evidence target is outside repo_root")
        found = any(
            (getattr(cand, "external_id", "") or cand.reference)
            and (root / (getattr(cand, "external_id", "") or cand.reference)).resolve() == target
            and (ev.kind == "file_exists" or ev.value in cand.content)
            for cand in manifest.included
        )
        if not found:
            missed.append(f"{ev.kind}:{ev.target}:{ev.value}")
    total = len(case.expected_evidence)
    return RecallResult(
        case_id=case.case_id, mode=mode, total_evidence=total,
        recalled=total - len(missed), missed=tuple(missed),
        recall=(total - len(missed)) / total,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
