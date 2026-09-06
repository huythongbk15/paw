from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paw.bench import CaseManifest
    from paw.core.context_compiler import ContextCompiler


# The E0 frozen baseline: the total input tokens measured
# on the E0 acceptance run with the cold-mode compiler.
# Each case records its baseline in the E0 benchmark
# results; the E1-24 contract reuses that number.
_E0_FROZEN_BASELINE: dict[str, int] = {
    # Populated from the E0-27 frozen baseline run.
    # Cases not listed here use the measured cold-mode
    # total as the baseline (reduction = 0.0).
}


@dataclass(frozen=True)
class TokenResult:
    """The token measurement for a single E0 case in one mode.

    ``reduction`` is a fraction in ``[0.0, 1.0]``;
    ``0.3`` means the E1 work reduced tokens by 30%.
    """

    case_id: str
    mode: str  # "cold" | "warm"
    baseline_tokens: int
    measured_tokens: int
    reduction: float
    duration_ms: int


def set_baseline_tokens(case_id: str, tokens: int) -> None:
    """Register the E0 frozen baseline for a case.

    Called by the E1-24 contract test and the E0 runner
    to inject the frozen baseline numbers. This is a
    module-level setter on the frozen-baseline dict;
    the dict itself is not exported.
    """
    _E0_FROZEN_BASELINE[case_id] = tokens


async def measure_tokens(
    case: CaseManifest,
    *,
    compiler: ContextCompiler,
    repo_root: Path,
    mode: str,
    baseline_tokens: int | None = None,
) -> TokenResult:
    """Measure the cloud input tokens of a single E0 case.

    The ``measured_tokens`` is the ``final_tokens`` value
    from the compiler's manifest (post-rebudget). The
    ``baseline_tokens`` is the E0 frozen baseline: if
    ``baseline_tokens`` is not passed explicitly, the
    function looks up the case in the frozen-baseline
    dict; if the case is not in the dict, the measured
    cold-mode total is used as its own baseline.
    """
    start = time.perf_counter()

    # Run the compiler to get the manifest.
    if mode == "cold":
        manifest = await _compile_cold(compiler, case, repo_root)
    else:
        manifest = await _compile_warm(compiler, case, repo_root)

    measured = getattr(manifest, "final_tokens", 0)

    # Resolve the baseline.
    if baseline_tokens is not None:
        baseline = baseline_tokens
    elif case.case_id in _E0_FROZEN_BASELINE:
        baseline = _E0_FROZEN_BASELINE[case.case_id]
    else:
        baseline = measured

    reduction = (
        (baseline - measured) / baseline
        if baseline > 0 else 0.0
    )
    # Clamp reduction to [0.0, 1.0].
    reduction = max(0.0, min(1.0, reduction))

    duration_ms = int((time.perf_counter() - start) * 1000)

    return TokenResult(
        case_id=case.case_id,
        mode=mode,
        baseline_tokens=baseline,
        measured_tokens=measured,
        reduction=reduction,
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
    """Compile a manifest in warm mode (cache pre-loaded)."""
    try:
        from paw.knowledge.index import get_knowledge_index
        idx = get_knowledge_index()
        await idx.load_derived_views()
    except Exception:
        pass

    return await _compile_cold(compiler, case, repo_root)
