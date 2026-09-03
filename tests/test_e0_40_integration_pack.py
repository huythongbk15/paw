"""E0-40 contract test: integration pack without E1-E3.

The E0-40 acceptance criterion is: the runner can
score the current-runtime traces from the human-
reviewed fixtures **without** depending on E1, E2, or
E3. This is the proof that E0 stands on its own.

The contract:

1. The deterministic runner imports no `paw.e1`,
   `paw.e2`, or `paw.e3` modules (none exist; this
   test asserts the absence).
2. The deterministic runner can score every minimum
   case in the E0 minimum case set.
3. The deterministic runner can score every research-
   decision case in E0-28..35.
4. The E0-27 integration-pack run is reproducible
   (re-running the pack produces the same outcomes
   per case with the same seed).
5. ``paw.core`` 11-symbol surface is preserved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.bench import load_case, run_case


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = PROJECT_ROOT / "benchmarks" / "e0" / "cases"


# --- 1. The deterministic runner depends on no E1-E3 ----------------


def test_runner_does_not_import_e1_e2_e3() -> None:
    """``paw.bench`` does not import any post-E0 module.
    The acceptance criterion is the absence of the
    import, not the presence of a guard.
    """
    from paw import bench
    bench_path = Path(bench.__file__).read_text()
    for forbidden in ["paw.e1", "paw.e2", "paw.e3"]:
        assert forbidden not in bench_path, (
            f"paw.bench imports {forbidden!r}; the E0 track "
            f"must stand on its own until E1 starts"
        )


# --- 2. Every minimum case runs through the runner -----------------


MINIMUM_CASES = [
    "repo_understand_small_repo",
    "defect_localization_simple_math",
    "cross_module_change_constant",
    "refactor_rename_function",
    "architecture_decision_cache",
    "interrupted_recovery_midway",
    "privacy_negative_secret_marker",
    "insufficient_context_empty_goal",
]


DECISION_CASES = [
    "decision_ready_simple_module",
    "decision_rejected_duplicate_owner",
    "decision_needs_clarification_auth",
    "decision_spike_exotic_locking",
    "decision_needs_research_security",
]


ALL_CASES = MINIMUM_CASES + DECISION_CASES


@pytest.mark.parametrize("case_id", ALL_CASES)
def test_every_case_runs_to_success(case_id: str) -> None:
    """E0-40: every E0 case produces a SUCCESS row when
    the deterministic runner scores the
    human-reviewed fixtures. The E0 gate is VERIFIED
    on this contract; E1-E3 may extend the scoring
    but cannot regress it.
    """
    case_path = CASES_DIR / f"{case_id}.yaml"
    manifest = load_case(case_path)
    result = run_case(manifest, project_root=PROJECT_ROOT, seed="e0-40")
    assert len(result.rows) == 1
    assert result.rows[0].outcome == "SUCCESS", (
        f"{case_id}: outcome {result.rows[0].outcome} expected SUCCESS"
    )


# --- 3. The integration pack is reproducible ---------------------


def test_integration_pack_is_reproducible() -> None:
    """Re-running every case with the same seed
    produces byte-identical outcome rows. A reviewer
    who wants to confirm the E0-27 gate can do so
    without depending on wall-clock state.
    """
    first = []
    second = []
    for case_id in ALL_CASES:
        case_path = CASES_DIR / f"{case_id}.yaml"
        manifest = load_case(case_path)
        result = run_case(
            manifest, project_root=PROJECT_ROOT, runs=1,
            seed="reproducible", deterministic_timestamps=True,
        )
        first.append((case_id, result.rows[0].to_jsonl()))
        result2 = run_case(
            manifest, project_root=PROJECT_ROOT, runs=1,
            seed="reproducible", deterministic_timestamps=True,
        )
        second.append((case_id, result2.rows[0].to_jsonl()))
    for (id_a, json_a), (id_b, json_b) in zip(first, second, strict=True):
        assert id_a == id_b
        assert json_a == json_b, (
            f"{id_a}: second run produced a different row"
        )


# --- 4. paw.core 11-symbol surface preserved ---------------------


def test_paw_core_unchanged_after_e0_40() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    assert expected.issubset(set(symbols))
