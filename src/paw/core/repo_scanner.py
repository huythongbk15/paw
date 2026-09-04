"""PAW Core — deterministic repository scanner (E1-05).

``scan_repo`` walks a real filesystem root deterministically
and returns the repo-relative POSIX paths that a
``RepoFilter`` accepts. The scanner is the *discovery*
half of the repository-loading contract; the
``RepoFilter`` is the *eligibility* half. The two are
composed: the caller passes a filter, the scanner walks
the tree, and every candidate is run through
``filter.match`` before it is added to the result.

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


def _walk(root: Path) -> Iterable[Path]:
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
    for dirpath, dirnames, filenames in os.walk(
        str(root), followlinks=False
    ):
        current = Path(dirpath)
        # Drop symlinked dirs in place so os.walk does not
        # descend into them. ``os.walk`` already respects
        # ``followlinks=False`` for the *traversal*, but a
        # symlink may still appear as a regular entry whose
        # real path is outside the root; we drop those.
        kept_dirs: list[str] = []
        for d in sorted(dirnames, key=str.casefold):
            try:
                p = current / d
            except ValueError:
                continue
            try:
                if p.is_symlink():
                    continue
                # Confirm the target stays inside ``root``;
                # any symlink with a resolved target outside
                # is also dropped.
                resolved = p.resolve(strict=False)
                if not resolved.is_relative_to(root.resolve(strict=False)):
                    continue
                kept_dirs.append(d)
            except (OSError, ValueError):
                continue
        dirnames[:] = kept_dirs

        for name in sorted(filenames, key=str.casefold):
            if "\x00" in name:
                continue
            try:
                p = current / name
            except ValueError:
                continue
            try:
                if p.is_symlink():
                    continue
                resolved = p.resolve(strict=False)
                if not resolved.is_relative_to(root.resolve(strict=False)):
                    continue
            except (OSError, ValueError):
                continue
            yield p


def scan_repo(
    root: str | Path,
    repo_filter: RepoFilter,
    *,
    follow_symlinks: bool = False,
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
    if follow_symlinks:
        raise ValueError(
            "follow_symlinks=True is not supported by the E1-05 contract; "
            "the scanner refuses to follow symbolic links at any depth"
        )
    root_path = Path(root)
    _assert_safe_root(root_path)
    # Collect every candidate first; sort; then apply the
    # filter once. The filter itself does the dedup, the
    # max_depth check, the include/exclude decision, and
    # the max_files cap.
    candidates: list[str] = []
    root_resolved = root_path.resolve(strict=False)
    for p in _walk(root_path):
        try:
            rel = p.relative_to(root_resolved)
        except ValueError:
            # Defensive: the is_relative_to guard above
            # should have caught this. Skip and continue.
            continue
        candidates.append(rel.as_posix())
    # Sort by POSIX parts for cross-platform determinism.
    candidates.sort(key=lambda s: (PurePosixPath(s).parts, s))
    return repo_filter.filter_paths(candidates)


__all__ = ["scan_repo"]
