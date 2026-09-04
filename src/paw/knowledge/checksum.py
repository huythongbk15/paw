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
from pathlib import Path


def compute_checksum(file_path: str | Path) -> str:
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
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


__all__ = ["compute_checksum"]
