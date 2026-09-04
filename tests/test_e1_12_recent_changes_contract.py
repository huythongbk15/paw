"""E1-12 contract test: recent-change and affected-area views from local VCS evidence.

The contract is documented in
``docs/benchmarks/e1/recent_changes.md``.
The test pins:

- ``recent_changes``: empty / non-git path (clean
  no-op, no crash); ordering (most-recent first);
  parse correctness (sha, author, date, message,
  changed files); ``since`` filter; ``max_count``
  cap; determinism;
- ``affected_areas``: E1-10 symbol join (per-file
  filter); E1-11 test association join (per-file
  filter); the output is sorted by date desc;
  determinism;
- shell=False posture: the function never receives a
  shell string as ``since``; a malformed ``since``
  ref returns ``[]`` cleanly.

The contract test uses a real temp git repo (no
mocks); the ``git log`` subprocess is the real binary
on the system PATH.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from paw.knowledge.changes import (
    AffectedArea,
    RecentChange,
    affected_areas,
    recent_changes,
)


# --- 1. Helper: build a real temp git repo ----------------------------


def _init_repo(root: Path, files: dict[str, str]) -> None:
    """Initialize a git repo under ``root`` and commit
    every file in ``files`` (path -> content) as a
    single commit. The function shells out to ``git``
    with ``shell=False`` (the E1-03 hardening)."""
    root.mkdir(parents=True, exist_ok=True)
    # Drop a ``.gitignore`` that excludes the autouse
    # ``session_db`` fixture's paw.db file (the
    # function-scoped temp DB the conftest creates for
    # every test). Without this the initial commit
    # would include ``paw.db`` + ``paw.db-wal`` and the
    # ``changed_files`` tuple would be polluted.
    (root / ".gitignore").write_text("*.db\n*.db-wal\n*.db-shm\n")
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    # Init + commit in one go.
    subprocess.run(
        ["git", "init", "-q"],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )
    subprocess.run(
        ["git", "add", "."],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )


def _commit(root: Path, files: dict[str, str], message: str) -> str:
    """Add or update files in ``root`` and commit
    them with ``message``. Returns the new commit's
    short SHA."""
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    subprocess.run(
        ["git", "add", "."],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        shell=False, check=True, capture_output=True,
        cwd=str(root),
    )
    return result.stdout.decode("utf-8").strip()


# --- 2. Non-git path returns [] cleanly --------------------------------


def test_non_git_path_returns_empty(tmp_path) -> None:
    """A path that is not a git repo returns ``[]``;
    the function does not crash."""
    out = recent_changes(tmp_path)
    assert out == []


# --- 3. Single commit, single file -----------------------------------


def test_recent_changes_single_commit(tmp_path) -> None:
    _init_repo(tmp_path, {"a.py": "x = 1\n"})
    out = recent_changes(tmp_path)
    assert len(out) == 1
    c = out[0]
    # The initial commit includes the .gitignore we
    # drop in ``_init_repo`` and the file under test.
    # We check membership rather than equality so the
    # test is robust to the gitignore presence.
    assert "a.py" in c.changed_files
    assert ".gitignore" in c.changed_files
    assert c.message == "initial"
    assert c.author == "Test User"
    assert c.sha  # non-empty
    assert c.short_sha  # non-empty
    assert c.date  # ISO-8601


# --- 4. Most-recent-first ordering ------------------------------------


def test_recent_changes_ordering(tmp_path) -> None:
    _init_repo(tmp_path, {"a.py": "x = 1\n"})
    _commit(tmp_path, {"b.py": "y = 2\n"}, "second")
    _commit(tmp_path, {"c.py": "z = 3\n"}, "third")
    out = recent_changes(tmp_path)
    messages = [c.message for c in out]
    assert messages == ["third", "second", "initial"]


# --- 5. max_count cap -------------------------------------------------


def test_recent_changes_max_count(tmp_path) -> None:
    _init_repo(tmp_path, {"a.py": "x = 1\n"})
    for i in range(5):
        _commit(tmp_path, {f"f{i}.py": f"# {i}\n"}, f"commit {i}")
    out = recent_changes(tmp_path, max_count=3)
    assert len(out) == 3
    assert [c.message for c in out] == ["commit 4", "commit 3", "commit 2"]


# --- 6. since filter --------------------------------------------------


def test_recent_changes_since_ref(tmp_path) -> None:
    _init_repo(tmp_path, {"a.py": "x = 1\n"})
    first_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        shell=False, check=True, capture_output=True,
        cwd=str(tmp_path),
    ).stdout.decode("utf-8").strip()
    _commit(tmp_path, {"b.py": "y = 2\n"}, "second")
    out = recent_changes(tmp_path, since=first_sha)
    assert len(out) == 1
    assert out[0].message == "second"


# --- 7. Determinism --------------------------------------------------


def test_recent_changes_deterministic(tmp_path) -> None:
    _init_repo(tmp_path, {"a.py": "x = 1\n"})
    _commit(tmp_path, {"b.py": "y = 2\n"}, "second")
    a = recent_changes(tmp_path)
    b = recent_changes(tmp_path)
    assert a == b


# --- 8. affected_areas: E1-10 symbol join ----------------------------


def test_affected_areas_symbol_join(tmp_path) -> None:
    _init_repo(
        tmp_path,
        {
            "src/foo.py": "def bar():\n    pass\n",
            "tests/test_foo.py": "def test_bar():\n    pass\n",
        },
    )
    _commit(tmp_path, {"src/foo.py": "def bar():\n    return 1\n"}, "change foo")
    changes = recent_changes(tmp_path)
    out = affected_areas(
        changes,
        source_paths=["src/foo.py"],
        test_paths=["tests/test_foo.py"],
        repo_root=tmp_path,
    )
    assert len(out) == 2  # initial + change foo
    # The "change foo" commit changed src/foo.py; the
    # affected symbols include the module + the function.
    change_foo = next(a for a in out if a.change.message == "change foo")
    symbol_qualified = {s.qualified_name for s in change_foo.affected_symbols}
    assert "src.foo" in symbol_qualified
    assert "src.foo.bar" in symbol_qualified


def test_affected_areas_test_join(tmp_path) -> None:
    _init_repo(
        tmp_path,
        {
            "src/foo.py": "def bar():\n    pass\n",
            "tests/test_foo.py": "def test_bar():\n    pass\n",
        },
    )
    _commit(tmp_path, {"tests/test_foo.py": "def test_bar():\n    assert True\n"}, "change test")
    changes = recent_changes(tmp_path)
    out = affected_areas(
        changes,
        source_paths=["src/foo.py"],
        test_paths=["tests/test_foo.py"],
        repo_root=tmp_path,
    )
    # The "change test" commit touched tests/test_foo.py.
    change_test = next(a for a in out if a.change.message == "change test")
    test_qualified = {t.test_qualified_name for t in change_test.affected_tests}
    assert "tests.test_foo.test_bar" in test_qualified


def test_affected_areas_unrelated_commit_is_empty(tmp_path) -> None:
    _init_repo(
        tmp_path,
        {
            "src/foo.py": "def bar():\n    pass\n",
            "tests/test_foo.py": "def test_bar():\n    pass\n",
        },
    )
    # A change to a non-Python file: the affected_symbols
    # and affected_tests are empty for this commit.
    _commit(tmp_path, {"README.md": "hello\n"}, "docs only")
    changes = recent_changes(tmp_path)
    out = affected_areas(
        changes,
        source_paths=["src/foo.py"],
        test_paths=["tests/test_foo.py"],
        repo_root=tmp_path,
    )
    docs_commit = next(a for a in out if a.change.message == "docs only")
    assert docs_commit.affected_symbols == ()
    assert docs_commit.affected_tests == ()


# --- 9. affected_areas: date desc order -------------------------------


def test_affected_areas_date_desc(tmp_path) -> None:
    _init_repo(tmp_path, {"a.py": "x = 1\n"})
    _commit(tmp_path, {"b.py": "y = 2\n"}, "second")
    _commit(tmp_path, {"c.py": "z = 3\n"}, "third")
    changes = recent_changes(tmp_path)
    out = affected_areas(
        changes,
        source_paths=["a.py", "b.py", "c.py"],
        test_paths=[],
        repo_root=tmp_path,
    )
    messages = [a.change.message for a in out]
    assert messages == ["third", "second", "initial"]


# --- 10. Determinism: affected_areas ---------------------------------


def test_affected_areas_deterministic(tmp_path) -> None:
    _init_repo(
        tmp_path,
        {"src/foo.py": "def bar():\n    pass\n"},
    )
    _commit(tmp_path, {"src/foo.py": "def bar():\n    return 1\n"}, "change")
    changes = recent_changes(tmp_path)
    a = affected_areas(
        changes,
        source_paths=["src/foo.py"],
        test_paths=[],
        repo_root=tmp_path,
    )
    b = affected_areas(
        changes,
        source_paths=["src/foo.py"],
        test_paths=[],
        repo_root=tmp_path,
    )
    assert a == b


# --- 11. Malformed since ref returns [] cleanly ----------------------


def test_malformed_since_ref_returns_empty(tmp_path) -> None:
    _init_repo(tmp_path, {"a.py": "x = 1\n"})
    out = recent_changes(tmp_path, since="this-ref-does-not-exist")
    assert out == []


# --- 12. Dataclass shape ---------------------------------------------


def test_recent_change_is_frozen() -> None:
    import dataclasses

    c = RecentChange(
        sha="a" * 40,
        short_sha="a" * 7,
        author="x",
        date="2026-09-04T00:00:00+00:00",
        message="m",
        changed_files=("a.py",),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.message = "y"  # type: ignore[misc]


def test_affected_area_is_frozen() -> None:
    import dataclasses

    a = AffectedArea(
        change=RecentChange(
            sha="a" * 40,
            short_sha="a" * 7,
            author="x",
            date="2026-09-04T00:00:00+00:00",
            message="m",
        ),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.change = None  # type: ignore[misc]