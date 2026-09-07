"""Regression tests for scripts/run_e1_measurement.py.

The script's contract is documented at
``docs/IMPLEMENTATION_MAP.md`` §"Measurement provenance repair" and the
execution record below that section. These tests pin:

- the script runs end-to-end and never overwrites an existing report;
- the JSON records HEAD + dirty state + per-case recall/tokens;
- per-case isolation (each case uses a fresh SQLite DB, no global state);
- the fixture corpus is ingested BEFORE compile (not substituted by skills);
- a malformed case (missing fixture) propagates as `qualification: BLOCKED`.

No mocks for storage / bench modules; real temp SQLite per case.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path("scripts/run_e1_measurement.py")


def _run(tmp_path: Path, output: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_script_runs_and_writes_report(tmp_path: Path) -> None:
    """End-to-end: the script produces a non-empty JSON with the
    documented schema fields."""
    out = tmp_path / "report.json"
    result = _run(tmp_path, out)
    assert result.returncode == 0, result.stderr
    assert out.exists()
    report = json.loads(out.read_text())
    # Documented schema fields
    assert report["scope"].startswith("diagnostic")
    assert "revision" in report
    assert "dirty" in report
    assert report["baseline_method"].startswith("sum TokenEstimator")
    assert report["baseline_status"].startswith("diagnostic")
    assert "configuration" in report
    assert report["embeddings"] == "disabled"
    assert report["unverified"] == [
        "privacy", "answer quality", "cache benefit", "cloud savings",
    ]
    assert "hashes" in report
    assert "cases" in report
    assert len(report["cases"]) == 4  # 2 cases x 2 modes
    assert report["qualification"] == "PARTIAL"


def test_script_records_inputs_unchanged(tmp_path: Path) -> None:
    """Inputs_unchanged must be True for a fresh, unmodified run."""
    out = tmp_path / "report.json"
    result = _run(tmp_path, out)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    assert report["inputs_unchanged"] is True
    assert report["revision_unchanged"] is True


def test_script_never_overwrites_existing_report(tmp_path: Path) -> None:
    """The output path opens with mode='x' (exclusive create), so
    re-running on an existing path must fail loudly, not silently
    overwrite the prior report."""
    out = tmp_path / "report.json"
    result = _run(tmp_path, out)
    assert result.returncode == 0
    # Second run on the same path must fail
    result2 = _run(tmp_path, out)
    assert result2.returncode != 0
    # The original report must still be intact
    report = json.loads(out.read_text())
    assert report["scope"].startswith("diagnostic")


def test_recall_matches_fixture_content_not_skills(tmp_path: Path) -> None:
    """Both cases must achieve recall = 1.0 in cold and warm modes
    because the script ingests the actual fixture corpus via
    KnowledgeSourceManager + KnowledgeChunkStore before compiling."""
    out = tmp_path / "report.json"
    result = _run(tmp_path, out)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    for entry in report["cases"]:
        recall = entry["recall"]
        assert recall["total_evidence"] == 2
        assert recall["recalled"] == 2
        assert recall["missed"] == []
        assert recall["recall"] == 1.0


def test_baseline_tokens_match_fixture_size(tmp_path: Path) -> None:
    """Baseline tokens must come from the actual fixture files, not
    arbitrary 4000/3000. The two fixture files are ~700 bytes and
    ~500 bytes; TokenEstimator estimates are well under 200 per case."""
    out = tmp_path / "report.json"
    result = _run(tmp_path, out)
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text())
    by_case = {}
    for entry in report["cases"]:
        if entry["tokens"]["mode"] == "cold":
            by_case[entry["tokens"]["case_id"]] = entry["tokens"]["baseline_tokens"]
    # Both cases must have small baselines (well under 1000)
    for case_id, baseline in by_case.items():
        assert 0 < baseline < 1000, (
            f"case {case_id} has suspicious baseline {baseline}; "
            f"should be derived from actual fixture, not arbitrary"
        )


def test_per_case_sqlite_isolation(tmp_path: Path) -> None:
    """Each case runs in its own TemporaryDirectory; the script must
    not reuse a single global DB across cases. Verify by inspecting
    the script source for TemporaryDirectory use."""
    script_text = SCRIPT.read_text()
    assert "TemporaryDirectory(prefix=\"paw-e1-\")" in script_text
    # And the per-case DB is created inside the temporary directory
    assert "directory" in script_text
    assert "measurement.db" in script_text


def test_script_does_not_substitute_skills_for_files(tmp_path: Path) -> None:
    """The previous (incorrect) draft suggested letting skills count
    as file evidence. The script must instead ingest the case's
    fixture files via KnowledgeSourceManager and KnowledgeChunkStore."""
    script_text = SCRIPT.read_text()
    # Fixture ingestion is wired
    assert "KnowledgeSourceManager" in script_text
    assert "KnowledgeChunkStore" in script_text
    assert "manager.create" in script_text
    assert "add_chunk" in script_text
    # The script reads fixture paths from the case manifest, not
    # from the skill fabric
    assert "case.fixtures" in script_text
