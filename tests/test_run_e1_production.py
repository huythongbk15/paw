"""Contract tests for the tracked E1 production measurement runner."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from paw.bench.e1_production import (
    _chunk_python_file,
    _measurement_decision,
    measure,
)
from paw.core.context import ContextBudget

MODULE = "paw.bench.e1_production"


def _run(args: list[str], output: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", MODULE, *args, "--output", str(output)],
        capture_output=True, text=True, timeout=120,
    )


@pytest.fixture
def fresh_output(tmp_path: Path) -> Path:
    return tmp_path / "report.json"


def test_synthetic_corpus_proves_measurement_mechanics(fresh_output: Path) -> None:
    result = _run([
        "--roots", "benchmarks/e1/fixtures_paw",
        "--case-dir", "benchmarks/e1/cases_prod",
        "--max-tokens", "1500", "--max-fragments", "5", "--max-sources", "3",
    ], fresh_output)
    assert result.returncode == 0, result.stderr
    report = json.loads(fresh_output.read_text())
    assert report["metric_gate"] == "PASS"
    assert report["min_recall"] == 1.0
    assert report["median_warm_reduction"] >= 0.30
    assert len(report["samples"]) == 24
    assert report["fixtures_fresh"] is True
    assert report["measurement_gate"] == (
        "PARTIAL" if report["dirty"] else "PASS"
    )


def test_paw_source_is_the_representative_gate(fresh_output: Path) -> None:
    result = _run([
        "--roots", "src/paw", "--case-dir", "benchmarks/e1/cases",
        "--max-tokens", "5000", "--max-fragments", "30", "--max-sources", "10",
    ], fresh_output)
    assert result.returncode == 0, result.stderr
    report = json.loads(fresh_output.read_text())
    assert report["metric_gate"] == "PASS"
    assert report["min_recall"] >= 0.95
    assert report["median_warm_reduction"] >= 0.30
    assert report["measurement_gate"] != "PASS" or not report["dirty"]


def test_report_records_revision_hashes_and_evidence_state(fresh_output: Path) -> None:
    result = _run([
        "--roots", "benchmarks/e1/fixtures_paw",
        "--case-dir", "benchmarks/e1/cases_prod",
    ], fresh_output)
    assert result.returncode == 0, result.stderr
    report = json.loads(fresh_output.read_text())
    assert len(report["revision"]) == 40
    assert isinstance(report["dirty"], bool)
    assert report["evidence_state"] in {"OBSERVED", "VERIFIED"}
    assert report["revision_unchanged"] is True
    assert report["inputs_unchanged"] is True
    assert report["tree_state_unchanged"] is True
    assert report["evidence_state"] == (
        "VERIFIED" if report["measurement_gate"] == "PASS" else "OBSERVED"
    )
    for file in Path("benchmarks/e1/fixtures_paw").glob("*.py"):
        assert str(file) in report["input_hashes"]


def test_existing_report_is_preserved(fresh_output: Path) -> None:
    fresh_output.write_text("original", encoding="utf-8")
    result = _run([], fresh_output)
    assert result.returncode != 0
    assert fresh_output.read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize(("content", "expected"), [
    ("class Foo:\n    def bar(self):\n        return 1\n\ndef baz():\n    return 2\n", 3),
    ("this is { not python", 0),
    ("x = 1\ny = 2\n", 0),
])
def test_function_level_chunking(content: str, expected: int) -> None:
    chunks = _chunk_python_file("test.py", content)
    assert len(chunks) == expected
    assert all(start <= end and text for start, end, text in chunks)


def test_runner_is_part_of_the_paw_package() -> None:
    module_path = Path(__import__("paw.bench.e1_production", fromlist=["x"]).__file__)
    assert module_path.name == "e1_production.py"


def test_dirty_tree_cannot_self_certify_a_pass() -> None:
    decision, reasons = _measurement_decision(
        metric_gate="PASS",
        dirty=True,
        revision_unchanged=True,
        inputs_unchanged=True,
        tree_state_unchanged=True,
        fixtures_fresh=True,
    )
    assert decision == "PARTIAL"
    assert "dirty tree" in reasons[0]


@pytest.mark.asyncio
async def test_changed_input_during_run_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    import paw.bench.e1_production as production

    original = production._snapshot
    calls = 0

    def changed_snapshot(paths, repo_root):
        nonlocal calls
        calls += 1
        snapshot = original(paths, repo_root)
        if calls == 2:
            first = next(iter(snapshot))
            snapshot[first] = "changed-during-run"
        return snapshot

    monkeypatch.setattr(production, "_snapshot", changed_snapshot)
    report = await measure(
        repo_root=Path.cwd(),
        roots=["benchmarks/e1/fixtures_paw"],
        case_dir="benchmarks/e1/cases_prod",
        budget=ContextBudget(max_tokens=1500, max_fragments=5, max_sources=3),
    )
    assert report["metric_gate"] == "PASS"
    assert report["inputs_unchanged"] is False
    assert report["measurement_gate"] == "BLOCKED"
