"""E1-08 contract test: bounded repository tree view.

The contract is documented in
``docs/benchmarks/e1/bounded_tree_view.md``.
The test pins:

- the ``TreeNode`` shape (``name``, ``path``, ``kind``,
  ``children``, ``file_count``, ``leaf_count``);
- the ``scan_tree`` behavior on a real temp filesystem:
  empty root, single file, mixed tree, deep tree,
  filter-driven exclusion, the symlink/traversal
  negative controls, the ``max_files`` cap, the
  ``max_depth`` cap, the determinism guarantee.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.core.repo_filter import RepoFilter
from paw.core.repo_scanner import TreeNode, scan_tree


# --- 1. TreeNode shape -------------------------------------------------


def test_tree_node_is_frozen_and_immutable() -> None:
    import dataclasses

    n = TreeNode(name="x", path="x", kind="file")
    with pytest.raises(dataclasses.FrozenInstanceError):
        n.name = "y"  # type: ignore[misc]


def test_tree_node_is_file_property() -> None:
    f = TreeNode(name="x", path="x", kind="file")
    d = TreeNode(name="x", path="x", kind="dir")
    assert f.is_file() is True
    assert f.is_dir() is False
    assert d.is_file() is False
    assert d.is_dir() is True


# --- 2. scan_tree: empty root ------------------------------------------


def test_scan_tree_empty_root(tmp_path) -> None:
    (tmp_path / "root").mkdir()
    tree = scan_tree(tmp_path / "root", RepoFilter())
    assert tree.name == "."
    assert tree.path == "."
    assert tree.kind == "dir"
    assert tree.children == ()
    assert tree.file_count == 0
    assert tree.leaf_count == 0


# --- 3. scan_tree: single file ----------------------------------------


def test_scan_tree_single_file(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_text("alpha")
    tree = scan_tree(root, RepoFilter())
    assert tree.file_count == 1
    assert tree.leaf_count == 1
    assert len(tree.children) == 1
    only = tree.children[0]
    assert only.name == "a.py"
    assert only.path == "a.py"
    assert only.kind == "file"
    assert only.children == ()


# --- 4. scan_tree: mixed tree ------------------------------------------


def test_scan_tree_mixed_tree(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    # Top-level files.
    (root / "a.py").write_text("a")
    (root / "b.py").write_text("b")
    # Subdirectory with two files.
    sub = root / "sub"
    sub.mkdir()
    (sub / "x.py").write_text("x")
    (sub / "y.py").write_text("y")
    # Nested deeper.
    deep = sub / "deep"
    deep.mkdir()
    (deep / "z.py").write_text("z")

    tree = scan_tree(root, RepoFilter())
    # File counts: 5 (a, b, x, y, z).
    assert tree.file_count == 5
    assert tree.leaf_count == 5
    # Top-level: a.py, b.py, sub/ (3 entries, sorted).
    top_names = [c.name for c in tree.children]
    assert top_names == ["a.py", "b.py", "sub"]
    # The sub directory has 2 files (x, y) + the deep dir.
    sub_node = next(c for c in tree.children if c.name == "sub")
    assert sub_node.file_count == 3  # x, y, deep/z
    sub_names = [c.name for c in sub_node.children]
    assert sub_names == ["deep", "x.py", "y.py"]


# --- 5. Symlink negative controls --------------------------------------


def test_scan_tree_symlink_root_rejected(tmp_path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symbolic link"):
        scan_tree(link, RepoFilter())


def test_scan_tree_follow_symlinks_rejected(tmp_path) -> None:
    (tmp_path / "r").mkdir()
    with pytest.raises(ValueError, match="follow_symlinks"):
        scan_tree(tmp_path / "r", RepoFilter(), follow_symlinks=True)


def test_scan_tree_symlink_file_skipped(tmp_path) -> None:
    external = tmp_path / "external.txt"
    external.write_text("secret")
    root = tmp_path / "root"
    root.mkdir()
    (root / "keep.py").write_text("ok")
    (root / "leak.py").symlink_to(external)
    tree = scan_tree(root, RepoFilter())
    names = {c.name for c in tree.children}
    assert "keep.py" in names
    assert "leak.py" not in names
    assert tree.file_count == 1


def test_scan_tree_symlink_dir_skipped(tmp_path) -> None:
    external = tmp_path / "external_dir"
    external.mkdir()
    (external / "leak.py").write_text("secret")
    root = tmp_path / "root"
    root.mkdir()
    (root / "keep.py").write_text("ok")
    (root / "linked").symlink_to(external)
    tree = scan_tree(root, RepoFilter())
    names = {c.name for c in tree.children}
    assert "keep.py" in names
    assert "linked" not in names
    assert tree.file_count == 1


# --- 6. Filter integration ---------------------------------------------


def test_scan_tree_safe_default_excludes_pycache(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.py").write_text("ok")
    pc = root / "__pycache__"
    pc.mkdir()
    (pc / "x.pyc").write_text("bin")
    tree = scan_tree(root, RepoFilter.safe_default())
    assert tree.file_count == 1
    names = {c.name for c in tree.children}
    assert "ok.py" in names
    assert "__pycache__" not in names


# --- 7. Cap -----------------------------------------------------------


def test_scan_tree_respects_max_files(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for i in range(10):
        (root / f"f{i:02d}.py").write_text("x")
    tree = scan_tree(root, RepoFilter(max_files=3))
    assert tree.file_count == 3


def test_scan_tree_respects_max_depth(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    cur = root
    for i in range(5):
        cur = cur / f"d{i}"
        cur.mkdir()
    (cur / "leaf.py").write_text("x")
    # max_depth=2: only ``root/d0/`` is reachable; the
    # leaf at depth 6 is excluded.
    tree = scan_tree(root, RepoFilter(max_depth=2))
    assert tree.file_count == 0
    # max_depth=6: the leaf is reachable.
    tree2 = scan_tree(root, RepoFilter(max_depth=6))
    assert tree2.file_count == 1


# --- 8. Determinism --------------------------------------------------


def test_scan_tree_deterministic(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for name in ["c.py", "a.py", "b.py"]:
        (root / name).write_text("x")
    sub = root / "sub"
    sub.mkdir()
    for name in ["z.py", "x.py", "y.py"]:
        (sub / name).write_text("x")
    a = scan_tree(root, RepoFilter())
    b = scan_tree(root, RepoFilter())
    # Two TreeNode trees are equal iff every field is
    # equal. Children order is sorted, so this is a
    # robust equality check.
    assert a == b