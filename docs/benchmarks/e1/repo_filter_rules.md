# E1-04 Deterministic Include/Exclude Rules for Repository Files

This document is the **E1-04 deliverable**. It defines
the contract for the `RepoFilter` object that decides
which repository files are eligible to be loaded as
context candidates, plus the default safe filter the
runtime starts from.

## Why this contract exists

The E1 roadmap acceptance criteria (ROADMAP.md) require
that:

- every byte of remote project context is attributable
  to an approved context manifest;
- the runtime can produce a bounded repository tree
  view (E1-08);
- context manifest contents are inspectable; a
  reviewer can identify why a file was included or
  excluded (E1-17).

The `ContextPlan` already declares a `repo_paths:
list[str]` field and an `include_repo: bool` flag, but
the `_retrieve_repo_candidates` implementation is a
no-op. E1-04 fills the gap with a deterministic
include/exclude matcher that the context compiler
calls when assembling repository candidates.

The matcher is a *pure* function over a closed set of
inputs; two runs with the same input list and the same
`RepoFilter` produce the same output list, in the same
order, byte-identical. The contract test pins that.

## Canonical location

`RepoFilter` is the single owner of the include/exclude
rule schema and the matching algorithm. E1-04 introduces
it as a new module `paw.core.repo_filter` so the
context compiler, the E1-08 bounded tree-view, and the
E1-17 manifest inspection can all import the same
object. The `ContextPlan` dataclass is extended with a
single new field, `repo_filter: RepoFilter | None`,
alongside the existing `repo_paths: list[str]`.

## Rule schema

A `RepoFilter` has four fields:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `include_patterns` | `tuple[str, ...]` | `()` | fnmatch glob patterns. A path must match at least one pattern to be eligible. Empty tuple means "match everything" (the safe default before any include rule is set). |
| `exclude_patterns` | `tuple[str, ...]` | `()` | fnmatch glob patterns. A path that matches any pattern is rejected. Excludes are evaluated after includes. |
| `max_files` | `int` | `200` | Hard ceiling on the number of files the filter accepts. The contract is enforced: a `filter_paths` call on more than `max_files` matching paths returns the first `max_files` and the rest are dropped. |
| `max_depth` | `int` | `8` | Hard ceiling on the path depth (number of `pathlib.PurePosixPath` parts, not counting the leading `"/"`). Files deeper than `max_depth` are rejected. |

`include_patterns` and `exclude_patterns` are tuples
(rather than lists) so the dataclass is hashable; that
lets a reviewer cache a `RepoFilter` and a context
compiler compare two filters for equality.

## Default safe filter

A `RepoFilter.safe_default()` factory returns a filter
that rejects the common build-output / VCS / venv
directories and a small set of binary extensions. The
exact set is the change-control surface; the contract
test pins the literals.

```python
SAFE_DEFAULT_EXCLUDES = (
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    "*.pyc",
    "*.tmp",
    "*.pyo",
    "*.swp",
)

RepoFilter.safe_default() == RepoFilter(
    include_patterns=(),
    exclude_patterns=SAFE_DEFAULT_EXCLUDES,
    max_files=200,
    max_depth=8,
)
```

The `ContextCompiler` uses `RepoFilter.safe_default()`
when the plan sets `include_repo=True` but does not
provide a `repo_filter`; this is the fail-closed default
that keeps the runtime from accidentally loading
`__pycache__` or `.git/HEAD` into a context.

## Matcher contract

```python
@dataclass(frozen=True)
class RepoFilter:
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    max_files: int = 200
    max_depth: int = 8

    def match(self, rel_path: str) -> bool: ...
    def filter_paths(self, paths: Iterable[str]) -> list[str]: ...
```

`match(rel_path)`:

- `rel_path` must be a non-empty repository-relative
  POSIX path (no leading `/`, no `..` segments). Any
  other input returns `False` (fail-closed: a path
  that cannot be expressed safely is not a candidate).
- The path is depth-checked: a path with more parts
  than `max_depth` returns `False`.
- The path is include-checked: if `include_patterns`
  is non-empty, the path must `fnmatch.fnmatch` at
  least one include pattern. Empty `include_patterns`
  means "match everything" (until an exclude matches).
- The path is exclude-checked: if any exclude pattern
  matches, the result is `False`. Excludes win.
- The function never raises on input; the only
  `ValueError`s are at construction time
  (see "Hardening" below).

`filter_paths(paths)`:

- Accepts any iterable of repository-relative paths.
- The result is a `list[str]`, sorted lexicographically
  by `pathlib.PurePosixPath`, with at most `max_files`
  entries. The ordering is deterministic; two calls
  with the same input produce the same output.
- Paths that fail `match()` are dropped silently;
  `filter_paths` does not raise on a single bad path
  (the construction-time hardening is the contract).
- A single `ValueError` is raised if the input
  contains a duplicate path; the dedup is the reviewer's
  expectation and a duplicate is a contract violation
  worth surfacing.

## ContextPlan integration

`ContextPlan` (in `src/paw/core/context_compiler.py`)
gains one new field:

| Field | Type | Default | Notes |
|---|---|---|---|
| `repo_filter` | `RepoFilter \| None` | `None` | The include/exclude rule the compiler applies when retrieving repository candidates. `None` means "no filter" (every path in `repo_paths` is a candidate); `RepoFilter.safe_default()` is the fail-closed default the `ContextCompiler` uses when `include_repo=True` and the plan has no explicit filter. |

The existing `repo_paths: list[str]` and `include_repo:
bool` fields are unchanged. The new `_retrieve_repo_candidates`
implementation:

1. If `include_repo` is `False` or `repo_paths` is empty,
   return `[]`.
2. Otherwise, resolve the filter: `plan.repo_filter` if
   set, else `RepoFilter.safe_default()`.
3. Run the filter on `plan.repo_paths` and return one
   `ContextCandidate` per surviving path. The
   candidate's `source` is `"repository"`, `source_id`
   is the path, `content` is empty (lazy), and
   `metadata["filter"]` records the filter's repr so
   the manifest (E1-17) is inspectable.

## Hardening (security invariants)

The `RepoFilter` constructor enforces:

- `max_files > 0` and `max_depth > 0`;
- every include/exclude pattern is a non-empty
  repository-relative POSIX path (no `..`, no
  absolute);
- patterns that contain a `*` outside of `pathlib`
  glob semantics are still allowed (`fnmatch` is the
  algorithm), but a pattern that is `""` or `"."` or
  `"/"` is rejected.

The hardening is the change-control surface for
adversarial cases (path traversal, undeclared include
that pulls in secrets, etc.). The contract test exercises
each guard.

## Boundary exposure (E0-40 + E1-08 + E1-17)

The `RepoFilter` is consumed by:

- `ContextCompiler._retrieve_repo_candidates` (E1-04;
  this item);
- the E1-08 bounded repository tree view (next item);
- the E1-17 manifest inspector (`metadata["filter"]`).

The boundary is the `RepoFilter` dataclass itself: a
reviewer who wants to know "which files are eligible"
instantiates one with the same parameters and calls
`filter_paths` on the same input.

## Phase 4 sync contract

This document is the **source of truth** for E1-04.
The companion contract test
`tests/test_e1_04_repo_filter_contract.py` enforces:

- the field set, defaults, and `safe_default()`;
- the `match` predicate on a representative matrix
  (include only, exclude only, both, depth cutoff,
  bad path, leading `/`, `..` segments);
- the `filter_paths` determinism (same input → same
  output, byte-identical, ordering stable);
- the construction-time hardening (`max_files <= 0`,
  `max_depth <= 0`, absolute pattern, `..` pattern,
  empty pattern);
- the `ContextPlan` accepts a `repo_filter` field and
  exposes it;
- the `_retrieve_repo_candidates` flow is wired to the
  filter (the contract test exercises the flow with a
  stubbed path list and a stubbed `repo_filter`).

A later E1 item that adds another default-exclude
pattern must update `safe_default()` and the contract
test in the same change.