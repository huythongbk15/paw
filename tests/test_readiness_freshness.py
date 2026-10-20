"""Complete bounded source evidence, not an admission or approval artifact."""

from pathlib import Path

import pytest

from paw.core.repo_filter import RepoFilter
from paw.core.repo_scanner import scan_repo
from paw.knowledge import checksum


def test_strict_refuses_truncation_and_depth(tmp_path):
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    assert scan_repo(tmp_path, RepoFilter(max_files=1)) == ["a.py"]
    with pytest.raises(ValueError, match="file limit"):
        scan_repo(tmp_path, RepoFilter(max_files=1), require_complete=True)
    (tmp_path / "deep").mkdir()
    (tmp_path / "deep" / "c.py").write_text("c")
    with pytest.raises(ValueError, match="depth"):
        scan_repo(tmp_path, RepoFilter(max_depth=1), require_complete=True)


def test_strict_refuses_eligible_symlink_and_entry_limit(tmp_path):
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "linked.py").symlink_to(tmp_path / "a.py")
    with pytest.raises(ValueError, match="symlink"):
        scan_repo(tmp_path, RepoFilter(), require_complete=True)
    (tmp_path / "linked.py").unlink()
    with pytest.raises(ValueError, match="entry limit"):
        scan_repo(tmp_path, RepoFilter(), require_complete=True, max_entries=0)


def test_revision_dirty_add_delete_and_scope(tmp_path):
    root = tmp_path / "one"
    root.mkdir()
    source = root / "a.py"
    source.write_text("before")
    rules = RepoFilter.safe_default()
    before = checksum.compute_repo_revision(root, rules)
    assert checksum.compute_repo_revision(root, rules) == before
    source.write_text("after")
    assert checksum.compute_repo_revision(root, rules) != before
    source.write_text("before")
    assert checksum.compute_repo_revision(root, rules) == before
    (root / "b.py").write_text("new")
    assert checksum.compute_repo_revision(root, rules) != before
    (root / "b.py").unlink()
    assert checksum.compute_repo_revision(root, rules) == before
    assert checksum.compute_repo_revision(root, RepoFilter(max_files=201)) != before
    other = tmp_path / "two"
    other.mkdir()
    (other / "a.py").write_text("before")
    assert checksum.compute_repo_revision(other, rules) != before


def test_excluded_tree_and_byte_bounds(tmp_path):
    (tmp_path / "a.py").write_text("a")
    excluded = tmp_path / ".git"
    excluded.mkdir()
    (excluded / "secret").symlink_to("missing")
    rules = RepoFilter.safe_default()
    before = checksum.compute_repo_revision(tmp_path, rules)
    (excluded / "new").write_text("ignored")
    assert checksum.compute_repo_revision(tmp_path, rules) == before
    with pytest.raises(ValueError, match="byte limit"):
        checksum.compute_repo_revision(tmp_path, rules, max_bytes=0)


def test_scan_permission_error_is_not_a_complete_empty_tree(tmp_path, monkeypatch):
    import paw.core.repo_scanner as scanner

    def failed_walk(*args, **kwargs):
        kwargs["onerror"](PermissionError("unreadable"))
        return iter(())

    monkeypatch.setattr(scanner.os, "walk", failed_walk)
    with pytest.raises(PermissionError):
        scan_repo(tmp_path, RepoFilter(), require_complete=True)


def test_revision_refuses_inputs_changed_during_hash(tmp_path, monkeypatch):
    source = tmp_path / "a.py"
    source.write_text("a")
    original = checksum.compute_checksum

    def changing(path, **kwargs):
        result = original(path, **kwargs)
        Path(path).write_text("changed")
        return result

    monkeypatch.setattr(checksum, "compute_checksum", changing)
    with pytest.raises(ValueError, match="changed"):
        checksum.compute_repo_revision(tmp_path, RepoFilter())


def test_bounded_checksum_refuses_oversized_and_nonregular_input(tmp_path):
    import os

    source = tmp_path / "a.py"
    source.write_text("abcd")
    assert checksum.compute_checksum(source, max_bytes=4) == checksum.compute_checksum(source)
    with pytest.raises(ValueError, match="byte limit"):
        checksum.compute_checksum(source, max_bytes=3)
    if hasattr(os, "mkfifo"):
        pipe = tmp_path / "pipe"
        os.mkfifo(pipe)
        with pytest.raises(ValueError, match="regular"):
            checksum.compute_checksum(pipe, max_bytes=10)


def test_revision_detects_new_file_during_capture(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("a")
    original = checksum.compute_checksum

    def adding(path, **kwargs):
        result = original(path, **kwargs)
        (tmp_path / "new.py").write_text("new")
        return result

    monkeypatch.setattr(checksum, "compute_checksum", adding)
    with pytest.raises(ValueError, match="input set changed"):
        checksum.compute_repo_revision(tmp_path, RepoFilter())


@pytest.mark.parametrize("limit", [float("nan"), float("inf"), 1.5, True, -1])
def test_invalid_budgets_refuse_before_io(tmp_path, limit):
    with pytest.raises(ValueError):
        checksum.compute_repo_revision(tmp_path, RepoFilter(), max_bytes=limit)
    with pytest.raises(ValueError):
        scan_repo(tmp_path, RepoFilter(), require_complete=True, max_entries=limit)


def test_strict_rejects_symlink_ancestor(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "project").mkdir()
    (tmp_path / "linked").symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink ancestor"):
        scan_repo(tmp_path / "linked" / "project", RepoFilter(), require_complete=True)
