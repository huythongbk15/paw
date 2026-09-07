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

    # Determine which expected-evidence items were recalled.
    # An evidence item is "recalled" if its ``value`` string
    # (the matched string \u2014 e.g. a path fragment inside a
    # file_contains fixture) appears in the content of any
    # included candidate. When ``value`` is empty, fall back
    # to ``target`` (e.g. a ledger_event whose target is the
    # event identifier).
    def _evidence_key(ev):
        if ev.value:
            return ev.value
        return ev.target

    recalled_keys = set()
    for cand in manifest.included:
        for ev in expected_evidence:
            key = _evidence_key(ev)
            if key == "" or key is None:
                continue
            if (key in cand.source_id
                    or key in cand.content
                    or (cand.reference and key in cand.reference)):
                recalled_keys.add(key)

    total_keys = {
        _evidence_key(ev) for ev in expected_evidence
        if _evidence_key(ev) and _evidence_key(ev) != ""
    }
    missing_keys = total_keys - recalled_keys
    recalled_count = len(total_keys - missing_keys)

    duration_ms = int((time.perf_counter() - start) * 1000)

    total = len(total_keys)
    return RecallResult(
        case_id=case.case_id,
        mode=mode,
        total_evidence=total,
        recalled=recalled_count,
        missed=tuple(sorted(missing_keys)),
        recall=(recalled_count / total if total else 1.0),
        duration_ms=duration_ms,
    )


async def _compile_cold(
    compiler: ContextCompiler,
    case: CaseManifest,
    repo_root: Path,
) -> object:
    """Compile a manifest in cold mode (empty cache).

    Uses ``compile_manifest`` (the E1-20 entry point) so the
    returned ``ContextManifest`` carries the per-item E1-17
    record and the E1-18 exclusion reasons. A high token
    budget is applied so ``BudgetExceededError`` does not
    truncate the recall measurement \u2014 recall is about
    *coverage* of expected evidence, not budget adherence.
    """
    from paw.core.context_compiler import ContextBudget
    high_budget = ContextBudget(max_tokens=1_000_000, max_fragments=2000)
    try:
        return await compiler.compile_manifest(
            task_id=case.case_id,
            query=case.goal,
            session_id=None,
            budget=high_budget,
        )
    except Exception:
        # BudgetExceededError or other runtime error: fall back
        # to the raw compile() pipeline and reconstruct a minimal
        # manifest so recall is still measurable.
        context, candidates = await compiler.compile(
            task_id=case.case_id,
            query=case.goal,
            session_id=None,
            budget=high_budget,
        )
        from paw.core.context_compiler import ContextManifest
        included = [c for c in candidates if c.metadata.get("included")]
        excluded = [c for c in candidates if "excluded_reason" in c.metadata]
        return ContextManifest(
            task_id=case.case_id,
            budget=high_budget,
            included=tuple(included),
            excluded=tuple(excluded),
            final_tokens=getattr(context, "token_count",
                                 sum(c.token_estimate for c in included)),
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
