"""PAW Knowledge — dependency edges (E1-09).

``extract_dependencies`` parses each Python file under
``repo_root`` whose repo-relative path is in ``paths``
and returns a flat list of ``DependencyEdge`` records.
The function uses the standard-library ``ast`` module
plus a small regex/heuristic pass for dynamic imports
(``__import__`` / ``importlib.import_module``); the
result is sorted by ``(from_path, line, col)`` so two
calls with the same input produce the same output.

The function is the *static* half of the dependency
graph: it returns the edges the runtime can traverse,
not the traversed graph itself. E1-10 / E1-11 build on
these edges.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DependencyEdge:
    """One import edge in the dependency graph.

    A static ``import x`` statement produces one edge
    pointing at the module ``x``; a ``from x import y``
    statement produces one edge pointing at the module
    ``x`` (the ``y`` symbol is read from the same edge,
    not a new edge).

    ``kind`` is one of ``"absolute"``, ``"relative"``,
    ``"dynamic"``. ``confidence`` is ``1.0`` for static
    imports and ``0.5`` for dynamic imports; the runner
    filters edges whose confidence is below a threshold.
    """

    from_path: str
    to_module: str
    line: int
    col: int
    kind: str
    confidence: float


# Heuristic: match ``importlib.import_module("foo")`` or
# ``__import__("foo")`` in a single line. The pattern is
# intentionally narrow — we only catch the most common
# dynamic-import forms and accept that exotic forms are
# best-effort. A reviewer can always re-scan with a
# dedicated tool if they need them.
_DYNAMIC_IMPORT_RE = re.compile(
    r"""
    (?P<call>importlib\s*\.\s*import_module|__import__)  # call form
    \s*\(\s*
    (?P<q>['\"])
    (?P<name>[A-Za-z_][A-Za-z0-9_.]*)
    (?P=q)
    """,
    re.VERBOSE,
)


def _edges_from_ast(path: str, source: str) -> list[DependencyEdge]:
    """Return every ``Import`` / ``ImportFrom`` edge the
    ``ast`` finds in ``source``. Syntax errors return
    ``[]`` so the caller can keep going on the other
    files in the input list."""
    edges: list[DependencyEdge] = []
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError):
        return edges
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # ``import a, b, c`` — one edge per alias.
            for alias in node.names:
                edges.append(
                    DependencyEdge(
                        from_path=path,
                        to_module=alias.name,
                        line=node.lineno,
                        col=node.col_offset,
                        kind="absolute",
                        confidence=1.0,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            # ``from x import y`` / ``from . import y``.
            if node.level and node.level > 0:
                # Relative import. The ``module`` field is
                # ``None`` for a plain ``from . import y``
                # (where ``y`` is the imported name).
                kind = "relative"
                module = node.module or ""
                # The leading dots are encoded in
                # ``node.level``; we do not repeat them
                # in ``to_module``.
            else:
                kind = "absolute"
                module = node.module or ""
            # Emit the edge whenever the import names at
            # least one symbol, even when ``module`` is
            # empty (a plain ``from . import x``). The
            # consumer uses ``to_module`` + ``level`` to
            # resolve the import.
            if module or node.names:
                edges.append(
                    DependencyEdge(
                        from_path=path,
                        to_module=module,
                        line=node.lineno,
                        col=node.col_offset,
                        kind=kind,
                        confidence=1.0,
                    )
                )
            # The ``node.names`` list is the per-name
            # detail (the ``y`` in ``from x import y``).
            # We do not emit one edge per name; the
            # ``to_module`` is the package. The consumer
            # that wants the per-name detail reads the
            # AST itself; the E1-10 impact analysis
            # uses ``to_module`` only.
    return edges


def _edges_from_dynamic(path: str, source: str) -> list[DependencyEdge]:
    """Return edges the regex heuristic finds for
    ``importlib.import_module("x")`` or
    ``__import__("x")`` calls. The heuristic is
    best-effort: a syntax error elsewhere in the file
    does not stop us (we work on the raw text)."""
    edges: list[DependencyEdge] = []
    for m in _DYNAMIC_IMPORT_RE.finditer(source):
        # We do not have a reliable col/line for the
        # name itself from the regex match alone; we
        # approximate by finding the position of the
        # match in the source and computing line/col.
        start = m.start("name")
        line = source.count("\n", 0, start) + 1
        last_nl = source.rfind("\n", 0, start)
        col = start - (last_nl + 1)
        edges.append(
            DependencyEdge(
                from_path=path,
                to_module=m.group("name"),
                line=line,
                col=col,
                kind="dynamic",
                confidence=0.5,
            )
        )
    return edges


def extract_dependencies(
    paths: Iterable[str],
    repo_root: Path,
) -> list[DependencyEdge]:
    """Parse each Python file under ``repo_root`` whose
    repo-relative path is in ``paths`` and return a
    flat list of dependency edges.

    The result is sorted by ``(from_path, line, col)``
    so two calls with the same input produce the same
    output. Files that fail to parse (syntax errors,
    non-UTF-8 content) are silently skipped.
    """
    edges: list[DependencyEdge] = []
    for rel_path in paths:
        if not rel_path.endswith(".py"):
            continue
        absolute = repo_root / rel_path
        try:
            source = absolute.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        edges.extend(_edges_from_ast(rel_path, source))
        edges.extend(_edges_from_dynamic(rel_path, source))
    edges.sort(key=lambda e: (e.from_path, e.line, e.col))
    return edges


__all__ = ["DependencyEdge", "extract_dependencies"]
