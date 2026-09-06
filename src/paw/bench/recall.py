from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paw.bench import CaseManifest
    from paw.core.context_compiler import ContextCompiler


@dataclass(frozen=True)
class RecallResult:
    """The recall measurement for a single E0 case in one mode.

    ``missed`` is the change-control surface: a reviewer
    who sees a miss can decide whether the heuristic is
    the cause or the manifest is the cause.
    """

    case_id: str
    mode: str  # "cold" | "warm"
    total_evidence: int
    recalled: int
    missed: tuple[str, ...]
    recall: float  # recalled / total_evidence
    duration_ms: int


async def measure_recall(
    case: CaseManifest,
    *,
    compiler: ContextCompiler,
    repo_root: Path,
    mode: str,
) -> RecallResult:
    """Measure the recall of a single E0 case.

    Recall is the fraction of expected-evidence items the
    compiler's manifest can recall. A case with 3 expected
    evidence items where the manifest includes 2 has
    recall = 2/3 = 0.667.

    ``mode`` is ``"cold"`` (no cache) or ``"warm"`` (the
    E1-14 derived records are pre-loaded).
    """
    start = time.perf_counter()

    expected_evidence = case.expected_evidence
    total = len(expected_evidence)

    if total == 0:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return RecallResult(
            case_id=case.case_id,
            mode=mode,
            total_evidence=0,
            recalled=0,
            missed=(),
            recall=1.0,  # vacuous: nothing was expected, nothing was missed
            duration_ms=duration_ms,
        )

    # Run the compiler to get the manifest.
    if mode == "cold":
        manifest = await _compile_cold(compiler, case, repo_root)
    else:
        manifest = await _compile_warm(compiler, case, repo_root)

    # Determine which expected-evidence targets were recalled.
    # An evidence target is "recalled" if its ``target`` string
    # appears in the content of any included candidate.
    recalled_targets: set[str] = set()
    for cand in manifest.included:
        for ev in expected_evidence:
            target = ev.target
            if target == "" or target is None:
                continue
            if (target in cand.source_id
                    or target in cand.content
                    or (cand.reference and target in cand.reference)):
                recalled_targets.add(target)

    total_targets = {
        ev.target for ev in expected_evidence
        if ev.target and ev.target != ""
    }
    missing_targets = total_targets - recalled_targets
    recalled_count = len(total_targets - missing_targets)

    duration_ms = int((time.perf_counter() - start) * 1000)

    return RecallResult(
        case_id=case.case_id,
        mode=mode,
        total_evidence=len(total_targets),
        recalled=recalled_count,
        missed=tuple(sorted(missing_targets)),
        recall=(recalled_count / len(total_targets)
                if total_targets else 1.0),
        duration_ms=duration_ms,
    )


async def _compile_cold(
    compiler: ContextCompiler,
    case: CaseManifest,
    repo_root: Path,
) -> object:
    """Compile a manifest in cold mode (empty cache)."""
    context, _ = await compiler.compile(
        task_id=case.case_id,
        query=case.description,
        session_id=None,
    )
    from paw.core.context_compiler import ContextManifest
    if isinstance(context, ContextManifest):
        return context
    manifest = getattr(context, "manifest", None)
    if manifest is not None:
        return manifest
    return ContextManifest(
        task_id=case.case_id,
        budget=compiler.budget,
        included=tuple(getattr(context, "items", [])),
        excluded=(),
        final_tokens=getattr(context, "token_count", 0),
    )


async def _compile_warm(
    compiler: ContextCompiler,
    case: CaseManifest,
    repo_root: Path,
) -> object:
    """Compile a manifest in warm mode (cache pre-loaded).

    In warm mode the compiler's derived-record cache
    (E1-14) is populated before compilation, so the
    source-level data (knowledge chunks, symbols,
    test associations) is reused rather than re-derived
    from the repository files.
    """
    try:
        from paw.knowledge.index import get_knowledge_index
        idx = get_knowledge_index()
        await idx.load_derived_views()
    except Exception:
        pass  # graceful degradation: warm == cold if cache unavailable

    return await _compile_cold(compiler, case, repo_root)
