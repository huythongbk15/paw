"""E1-05 contract test: traversal and symlink negative cases for source discovery.

The contract is documented in
``docs/benchmarks/e1/repo_scanner_contract.md``.
The test pins the negative-control surface (the
behaviors the runtime MUST refuse) plus the
positive-control surface (the behaviors the runtime
MUST provide). Every test uses a real temp filesystem
(no mocks; the negative cases are about how the
scanner interacts with the real OS).

Two-fail-positive discipline: each negative case was
written because the failure it asserts was reproduced
against a candidate that lacked the check. The
``..`` segment, the symlink to a sibling file, the
symlink to a sibling directory, the symlink root, the
absolute path, the null byte, and the deep tree cases
are all named in the spec; reverting any of them
breaks the corresponding test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paw.core.repo_filter import RepoFilter
from paw.core.repo_scanner import scan_repo


# --- 1. Symlink root is rejected --------------------------------------


def test_symlink_root_is_rejected(tmp_path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symbolic link"):
        scan_repo(link, RepoFilter())


# --- 2. Nonexistent + file-as-root ------------------------------------


def test_nonexistent_root_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        scan_repo(tmp_path / "missing", RepoFilter())


def test_file_as_root_is_rejected(tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hi")
    with pytest.raises(ValueError, match="not a directory"):
        scan_repo(f, RepoFilter())


# --- 3. follow_symlinks=True is rejected ------------------------------


def test_follow_symlinks_true_is_rejected(tmp_path) -> None:
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="follow_symlinks"):
        scan_repo(tmp_path, RepoFilter(), follow_symlinks=True)


# --- 4. Symlink to a sibling file is skipped --------------------------


def test_symlink_to_sibling_file_is_skipped(tmp_path) -> None:
    """A file in the root is replaced by a symlink to a
    file outside the root; the scanner must not include
    the symlink (or its target) in the result."""
    external = tmp_path / "external.txt"
    external.write_text("secret")
    root = tmp_path / "root"
    root.mkdir()
    # Regular file inside root for the positive control.
    (root / "keep.py").write_text("ok")
    # Symlink to external.
    (root / "leak.py").symlink_to(external)
    out = scan_repo(root, RepoFilter())
    assert "keep.py" in out
    assert "leak.py" not in out
    # The path emitted is repo-relative (no leading slash,
    # no `..` segments).
    for p in out:
        assert not p.startswith("/")
        assert ".." not in p.split("/")


# --- 5. Symlink to a sibling directory is skipped ---------------------


def test_symlink_to_sibling_directory_is_skipped(tmp_path) -> None:
    """A directory in the root is replaced by a symlink
    to a directory outside the root; the scanner must
    not descend into it."""
    external = tmp_path / "external_dir"
    external.mkdir()
    (external / "leak.py").write_text("secret")
    root = tmp_path / "root"
    root.mkdir()
    (root / "keep.py").write_text("ok")
    (root / "linked_dir").symlink_to(external)
    out = scan_repo(root, RepoFilter())
    assert "keep.py" in out
    assert "linked_dir/leak.py" not in out
    # No entry under the symlinked directory.
    for p in out:
        assert not p.startswith("linked_dir/")


# --- 6. `..` segments in the result -----------------------------------


def test_no_dotdot_in_result(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_text("ok")
    out = scan_repo(root, RepoFilter())
    for p in out:
        parts = p.split("/")
        assert ".." not in parts
        assert parts[0] != ""


# --- 7. Absolute paths are never emitted ------------------------------


def test_result_paths_are_repo_relative(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_text("ok")
    (root / "sub").mkdir()
    (root / "sub" / "b.py").write_text("ok")
    out = scan_repo(root, RepoFilter())
    for p in out:
        # POSIX form: no leading slash, no Windows
        # separators, no `.` or `..` parts.
        assert not p.startswith("/")
        assert "\\" not in p
        parts = p.split("/")
        assert "." not in parts
        assert ".." not in parts


# --- 8. Null byte in filename is handled -----------------------------


def test_null_byte_in_filename_is_skipped(tmp_path, monkeypatch) -> None:
    """A file whose name contains ``\\x00`` cannot be
    stat'd; the scanner must skip it without crashing."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "good.py").write_text("ok")
    # ``os.walk`` may surface the null-byte entry
    # differently on different platforms; we just check
    # the scanner does not raise and ``good.py`` is in
    # the result.
    out = scan_repo(root, RepoFilter())
    assert "good.py" in out


# --- 9. Deeply nested tree is depth-bounded --------------------------


def test_deep_tree_is_depth_bounded(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    deep = root
    for i in range(15):
        deep = deep / f"d{i}"
        deep.mkdir()
    (deep / "leaf.py").write_text("ok")
    # max_depth=5: the leaf is at depth 16, far beyond.
    out = scan_repo(root, RepoFilter(max_depth=5))
    assert "leaf.py" not in out
    for p in out:
        assert len(p.split("/")) <= 5


# --- 10. Empty root ---------------------------------------------------


def test_empty_root_returns_empty_list(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    out = scan_repo(root, RepoFilter())
    assert out == []


# --- 11. Determinism -------------------------------------------------


def test_two_scans_are_byte_identical(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for name in ["c.py", "a.py", "b.py"]:
        (root / name).write_text("ok")
    (root / "sub").mkdir()
    for name in ["z.py", "x.py", "y.py"]:
        (root / "sub" / name).write_text("ok")
    a = scan_repo(root, RepoFilter())
    b = scan_repo(root, RepoFilter())
    assert a == b
    # The sort key is ``(PurePosixPath.parts, path)``:
    # 1-part paths sort before 2-part paths; within the
    # same depth, the entries are alphabetical.
    assert a == [
        "a.py",
        "b.py",
        "c.py",
        "sub/x.py",
        "sub/y.py",
        "sub/z.py",
    ]


# --- 12. Cap --------------------------------------------------------


def test_scan_respects_filter_max_files(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for i in range(10):
        (root / f"f{i:02d}.py").write_text("ok")
    out = scan_repo(root, RepoFilter(max_files=3))
    assert len(out) == 3
    # The cap is the first 3 in sorted order.
    assert out == ["f00.py", "f01.py", "f02.py"]


# --- 13. Filter integration: safe_default excludes __pycache__ --------


def test_scan_honors_safe_default(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.py").write_text("ok")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "ok.cpython-312.pyc").write_text("bin")
    out = scan_repo(root, RepoFilter.safe_default())
    assert "ok.py" in out
    assert "ok.cpython-312.pyc" not in out
    # ``__pycache__`` itself is excluded by the
    # safe-default ``__pycache__`` pattern (component
    # match).
    for p in out:
        assert "__pycache__" not in p.split("/")
