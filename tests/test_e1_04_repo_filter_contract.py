"""E1-04 contract test: deterministic include/exclude rules for repository files.

The contract is documented in
``docs/benchmarks/e1/repo_filter_rules.md``.
The test pins:

- the field set, defaults, and ``safe_default()``;
- the ``match`` predicate on a representative matrix
  (include only, exclude only, both, depth cutoff,
  bad path, leading ``/``, ``..`` segments);
- the ``filter_paths`` determinism (same input → same
  output, byte-identical, ordering stable, ``max_files``
  ceiling);
- the construction-time hardening (``max_files <= 0``,
  ``max_depth <= 0``, absolute pattern, ``..`` pattern,
  empty pattern);
- the ``ContextPlan`` accepts a ``repo_filter`` field and
  exposes it;
- the ``_retrieve_repo_candidates`` flow is wired to the
  filter (the contract test exercises the flow with a
  stubbed path list and a stubbed ``repo_filter``).

Two-fail-positive discipline: this test is added
together with the filter and the wiring. Reverting the
wiring would break the integration test; reverting the
hardening would break the construction-time rejects.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from paw.core.context_compiler import ContextPlan
from paw.core.repo_filter import SAFE_DEFAULT_EXCLUDES, RepoFilter


REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "docs" / "benchmarks" / "e1" / "repo_filter_rules.md"


# --- 1. Field set + defaults -------------------------------------------


def test_repo_filter_fields_and_defaults() -> None:
    f = RepoFilter()
    assert f.include_patterns == ()
    assert f.exclude_patterns == ()
    assert f.max_files == 200
    assert f.max_depth == 8


def test_repo_filter_is_frozen_and_hashable() -> None:
    """Frozen so the object is hashable; the runtime can
    use it as a dict key or compare two filters by
    equality without worrying about mutation."""
    f = RepoFilter()
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.max_files = 10  # type: ignore[misc]
    # Hashable + equality.
    g = RepoFilter()
    assert hash(f) == hash(g)
    assert f == g


# --- 2. safe_default ----------------------------------------------------


def test_safe_default_excludes_pin() -> None:
    """The contract test pins the literal default-exclude
    set; changing it is a change-control surface."""
    assert SAFE_DEFAULT_EXCLUDES == (
        "__pycache__",
        ".git",
        ".venv",
        "node_modules",
        "*.pyc",
        "*.tmp",
        "*.pyo",
        "*.swp",
    )


def test_safe_default_factory() -> None:
    f = RepoFilter.safe_default()
    assert f.exclude_patterns == SAFE_DEFAULT_EXCLUDES
    assert f.include_patterns == ()
    # The safe default rejects the common build-output dirs.
    assert f.match("src/paw/core/memory.py") is True
    assert f.match("__pycache__/foo.pyc") is False
    assert f.match("src/__pycache__/foo.py") is False
    assert f.match(".git/HEAD") is False
    assert f.match("foo.tmp") is False


# --- 3. match predicate matrix ----------------------------------------


@pytest.mark.parametrize(
    "rel_path,expected",
    [
        # Plain include-only filter accepts the path.
        ("src/paw/core/memory.py", True),
        ("tests/test_phase1.py", True),
        # Exclude wins.
        ("__pycache__/foo.py", False),
        (".git/HEAD", False),
        ("foo.pyc", False),
        ("foo.tmp", False),
        # Bad path inputs (fail-closed).
        ("", False),
        ("/etc/passwd", False),
        ("../etc/passwd", False),
        ("src/../../etc/passwd", False),
        (".", False),
    ],
)
def test_match_safe_default(rel_path, expected) -> None:
    f = RepoFilter.safe_default()
    assert f.match(rel_path) is expected


def test_match_include_only_filter() -> None:
    f = RepoFilter(include_patterns=("src/**/*.py",))
    assert f.match("src/paw/core/memory.py") is True
    assert f.match("src/paw/memory.py") is True
    # ``*`` in fnmatch does not match ``/`` by default,
    # so a top-level file is rejected.
    assert f.match("tests/test_phase1.py") is False


def test_match_depth_cutoff() -> None:
    f = RepoFilter(max_depth=2)
    # 2-part path: ok.
    assert f.match("src/memory.py") is True
    # 3-part path: rejected.
    assert f.match("src/paw/memory.py") is False


# --- 4. filter_paths determinism --------------------------------------


def test_filter_paths_is_deterministic() -> None:
    """Two calls with the same input produce the same
    output, byte-identical."""
    f = RepoFilter(include_patterns=("src/**/*.py",))
    paths = [
        "src/paw/memory.py",
        "src/paw/core/memory.py",
        "src/paw/core/skills.py",
        "src/__pycache__/foo.py",
        "tests/test_phase1.py",
    ]
    a = f.filter_paths(paths)
    b = f.filter_paths(paths)
    assert a == b
    # And the order is lexicographic by POSIX parts.
    expected = sorted(
        [
            "src/paw/memory.py",
            "src/paw/core/memory.py",
            "src/paw/core/skills.py",
            "src/__pycache__/foo.py",
        ],
        key=lambda s: (Path(s).parts, s),
    )
    assert a == expected


def test_filter_paths_respects_max_files() -> None:
    f = RepoFilter(max_files=2)
    paths = [f"src/paw/a{i}.py" for i in range(5)]
    out = f.filter_paths(paths)
    assert len(out) == 2
    # The survivors are the first two in sorted order.
    assert out == sorted(paths)[:2]


def test_filter_paths_rejects_duplicate() -> None:
    f = RepoFilter()
    with pytest.raises(ValueError, match="duplicate path"):
        f.filter_paths(["src/a.py", "src/a.py"])


def test_filter_paths_silently_drops_bad_paths() -> None:
    """A single bad path is dropped; the call still
    succeeds. (The construction-time hardening is the
    contract; ``filter_paths`` does not raise per-path.)"""
    f = RepoFilter.safe_default()
    out = f.filter_paths(
        [
            "src/paw/memory.py",
            "",
            "/etc/passwd",
            "../escape.py",
            "src/paw/skills.py",
        ]
    )
    assert out == ["src/paw/memory.py", "src/paw/skills.py"]


# --- 5. Construction-time hardening -----------------------------------


def test_max_files_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_files must be > 0"):
        RepoFilter(max_files=0)
    with pytest.raises(ValueError, match="max_files must be > 0"):
        RepoFilter(max_files=-1)


def test_max_depth_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_depth must be > 0"):
        RepoFilter(max_depth=0)
    with pytest.raises(ValueError, match="max_depth must be > 0"):
        RepoFilter(max_depth=-1)


@pytest.mark.parametrize(
    "pat",
    [
        "",
        "/abs/path",
        "..",
        "src/../../etc",
    ],
)
def test_unsafe_include_pattern_rejected(pat) -> None:
    with pytest.raises(ValueError, match="include pattern is unsafe"):
        RepoFilter(include_patterns=(pat,))


@pytest.mark.parametrize(
    "pat",
    [
        "",
        "/abs/path",
        "..",
        "src/../../etc",
    ],
)
def test_unsafe_exclude_pattern_rejected(pat) -> None:
    with pytest.raises(ValueError, match="exclude pattern is unsafe"):
        RepoFilter(exclude_patterns=(pat,))


# --- 6. ContextPlan integration ----------------------------------------


def test_context_plan_accepts_repo_filter() -> None:
    """The new field is part of the contract; a reviewer
    who instantiates a ``ContextPlan`` with no filter gets
    ``None`` (no filter; the compiler falls back to the
    safe default)."""
    plan = ContextPlan(task_id="t", query="q", token_budget=1000)
    assert plan.repo_filter is None

    f = RepoFilter(include_patterns=("src/**/*.py",))
    plan2 = ContextPlan(
        task_id="t", query="q", token_budget=1000, repo_filter=f
    )
    assert plan2.repo_filter is f


# --- 7. _retrieve_repo_candidates wiring ------------------------------


async def test_retrieve_repo_candidates_uses_plan_filter() -> None:
    """The wiring test exercises the real ``_retrieve_repo_candidates``
    with an explicit filter; the result must honor the
    filter and record the filter's repr in the candidate
    metadata."""
    from paw.core.context_compiler import ContextCompiler

    compiler = ContextCompiler()
    plan = ContextPlan(
        task_id="t",
        query="q",
        token_budget=1000,
        include_repo=True,
        repo_paths=[
            "src/paw/memory.py",
            "__pycache__/foo.pyc",
            ".git/HEAD",
            "src/paw/skills.py",
        ],
        repo_filter=RepoFilter(),  # no rules, accept all
    )
    out = await compiler._retrieve_repo_candidates(plan)
    # Without a filter, every path is accepted (the
    # filter defaults to match-everything).
    assert {c.source_id for c in out} == {
        "src/paw/memory.py",
        "__pycache__/foo.pyc",
        ".git/HEAD",
        "src/paw/skills.py",
    }
    # The candidate metadata records the filter's repr so
    # the E1-17 manifest inspector is inspectable.
    for c in out:
        assert "filter" in c.metadata
        assert "RepoFilter" in c.metadata["filter"]


async def test_retrieve_repo_candidates_uses_safe_default_when_no_filter() -> None:
    """When ``include_repo=True`` but the plan has no
    explicit filter, the compiler falls back to the safe
    default (which rejects ``__pycache__`` / ``.git`` /
    ``*.tmp``)."""
    from paw.core.context_compiler import ContextCompiler

    compiler = ContextCompiler()
    plan = ContextPlan(
        task_id="t",
        query="q",
        token_budget=1000,
        include_repo=True,
        repo_paths=[
            "src/paw/memory.py",
            "__pycache__/foo.pyc",
            "foo.tmp",
        ],
    )
    out = await compiler._retrieve_repo_candidates(plan)
    assert {c.source_id for c in out} == {"src/paw/memory.py"}


# --- 8. Doc sync -------------------------------------------------------


def test_e1_04_spec_documents_safe_default() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")
    # The spec documents the safe-default excludes; it
    # must list every default pattern.
    for pat in SAFE_DEFAULT_EXCLUDES:
        assert pat in spec, f"spec missing default-exclude {pat!r}"
    # The spec is a Phase 4 sync contract; it must
    # reference the contract test file.
    assert "test_e1_04_repo_filter_contract.py" in spec
    # And the change-control surface (the contract test
    # that pins the literals).
    m = re.search(
        r"SAFE_DEFAULT_EXCLUDES\s*=\s*\(([^)]+)\)",
        spec,
    )
    assert m is not None, "spec missing SAFE_DEFAULT_EXCLUDES literal"