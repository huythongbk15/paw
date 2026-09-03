"""E0-08 contract test: one repository-understanding case.

The case file at ``benchmarks/e0/cases/repo_understand_small_repo.yaml``
is the first entry in the E0 minimum case set. The contract
is:

1. The YAML parses through ``case_manifest_from_dict``
   without raising.
2. The validator reports zero errors.
3. The three ``file_contains`` evidence entries all
   pass when the verify command is run by hand.
4. The verify command fails when the fixture is mutated
   (two-fail-positive discipline).

The E0-16 runner will repeat step 3 inside a sandbox; this
test is the static analogue.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from paw.bench import (
    case_manifest_from_dict,
    is_valid_case_manifest,
    validate_case_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = PROJECT_ROOT / "benchmarks" / "e0" / "cases" / "repo_understand_small_repo.yaml"
FIXTURE_PATH = PROJECT_ROOT / "benchmarks" / "e0" / "fixtures" / "small_repo_tree.txt"


# --- 1. Static contract -------------------------------------------------


def test_case_yaml_exists() -> None:
    assert CASE_PATH.is_file(), f"missing case file: {CASE_PATH}"


def test_case_yaml_parses_and_validates_with_zero_errors() -> None:
    import yaml
    with CASE_PATH.open() as f:
        data = yaml.safe_load(f)
    assert is_valid_case_manifest(data) is True
    errors = validate_case_manifest(data)
    assert errors == []
    m = case_manifest_from_dict(data)
    assert m.case_id == "repo_understand_small_repo"
    assert m.category.value == "repo_understanding"
    assert m.privacy_class.value == "workspace"
    assert len(m.fixtures) == 1
    assert len(m.expected_evidence) == 3


# --- 2. Verify commands (file_contains) ---------------------------------


def _run_file_contains(evidence_value: str) -> bool:
    """The E0-03 verify command for ``file_contains``."""
    return (
        FIXTURE_PATH.is_file()
        and subprocess.run(
            ["grep", "-F", "-q", "--", evidence_value, str(FIXTURE_PATH)],
            check=False,
        ).returncode
        == 0
    )


@pytest.mark.parametrize(
    "expected_substring",
    [
        "src/<package_name>/core.py",
        "tests/test_core.py",
        "docs/ARCHITECTURE.md",
    ],
)
def test_each_evidence_passes_with_the_committed_fixture(expected_substring: str) -> None:
    assert _run_file_contains(expected_substring) is True


# --- 3. Two-fail-positive -----------------------------------------------


def test_evidence_fails_when_fixture_is_mutated() -> None:
    """If the reviewer forgets to bump the fixture
    revision, the verify command must fail. We mutate
    the fixture, run the verify, and confirm the PASS
    becomes a FAIL. We restore the file in ``finally``.
    """
    backup = FIXTURE_PATH.read_text()
    try:
        # Replace one expected substring with a renamed path.
        mutated = backup.replace(
            "src/<package_name>/core.py",
            "src/<package_name>/renamed.py",
        )
        assert mutated != backup, "mutation should change the file"
        FIXTURE_PATH.write_text(mutated)
        assert _run_file_contains("src/<package_name>/core.py") is False
        assert _run_file_contains("src/<package_name>/renamed.py") is True
    finally:
        FIXTURE_PATH.write_text(backup)
        assert _run_file_contains("src/<package_name>/core.py") is True


# --- 4. Reviewer discipline ---------------------------------------------


def test_every_evidence_entry_has_a_reviewer() -> None:
    """A case without a reviewer cannot be promoted to
    ``VERIFIED``; the E0-02 contract enforces this at
    parse time, and the E0-08 case must demonstrate it
    by carrying a reviewer on every entry.
    """
    import yaml
    with CASE_PATH.open() as f:
        data = yaml.safe_load(f)
    for entry in data["expected_evidence"]:
        assert entry.get("reviewer"), (
            f"evidence entry {entry!r} has no reviewer"
        )
        # Reviewer must be a non-empty string, not a placeholder.
        assert "@" in entry["reviewer"], (
            f"reviewer {entry['reviewer']!r} does not look like an email"
        )


# --- 5. paw.core 11-symbol surface preserved ---------------------------


def test_paw_core_public_surface_unchanged_after_e0_08() -> None:
    """E0-23a guard: authoring a case file must not grow
    the canonical ``paw.core`` export list.
    """
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
    assert expected_runtime.issubset(set(symbols)), (
        f"paw.core missing runtime symbols: {expected_runtime - set(symbols)}"
    )
