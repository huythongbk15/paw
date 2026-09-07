"""Behavioral integration tests with controlled compiler outputs."""
from pathlib import Path
from types import SimpleNamespace
import shutil

import pytest

from paw.bench.integration import run_integration_pack


class Compiler:
    def __init__(self, content, tokens):
        self.calls = []
        self.content = content
        self.tokens = tokens

    async def compile_manifest(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            included=[SimpleNamespace(
                reference="benchmarks/e0/fixtures/architecture_decision.txt",
                content=self.content,
            )],
            final_tokens=self.tokens,
        )


@pytest.mark.parametrize("exists", [False, True])
async def test_empty_directory_is_blocked(tmp_path, exists):
    cases = tmp_path / "cases"
    if exists:
        cases.mkdir()
    compiler = Compiler("", 0)
    result = await run_integration_pack(
        cases, compiler=compiler, repo_root=tmp_path,
        report_path=tmp_path / "report.md",
    )
    assert result.gate_decision == "BLOCKED"
    assert not compiler.calls


@pytest.mark.parametrize(("content", "tokens", "decision"), [
    ("Option A: in-memory cache Decision: choose Option A", 60, "PASS"),
    ("Option A: in-memory cache Decision: choose Option A", 90, "PARTIAL"),
    ("Option A: in-memory cache Decision: choose Option A", 200, "PARTIAL"),
    ("Option A: in-memory cache", 60, "PARTIAL"),
    ("unrelated", 60, "FAIL"),
])
async def test_measurement_gate(tmp_path, content, tokens, decision):
    cases = tmp_path / "cases"
    cases.mkdir()
    shutil.copy(
        Path("benchmarks/e0/cases/architecture_decision_cache.yaml"),
        cases / "case.yaml",
    )
    compiler = Compiler(content, tokens)
    result = await run_integration_pack(
        cases, compiler=compiler, repo_root=tmp_path,
        report_path=tmp_path / "report.md",
        baseline_tokens={"architecture_decision_cache": 100},
    )
    assert result.gate_decision == decision
    assert result.case_count == 1
    assert len(compiler.calls) == 2
    assert all("budget" not in call for call in compiler.calls)
    assert [r.mode for r in result.recall_results] == ["cold", "warm"]
    assert [r.mode for r in result.token_results] == ["cold", "warm"]
    assert result.token_results[1].reduction == (100 - tokens) / 100
    assert "not full E1 qualification" in result.report_path.read_text()
