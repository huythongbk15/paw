"""Regression tests for scripts/run_e1_production.py.

The runner is the production-corpus measurement path for E1-27. It
differs from the diagnostic runner (test_run_e1_measurement.py) in
three ways:

- It ingests a reviewed production corpus (default: the PAW source
  tree or a synthetic 12-file corpus at benchmarks/e1/fixtures_paw).
- Python files are chunked by top-level function/class definition
  (one KnowledgeSource per file, multiple KnowledgeChunks).
- The baseline is the sum of every chunk's token estimate + the
  always-on skill overhead.

These tests pin the runner contract:

1. The script runs end-to-end on the synthetic corpus and produces a
   JSON that satisfies the E1-27 gate (PASS).
2. The JSON records HEAD + dirty state + per-case recall + per-case
   reduction + hashes for every input file.
3. The script refuses to overwrite an existing report.
4. The function-level chunker produces multiple chunks per file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/run_e1_production.py")


def _run(args: list[str], output: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def fresh_output(tmp_path: Path) -> Path:
    return tmp_path / "report.json"


class TestScriptRunsAndPassesGate:
    """On the synthetic 12-file corpus, the runner produces a PASS
    report (recall=1.00, reduction=0.81)."""

    def test_synthetic_corpus_passes_e1_27(self, fresh_output: Path) -> None:
        result = _run(
            [
                "--roots", "benchmarks/e1/fixtures_paw",
                "--case-dir", "benchmarks/e1/cases_prod",
                "--max-tokens", "1500",
                "--max-fragments", "5",
                "--max-sources", "3",
            ],
            fresh_output,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(fresh_output.read_text())
        assert report["qualification"] == "PASS"
        assert report["min_recall"] == 1.0
        assert report["median_warm_reduction"] >= 0.30
        # 12 cases x 2 modes = 24 samples
        assert len(report["cases"]) == 24
        # Every case has recall=1.0 on both modes
        for entry in report["cases"]:
            assert entry["recall"]["recall"] == 1.0


class TestScriptMetadata:
    """The runner records provenance + per-file hashes."""

    def test_records_revision_and_dirty(self, fresh_output: Path) -> None:
        _run(
            [
                "--roots", "benchmarks/e1/fixtures_paw",
                "--case-dir", "benchmarks/e1/cases_prod",
            ],
            fresh_output,
        )
        report = json.loads(fresh_output.read_text())
        assert "revision" in report
        assert "dirty" in report
        assert isinstance(report["dirty"], bool)
        assert "script_hash" in report
        assert "corpus_hashes" in report
        assert "case_hashes" in report

    def test_corpus_hashes_match_corpus(self, fresh_output: Path) -> None:
        _run(
            [
                "--roots", "benchmarks/e1/fixtures_paw",
                "--case-dir", "benchmarks/e1/cases_prod",
            ],
            fresh_output,
        )
        report = json.loads(fresh_output.read_text())
        # Every file under fixtures_paw has a hash
        corpus_dir = Path("benchmarks/e1/fixtures_paw")
        for f in sorted(corpus_dir.glob("*.py")):
            rel = str(f)
            assert rel in report["corpus_hashes"]


class TestScriptNeverOverwrites:
    """The output path opens with mode='x' (exclusive-create)."""

    def test_existing_report_is_preserved(self, fresh_output: Path) -> None:
        result1 = _run(
            [
                "--roots", "benchmarks/e1/fixtures_paw",
                "--case-dir", "benchmarks/e1/cases_prod",
            ],
            fresh_output,
        )
        assert result1.returncode == 0
        report_before = fresh_output.read_text()
        result2 = _run(
            [
                "--roots", "benchmarks/e1/fixtures_paw",
                "--case-dir", "benchmarks/e1/cases_prod",
            ],
            fresh_output,
        )
        assert result2.returncode != 0
        assert fresh_output.read_text() == report_before


class TestFunctionLevelChunking:
    """The runner chunks Python files by top-level def/class."""

    def test_chunk_python_file_returns_chunks(self) -> None:
        from scripts.run_e1_production import _chunk_python_file

        content = (
            "class Foo:\n"
            "    def bar(self):\n"
            "        return 1\n\n"
            "def baz():\n"
            "    return 2\n"
        )
        chunks = _chunk_python_file("test.py", content)
        assert len(chunks) == 2
        # Each chunk is (span_start, span_end, content)
        starts = [c[0] for c in chunks]
        assert 1 in starts
        # The Foo class is on line 1, the baz function starts later
        assert any("class Foo" in c[2] for c in chunks)
        assert any("def baz" in c[2] for c in chunks)

    def test_unparseable_file_returns_empty(self) -> None:
        from scripts.run_e1_production import _chunk_python_file

        chunks = _chunk_python_file("bad.py", "this is { not python")
        assert chunks == []

    def test_file_with_no_top_level_defs_returns_empty(self) -> None:
        from scripts.run_e1_production import _chunk_python_file

        chunks = _chunk_python_file("empty.py", "x = 1\ny = 2\n")
        assert chunks == []
