"""PAW Knowledge — recent-change and affected-area views (E1-12).

``recent_changes`` reads the local VCS (``git``) history
and returns the most recent commits as a list of
``RecentChange`` records. ``affected_areas`` joins each
commit to the E1-10 symbol view and the E1-11 test
associations so a reviewer can answer "what changed
and which tests / source symbols are affected?".

The functions are read-only: they shell out to ``git
log`` and ``git show --name-only`` with ``shell=False``
(the E1-03 hardening posture); the args are a fixed
list, never a shell string. A path that is not a git
repo returns an empty list; the runtime does not
crash on a malformed input.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .symbols import SymbolRecord, extract_symbols
from .test_associations import TestLink, associate_tests

# The Unit-Separator character is not valid in commit
# messages or repo-relative POSIX paths; using it as a
# field separator keeps the parser robust without
# quoting.
_FIELD_SEP = "\x1f"


@dataclass(frozen=True)
class RecentChange:
    """One commit's metadata."""

    sha: str
    short_sha: str
    author: str
    date: str
    message: str
    changed_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class AffectedArea:
    """A ``RecentChange`` joined to the E1-10 symbols
    and the E1-11 test associations whose files overlap
    with the commit's changed files.
    """

    change: RecentChange
    affected_symbols: tuple[SymbolRecord, ...] = ()
    affected_tests: tuple[TestLink, ...] = ()


def _run_git_log(
    repo_root: Path,
    *,
    since: str | None,
    max_count: int,
) -> str:
    """Run ``git log --pretty=... --name-only`` and
    return the raw output. A non-zero return code is
    treated as "no output" (the caller returns ``[]``)
    rather than raising.
    """
    argv: list[str] = [
        "git", "log",
        f"--pretty=format:%H{_FIELD_SEP}%h{_FIELD_SEP}%an{_FIELD_SEP}%aI{_FIELD_SEP}%s",
        "--name-only",
        f"-n{int(max_count)}",
    ]
    if since:
        # ``since`` is treated as a "after this ref"
        # boundary: ``<since>..HEAD`` excludes the
        # boundary itself. The caller's ref (a SHA, a
        # branch name, or an ISO-8601 date) is the
        # boundary; everything reachable from HEAD but
        # not from ``since`` is the result.
        argv.append(f"{since}..HEAD")
    try:
        result = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            timeout=30,
            cwd=str(repo_root),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def _parse_log(output: str) -> list[RecentChange]:
    """Parse the ``git log`` output into a list of
    ``RecentChange`` records. The output is a sequence
    of commits, each separated by a blank line; the
    first line of each commit is the metadata tuple
    (5 fields joined by ``_FIELD_SEP``); the
    subsequent lines are the changed files (one per
    line, until the next blank line)."""
    if not output.strip():
        return []
    commits: list[RecentChange] = []
    for block in output.split("\n\n"):
        lines = block.splitlines()
        if not lines:
            continue
        meta = lines[0]
        fields = meta.split(_FIELD_SEP)
        if len(fields) < 5:
            # Malformed block; skip.
            continue
        sha, short_sha, author, date, message = fields[:5]
        files: list[str] = []
        for f in lines[1:]:
            f = f.strip()
            if f:
                files.append(f)
        commits.append(
            RecentChange(
                sha=sha,
                short_sha=short_sha,
                author=author,
                date=date,
                message=message,
                changed_files=tuple(files),
            )
        )
    return commits


def recent_changes(
    repo_root: str | Path,
    *,
    since: str | None = None,
    max_count: int = 50,
) -> list[RecentChange]:
    """Return every commit in the ``repo_root`` git
    history, ordered most-recent-first.

    A path that is not a git repo returns ``[]`` (no
    crash). The result is deterministic: two calls with
    the same input produce the same list.
    """
    root = Path(repo_root)
    output = _run_git_log(root, since=since, max_count=max_count)
    return _parse_log(output)


def affected_areas(
    changes: Iterable[RecentChange],
    *,
    source_paths: Iterable[str],
    test_paths: Iterable[str],
    repo_root: Path,
) -> list[AffectedArea]:
    """For every ``RecentChange`` in ``changes``, return
    an ``AffectedArea`` whose ``affected_symbols`` is
    the E1-10 symbols in the commit's changed files
    and whose ``affected_tests`` is the E1-11 test
    associations whose test_file is in the changed
    files.

    The function is deterministic: same input -> same
    output, in the same order (sorted by commit date,
    most-recent first).
    """
    source_list = list(source_paths)
    test_list = list(test_paths)
    out: list[AffectedArea] = []
    for change in changes:
        changed = list(change.changed_files)
        # 1. Symbols whose ``file`` is in the commit's
        # changed files.
        symbols = tuple(
            s for s in extract_symbols(source_list, repo_root)
            if s.file in changed
        )
        # 2. Test associations whose test_file is in
        # the changed files. We re-run the E1-11
        # join over the unchanged source set so the
        # associations include both the changed and
        # the unchanged test names; the filter then
        # keeps only the tests whose test_file is in
        # the commit's changed files.
        associations = associate_tests(test_list, source_list, repo_root)
        tests = tuple(
            t for t in associations
            if t.test_file in changed
        )
        out.append(
            AffectedArea(
                change=change,
                affected_symbols=symbols,
                affected_tests=tests,
            )
        )
    out.sort(key=lambda a: a.change.date, reverse=True)
    return out


__all__ = ["AffectedArea", "RecentChange", "affected_areas", "recent_changes"]
