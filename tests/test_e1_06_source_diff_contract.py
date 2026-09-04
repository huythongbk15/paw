"""E1-06 contract test: incremental changed/unchanged/deleted source detection.

The contract is documented in
``docs/benchmarks/e1/source_incremental_diff.md``.
The test pins:

- ``compute_checksum``: deterministic SHA-256, empty-file
  hash, symlink rejection, non-existent path, directory
  path;
- ``diff_sources``: empty / empty, empty / persisted,
  scan / empty, single changed, single unchanged, the
  full 4-bucket mix, determinism, the bucket-membership
  invariants (no path in two buckets; the totals add up);
- the manager additions: ``update_checksum`` writes the
  new hash, ``mark_path_missing`` is a one-liner for the
  deleted bucket.

Two-fail-positive discipline: each negative case was
written because the failure it asserts was reproduced
against a candidate that lacked the check. Reverting
the read-only optimization (skip unchanged files) breaks
the determinism test; reverting the bucket-membership
invariants breaks the totals test; reverting the
``mark_path_missing`` shortcut breaks the round-trip
test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.core.privacy import PrivacyClass
from paw.knowledge.checksum import compute_checksum
from paw.knowledge.source import (
    DiffChanged,
    DiffDeleted,
    DiffNew,
    DiffUnchanged,
    KnowledgeSource,
    KnowledgeSourceManager,
    SourceDiff,
    diff_sources,
)


# --- 1. compute_checksum contract --------------------------------------


def test_compute_checksum_deterministic(tmp_path) -> None:
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello world")
    a = compute_checksum(f)
    b = compute_checksum(f)
    assert a == b
    # And the known SHA-256 of "hello world".
    expected = (
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )
    assert a == expected


def test_compute_checksum_empty_file(tmp_path) -> None:
    f = tmp_path / "empty.txt"
    f.write_bytes(b"")
    assert compute_checksum(f) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_compute_checksum_refuses_symlink(tmp_path) -> None:
    target = tmp_path / "real.txt"
    target.write_bytes(b"x")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        compute_checksum(link)


def test_compute_checksum_nonexistent(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        compute_checksum(tmp_path / "missing.txt")


def test_compute_checksum_directory(tmp_path) -> None:
    d = tmp_path / "d"
    d.mkdir()
    with pytest.raises(ValueError, match="directory"):
        compute_checksum(d)


# --- 2. diff_sources: empty / empty ----------------------------------


async def test_diff_empty_scan_empty_persisted() -> None:
    diff = await diff_sources([], [])
    assert diff == SourceDiff()
    assert diff.total == 0


# --- 3. diff_sources: empty scan / persisted --------------------------


async def test_diff_empty_scan_persisted_only(tmp_path) -> None:
    # Three persisted sources, but the scan finds nothing.
    a = KnowledgeSource(id="a", name="a", path="src/a.py", checksum="x")
    b = KnowledgeSource(id="b", name="b", path="src/b.py", checksum="y")
    c = KnowledgeSource(id="c", name="c", path="src/c.py", checksum="z")
    diff = await diff_sources([], [a, b, c])
    assert diff == SourceDiff(
        new=(),
        changed=(),
        unchanged=(),
        deleted=(
            DiffDeleted(source=a),
            DiffDeleted(source=b),
            DiffDeleted(source=c),
        ),
    )
    assert diff.total == 3


# --- 4. diff_sources: scan / no persisted -----------------------------


async def test_diff_scan_only_persisted_empty(tmp_path) -> None:
    (tmp_path / "a.py").write_text("alpha")
    (tmp_path / "b.py").write_text("bravo")
    (tmp_path / "c.py").write_text("charlie")
    diff = await diff_sources(
        ["a.py", "b.py", "c.py"],
        [],
        repo_root=tmp_path,
    )
    # Every path lands in ``new``; each carries its SHA.
    new_paths = {d.path for d in diff.new}
    assert new_paths == {"a.py", "b.py", "c.py"}
    for d in diff.new:
        assert len(d.sha256) == 64  # SHA-256 hex
    assert diff.changed == ()
    assert diff.unchanged == ()
    assert diff.deleted == ()


# --- 5. diff_sources: one changed file -------------------------------


async def test_diff_one_changed_file(tmp_path) -> None:
    f = tmp_path / "src.py"
    f.write_text("old")
    old_sha = compute_checksum(f)
    f.write_text("new")
    new_sha = compute_checksum(f)
    persisted = [
        KnowledgeSource(
            id="s1", name="src", path="src.py", checksum=old_sha,
        )
    ]
    diff = await diff_sources(["src.py"], persisted, repo_root=tmp_path)
    assert diff.changed == (DiffChanged(
        source=persisted[0], new_sha256=new_sha,
    ),)
    assert diff.unchanged == ()
    assert diff.new == ()
    assert diff.deleted == ()


# --- 6. diff_sources: one unchanged file -----------------------------


async def test_diff_one_unchanged_file(tmp_path) -> None:
    f = tmp_path / "src.py"
    f.write_text("same")
    sha = compute_checksum(f)
    persisted = [
        KnowledgeSource(id="s1", name="src", path="src.py", checksum=sha),
    ]
    diff = await diff_sources(["src.py"], persisted, repo_root=tmp_path)
    assert diff.unchanged == (DiffUnchanged(source=persisted[0]),)
    assert diff.changed == ()
    assert diff.new == ()
    assert diff.deleted == ()


# --- 7. diff_sources: full 4-bucket mix ------------------------------


async def test_diff_full_four_bucket_mix(tmp_path) -> None:
    # Four files on disk.
    f_unchanged = tmp_path / "unchanged.py"
    f_unchanged.write_text("u")
    unchanged_sha = compute_checksum(f_unchanged)

    f_changed = tmp_path / "changed.py"
    f_changed.write_text("old")
    changed_old_sha = compute_checksum(f_changed)
    f_changed.write_text("new")
    changed_new_sha = compute_checksum(f_changed)

    f_new = tmp_path / "new.py"
    f_new.write_text("n")
    new_sha = compute_checksum(f_new)

    # Three persisted rows; one matches (unchanged), one
    # differs (changed), one is gone from disk (deleted).
    persisted = [
        KnowledgeSource(
            id="s-unchanged",
            name="unchanged",
            path="unchanged.py",
            checksum=unchanged_sha,
        ),
        KnowledgeSource(
            id="s-changed",
            name="changed",
            path="changed.py",
            checksum=changed_old_sha,
        ),
        KnowledgeSource(
            id="s-deleted",
            name="deleted",
            path="deleted.py",
            checksum="deadbeef",
        ),
    ]
    diff = await diff_sources(
        ["unchanged.py", "changed.py", "new.py"],
        persisted,
        repo_root=tmp_path,
    )
    assert diff.unchanged == (DiffUnchanged(source=persisted[0]),)
    assert diff.changed == (DiffChanged(
        source=persisted[1], new_sha256=changed_new_sha,
    ),)
    assert diff.new == (DiffNew(path="new.py", sha256=new_sha),)
    assert diff.deleted == (DiffDeleted(source=persisted[2]),)
    # Bucket-membership invariants.
    all_paths_in_scan = {"unchanged.py", "changed.py", "new.py"}
    seen = (
        {d.source.path for d in diff.unchanged}
        | {d.source.path for d in diff.changed}
        | {d.path for d in diff.new}
    )
    assert seen == all_paths_in_scan


# --- 8. diff_sources: determinism ------------------------------------


async def test_diff_is_deterministic(tmp_path) -> None:
    (tmp_path / "a.py").write_text("alpha")
    (tmp_path / "b.py").write_text("bravo")
    a = await diff_sources(["a.py", "b.py"], [], repo_root=tmp_path)
    b = await diff_sources(["a.py", "b.py"], [], repo_root=tmp_path)
    assert a == b
    # And the SHA on the new bucket is stable.
    for d in a.new:
        assert d.sha256 == compute_checksum(tmp_path / d.path)


# --- 9. update_checksum + mark_path_missing manager additions --------


async def test_update_checksum_writes_new_hash() -> None:
    mgr = KnowledgeSourceManager()
    src = await mgr.create(name="e1-06-update", path="src.py")
    # The create call wrote a default empty checksum.
    assert src.checksum == ""
    await mgr.update_checksum(src.id, "abc123")
    refetched = await mgr.get(src.id)
    assert refetched is not None
    assert refetched.checksum == "abc123"


async def test_update_checksum_clears_checksum_mismatch_invalidation() -> None:
    """A successful re-ingest supersedes a previous
    ``checksum_mismatch`` invalidation: the source goes
    back to ``active`` and the invalidation fields are
    cleared. Other invalidation reasons are preserved."""
    mgr = KnowledgeSourceManager()
    src = await mgr.create(name="e1-06-cleared", path="src.py")
    await mgr.mark_invalid(src.id, "checksum_mismatch")
    cleared = await mgr.update_checksum(src.id, "newhash")
    assert cleared is True
    refetched = await mgr.get(src.id)
    assert refetched is not None
    assert refetched.invalidated_at is None
    assert refetched.invalidation_reason == ""
    assert refetched.status == "active"
    assert refetched.checksum == "newhash"


async def test_mark_path_missing_one_liner() -> None:
    mgr = KnowledgeSourceManager()
    src = await mgr.create(name="e1-06-missing", path="src.py")
    marked = await mgr.mark_path_missing(src.id)
    assert marked.invalidation_reason == "path_missing"
    assert marked.invalidated_at is not None
    assert marked.is_stale is True


# --- 10. PrivacyClass untouched (E1-03 owner preserved) -------------


def test_knowledge_source_default_privacy_class_preserved() -> None:
    src = KnowledgeSource()
    assert src.privacy_class is PrivacyClass.INTERNAL