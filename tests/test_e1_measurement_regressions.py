"""Behavioral negative controls for measurement integrity."""
from types import SimpleNamespace
from pathlib import Path

import pytest

from paw.bench.recall import measure_recall
from paw.bench.tokens import measure_tokens
from paw.knowledge.history import re_evaluate_on_revision


class Compiler:
    def __init__(self, manifest):
        self.manifest = manifest
        self.calls = []

    async def compile_manifest(self, **kwargs):
        self.calls.append(kwargs)
        return self.manifest


def case():
    return SimpleNamespace(case_id="measurement-negative", goal="find code", expected_evidence=[
        SimpleNamespace(kind="file_contains", target="a.py", value="needle"),
        SimpleNamespace(kind="file_contains", target="b.py", value="needle"),
    ])


async def test_token_regression_is_negative():
    result = await measure_tokens(case(), compiler=Compiler(SimpleNamespace(final_tokens=200)),
                                  repo_root=Path.cwd(), mode="cold", baseline_tokens=100)
    assert result.reduction == -1.0


async def test_missing_baseline_rejected():
    with pytest.raises(ValueError, match="baseline"):
        await measure_tokens(case(), compiler=Compiler(SimpleNamespace(final_tokens=100)),
                             repo_root=Path.cwd(), mode="cold")


async def test_recall_preserves_budget_and_distinct_sources():
    compiler = Compiler(SimpleNamespace(included=[
        SimpleNamespace(content="needle", reference="a.py", source_id="opaque")]))
    result = await measure_recall(case(), compiler=compiler, repo_root=Path.cwd(), mode="cold")
    assert result.recall == 0.5
    assert result.total_evidence == 2
    assert "budget" not in compiler.calls[0]


async def test_ancestor_revision_is_stale():
    result = await re_evaluate_on_revision(pinned_revision="old", current_revision="new",
                                           recent_changes=[SimpleNamespace(sha="old")])
    assert result.stale


@pytest.mark.parametrize("baseline", [0, -1, True, 1.5, float("nan")])
async def test_invalid_baseline_rejected(baseline):
    compiler = Compiler(SimpleNamespace(final_tokens=10))
    with pytest.raises(ValueError, match="baseline"):
        await measure_tokens(case(), compiler=compiler, repo_root=Path.cwd(),
                             mode="warm", baseline_tokens=baseline)
    assert not compiler.calls


async def test_compile_error_is_not_hidden():
    class Broken:
        async def compile_manifest(self, **kwargs):
            raise RuntimeError("compile failed")

    with pytest.raises(RuntimeError, match="compile failed"):
        await measure_recall(case(), compiler=Broken(), repo_root=Path.cwd(), mode="warm")


async def test_wrong_source_cannot_satisfy_recall():
    compiler = Compiler(SimpleNamespace(included=[
        SimpleNamespace(content="needle", reference="wrong.py", source_id="a.py")]))
    result = await measure_recall(case(), compiler=compiler, repo_root=Path.cwd(), mode="cold")
    assert result.recall == 0


async def test_knowledge_external_id_is_source_identity():
    compiler = Compiler(SimpleNamespace(included=[
        SimpleNamespace(content="needle", reference="opaque-chunk", external_id="a.py")]))
    result = await measure_recall(case(), compiler=compiler, repo_root=Path.cwd(), mode="cold")
    assert result.recall == 0.5


@pytest.mark.parametrize("evidence", [[], [SimpleNamespace(kind="ledger_event")]])
async def test_unsupported_or_empty_evidence_rejected(evidence):
    item = case()
    item.expected_evidence = evidence
    with pytest.raises(ValueError):
        await measure_recall(item, compiler=Compiler(None), repo_root=Path.cwd(), mode="cold")
