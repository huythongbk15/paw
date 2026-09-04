# E1-09 Dependency Edges with Source Locations and Confidence

This document is the **E1-09 deliverable**. It defines
the contract for `extract_dependencies`, the function
that scans Python source files and produces a list of
dependency edges with source locations (file, line,
column) and a confidence value.

## Why this contract exists

The E1-08 bounded tree view shows *what is in* a
repository. E1-09 shows *how the files depend on each
other*: which module does `src/paw/memory.py` import,
which file does `tests/test_phase1.py` import, which
relative sibling does `src/paw/core/memory.py` import.
A reviewer who can see the dependency graph can answer
"if I change this module, what other modules will
break?" — a question the E1-10 / E1-11 change-impact
items build on.

The contract pins the *deterministic* and
*source-backed* properties: every edge carries a
file path + line + column a reviewer can open; the
confidence value lets the runner filter out edges that
came from a dynamic-import heuristic.

## Canonical location

`extract_dependencies` is a new function in
`paw.knowledge.dependencies` (a new module). The
function takes a list of repo-relative POSIX paths
plus a `Path` root, walks each file with the Python
`ast` module, and produces a `DependencyEdge` list.

## `DependencyEdge` shape

```python
@dataclass(frozen=True)
class DependencyEdge:
    """One import edge in the dependency graph.

    A static ``import x`` statement produces one edge
    pointing at the module ``x``; a
    ``from x import y`` statement produces one edge
    pointing at the module ``x`` (the ``y`` symbol is
    a separate notion the E1-10 impact analysis reads
    from the same edge, not a new edge).
    """
    from_path: str           # repo-relative POSIX path
    to_module: str           # dotted module name
    line: int                # 1-based line in the source
    col: int                 # 0-based column offset
    kind: str                # "absolute" | "relative" | "dynamic"
    confidence: float        # [0.0, 1.0]
```

`kind`:
- `"absolute"`: a top-level `import x` or
  `from x import y` — the module is named absolutely.
- `"relative"`: a `from . import y` or `from ..pkg
  import y` — the module is referenced relative to
  the current package.
- `"dynamic"`: an `__import__()` call or a string-based
  `importlib.import_module()` — the import is not
  statically resolvable.

`confidence`:
- `1.0` for `"absolute"` and `"relative"` (the `ast`
  found a real `Import` / `ImportFrom` node).
- `0.5` for `"dynamic"` (the function saw an
  `__import__()` call or a string-based import).

## Signature

```python
def extract_dependencies(
    paths: Iterable[str],
    repo_root: Path,
) -> list[DependencyEdge]:
    """Parse each Python file under ``repo_root`` whose
    repo-relative path is in ``paths`` and return a flat
    list of dependency edges.

    The result is sorted by ``(from_path, line, col)`` so
    two calls with the same input produce the same
    output. Files that fail to parse (syntax errors,
    non-UTF-8 content) are silently skipped; the
    contract is "a syntax error in one file does not
    stop the rest".
    """
```

The function does **not** follow the dependency
graph — it returns the *edges* the runtime can
traverse. The E1-10 impact analysis is the consumer
that traverses the graph.

## Negative cases

| Case | Expected result |
|---|---|
| Empty `paths` | `[]` |
| `import os` | One edge `from_path -> "os"`, kind=absolute, confidence=1.0, line=N, col=M. |
| `from . import sibling` | One edge, kind=relative, confidence=1.0. |
| `from ..pkg import y` | One edge, kind=relative, confidence=1.0, `to_module="pkg"` (the leading `..` is dropped; the level is part of the import statement's metadata, not the `to_module` field). |
| `__import__("foo")` | One edge, kind=dynamic, confidence=0.5. |
| `importlib.import_module("bar")` | One edge, kind=dynamic, confidence=0.5. |
| Syntax error in one file | The file is skipped; other files still produce edges. |
| Non-Python file (e.g. `.txt`) | Skipped silently. |
| Determinism | Two calls with the same input produce the same output list. |
| Multi-line `from x import (a, b, c)` | One edge per `a`, `b`, `c` (the `ast` yields a list of names). |

## Phase 4 sync contract

This document is the **source of truth** for E1-09.
The companion contract test
`tests/test_e1_09_dependency_edges_contract.py`
enforces the cases above.

A later E1 item that adds a "level" field for relative
imports must update both this spec and the contract
test in the same change.