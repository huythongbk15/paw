"""PAW Knowledge — symbol ownership and signature records (E1-10).

``extract_symbols`` parses each Python file under
``repo_root`` whose repo-relative path is in ``paths``
and returns a flat list of ``SymbolRecord`` records.
The function uses the stdlib ``ast`` module; the
result is sorted by ``(file, line, col)`` so two calls
with the same input produce the same output.

The function is the *static* owner of the symbol view:
every function / async function / class / method in
each input file is recorded with the file/line/column
of its definition and a textual signature. The
runtime does not need the function body to answer
"who owns this symbol".
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SymbolRecord:
    """One symbol in a Python file.

    ``kind`` is one of:
    - ``"module"``: implicit symbol of a file.
    - ``"class"``: top-level or nested class.
    - ``"function"``: top-level function.
    - ``"async_function"``: top-level async function.
    - ``"method"``: function inside a class.
    - ``"async_method"``: async function inside a class.

    See ``docs/benchmarks/e1/symbol_ownership.md`` for
    the full contract.
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


def _module_root(rel_path: str) -> str:
    """Build a dotted module root from a repo-relative
    POSIX path. ``"src/paw/memory.py"`` becomes
    ``"src.paw.memory"``; ``"src/paw/__init__.py"``
    becomes ``"src.paw"``; ``"a.py"`` becomes ``"a"``."""
    if rel_path.endswith("/__init__.py"):
        rel_path = rel_path[: -len("/__init__.py")]
    elif rel_path.endswith(".py"):
        rel_path = rel_path[: -len(".py")]
    parts = [p for p in rel_path.split("/") if p]
    return ".".join(parts) if parts else rel_path


def _render_annotation(node: ast.expr | None) -> str:
    """Render an AST annotation node as a string. The
    ``ast.unparse`` function is available on Python
    3.9+; we fall back to ``""`` if unparse fails
    (some custom AST nodes are not unparseable)."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _render_arg(arg: ast.arg, *, default: ast.expr | None = None) -> str:
    """Render a single argument: ``name`` (with
    annotation) and ``= default`` when a default is
    present. The ``default`` may be None for
    positional-or-keyword args without a default."""
    out = arg.arg
    annotation = _render_annotation(arg.annotation)
    if annotation:
        out = f"{out}: {annotation}"
    if default is not None:
        try:
            out = f"{out} = {ast.unparse(default)}"
        except Exception:
            out = f"{out} = ..."
    return out


def _render_arguments(args: ast.arguments) -> str:
    """Render an ``ast.arguments`` node as a
    parenthesized signature string.

    The rendering is:
    - positional-only args: ``a, b, /``
    - positional-or-keyword args (may have defaults)
    - ``*args`` (annotation after ``:``)
    - keyword-only args (may have defaults; ``*,`` is
      emitted when the keyword-only block is non-empty)
    - ``**kwargs`` (annotation after ``:``)

    Return annotations are NOT included; the consumer
    that wants them reads the AST.
    """
    parts: list[str] = []

    # Positional-only.
    posonly = list(args.posonlyargs)
    regular = list(args.args)
    # If ``posonly`` is non-empty the last regular arg is
    # actually still part of the positional-only block;
    # we keep them as separate lists in case the AST is
    # in the canonical form.
    n_posonly = len(posonly)
    if n_posonly:
        defaults_iter = iter(args.defaults or [])
        # Align defaults: positional-only defaults are
        # the *last* len(defaults) of posonlyargs.
        n_defaults = len(args.defaults or [])
        first_default = n_posonly - n_defaults
        for i, a in enumerate(posonly):
            d = next(defaults_iter, None) if i >= first_default else None
            parts.append(_render_arg(a, default=d))
        parts.append("/")

    # Positional-or-keyword: defaults are right-aligned.
    n_regular = len(regular)
    defaults = args.defaults or []
    n_defaults = len(defaults)
    first_default = max(0, n_regular - n_defaults)
    for i, a in enumerate(regular):
        d = defaults[i - first_default] if i >= first_default else None
        parts.append(_render_arg(a, default=d))

    # ``*args``.
    if args.vararg is not None:
        v = args.vararg
        annotation = _render_annotation(v.annotation)
        parts.append(f"*{v.arg}" + (f": {annotation}" if annotation else ""))

    # Keyword-only.
    if args.kwonlyargs:
        # The ``*,`` marker is explicit when there is
        # no ``*args`` (the marker separates positional-
        # or-keyword from keyword-only). When ``*args``
        # is present, the ``*args`` token itself does
        # the separating.
        if args.vararg is None:
            parts.append("*")
        kw_defaults = args.kw_defaults or [None] * len(args.kwonlyargs)
        for a, d in zip(args.kwonlyargs, kw_defaults, strict=True):
            parts.append(_render_arg(a, default=d))

    # ``**kwargs``.
    if args.kwarg is not None:
        k = args.kwarg
        annotation = _render_annotation(k.annotation)
        parts.append(f"**{k.arg}" + (f": {annotation}" if annotation else ""))

    return "(" + ", ".join(parts) + ")"


def _render_class_bases(bases: list[ast.expr]) -> str:
    """Render the parenthesized base list of a class
    definition. Returns ``""`` for a class without
    explicit bases; returns ``"(Base1, Base2)"``
    otherwise."""
    if not bases:
        return ""
    rendered: list[str] = []
    for b in bases:
        try:
            rendered.append(ast.unparse(b))
        except Exception:
            rendered.append("...")
    return "(" + ", ".join(rendered) + ")"


def _decorator_name(node: ast.expr) -> str:
    """Best-effort dotted name for a decorator
    expression. ``@staticmethod`` is ``"staticmethod"``;
    ``@app.route("/x")`` is ``"app.route"``; an
    unparseable expression is ``"?"``."""
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def _walk_class(
    cls: ast.ClassDef,
    *,
    module_root: str,
    file: str,
) -> list[SymbolRecord]:
    """Walk a class definition and produce a record for
    the class itself plus one record per method /
    async method / nested class."""
    class_qname = f"{module_root}.{cls.name}" if module_root else cls.name
    out: list[SymbolRecord] = []
    out.append(
        SymbolRecord(
            qualified_name=class_qname,
            kind="class",
            file=file,
            line=cls.lineno,
            col=cls.col_offset,
            signature=_render_class_bases(cls.bases),
            decorators=tuple(_decorator_name(d) for d in cls.decorator_list),
            parent=module_root or None,
        )
    )
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = (
                "async_method" if isinstance(item, ast.AsyncFunctionDef)
                else "method"
            )
            method_qname = f"{class_qname}.{item.name}"
            out.append(
                SymbolRecord(
                    qualified_name=method_qname,
                    kind=kind,
                    file=file,
                    line=item.lineno,
                    col=item.col_offset,
                    signature=_render_arguments(item.args),
                    decorators=tuple(_decorator_name(d) for d in item.decorator_list),
                    parent=class_qname,
                )
            )
        elif isinstance(item, ast.ClassDef):
            # Nested class: recurse; the nested class's
            # ``parent`` is the outer class's qualified
            # name (set via the module_root argument).
            out.extend(
                _walk_class(
                    item,
                    module_root=class_qname,
                    file=file,
                )
            )
    return out


def _extract_file(rel_path: str, source: str) -> list[SymbolRecord]:
    """Parse ``source`` and produce every symbol record
    the file declares. Syntax errors return ``[]`` so
    the caller can keep going on other files."""
    out: list[SymbolRecord] = []
    try:
        tree = ast.parse(source, filename=rel_path)
    except (SyntaxError, ValueError):
        return out
    module_root = _module_root(rel_path)
    # Implicit module symbol: one per file.
    out.append(
        SymbolRecord(
            qualified_name=module_root,
            kind="module",
            file=rel_path,
            line=1,
            col=0,
            signature="",
            parent=None,
        )
    )
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            out.extend(
                _walk_class(
                    node,
                    module_root=module_root,
                    file=rel_path,
                )
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = (
                "async_function" if isinstance(node, ast.AsyncFunctionDef)
                else "function"
            )
            qname = f"{module_root}.{node.name}" if module_root else node.name
            out.append(
                SymbolRecord(
                    qualified_name=qname,
                    kind=kind,
                    file=rel_path,
                    line=node.lineno,
                    col=node.col_offset,
                    signature=_render_arguments(node.args),
                    decorators=tuple(
                        _decorator_name(d) for d in node.decorator_list
                    ),
                    parent=module_root or None,
                )
            )
    return out


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
    skipped; non-Python files are silently skipped.
    """
    records: list[SymbolRecord] = []
    for rel_path in paths:
        if not rel_path.endswith(".py"):
            continue
        absolute = repo_root / rel_path
        try:
            source = absolute.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        records.extend(_extract_file(rel_path, source))
    records.sort(key=lambda r: (r.file, r.line, r.col))
    return records


__all__ = ["SymbolRecord", "extract_symbols"]
