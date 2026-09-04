# E1-12 Recent-Change and Affected-Area Views from Local VCS Evidence

This document is the **E1-12 deliverable**. It defines
the contract for `recent_changes` and
`affected_areas`, the functions that turn local VCS
(`git`) evidence into the per-commit "what changed"
and "which tests / source symbols are affected" views
a reviewer uses to scope a re-run.

## Why this contract exists

The E1-09 dependency graph, the E1-10 symbol view, and
the E1-11 test associations answer "what does the
code look like *now*". E1-12 answers the *change*
question: "what changed in the last 7 days, and which
tests / source symbols are affected by those changes?"
A reviewer who sees a recent commit can use the
affected-area view to decide which tests to re-run
without a full test suite.

The local-VCS posture keeps the contract fail-closed:
the function reads `git` read-only (`git log`,
`git show --name-only`, no `git checkout`); a path
that is not a git repo returns an empty list, not a
crash. The runtime stays deterministic and offline.

## Canonical location

`recent_changes` and `affected_areas` are new
functions in `paw.knowledge.changes` (a new module).
The functions shell out to `git` via
`subprocess.run(argv, shell=False, ...)` (the E1-03
hardening posture); the args are a fixed list, never a
shell string.

## `RecentChange` shape

```python
@dataclass(frozen=True)
class RecentChange:
    """One commit's metadata, used by both the
    recent-change view and the affected-area view.
    """
    sha: str                # full SHA
    short_sha: str          # 7-char prefix
    author: str             # author name
    date: str               # ISO-8601 UTC
    message: str            # first line of the commit message
    changed_files: tuple[str, ...]   # repo-relative POSIX
```

`changed_files` is the set of files touched by the
commit; the function does not include untracked files
or the working tree (no diff against HEAD).

## `AffectedArea` shape

```python
@dataclass(frozen=True)
class AffectedArea:
    """The result of joining a ``RecentChange`` to the
    E1-10 symbol view and the E1-11 test associations.
    """
    change: RecentChange
    affected_files: tuple[str, ...]           # same as change.changed_files
    affected_symbols: tuple[SymbolRecord, ...]  # symbols in the touched files
    affected_tests: tuple[TestLink, ...]      # tests whose test_file
                                              # is in the touched files
```

`affected_symbols` is built by feeding the changed
files into the E1-10 `extract_symbols`. `affected_tests`
is built by feeding the changed files into the E1-11
`associate_tests` (with the unchanged source files as
the source set). The join is deterministic; the same
input produces the same `affected_tests` list.

## `recent_changes` signature

```python
def recent_changes(
    repo_root: str | Path,
    *,
    since: str | None = None,   # git ref (HEAD, main, sha, date)
    max_count: int = 50,
) -> list[RecentChange]:
    """Return every commit in the ``repo_root`` git
    history, ordered most-recent-first.

    ``since`` is a ``git log``-style ref (``HEAD``,
    ``main``, a SHA, or an ISO-8601 date like
    ``2026-09-01``). When ``None``, the function
    returns the last ``max_count`` commits.

    The function is deterministic: two calls with the
    same input produce the same list. A path that is
    not a git repo returns ``[]`` (no crash).
    """
```

The function reads `git log --pretty=format:%H%x1f%h%x1f%an%x1f%aI%x1f%s --name-only -n <max_count> [since]`
and parses the output. The ``%x1f`` field separator
is a Unit-Separator character that does not appear in
commit messages or file paths; the parsing is robust.

## `affected_areas` signature

```python
def affected_areas(
    changes: Iterable[RecentChange],
    *,
    source_paths: Iterable[str],
    test_paths: Iterable[str],
    repo_root: Path,
) -> list[AffectedArea]:
    """For every ``RecentChange`` in ``changes``,
    return an ``AffectedArea`` whose
    ``affected_symbols`` is the E1-10 symbols in the
    commit's changed files and whose ``affected_tests``
    is the E1-11 test associations whose test_file
    overlaps with the changed files.

    The function is deterministic: same input -> same
    output, in the same order. The output is sorted by
    ``change.date`` (most-recent first) so two calls
    produce the same list.
    """
```

The caller passes the source and test paths (the
output of `scan_repo`); the function does not re-walk
the filesystem.

## Negative cases

| Case | Expected result |
|---|---|
| Path is not a git repo | `[]`; the function does not crash. |
| `git log` produces no output (empty repo) | `[]`. |
| `since=<ref>` with an invalid ref | `[]`; the function does not crash. |
| A commit that changes only a non-Python file | The commit is in `recent_changes`; the `affected_symbols` and `affected_tests` are empty for that commit. |
| A commit that changes a Python file with no symbols (e.g. `__init__.py` with imports only) | The commit is in `recent_changes`; `affected_symbols` may still be non-empty (the `module` symbol). |
| Determinism | Two calls produce the same list. |
| Stale untracked files | Ignored; only tracked files are in the result. |
| The function never mutates the working tree | No `git checkout`, no `git reset`, no `git commit`. |

## Boundary exposure (E1-13 + future change-impact)

`recent_changes` and `affected_areas` are consumed by:

- E1-13 budget-bound view (which joins the affected
  area with the token budget to produce a "what
  changed" manifest);
- the future change-impact analysis (which uses the
  E1-09 edges + the E1-10 symbols + the E1-11 test
  associations to answer "if I change this symbol,
  which tests will be affected?").

The boundary is the two function signatures: a caller
who wants "what changed" calls `recent_changes`; a
caller who wants "what changed + which tests / symbols
are affected" calls `affected_areas`.

## Phase 4 sync contract

This document is the **source of truth** for E1-12.
The companion contract test
`tests/test_e1_12_recent_changes_contract.py`
enforces the cases above.