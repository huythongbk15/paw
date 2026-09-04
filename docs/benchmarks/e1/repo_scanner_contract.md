# E1-05 Source Discovery: Traversal and Symlink Negative Cases

This document is the **E1-05 deliverable**. It defines
the `scan_repo` contract for deterministic repository
discovery and the negative-control surface that proves
the discovery path is safe.

## Why this contract exists

The E1-04 `RepoFilter` decides which *paths* are
eligible. E1-05 is about how those paths are *found*:
the discovery function that walks a repository root and
returns a list of repo-relative POSIX paths. The
discovery function is a separate concern from the
filter because the failure modes are different:

- the filter is a pure matcher over a closed set of
  strings; failure is a `False` result;
- the discovery function interacts with the real
  filesystem; failure modes include `..` segments that
  escape the root, symlinks that point outside the root,
  absolute paths, and null bytes in path names.

The existing `LocalFilesystemExecutor` (in
`src/paw/executors/filesystem.py`) already enforces the
same hardening for *write* operations; the E1-05
contract is the *read* equivalent for source
discovery, so a reviewer who accepts the E1-05
contract can be sure the runtime cannot load a file
outside the workspace into a context.

## Canonical location

`scan_repo` is a new function in `paw.core.repo_scanner`
(a new module). The function is the single source of
truth for the discovery path; the `RepoFilter` remains
the single source of truth for the *eligibility* rule.
The two are composed: the caller passes a `RepoFilter`,
the scanner walks the tree, and every candidate is run
through `filter.match` before it is added to the
result.

## Signature

```python
def scan_repo(
    root: str | Path,
    filter: RepoFilter,
    *,
    follow_symlinks: bool = False,
) -> list[str]:
    """Walk ``root`` deterministically and return the
    repo-relative POSIX paths that ``filter.match`` accepts.

    The result is sorted lexicographically by
    ``pathlib.PurePosixPath`` parts so two scans of the
    same tree produce the same output list. The result is
    capped at ``filter.max_files``; the cap is the
    reviewer's expectation, not the scanner's choice.
    """
```

`root` must be a real existing directory; the function
rejects (with `ValueError`):

- a non-existent path;
- a path that is a file, not a directory;
- a path that is a symlink (the scanner refuses to walk
  through a symlink root, because the symlink target
  may be outside the intended workspace);
- a path containing a null byte.

`follow_symlinks=False` is the only supported mode in
this contract. The argument is accepted for future
flexibility (a reviewer may want to allow symlinks that
stay inside the root) but the implementation rejects
every symlink at every depth; a follow-up item may
relax this with a separate change-control surface.

## Negative cases (the contract)

The contract test exercises the following negative
cases. Each case is a real test (no mock; real temp
filesystem) and the assertion is on the function's
return value, not on an exception class — the scanner
returns a list, and the negative case is "the offending
path is not in the list".

| Case | What the test does | Expected result |
|---|---|---|
| `..` in relative path passed to a sub-walk | The scanner walks a tree; an entry is replaced by a symlink that resolves outside the root. | The symlink is not followed; the resulting list does not contain any path from outside the root. |
| Symlink to a sibling file | A file in the root is replaced by a symlink to a file outside the root; the scanner is asked to walk the root. | The symlink is skipped; the resulting list does not contain the symlink's name. |
| Symlink to a sibling directory | A directory in the root is replaced by a symlink to a directory outside the root. | The symlink is skipped; the resulting list does not contain any path under the symlinked directory. |
| Symlink root | The caller passes a symlink as the `root` argument. | `ValueError` raised at construction; the function does not start a walk. |
| Absolute path inside the tree | A file at `/tmp/external.txt` is referenced by an absolute path the scanner might emit. | The scanner emits only repo-relative POSIX paths; no path starting with `/` is in the result. |
| Null byte in filename | A file is created whose name contains a `\x00`. | The scanner skips the file (the OS-level call returns an error); no crash. |
| Hidden files (leading `.`) | A `.hidden` file is present. | Whether included depends on the filter; the default `safe_default()` does not exclude dotfiles explicitly, so a `.hidden` file *is* included unless the caller passes an `include_patterns` rule. The contract pins this behavior. |
| Deeply nested tree | A file is at depth 100. | The scanner stops at `filter.max_depth`; the deeply-nested file is rejected by the filter and not in the result. |
| Empty root | The root is an empty directory. | The result is `[]`. |
| Determinism | The same tree is scanned twice. | The two results are byte-identical (same length, same elements in the same order). |
| Cap | The tree has 300 files; `filter.max_files=200`. | The result has 200 entries (the filter's cap, not the scanner's choice). |

## Result format

Each entry is a `str` of the form
`relative/path/to/file.ext` — the same shape the
`ContextPlan.repo_paths` field expects. The string is
always relative to `root`; it never starts with `/`,
never contains `..` segments, and never uses Windows
path separators (the scanner normalizes via
`PurePosixPath`).

## Boundary exposure (E0-40 + E1-08 + E1-17)

`scan_repo` is consumed by:

- the E1-08 bounded tree view (the next item in the
  queue);
- the E1-17 manifest inspector, which reads the result
  and records the filter's `repr` for each included
  path;
- the `ContextCompiler._retrieve_repo_candidates`
  follow-up, which may take a `plan.repo_root` field
  and call `scan_repo(plan.repo_root, plan.repo_filter)`.

The boundary is the function signature itself: a
reviewer who wants to know "which files are eligible
on disk" calls the function and inspects the result.

## Phase 4 sync contract

This document is the **source of truth** for E1-05.
The companion contract test
`tests/test_e1_05_repo_scanner_contract.py` enforces
the negative cases in the table above plus the
positive-control cases (empty root, deep tree, cap,
determinism). A reviewer who reads the test file
gets a complete enumeration of the safety
invariants.

A later E1 item that adds a "follow symlinks" mode
must update both this spec and the contract test in
the same change.