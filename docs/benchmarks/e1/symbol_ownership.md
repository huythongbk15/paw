# E1-10 Symbol Ownership and Signature Records

This document is the **E1-10 deliverable**. It defines
the contract for `extract_symbols`, the function that
turns a set of Python source files into a flat list of
symbol records (functions, methods, classes, modules)
with the file/line/column of their definition and a
textual signature.

## Why this contract exists

The E1-09 dependency graph tells the runtime *which
files import which modules*. The E1-10 symbol view
answers the second half of the question: *who owns
this function or class?* A reviewer who sees
`KnowledgeSourceManager.mark_invalid` in a
dependency edge wants to know what file + line it is
defined in and what its signature looks like, without
opening the file.

The E1-10 contract is the canonical owner of the
*symbol* view of the source tree. The E1-11 test
associations, the E1-12 recent-change view, the
E1-17 manifest inspector, and the future change-impact
analysis all read this view.

## Canonical location

`extract_symbols` is a new function in
`paw.knowledge.symbols` (a new module). The function
uses the stdlib `ast` module to parse each Python file
and produce a `SymbolRecord` per top-level definition
and per nested method. The result is sorted by
`(file, line, col)` so two calls produce the same
output.

## `SymbolRecord` shape

```python
@dataclass(frozen=True)
class SymbolRecord:
    """One symbol in a Python file.

    ``kind`` is one of:

    - ``"module"``: the implicit symbol of a file (one
      per file). ``qualified_name`` is the dotted module
      path; ``signature`` is empty; ``parent`` is None.
    - ``"class"``: a top-level class or nested class.
      ``signature`` is the parenthesized base-list
      (e.g. ``"(KnowledgeSource)"``).
    - ``"function"``: a top-level function.
    - ``"async_function"``: an async top-level function.
    - ``"method"``: a function defined inside a class.
      ``parent`` is the enclosing class's qualified name.
    - ``"async_method"``: an async method.

    ``qualified_name`` is the dotted path a Python
    caller would use to reach the symbol
    (``"KnowledgeSourceManager.mark_invalid"``).
    ``signature`` is the parameter list as a string
    (``"self, source_id: str, reason: str,
    superseded_by: str = ''"``); the parameter types
    are the AST annotations when present, otherwise
    empty.

    ``decorators`` is a tuple of dotted names
    (``("staticmethod",)`` for a static method,
    ``("classmethod",)`` for a class method,
    ``("property",)`` for a property). The first
    decorator is the one closest to the ``def`` line.

    ``confidence`` is always ``1.0`` for the E1-10
    static pass; the field exists so the future
    dynamic-symbol pass can lower it.
    """
    qualified_name: str
    kind: str
    file: str
    line: int
    col: int
    signature: str = ""
    decorators: tuple[str, ...] = ()
    parent: str | None = None
    confidence: float = 1.0
```

The record does **not** store the function body. The
E1-17 manifest inspector renders the `signature`
field; the runtime does not need the body to answer
"who owns this function".

## Signature rendering

The `signature` field is built by walking the AST
`arguments` node:

- positional-only args (Python 3.8+): `a, /`
- positional-or-keyword args: `a` (with annotation) or
  `a: int`
- variadic: `*args` (annotation after `:`)
- keyword-only: `*, a` (between `*` and the next arg)
- keyword variadic: `**kwargs`

Defaults are rendered as `= value` using the AST
default. Annotations are rendered as `: T`. The
return annotation is **not** in the signature field
(it is part of the function header but the consumer
that wants it reads the AST). The whole signature is
prefixed with `(` and suffixed with `)`.

The signature is a string, not a structured object,
because the E1-17 manifest inspector renders it
verbatim.

## `extract_symbols` signature

```python
def extract_symbols(
    paths: Iterable[str],
    repo_root: Path,
) -> list[SymbolRecord]:
    """Parse each Python file under ``repo_root`` whose
    repo-relative path is in ``paths`` and return a
    flat list of symbol records.

    The result is sorted by ``(file, line, col)`` so
    two calls with the same input produce the same
    output. Files that fail to parse are silently
    skipped (one bad file does not stop the rest);
    non-Python files are silently skipped.
    """
```

The function does **not** resolve cross-file imports.
A symbol's `qualified_name` is the local dotted path
from its file's module root; the E1-09 dependency
graph is the consumer that joins symbols across
files.

## Negative cases

| Case | Expected result |
|---|---|
| Empty `paths` | `[]`. |
| `def foo(): pass` | One `function` record: `qualified_name="<module>.foo"`, `signature="()"`, no parent. |
| `class C: pass` | One `class` record: `qualified_name="<module>.C"`, `signature=""`, no parent. |
| `class C: def m(self): pass` | Two records: a `class` `C` and a `method` `C.m`. The method's `parent` is `"<module>.C"`. |
| `async def f(): pass` | One `async_function` record. |
| `def f(self, a: int, b: str = '') -> None: pass` | Signature rendered: `"(self, a: int, b: str = '')"` (return annotation omitted). |
| `@staticmethod def f(): pass` | `decorators=("staticmethod",)`. |
| `@property def x(self): return 1` | `decorators=("property",)`. |
| Nested class: `class C: class D: pass` | A `class` `C` and a `class` `C.D`. `C.D.parent == "<module>.C"`. |
| Syntax error in one file | The file is skipped; other files still produce records. |
| Non-Python file | Skipped silently. |
| Determinism | Two calls produce the same list. |
| Multi-line `def f(a, b, c): pass` | Signature rendered: `"(a, b, c)"`. |
| `def f(*args, **kwargs): pass` | Signature rendered: `"(*args, **kwargs)"`. |
| `def f(a, /, b, *, c): pass` (positional-only) | Signature rendered: `"(a, /, b, *, c)"`. |

## Boundary exposure (E1-11 + E1-12 + E1-17 + future change-impact)

`extract_symbols` is consumed by:

- E1-11 test-to-source association (matches test
  function names to source symbol names);
- E1-12 recent-change view (joins VCS file changes to
  the symbols those files own);
- E1-17 manifest inspector (renders the `signature`
  field for each symbol referenced in the manifest);
- the future change-impact analysis (uses the
  E1-09 edges + the E1-10 qualified names to answer
  "if I change `KnowledgeSource.mark_invalid`, what
  other modules will break?").

The boundary is the `SymbolRecord` dataclass: every
consumer reads the same eight fields, no new
abstractions.

## Phase 4 sync contract

This document is the **source of truth** for E1-10.
The companion contract test
`tests/test_e1_10_symbol_ownership_contract.py`
enforces the cases above.

A later E1 item that adds a new symbol kind
(e.g. ``"property_descriptor"``) must update both this
spec and the contract test in the same change.