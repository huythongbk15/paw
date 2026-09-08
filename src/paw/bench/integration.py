"""PAW Bench — E1 integration pack (E1-27).

``run_integration_pack`` runs every E0 case through
the E1 compiler pipeline (recall + token measurement
+ gate) and produces a gate decision. The contract
is documented in
``docs/benchmarks/e1/integration_pack.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from .recall import RecallResult, measure_recall
from .tokens import TokenResult, measure_tokens

# Gate thresholds. The contract test pins these; a
# change to the numbers is a change-control surface.
GATE_RECALL_THRESHOLD = 0.95
GATE_REGRESSION_THRESHOLD = 0.5
GATE_REDUCTION_FLOOR = 0.30


def evaluate_measurement_metrics(
    recall_values: list[float], warm_reductions: list[float],
) -> tuple[str, tuple[str, ...]]:
    """Evaluate the one canonical E1 recall/reduction threshold contract."""
    if not recall_values or not warm_reductions:
        return "BLOCKED", ("measurement samples are missing",)
    if any(value < GATE_REGRESSION_THRESHOLD for value in recall_values):
        return "FAIL", (
            f"at least one recall sample is below {GATE_REGRESSION_THRESHOLD:.2f}",
        )
    reasons = []
    if any(value < GATE_RECALL_THRESHOLD for value in recall_values):
        reasons.append(
            f"at least one recall sample is below {GATE_RECALL_THRESHOLD:.2f}"
        )
    warm_median = median(warm_reductions)
    if warm_median < GATE_REDUCTION_FLOOR:
        reasons.append(
            f"median warm token reduction {warm_median:.2f} "
            f"< {GATE_REDUCTION_FLOOR:.2f}"
        )
    return ("PARTIAL", tuple(reasons)) if reasons else (
        "PASS", ("measurement thresholds passed",),
    )


@dataclass(frozen=True)
class IntegrationResult:
    case_count: int
    recall_results: tuple
    token_results: tuple
    gate_decision: str
    gate_reasons: tuple[str, ...]
    report_path: Path


async def run_integration_pack(
    case_dir: Path,
    *,
    compiler,  # ContextCompiler (avoid import cycle)
    repo_root: Path,
    report_path: Path,
    baseline_tokens: Mapping[str, int] | None = None,
) -> IntegrationResult:
    """Run every case in ``case_dir`` through the
    E1 compiler pipeline (cold + warm), aggregate the
    recall + token results, and write a markdown
    report to ``report_path``. The gate decision is
    the E1-27 contract.
    """
    from . import case_manifest_from_dict

    # Discover case files.
    case_files = sorted(case_dir.glob("*.yaml"))
    if not case_files:
        # Missing evidence cannot establish a successful gate.
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            "# E1 Integration Pack Report\n\n"
            "Cases: 0\nGate: **BLOCKED**\n\n"
            "## Gate reasons\n- no cases in directory\n",
            encoding="utf-8",
        )
        return IntegrationResult(
            case_count=0,
            recall_results=(),
            token_results=(),
            gate_decision="BLOCKED",
            gate_reasons=("no cases in directory",),
            report_path=report_path,
        )

    recall_results: list[RecallResult] = []
    token_results: list[TokenResult] = []
    seen: set[str] = set()
    for case_file in case_files:
        data = case_manifest_from_dict(
            # The YAML loader is in
            # ``paw.bench.__init__``; re-use the path
            # loader to keep the integration pack
            # self-contained.
            __import__("yaml", fromlist=["safe_load"]).safe_load(
                case_file.read_text(encoding="utf-8")
            )
        )
        if data.case_id in seen:
            raise ValueError(f"duplicate case id: {data.case_id}")
        seen.add(data.case_id)
        baseline = (baseline_tokens or {}).get(data.case_id)
        if type(baseline) is not int or baseline <= 0:
            raise ValueError(f"missing or invalid baseline for {data.case_id}")
        for mode in ("cold", "warm"):
            manifest = await compiler.compile_manifest(
                task_id=data.case_id, query=data.goal, session_id=None,
            )
            recall_results.append(await measure_recall(
                data, compiler=compiler, repo_root=repo_root,
                mode=mode, manifest=manifest,
            ))
            token_results.append(await measure_tokens(
                data, compiler=compiler, repo_root=repo_root,
                mode=mode, manifest=manifest,
                baseline_tokens=baseline,
            ))

    # Gate decision.
    decision, metric_reasons = evaluate_measurement_metrics(
        [result.recall for result in recall_results],
        [result.reduction for result in token_results if result.mode == "warm"],
    )
    reasons = list(metric_reasons)
    if decision == "PASS":
        reasons.append("full E1 acceptance is not established by metrics alone")

    # Markdown report.
    lines: list[str] = []
    lines.append("# E1 Integration Pack Report")
    lines.append("")
    lines.append("Scope: budgeted context measurement only, not full E1 qualification.")
    lines.append(f"Cases: {len(case_files)}")
    lines.append(f"Gate: **{decision}**")
    lines.append("")
    lines.append("## Recall")
    for r in recall_results:
        lines.append(
            f"- {r.case_id}: recall={r.recall:.2f} "
            f"({r.recalled}/{r.total_evidence}) "
            f"mode={r.mode} duration={r.duration_ms}ms"
        )
    lines.append("")
    lines.append("## Tokens")
    for t in token_results:
        lines.append(
            f"- {t.case_id}: baseline={t.baseline_tokens} "
            f"measured={t.measured_tokens} "
            f"reduction={t.reduction:.2f} "
            f"mode={t.mode} duration={t.duration_ms}ms"
        )
    lines.append("")
    lines.append("## Gate reasons")
    for reason in reasons:
        lines.append(f"- {reason}")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return IntegrationResult(
        case_count=len(case_files),
        recall_results=tuple(recall_results),
        token_results=tuple(token_results),
        gate_decision=decision,
        gate_reasons=tuple(reasons),
        report_path=report_path,
    )


__all__ = [
    "GATE_RECALL_THRESHOLD",
    "GATE_REDUCTION_FLOOR",
    "GATE_REGRESSION_THRESHOLD",
    "IntegrationResult",
    "evaluate_measurement_metrics",
    "run_integration_pack",
]
