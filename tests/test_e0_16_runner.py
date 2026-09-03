"""E0-16 contract test: deterministic case runner.

The runner (``paw.bench.run_case``) reads a case manifest,
runs the deterministic verify commands for each
expected-evidence entry, and writes the per-run JSONL
rows plus a ``CaseRunResult``.

The contract:

1. The runner loads a case via ``load_case`` and refuses
   malformed manifests.
2. A case with all-PASS evidence produces outcome
   ``SUCCESS``.
3. A case with all-FAIL evidence produces outcome
   ``FAILURE``.
4. The runner is deterministic: two runs with the same
   seed produce byte-identical ``runs.jsonl`` lines.
5. The runner refuses commands on the deny-list.
6. The runner writes valid JSONL.
7. ``paw.core`` still exports 11 runtime symbols.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from paw.bench import (
    CASE_MANIFEST_SCHEMA_VERSION,
    CaseCategory,
    CaseManifest,
    ExpectedEvidence,
    FixtureRef,
    PrivacyClass,
    RunRow,
    RunnerError,
    load_case,
    run_case,
    run_case_file,
    write_runs_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = PROJECT_ROOT / "benchmarks" / "e0" / "cases"


def _good_manifest(evidence_values: list[str]) -> CaseManifest:
    return CaseManifest(
        case_id="test_case",
        schema_version=CASE_MANIFEST_SCHEMA_VERSION,
        category=CaseCategory.REPO_UNDERSTANDING,
        privacy_class=PrivacyClass.WORKSPACE,
        goal="Verify three substrings in the fixture.",
        fixtures=[
            FixtureRef(
                path="benchmarks/e0/fixtures/small_repo_tree.txt",
                revision="f3ad4ef",
                purpose="test fixture",
            ),
        ],
        expected_evidence=[
            ExpectedEvidence(
                kind="file_contains",
                target="benchmarks/e0/fixtures/small_repo_tree.txt",
                value=v,
                reviewer="alice@example.com",
            )
            for v in evidence_values
        ],
        timeout_seconds=10,
        max_iterations=5,
    )


# --- 1. Happy path: load + run + write ---------------------------------


def test_load_real_case_file() -> None:
    """The E0-08 case must load and pass its verify commands."""
    case_path = BENCH_DIR / "repo_understand_small_repo.yaml"
    manifest = load_case(case_path)
    assert manifest.case_id == "repo_understand_small_repo"
    result = run_case(manifest, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "SUCCESS"
    assert result.rows[0].passed_evidence == 3
    assert result.rows[0].total_evidence == 3
    assert result.rows[0].unsafe_preconditions == []


def test_runner_writes_valid_jsonl(tmp_path) -> None:
    case_path = BENCH_DIR / "repo_understand_small_repo.yaml"
    manifest = load_case(case_path)
    result = run_case(manifest, project_root=PROJECT_ROOT)
    out = tmp_path / "runs.jsonl"
    write_runs_jsonl(result, out)
    lines = out.read_text().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["case_id"] == "repo_understand_small_repo"
    assert parsed["outcome"] == "SUCCESS"
    assert "seed" in parsed
    assert "duration_ms" in parsed


# --- 2. Outcome rules (E0-04) -----------------------------------------


def test_all_pass_outcome_is_success() -> None:
    m = _good_manifest([
        "src/<package_name>/core.py",
        "tests/test_core.py",
        "docs/ARCHITECTURE.md",
    ])
    result = run_case(m, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "SUCCESS"
    assert result.summary()["outcomes"] == {"SUCCESS": 1}


def test_partial_outcome_when_majority_passes() -> None:
    """Two of three pass -> PARTIAL (strictly more than half)."""
    m = _good_manifest([
        "src/<package_name>/core.py",  # PASS
        "tests/test_core.py",          # PASS
        "this_substring_does_not_exist",  # FAIL
    ])
    result = run_case(m, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "PARTIAL"
    assert result.rows[0].passed_evidence == 2
    assert result.rows[0].total_evidence == 3


def test_failure_outcome_when_at_most_half_passes() -> None:
    """One of three pass -> FAILURE (1 <= 3/2)."""
    m = _good_manifest([
        "src/<package_name>/core.py",  # PASS
        "this_substring_does_not_exist_1",  # FAIL
        "this_substring_does_not_exist_2",  # FAIL
    ])
    result = run_case(m, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "FAILURE"


def test_all_fail_outcome_is_failure() -> None:
    m = _good_manifest([
        "nope_1", "nope_2", "nope_3",
    ])
    result = run_case(m, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "FAILURE"
    assert result.rows[0].passed_evidence == 0


def test_no_evidence_means_failure() -> None:
    """The E0-02 manifest contract already requires
    ``expected_evidence`` to be non-empty (a case with no
    evidence cannot be VERIFIED). The runner therefore
    cannot construct a zero-evidence case through the
    public API; this test asserts that fact.
    """
    import dataclasses
    import pytest
    from paw.bench import CaseManifest
    m = _good_manifest(["src/<package_name>/core.py"])
    with pytest.raises(ValueError, match="expected_evidence"):
        dataclasses.replace(m, expected_evidence=[])


# --- 3. Determinism (E0-06) ------------------------------------------


def test_two_runs_with_same_seed_are_byte_identical() -> None:
    m = _good_manifest([
        "src/<package_name>/core.py",
        "tests/test_core.py",
        "docs/ARCHITECTURE.md",
    ])
    r1 = run_case(
        m, project_root=PROJECT_ROOT, runs=1, seed="s1",
        deterministic_timestamps=True,
    )
    r2 = run_case(
        m, project_root=PROJECT_ROOT, runs=1, seed="s1",
        deterministic_timestamps=True,
    )
    assert r1.rows[0].to_jsonl() == r2.rows[0].to_jsonl()


def test_runs_jsonl_preserves_run_order() -> None:
    m = _good_manifest([
        "src/<package_name>/core.py",
        "tests/test_core.py",
    ])
    result = run_case(m, project_root=PROJECT_ROOT, runs=5, seed="multi")
    assert len(result.rows) == 5
    for i, row in enumerate(result.rows, start=1):
        assert row.run_index == i
        assert row.seed == "multi"


# --- 4. Command-exit safety (E0-03 deny-list) -----------------------


def test_command_exit_with_safe_command_succeeds() -> None:
    """``grep -F -q`` returns exit 0 if the substring is
    present, exit 1 if it is not. The verify passes
    when ``value == "0"`` because exit 0 means the
    substring was found.
    """
    fixture = "benchmarks/e0/fixtures/small_repo_tree.txt"
    m = CaseManifest(
        case_id="test_safe_command",
        schema_version=CASE_MANIFEST_SCHEMA_VERSION,
        category=CaseCategory.REPO_UNDERSTANDING,
        privacy_class=PrivacyClass.WORKSPACE,
        goal="Run a safe read-only command.",
        fixtures=[
            FixtureRef(
                path=fixture, revision="f3ad4ef", purpose="test fixture"
            ),
        ],
        expected_evidence=[
            ExpectedEvidence(
                kind="command_exit",
                # List-literal form; the runner parses argv
                # with ast.literal_eval and runs without a
                # shell. ``grep -F -q`` returns 0 if found.
                target=f'["grep", "-F", "-q", "--", "src/<package_name>", "{fixture}"]',
                value="0",
                reviewer="alice@example.com",
            ),
        ],
        timeout_seconds=10,
        max_iterations=5,
    )
    result = run_case(m, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "SUCCESS"


def test_command_exit_with_deny_list_token_fails_safely() -> None:
    """``rm`` is on the deny-list; the runner refuses to
    even invoke the command, so the verify reports FAIL
    with a deny-list reason (not a runtime error).
    """
    m = CaseManifest(
        case_id="test_deny_list",
        schema_version=CASE_MANIFEST_SCHEMA_VERSION,
        category=CaseCategory.REPO_UNDERSTANDING,
        privacy_class=PrivacyClass.WORKSPACE,
        goal="A command on the deny-list must not run.",
        fixtures=[
            FixtureRef(
                path="benchmarks/e0/fixtures/small_repo_tree.txt",
                revision="f3ad4ef",
                purpose="test fixture",
            ),
        ],
        expected_evidence=[
            ExpectedEvidence(
                kind="command_exit",
                # List-literal form; ``rm`` is on the deny-list.
                target='["rm", "-rf", "/"]',
                value="0",
                reviewer="alice@example.com",
            ),
        ],
        timeout_seconds=10,
        max_iterations=5,
    )
    result = run_case(m, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "FAILURE"
    assert result.rows[0].passed_evidence == 0


def test_command_exit_with_unparseable_command_fails() -> None:
    m = CaseManifest(
        case_id="test_unparseable",
        schema_version=CASE_MANIFEST_SCHEMA_VERSION,
        category=CaseCategory.REPO_UNDERSTANDING,
        privacy_class=PrivacyClass.WORKSPACE,
        goal="An unparseable command is rejected, not invoked.",
        fixtures=[
            FixtureRef(
                path="benchmarks/e0/fixtures/small_repo_tree.txt",
                revision="f3ad4ef",
                purpose="test fixture",
            ),
        ],
        expected_evidence=[
            ExpectedEvidence(
                kind="command_exit",
                target="[this is not valid",
                value="0",
                reviewer="alice@example.com",
            ),
        ],
        timeout_seconds=10,
        max_iterations=5,
    )
    result = run_case(m, project_root=PROJECT_ROOT)
    assert result.rows[0].outcome == "FAILURE"


# --- 5. Manifest loader errors ---------------------------------------


def test_load_case_rejects_invalid_manifest(tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("case_id: ''\n")  # empty required string
    with pytest.raises(ValueError, match="case_id"):
        load_case(bad)


# --- 6. Repeated-runs summary (E0-06) --------------------------------


def test_summary_counts_outcomes_across_runs() -> None:
    """E0-06: the summary aggregates outcomes across runs."""
    m = _good_manifest([
        "src/<package_name>/core.py",
        "tests/test_core.py",
    ])
    result = run_case(m, project_root=PROJECT_ROOT, runs=3)
    summary = result.summary()
    assert summary["runs"] == 3
    assert summary["outcomes"] == {"SUCCESS": 3}
    assert summary["passed_evidence_total"] == 6
    assert summary["total_evidence_total"] == 6
    assert summary["unsafe_preconditions_observed"] is False


# --- 7. End-to-end smoke test (E0-16 deliverable) ---------------------


@pytest.mark.parametrize("case_id", [
    "repo_understand_small_repo",
    "defect_localization_simple_math",
    "cross_module_change_constant",
    "refactor_rename_function",
    "architecture_decision_cache",
    "interrupted_recovery_midway",
    "privacy_negative_secret_marker",
    "insufficient_context_empty_goal",
])
def test_every_minimum_case_loads_and_runs(case_id: str) -> None:
    """All 8 E0 cases load via the runner and produce a
    row. Outcomes are not asserted (the deterministic
    runner scores file_contains; the future
    runtime-driven runner will score the other kinds);
    the contract is "no crash, valid JSONL row".
    """
    case_path = BENCH_DIR / f"{case_id}.yaml"
    result = run_case_file(case_path, project_root=PROJECT_ROOT)
    assert len(result.rows) >= 1
    for row in result.rows:
        assert row.case_id == case_id
        assert row.outcome in {"SUCCESS", "PARTIAL", "FAILURE", "UNSAFE"}


# --- 8. paw.core 11-symbol surface preserved -------------------------


def test_paw_core_public_surface_unchanged_after_e0_16() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected_runtime = {
        "AutonomyDecision",
        "Capability",
        "ExecutionObservation",
        "PawRuntime",
        "PolicyDecision",
        "ProposedAction",
        "ResourceUsage",
        "RuntimeOutcome",
        "StopReason",
        "TaskResult",
        "TaskStatus",
    }
    assert expected_runtime.issubset(set(symbols))


# --- 9. CLI smoke test -----------------------------------------------


def test_cli_runs_one_case(tmp_path) -> None:
    """The runner can be invoked from a subprocess via
    ``python -c``; this proves the module is importable
    and the entry point works end-to-end.
    """
    case_path = BENCH_DIR / "repo_understand_small_repo.yaml"
    out = tmp_path / "runs.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path;"
                "from paw.bench import run_case_file, write_runs_jsonl;"
                f"r = run_case_file(Path({str(case_path)!r}));"
                f"write_runs_jsonl(r, Path({str(out)!r}))"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, (
        f"CLI smoke failed: {result.stderr!r}"
    )
    assert out.is_file()
    assert out.read_text().count("\n") == 1
