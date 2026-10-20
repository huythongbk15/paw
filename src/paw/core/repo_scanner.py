"""PAW Core — deterministic repository scanner (E1-05 + E1-08).

``scan_repo`` walks a real filesystem root deterministically
and returns the repo-relative POSIX paths that a
``RepoFilter`` accepts. ``scan_tree`` turns the same walk
into a bounded, hierarchical tree view. Both share the
E1-05 symlink/traversal hardening.

The scanner enforces the same hardening the existing
``LocalFilesystemExecutor`` does for *write* operations:
``..`` segments are rejected, symlinks are never followed
(the symlink target may be outside the intended
workspace), absolute paths are never emitted, and null
bytes in filenames cause the OS-level call to fail
without crashing the scanner.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from .repo_filter import RepoFilter


def _assert_safe_root(root: Path) -> None:
    """Reject roots that are not safe to walk.

    The scanner refuses to walk through a symlink root
    because the symlink target may be outside the
    intended workspace. It also refuses non-existent
    paths, files (not directories), and paths that
    contain a null byte (which would be an OS-level
    error anyway; we surface it as a clear
    ``ValueError``).
    """
    raw = str(root)
    if "\x00" in raw:
        raise ValueError(f"repo root contains null byte: {raw!r}")
    if not root.exists():
        raise ValueError(f"repo root does not exist: {raw!r}")
    if root.is_symlink():
        raise ValueError(
            f"repo root is a symbolic link; refusing to walk: {raw!r}. "
            f"Pass the resolved directory instead."
        )
    if not root.is_dir():
        raise ValueError(f"repo root is not a directory: {raw!r}")


def _walk(
    root: Path, *, strict_filter: RepoFilter | None = None, max_entries: int = 10000,
) -> Iterable[Path]:
    """Deterministic walk over ``root`` that skips symlinks
    at every depth.

    The walk order is sorted by the entry name (case-folded
    so the order is identical on case-sensitive and
    case-insensitive filesystems). Symlinked entries are
    skipped entirely; their *lexical* presence is the
    negative control the E1-05 contract test exercises.

    Files that cannot be stat'd (a broken symlink, a
    permission error, a name with a null byte) are
    skipped without raising; the scanner's job is to
    return a list of usable paths, not to surface every
    transient filesystem error.
    """
    def unreadable(error):
        raise error

    walk_options = {"followlinks": False}
    if strict_filter is not None:
        walk_options["onerror"] = unreadable
    unbounded_depth = replace(strict_filter, max_depth=10**9) if strict_filter else None
    directory_filter = replace(unbounded_depth, include_patterns=()) if strict_filter else None
    seen = 0
    for dirpath, dirnames, filenames in os.walk(str(root), **walk_options):
        current = Path(dirpath)
        # Drop symlinked dirs in place so os.walk does not
        # descend into them. ``os.walk`` already respects
        # ``followlinks=False`` for the *traversal*, but a
        # symlink may still appear as a regular entry whose
        # real path is outside the root; we drop those.
        kept_dirs: list[str] = []
        for d in sorted(dirnames, key=str.casefold):
            if strict_filter is not None:
                seen += 1
                if seen > max_entries:
                    raise ValueError("repository entry limit exceeded")
                relative = (current / d).relative_to(root).as_posix()
                if not directory_filter.match(relative):
                    continue
                if len(PurePosixPath(relative).parts) >= strict_filter.max_depth:
                    raise ValueError("repository depth limit exceeded")
            try:
                p = current / d
            except ValueError:
                continue
            try:
                if p.is_symlink():
                    if strict_filter is not None:
                        raise ValueError("eligible repository symlink refused")
                    continue
                # Confirm the target stays inside ``root``;
                # any symlink with a resolved target outside
                # is also dropped.
                resolved = p.resolve(strict=False)
                if not resolved.is_relative_to(root.resolve(strict=False)):
                    if strict_filter is not None:
                        raise ValueError("repository path escaped root")
                    continue
                kept_dirs.append(d)
            except (OSError, ValueError):
                if strict_filter is not None:
                    raise
                continue
        dirnames[:] = kept_dirs

        for name in sorted(filenames, key=str.casefold):
            if strict_filter is not None:
                seen += 1
                if seen > max_entries:
                    raise ValueError("repository entry limit exceeded")
                relative = (current / name).relative_to(root).as_posix()
                if not unbounded_depth.match(relative):
                    continue
                if len(PurePosixPath(relative).parts) > strict_filter.max_depth:
                    raise ValueError("repository depth limit exceeded")
            if "\x00" in name:
                continue
            try:
                p = current / name
            except ValueError:
                continue
            try:
                if p.is_symlink():
                    if strict_filter is not None:
                        raise ValueError("eligible repository symlink refused")
                    continue
                resolved = p.resolve(strict=False)
                if not resolved.is_relative_to(root.resolve(strict=False)):
                    if strict_filter is not None:
                        raise ValueError("repository path escaped root")
                    continue
            except (OSError, ValueError):
                if strict_filter is not None:
                    raise
                continue
            yield p


def scan_repo(
    root: str | Path,
    repo_filter: RepoFilter,
    *,
    follow_symlinks: bool = False,
    require_complete: bool = False,
    max_entries: int = 10000,
) -> list[str]:
    """Walk ``root`` deterministically and return the
    repo-relative POSIX paths that ``repo_filter.match``
    accepts.

    The result is sorted lexicographically by
    ``pathlib.PurePosixPath`` parts (so the output is
    byte-identical across runs and platforms) and capped
    at ``repo_filter.max_files``. The cap is the
    reviewer's expectation, not the scanner's choice;
    a caller who wants no cap uses ``RepoFilter(max_files=10**9)``.

    ``follow_symlinks=False`` is the only supported mode
    in this contract. A ``ValueError`` is raised if a
    caller asks for ``follow_symlinks=True``: the E1-05
    contract is fail-closed on symlinks; a follow-up
    item may relax this with a separate change-control
    surface.
    """
    if require_complete:
        if type(max_entries) is not int or max_entries <= 0:
            raise ValueError("repository entry limit must be a positive integer")
        if type(repo_filter.max_files) is not int or type(repo_filter.max_depth) is not int:
            raise ValueError("complete repository file/depth limits must be integers")
    if follow_symlinks:
        raise ValueError(
            "follow_symlinks=True is not supported by the E1-05 contract; "
            "the scanner refuses to follow symbolic links at any depth"
        )
    root_path = Path(root)
    _assert_safe_root(root_path)
    if require_complete and any(parent.is_symlink() for parent in root_path.parents):
        raise ValueError("repository root has a symlink ancestor")
    # Collect every candidate first; sort; then apply the
    # filter once. The filter itself does the dedup, the
    # max_depth check, the include/exclude decision, and
    # the max_files cap.
    candidates: list[str] = []
    root_resolved = root_path.resolve(strict=False)
    # The walk is rooted at ``root_path``; the yielded
    # ``Path`` objects are relative to the cwd (the same
    # form as ``root_path`` itself). Resolve each one so
    # the ``relative_to`` step works regardless of
    # whether the caller passed an absolute or relative
    # ``root``.
    walk = (
        _walk(root_path, strict_filter=repo_filter, max_entries=max_entries)
        if require_complete else _walk(root_path)
    )
    for p in walk:
        try:
            rel = p.resolve(strict=False).relative_to(root_resolved)
        except ValueError:
            if require_complete:
                raise
            # Defensive: the is_relative_to guard above
            # should have caught this. Skip and continue.
            continue
        candidates.append(rel.as_posix())
        if require_complete and len(candidates) > repo_filter.max_files:
            raise ValueError("repository file limit exceeded")
    # Sort by POSIX parts for cross-platform determinism.
    candidates.sort(key=lambda s: (PurePosixPath(s).parts, s))
    return repo_filter.filter_paths(candidates)


__all__ = ["TreeNode", "scan_repo", "scan_tree"]


# --- E1-08: bounded tree view ----------------------------------------


@dataclass(frozen=True)
class TreeNode:
    """A node in the bounded repository tree.

    ``name`` is the single-part name (``"src"`` or
    ``"memory.py"``); ``path`` is the full repo-relative
    POSIX path. ``kind`` is ``"dir"`` for a directory and
    ``"file"`` for a file. ``children`` is empty for
    files; for directories, it is a tuple of
    ``TreeNode`` whose combined ``file_count`` equals
    this node's ``file_count``.

    ``file_count`` is the recursive count of *files*
    under this node (zero for a file, N for a directory
    whose subtree contains N files). ``leaf_count`` is
    the same as ``file_count`` but exposed for
    reviewer-friendly display.
    """

    name: str
    path: str
    kind: str
    children: tuple[TreeNode, ...] = ()
    file_count: int = 0
    leaf_count: int = 0

    def is_dir(self) -> bool:
        return self.kind == "dir"

    def is_file(self) -> bool:
        return self.kind == "file"


def _build_tree(
    rel_paths: Iterable[str],
    *,
    max_depth: int,
) -> TreeNode:
    """Assemble a ``TreeNode`` tree from a flat list of
    repo-relative POSIX paths. The function is pure: it
    does not touch the filesystem. ``max_depth`` is the
    depth cutoff (paths with more parts than ``max_depth``
    are dropped silently; the same contract
    ``RepoFilter`` enforces).
    """
    # Group by parent path. A path ``a/b/c.py`` belongs to
    # parent ``a/b``. The root's parent is ``.``.
    # We use a dict-of-dicts structure that mirrors the
    # directory hierarchy; ``""`` is the root's name.
    # Each node in ``tree`` is a (kind, children_map) pair
    # where ``kind`` is ``"dir"`` or ``"file"``.
    children_map: dict[str, dict] = {}

    for p in sorted(set(rel_paths)):
        parts = PurePosixPath(p).parts
        if not parts or len(parts) > max_depth:
            continue
        # Walk the tree, creating directories as we go.
        cur = children_map
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if part not in cur:
                cur[part] = {"kind": "dir", "children": {}}
            node = cur[part]
            if is_last:
                # The leaf is a file; the directory was
                # already created if the parent path
                # exists.
                node["kind"] = "file"
                node["children"] = {}
            cur = node["children"]

    def _make_node(
        name: str,
        path: str,
        node: dict,
    ) -> TreeNode:
        kind = node["kind"]
        if kind == "file":
            return TreeNode(
                name=name, path=path, kind="file",
                file_count=1, leaf_count=1,
            )
        # Directory: build children first, then count.
        kids: list[TreeNode] = []
        for child_name, child_node in sorted(node["children"].items()):
            child_path = (
                child_name if path == "."
                else f"{path}/{child_name}"
            )
            kids.append(_make_node(child_name, child_path, child_node))
        # Counts.
        fc = sum(c.file_count for c in kids)
        lc = sum(c.leaf_count for c in kids)
        return TreeNode(
            name=name, path=path, kind="dir",
            children=tuple(kids),
            file_count=fc, leaf_count=lc,
        )

    return _make_node(".", ".", {"kind": "dir", "children": children_map})


def scan_tree(
    root: str | Path,
    repo_filter: RepoFilter,
    *,
    follow_symlinks: bool = False,
) -> TreeNode:
    """Walk ``root`` and return a bounded tree view.

    The single root ``TreeNode`` has ``name='.'`` and
    ``path='.'``; its children are the top-level
    directories and files. The tree is bounded by
    ``repo_filter`` (same include/exclude + max_files +
    max_depth rules as ``scan_repo``). The tree is
    deterministic: same input → same output, in the
    same order. The function refuses to walk symlinks
    (fail-closed posture from ``scan_repo``).
    """
    paths = scan_repo(root, repo_filter, follow_symlinks=follow_symlinks)
    return _build_tree(paths, max_depth=repo_filter.max_depth)
