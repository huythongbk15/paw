"""E2-24: Run the E2 integration pack once and record the gate decision.

This is the E2 track integration gate. It names the E2 core contract/runtime
pack and records the overall gate outcome.

Why the pack run is opt-in
--------------------------
The default suite already executes every file listed in ``E2_CORE_TEST_FILES``
in-process (361 tests, ~254s). This module used to *additionally* spawn a
subprocess pytest over the same files, so the whole E2 track ran twice on every
full run: 278s of the suite, roughly 14% of total runtime, adding no coverage
the default run does not already provide -- and hiding the real failure behind a
subprocess exit code instead of naming the failing test.

The pack run is therefore explicit opt-in, alongside the E4 live provider test:

    PAW_E2_PACK=1 python -m pytest tests/test_e2_24_integration_pack.py

Making it opt-in introduces exactly one new risk -- the file list silently
 rotting when an E2 file is renamed or deleted. ``TestPackManifest`` below
 closes that gap in milliseconds instead of 254 seconds.

Verification:
- D3: full E2 core test pack runs green; gate decision recorded.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

E2_CORE_TEST_FILES = [
    "tests/test_e2_02_cognitive_roles.py",
    "tests/test_e2_03_role_contracts.py",
    "tests/test_e2_04_task_signals.py",
    "tests/test_e2_05_local_eligibility.py",
    "tests/test_e2_06_router_consumes_signals.py",
    "tests/test_e2_07_ledger_provenance.py",
    "tests/test_e2_08_reconnaissance.py",
    "tests/test_e2_09_inference_gate.py",
    "tests/test_e2_10_re_evaluate_routing.py",
    "tests/test_e2_19_negative_pre_exec.py",
    "tests/test_e2_20_resume_completed_op.py",
    "tests/test_e2_21_static_vs_trajectory_routing.py",
    "tests/test_e2_22_threshold_calibration.py",
    "tests/test_e2_23_inspect_output.py",
    "tests/test_e2_26_single_decision_artifact.py",
    "tests/test_e2_27_readiness_enum.py",
    "tests/test_e2_28_decision_persistence.py",
    "tests/test_e2_29_research_depth.py",
    "tests/test_e2_30_research_budget.py",
    "tests/test_e2_31_research_depth_contract.py",
    "tests/test_e2_39_needs_clarification.py",
    "tests/test_e2_40_rejected_stop.py",
    "tests/test_e2_41_spike_research_only_plan.py",
    "tests/test_e2_42_spike_isolation.py",
    "tests/test_e2_43_inspect_output.py",
    "tests/test_e2_44_readiness_negative_matrix.py",
    "tests/test_e2_45_plan_purpose_contract.py",
    "tests/test_e2_46_effect_constraints_runtime.py",
    "tests/test_e2_47_48_49_contract.py",
    "tests/test_e2_50_no_provider_escalation.py",
]

REPO_ROOT = Path(__file__).resolve().parents[1]

skip_unless_pack_requested = pytest.mark.skipif(
    os.environ.get("PAW_E2_PACK") != "1",
    reason=(
        "E2 pack subprocess is opt-in (PAW_E2_PACK=1): the default suite already "
        "runs these files in-process, and a second pass added no coverage"
    ),
)


@skip_unless_pack_requested
def test_e2_integration_pack_runs_green():
    """Opt-in: run the E2 pack in a fresh process, as a standalone pack."""
    cmd = [
        sys.executable, "-m", "pytest",
        "-q", "-p", "no:cacheprovider",
        *E2_CORE_TEST_FILES,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if proc.returncode != 0:
        pytest.fail(f"E2 integration pack failed with rc={proc.returncode}\n{proc.stdout}{proc.stderr}")
    assert "passed" in (proc.stdout + proc.stderr).lower()


class TestPackManifest:
    """Cheap guard for the opt-in list: the named pack must stay real."""

    def test_every_named_file_exists(self):
        missing = [name for name in E2_CORE_TEST_FILES if not (REPO_ROOT / name).is_file()]
        assert missing == [], f"E2 pack names files that do not exist: {missing}"

    def test_every_named_file_is_under_the_default_test_path(self):
        """A file outside testpaths/ would not run in the default suite."""
        outside = [name for name in E2_CORE_TEST_FILES if not name.startswith("tests/")]
        assert outside == [], f"E2 pack files outside the default test path: {outside}"

    def test_pack_is_not_empty_and_has_no_duplicates(self):
        assert len(E2_CORE_TEST_FILES) >= 20, "E2 pack manifest lost entries"
        duplicates = {name for name in E2_CORE_TEST_FILES if E2_CORE_TEST_FILES.count(name) > 1}
        assert duplicates == set(), f"duplicate entries in the E2 pack manifest: {duplicates}"

    def test_named_files_actually_contain_tests(self):
        empty = [
            name
            for name in E2_CORE_TEST_FILES
            if "def test_" not in (REPO_ROOT / name).read_text(encoding="utf-8")
        ]
        assert empty == [], f"E2 pack files contain no test functions: {empty}"
