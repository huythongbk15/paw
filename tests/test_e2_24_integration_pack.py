"""E2-24: Run the E2 integration pack once and record the gate decision.

This is the E2 track integration gate. It collects and runs the core E2
contract/runtime tests and records the overall gate outcome.

Verification:
- D3: full E2 core test pack runs green; gate decision recorded.
"""
from __future__ import annotations

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


def _run_e2_pack() -> tuple[int, str]:
    cmd = [
        sys.executable, "-m", "pytest",
        "-q", "-p", "no:cacheprovider",
        *E2_CORE_TEST_FILES,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    return proc.returncode, proc.stdout + proc.stderr


def test_e2_integration_pack_runs_green():
    returncode, output = _run_e2_pack()
    if returncode != 0:
        pytest.fail(f"E2 integration pack failed with rc={returncode}\n{output}")
    assert "passed" in output.lower()
