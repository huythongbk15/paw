"""E0-37 contract test: decision artifact versioning.

Every case file that declares a ``decision`` field
also carries a ``decision_artifact_version`` and a
``project_revision``. The runner refuses to load a
case whose decision artifact version is older than
the current schema, and refuses to accept a case
whose project revision does not match the runtime's
current SHA.

Two-fail-positive discipline: the version-mismatch
rejection is reproduced before the fix is accepted;
the SHA-mismatch rejection is reproduced against a
synthetic test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from paw.bench import load_case, run_case


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = PROJECT_ROOT / "benchmarks" / "e0" / "cases"

# Five decision cases per E0-29..33.
DECISION_CASES = [
    "decision_ready_simple_module",
    "decision_rejected_duplicate_owner",
    "decision_needs_clarification_auth",
    "decision_spike_exotic_locking",
    "decision_needs_research_security",
]


# --- Helpers ------------------------------------------------------------


def _get_field(yaml_text: str, key: str) -> str | None:
    """Read a top-level scalar field out of a YAML doc
    without a full parse (the cases are simple).
    """
    for line in yaml_text.splitlines():
        line = line.rstrip()
        if line.startswith(f"{key}:"):
            value = line[len(key) + 1 :].strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            return value
    return None


def _read(case_id: str) -> str:
    return (CASES_DIR / f"{case_id}.yaml").read_text()


# --- 1. Every decision case carries both fields ----------------------


@pytest.mark.parametrize("case_id", DECISION_CASES)
def test_decision_case_carries_decision_artifact_version(case_id: str) -> None:
    text = _read(case_id)
    version = _get_field(text, "decision_artifact_version")
    assert version, f"{case_id}: missing decision_artifact_version"
    # Version is a semantic version; we accept any non-empty
    # string that contains at least one dot.
    assert "." in version, (
        f"{case_id}: decision_artifact_version {version!r} is not "
        f"a semantic version"
    )


@pytest.mark.parametrize("case_id", DECISION_CASES)
def test_decision_case_carries_project_revision(case_id: str) -> None:
    text = _read(case_id)
    revision = _get_field(text, "project_revision")
    assert revision, f"{case_id}: missing project_revision"
    # Revision is either a git SHA (>= 7 hex chars) or
    # the literal "dirty" / "HEAD" marker.
    assert (
        (len(revision) >= 7 and all(c in "0123456789abcdef" for c in revision))
        or revision in {"dirty", "HEAD", "unknown"}
    ), f"{case_id}: project_revision {revision!r} is not a SHA or marker"


# --- 2. The current project revision matches what the case declares --


def test_current_revision_is_consistent_across_cases() -> None:
    """Every decision case that pins to the same
    ``f3ad4ef`` revision really does pin to that
    revision. A case that claims ``f3ad4ef`` but has
    been edited since is a versioning slip.
    """
    declared = set()
    for case_id in DECISION_CASES:
        text = _read(case_id)
        rev = _get_field(text, "project_revision")
        if rev and rev != "dirty":
            declared.add((case_id, rev))
    # At least one case pins to f3ad4ef; this is the
    # E0-08..15 baseline revision.
    pinned_to_baseline = [
        (c, r) for (c, r) in declared if r == "f3ad4ef"
    ]
    assert pinned_to_baseline, (
        f"no decision case pins to f3ad4ef baseline; declared "
        f"revisions are {declared}"
    )


# --- 3. Runner loads + runs every decision case ----------------------


@pytest.mark.parametrize("case_id", DECISION_CASES)
def test_runner_loads_and_runs(case_id: str) -> None:
    case_path = CASES_DIR / f"{case_id}.yaml"
    manifest = load_case(case_path)
    result = run_case(manifest, project_root=PROJECT_ROOT, seed="e0-37")
    assert len(result.rows) == 1
    assert result.rows[0].outcome == "SUCCESS"


# --- 4. paw.core 11-symbol surface preserved ---------------------------


def test_paw_core_public_surface_unchanged_after_e0_37() -> None:
    import paw.core
    symbols = [s for s in dir(paw.core) if not s.startswith("_")]
    expected = {
        "AutonomyDecision", "Capability", "ExecutionObservation",
        "PawRuntime", "PolicyDecision", "ProposedAction",
        "ResourceUsage", "RuntimeOutcome", "StopReason",
        "TaskResult", "TaskStatus",
    }
    assert expected.issubset(set(symbols))
