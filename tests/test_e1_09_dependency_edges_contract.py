"""E1-09 contract test: dependency edges with source locations and confidence.

The contract is documented in
``docs/benchmarks/e1/dependency_edges.md``.
The test pins:

- the empty-input case;
- static ``import`` / ``from ... import`` edges (kind,
  confidence, line, col, to_module);
- relative imports (leading dots);
- dynamic imports via ``__import__`` and
  ``importlib.import_module`` (lower confidence);
- multi-name ``from x import a, b, c`` produces one
  edge per file (the package), not per name;
- syntax errors in one file do not stop the rest;
- non-Python files are silently skipped;
- determinism: two calls produce the same list.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.knowledge.dependencies import DependencyEdge, extract_dependencies


# --- 1. Empty input ----------------------------------------------------


def test_extract_dependencies_empty(tmp_path) -> None:
    assert extract_dependencies([], tmp_path) == []


# --- 2. Static import -------------------------------------------------


def test_extract_dependencies_static_import(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("import os\n")
    edges = extract_dependencies(["a.py"], tmp_path)
    assert len(edges) == 1
    e = edges[0]
    assert e.from_path == "a.py"
    assert e.to_module == "os"
    assert e.line == 1
    assert e.kind == "absolute"
    assert e.confidence == 1.0


def test_extract_dependencies_from_import(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("from collections import OrderedDict\n")
    edges = extract_dependencies(["a.py"], tmp_path)
    assert len(edges) == 1
    e = edges[0]
    assert e.to_module == "collections"
    assert e.kind == "absolute"
    assert e.confidence == 1.0


def test_extract_dependencies_multiple_imports(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "import os\n"
        "import sys\n"
        "from collections import OrderedDict\n"
    )
    edges = extract_dependencies(["a.py"], tmp_path)
    assert {e.to_module for e in edges} == {"os", "sys", "collections"}


def test_extract_dependencies_multi_name_from(tmp_path) -> None:
    """``from x import a, b, c`` produces ONE edge (the
    package ``x``), not three. The per-name detail is
    available to consumers via the AST."""
    f = tmp_path / "a.py"
    f.write_text("from collections import OrderedDict, defaultdict, Counter\n")
    edges = extract_dependencies(["a.py"], tmp_path)
    assert len(edges) == 1
    assert edges[0].to_module == "collections"


# --- 3. Relative import -----------------------------------------------


def test_extract_dependencies_relative_import(tmp_path) -> None:
    f = tmp_path / "sub" / "a.py"
    f.parent.mkdir()
    f.write_text("from . import sibling\n")
    edges = extract_dependencies(["sub/a.py"], tmp_path)
    assert len(edges) == 1
    e = edges[0]
    assert e.kind == "relative"
    assert e.to_module == ""
    assert e.confidence == 1.0


def test_extract_dependencies_relative_from_package(tmp_path) -> None:
    f = tmp_path / "sub" / "a.py"
    f.parent.mkdir()
    f.write_text("from ..pkg import y\n")
    edges = extract_dependencies(["sub/a.py"], tmp_path)
    assert len(edges) == 1
    e = edges[0]
    assert e.kind == "relative"
    # The leading ``..`` is dropped from ``to_module``;
    # the level is in the import statement's metadata,
    # not the field.
    assert e.to_module == "pkg"


# --- 4. Dynamic import -----------------------------------------------


def test_extract_dependencies_dynamic_dunder_import(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text('__import__("foo")\n')
    edges = extract_dependencies(["a.py"], tmp_path)
    assert len(edges) == 1
    e = edges[0]
    assert e.to_module == "foo"
    assert e.kind == "dynamic"
    assert e.confidence == 0.5


def test_extract_dependencies_dynamic_importlib(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text('importlib.import_module("bar")\n')
    edges = extract_dependencies(["a.py"], tmp_path)
    assert len(edges) == 1
    e = edges[0]
    assert e.to_module == "bar"
    assert e.kind == "dynamic"
    assert e.confidence == 0.5


# --- 5. Syntax error tolerance ---------------------------------------


def test_extract_dependencies_syntax_error_in_one_file(tmp_path) -> None:
    (tmp_path / "good.py").write_text("import os\n")
    (tmp_path / "bad.py").write_text("def broken(:\n")
    edges = extract_dependencies(["good.py", "bad.py"], tmp_path)
    # The good file is parsed; the bad file is skipped.
    assert len(edges) == 1
    assert edges[0].to_module == "os"


# --- 6. Non-Python files are skipped ---------------------------------


def test_extract_dependencies_non_python_file_skipped(tmp_path) -> None:
    (tmp_path / "a.py").write_text("import os\n")
    (tmp_path / "readme.txt").write_text("not python")
    (tmp_path / "data.json").write_text("{}")
    edges = extract_dependencies(
        ["a.py", "readme.txt", "data.json"], tmp_path
    )
    assert len(edges) == 1
    assert edges[0].to_module == "os"


# --- 7. Determinism -------------------------------------------------


def test_extract_dependencies_deterministic(tmp_path) -> None:
    (tmp_path / "a.py").write_text("import os\nimport sys\n")
    (tmp_path / "b.py").write_text("from collections import OrderedDict\n")
    a = extract_dependencies(["a.py", "b.py"], tmp_path)
    b = extract_dependencies(["a.py", "b.py"], tmp_path)
    assert a == b
    # And the result is sorted by (from_path, line, col).
    assert [e.from_path for e in a] == ["a.py", "a.py", "b.py"]


# --- 8. Line / column accuracy --------------------------------------


def test_extract_dependencies_line_and_col(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "# comment line\n"
        "import os\n"
    )
    edges = extract_dependencies(["a.py"], tmp_path)
    assert len(edges) == 1
    e = edges[0]
    # Line 2 (the second line of the file).
    assert e.line == 2
    # Column 0 — the import starts at the beginning of
    # the line.
    assert e.col == 0


# --- 9. Mixed static + dynamic --------------------------------------


def test_extract_dependencies_mixed_static_and_dynamic(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "import os\n"
        'importlib.import_module("bar")\n'
    )
    edges = extract_dependencies(["a.py"], tmp_path)
    # Two edges: one static (confidence 1.0), one
    # dynamic (confidence 0.5). Both have the same
    # line, so the sort key is (from_path, line, col);
    # the static one is at col 0, the dynamic one is
    # at the start of the function call.
    assert len(edges) == 2
    by_kind = {e.kind: e for e in edges}
    assert by_kind["absolute"].to_module == "os"
    assert by_kind["dynamic"].to_module == "bar"
    assert by_kind["absolute"].confidence == 1.0
    assert by_kind["dynamic"].confidence == 0.5
