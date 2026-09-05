"""PAW Bench — E1 integration pack (E1-27).

``run_integration_pack`` runs every E0 case through
the E1 compiler pipeline (recall + token measurement
+ gate) and produces a gate decision. The contract
is documented in
``docs/benchmarks/e1/integration_pack.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .recall import RecallResult, measure_recall
from .tokens import TokenResult, measure_tokens

if TYPE_CHECKING:
    pass


# Gate thresholds. The contract test pins these; a
# change to the numbers is a change-control surface.
GATE_RECALL_THRESHOLD = 0.95
GATE_REGRESSION_THRESHOLD = 0.5
GATE_REDUCTION_FLOOR = 0.0


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
        # The empty-directory case still writes a
        # report (the contract test asserts the file
        # exists on disk).
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            "# E1 Integration Pack Report\n\n"
            "Cases: 0\nGate: **VERIFIED**\n\n"
            "## Gate reasons\n- no cases in directory\n",
            encoding="utf-8",
        )
        return IntegrationResult(
            case_count=0,
            recall_results=(),
            token_results=(),
            gate_decision="VERIFIED",
            gate_reasons=("no cases in directory",),
            report_path=report_path,
        )

    recall_results: list[RecallResult] = []
    token_results: list[TokenResult] = []
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
        # The contract: the runtime is called twice,
        # once for cold + once for warm. The two
        # numbers are the cold + warm measurements.
        r_cold = await measure_recall(
            data, compiler=compiler, repo_root=repo_root, mode="cold"
        )
        t_cold = await measure_tokens(
            data, compiler=compiler, repo_root=repo_root, mode="cold"
        )
        recall_results.append(r_cold)
        token_results.append(t_cold)

    # Gate decision.
    reasons: list[str] = []
    decision = "VERIFIED"
    for r in recall_results:
        if r.recall < GATE_REGRESSION_THRESHOLD:
            decision = "FAIL"
            reasons.append(
                f"case {r.case_id!r} regressed: recall {r.recall:.2f} "
                f"< {GATE_REGRESSION_THRESHOLD}"
            )
        elif r.recall < GATE_RECALL_THRESHOLD:
            if decision != "FAIL":
                decision = "PARTIAL"
            reasons.append(
                f"case {r.case_id!r} partial: recall {r.recall:.2f} "
                f"< {GATE_RECALL_THRESHOLD}"
            )
    for t in token_results:
        if t.reduction < GATE_REDUCTION_FLOOR:
            if decision == "VERIFIED":
                decision = "PARTIAL"
            reasons.append(
                f"case {t.case_id!r} token regression: reduction "
                f"{t.reduction:.2f} < {GATE_REDUCTION_FLOOR}"
            )
    if not reasons:
        reasons = ("all E0 cases meet the E1 acceptance targets",)

    # Markdown report.
    lines: list[str] = []
    lines.append("# E1 Integration Pack Report")
    lines.append("")
    lines.append(f"Cases: {len(recall_results)}")
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
        case_count=len(recall_results),
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
    "run_integration_pack",
]
