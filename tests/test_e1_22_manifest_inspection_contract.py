"""E1-22 contract test: CLI / library inspection projection for the current manifest.

The contract is documented in
``docs/benchmarks/e1/manifest_inspection.md``.
The test pins:

- ``render_manifest`` returns a deterministic,
  line-oriented string;
- every ``ContextManifest`` field is present in the
  output;
- the empty-manifest case renders cleanly;
- the included / excluded / snapshot fields are
  rendered in the documented format.
"""

from __future__ import annotations

from paw.core.context import ContextBudget
from paw.core.context_compiler import (
    ContextCandidate,
    ContextManifest,
    render_manifest,
)


def _manifest(
    *,
    included: tuple = (),
    excluded: tuple = (),
    recent_changes: tuple = (),
    symbols: tuple = (),
    test_links: tuple = (),
    dependency_edges: tuple = (),
) -> ContextManifest:
    return ContextManifest(
        task_id="t1",
        budget=ContextBudget(max_tokens=12000),
        included=included,
        excluded=excluded,
        recent_changes=recent_changes,
        symbols=symbols,
        test_links=test_links,
        dependency_edges=dependency_edges,
        final_tokens=0,
    )


# --- 1. Empty manifest renders cleanly -------------------------


def test_empty_manifest_renders() -> None:
    out = render_manifest(_manifest())
    assert "# ContextManifest" in out
    assert "task_id: t1" in out
    assert "budget.max_tokens: 12000" in out
    assert "included: 0 items" in out
    assert "excluded: 0 items" in out
    assert "recent_changes: 0 items" in out
    assert "affected_areas: 0 items" in out
    assert "symbols: 0 items" in out
    assert "test_links: 0 items" in out
    assert "dependency_edges: 0 items" in out


# --- 2. Included candidate appears in the output --------------


def test_included_candidate_in_output() -> None:
    cand = ContextCandidate(
        source="memory", source_id="m1", content="",
        relevance_score=0.9, priority=1.0, token_estimate=42,
    )
    out = render_manifest(_manifest(included=(cand,)))
    assert "included: 1 items" in out
    assert "[memory] m1" in out
    assert "relevance=0.9" in out
    assert "tokens=42" in out


# --- 3. Excluded candidate appears with reason ---------------


def test_excluded_candidate_in_output() -> None:
    cand = ContextCandidate(source="x", source_id="a", content="")
    cand.metadata["excluded_reason"] = "token_budget_exceeded"
    out = render_manifest(_manifest(excluded=(cand,)))
    assert "excluded: 1 items" in out
    assert "[x] a" in out
    assert "reason=token_budget_exceeded" in out


# --- 4. Recent changes appear in the output ------------------


def test_recent_changes_in_output() -> None:
    from paw.knowledge.changes import RecentChange

    ch = RecentChange(
        sha="a" * 40,
        short_sha="abcdef1",
        author="alice",
        date="2026-09-04T12:00:00+00:00",
        message="first commit",
        changed_files=("a.py",),
    )
    out = render_manifest(_manifest(recent_changes=(ch,)))
    assert "recent_changes: 1 items" in out
    assert "abcdef1" in out
    assert "alice" in out
    assert "first commit" in out


# --- 5. Symbols and test links and deps appear ---------------


def test_symbols_and_test_links_and_deps_in_output() -> None:
    from paw.knowledge.dependencies import DependencyEdge
    from paw.knowledge.symbols import SymbolRecord
    from paw.knowledge.test_associations import TestLink

    sym = SymbolRecord(
        qualified_name="src.foo", kind="function",
        file="src/foo.py", line=1, col=0,
    )
    tl = TestLink(
        test_qualified_name="tests.test_foo.test_bar",
        test_file="tests/test_foo.py",
        source_qualified_name="src.foo.bar",
        source_file="src/foo.py",
        confidence=1.0, reason="direct_name",
    )
    de = DependencyEdge(
        from_path="src/foo.py", to_module="os",
        line=1, col=0, kind="absolute", confidence=1.0,
    )
    out = render_manifest(
        _manifest(symbols=(sym,), test_links=(tl,), dependency_edges=(de,))
    )
    assert "symbols: 1 items" in out
    assert "src.foo" in out
    assert "test_links: 1 items" in out
    assert "tests.test_foo.test_bar" in out
    assert "src.foo.bar" in out
    assert "dependency_edges: 1 items" in out
    assert "src/foo.py:1:0 -> os" in out


# --- 6. Determinism ---------------------------------------


def test_render_deterministic() -> None:
    m = _manifest(
        included=(ContextCandidate(source="x", source_id="a", content=""),)
    )
    a = render_manifest(m)
    b = render_manifest(m)
    assert a == b


# --- 7. Multi-line output ends with newline ----------------


def test_output_ends_with_newline() -> None:
    out = render_manifest(_manifest())
    assert out.endswith("\n")