"""PAW Knowledge — file content checksum (E1-06).

``compute_checksum`` is the single source of truth for
the SHA-256 hex digest of a file's content. The
function is shared between the ``SourceDiff`` detection
loop and any future consumer (the E1-08 bounded tree
view, the E1-17 manifest inspector) that needs a
content hash.

The function is pure: same file content → same hash.
It is fail-closed on a symlink, on a non-existent
path, and on a directory path; the E1-05 scanner's
posture is the model.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from paw.core.repo_filter import RepoFilter
from paw.core.repo_scanner import scan_repo


def compute_checksum(file_path: str | Path, *, max_bytes: int | None = None) -> str:
    """Return the SHA-256 hex digest of ``file_path``'s content.

    The file is read in 64 KiB chunks; the memory
    footprint stays bounded for arbitrarily large files.
    The function refuses to follow symlinks (a symlink
    path raises ``ValueError``), refuses non-existent
    paths (``FileNotFoundError``), and refuses
    directories (``ValueError``).

    The return value is a lowercase 64-character hex
    string; an empty file returns the SHA-256 of the
    empty string
    (``e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855``).
    """
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
        raise ValueError("checksum byte limit must be a non-negative integer")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file does not exist: {path}")
    if path.is_symlink():
        raise ValueError(
            f"refusing to hash a symbolic link: {path}. "
            f"Pass the resolved file instead."
        )
    if path.is_dir():
        raise ValueError(f"path is a directory, not a file: {path}")
    sha = hashlib.sha256()
    consumed = 0
    if max_bytes is None:
        reader = path.open("rb")
    else:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        reader = os.fdopen(os.open(path, flags), "rb")
    with reader as fh:
        if max_bytes is not None and not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            raise ValueError("bounded checksum requires a regular file")
        while True:
            amount = 65536 if max_bytes is None else min(65536, max_bytes - consumed + 1)
            chunk = fh.read(amount)
            if not chunk:
                break
            consumed += len(chunk)
            if max_bytes is not None and consumed > max_bytes:
                raise ValueError("checksum byte limit exceeded")
            sha.update(chunk)
    return sha.hexdigest()


def compute_repo_revision(
    root: str | Path, repo_filter: RepoFilter, *, max_bytes: int = 33554432,
    max_entries: int = 10000,
) -> str:
    """Hash complete bounded eligible content, root and filter, including dirty files.

    Caller must authorize filesystem reads before invoking this operation.
    Detects observed concurrent changes but does not lock out external writers.
    """
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("repository byte limit must be a non-negative integer")
    root = Path(root)
    paths = scan_repo(root, repo_filter, require_complete=True, max_entries=max_entries)
    manifest = []
    signatures = {}
    consumed = 0

    def signature(path):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("repository input must be a regular file")
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("repository input escaped root")
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    for relative in paths:
        path = root / relative
        before = signature(path)
        if consumed + before[2] > max_bytes:
            raise ValueError("repository byte limit exceeded")
        digest = compute_checksum(path, max_bytes=max_bytes - consumed)
        if signature(path) != before:
            raise ValueError("repository input changed during snapshot")
        consumed += before[2]
        signatures[relative] = before
        manifest.append((relative, digest))
    if scan_repo(root, repo_filter, require_complete=True, max_entries=max_entries) != paths:
        raise ValueError("repository input set changed during snapshot")
    if any(signature(root / relative) != value for relative, value in signatures.items()):
        raise ValueError("repository input changed during snapshot")
    encoded = json.dumps(
        {"root": str(root.resolve()), "filter": asdict(repo_filter), "files": manifest},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def compute_constraint_fingerprint(constraints: Mapping[str, object]) -> str:
    """Digest server-configured hard constraints, not a caller-provided digest."""
    if not isinstance(constraints, Mapping) or not constraints:
        raise ValueError("hard constraints must be a nonempty mapping")
    if any(not isinstance(key, str) for key in constraints):
        raise ValueError("hard constraint keys must be strings")
    try:
        encoded = json.dumps(dict(constraints), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("hard constraints must be finite JSON-shaped values") from error
    return hashlib.sha256(encoded.encode()).hexdigest()


__all__ = ["compute_checksum"]
