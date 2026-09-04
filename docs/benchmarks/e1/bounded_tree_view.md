# E1-08 Bounded Repository Tree View

This document is the **E1-08 deliverable**. It defines
the contract for `scan_tree`, the function that turns
a real repository root into a bounded, hierarchical
tree view the context compiler and the E1-17 manifest
inspector can consume.

## Why this contract exists

The E1-05 `scan_repo` returns a flat list of repo-relative
POSIX paths. A reviewer who wants to see "what is in
this repository" needs a *tree*, not a list — directories
containing files, with the file count per directory,
with the depth-bounded subtree they would expect to see
in a `tree(1)` output.

The E1-08 contract is the deterministic, filter-aware
version of that. The output is a single root
`TreeNode` whose children are subdirectories and files,
in lexicographic order, with the file counts and total
sizes the E1-17 manifest inspector needs to display
"what is in this repository".

## Canonical location

`scan_tree` is a new function in `paw.core.repo_scanner`
(the same module that owns `scan_repo`). The function
re-uses the E1-05 `_walk` helper to keep the symlink
hardening consistent; the only new behavior is the
*tree assembly*.

## `TreeNode` shape

```python
@dataclass(frozen=True)
class TreeNode:
    name: str                # The single-part name ("src", not "src/")
    path: str                # Repo-relative POSIX path
    kind: str                # "dir" or "file"
    children: tuple[TreeNode, ...] = ()  # Empty for files
    file_count: int = 0      # Recursive: 0 for files, N for dirs
    leaf_count: int = 0      # Recursive: 1 for files, 0 for dirs
```

`name` is the single-part name (e.g. `"src"`,
`"memory.py"`); `path` is the full repo-relative
POSIX path. `kind` is `"dir"` for a directory and
`"file"` for a file. `children` is empty for files
and is a tuple of `TreeNode` for directories. The
two count fields let the E1-17 manifest inspector
display "this dir contains N files" without
re-walking the tree.

## `scan_tree` signature

```python
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
    max_depth rules as the E1-05 scanner). The tree is
    deterministic: same input → same output, in the
    same order. The function refuses to walk symlinks
    (fail-closed posture from E1-05).
    """
```

The return type is a single `TreeNode` whose
`name='.'` and `path='.'`; the root itself never
appears as a child. Empty roots produce a `TreeNode`
with no children and `file_count=0` /
`leaf_count=0`.

## Negative cases

| Case | Expected result |
|---|---|
| Empty root | `TreeNode(name='.', path='.', children=(), file_count=0, leaf_count=0)`. |
| Symlink root | `ValueError` (same posture as `scan_repo`). |
| Symlinked file in the tree | The symlink is skipped; the file's name is not in the tree. |
| Symlinked directory | The symlink is skipped; the directory's contents are not in the tree. |
| `follow_symlinks=True` | `ValueError` (E1-05 contract). |
| Deep tree beyond `max_depth` | Files beyond `max_depth` are not in the tree. |
| `__pycache__` with safe_default | Not in the tree (filtered). |
| Determinism | Two calls produce byte-identical trees. |
| `max_files` cap | The total `file_count` is `<= max_files`. |

## Boundary exposure (E0-40 + E1-17)

`scan_tree` is consumed by:

- the E1-17 manifest inspector (which renders the
  tree in the per-item manifest);
- the E0-40 runtime-driven runner (which uses the
  tree's `file_count` to size the manifest's
  summary).

The boundary is the function signature itself.

## Phase 4 sync contract

This document is the **source of truth** for E1-08.
The companion contract test
`tests/test_e1_08_bounded_tree_contract.py` enforces
the cases above.