"""E1-10 contract test: symbol ownership and signature records.

The contract is documented in
``docs/benchmarks/e1/symbol_ownership.md``.
The test pins:

- the ``SymbolRecord`` shape (8 fields, frozen,
  hashable);
- the signature rendering for the standard forms
  (no args, single arg, multiple args, default values,
  type annotations, *args, **kwargs, positional-only,
  keyword-only);
- the symbol kinds (``module``, ``class``,
  ``function``, ``async_function``, ``method``,
  ``async_method``);
- decorators (``@staticmethod``,
  ``@property``, etc.);
- nested classes (the inner class's ``parent`` is the
  outer class's qualified name);
- syntax error tolerance and non-Python file skip;
- determinism: two calls produce the same list.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.knowledge.symbols import SymbolRecord, extract_symbols


# --- 1. Empty input ---------------------------------------------------


def test_extract_symbols_empty(tmp_path) -> None:
    assert extract_symbols([], tmp_path) == []


# --- 2. Symbol kinds -------------------------------------------------


def test_extract_symbols_module_only(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("# no symbols\n")
    records = extract_symbols(["a.py"], tmp_path)
    assert len(records) == 1
    r = records[0]
    assert r.kind == "module"
    assert r.qualified_name == "a"
    assert r.signature == ""
    assert r.parent is None
    assert r.confidence == 1.0


def test_extract_symbols_function(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("def foo():\n    pass\n")
    records = extract_symbols(["a.py"], tmp_path)
    # 1 module + 1 function.
    assert len(records) == 2
    func = next(r for r in records if r.kind == "function")
    assert func.qualified_name == "a.foo"
    assert func.signature == "()"
    assert func.parent == "a"
    assert func.confidence == 1.0


def test_extract_symbols_async_function(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("async def bar():\n    pass\n")
    records = extract_symbols(["a.py"], tmp_path)
    func = next(r for r in records if r.kind == "async_function")
    assert func.qualified_name == "a.bar"
    assert func.signature == "()"


def test_extract_symbols_class(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("class C:\n    pass\n")
    records = extract_symbols(["a.py"], tmp_path)
    cls = next(r for r in records if r.kind == "class")
    assert cls.qualified_name == "a.C"
    assert cls.signature == ""
    assert cls.parent == "a"


def test_extract_symbols_class_with_bases(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("class C(BaseModel):\n    pass\n")
    records = extract_symbols(["a.py"], tmp_path)
    cls = next(r for r in records if r.kind == "class")
    assert cls.signature == "(BaseModel)"


def test_extract_symbols_method(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("class C:\n    def m(self):\n        pass\n")
    records = extract_symbols(["a.py"], tmp_path)
    method = next(r for r in records if r.kind == "method")
    assert method.qualified_name == "a.C.m"
    assert method.signature == "(self)"
    assert method.parent == "a.C"


def test_extract_symbols_async_method(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("class C:\n    async def m(self):\n        pass\n")
    records = extract_symbols(["a.py"], tmp_path)
    method = next(r for r in records if r.kind == "async_method")
    assert method.qualified_name == "a.C.m"


def test_extract_symbols_nested_class(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "class C:\n"
        "    class D:\n"
        "        pass\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    kinds_q = {(r.kind, r.qualified_name) for r in records}
    assert ("class", "a.C") in kinds_q
    assert ("class", "a.C.D") in kinds_q
    # The nested class's parent is the outer class.
    d = next(r for r in records if r.qualified_name == "a.C.D")
    assert d.parent == "a.C"


# --- 3. Signature rendering -------------------------------------------


def test_signature_no_args(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text("def f():\n    pass\n")
    records = extract_symbols(["a.py"], tmp_path)
    func = next(r for r in records if r.kind == "function")
    assert func.signature == "()"


def test_signature_with_annotations(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "def f(a: int, b: str):\n"
        "    pass\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    func = next(r for r in records if r.kind == "function")
    assert func.signature == "(a: int, b: str)"


def test_signature_with_defaults(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "def f(a, b: str = 'x'):\n"
        "    pass\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    func = next(r for r in records if r.kind == "function")
    assert func.signature == "(a, b: str = 'x')"


def test_signature_varargs_kwargs(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "def f(*args, **kwargs):\n"
        "    pass\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    func = next(r for r in records if r.kind == "function")
    assert func.signature == "(*args, **kwargs)"


def test_signature_positional_only(tmp_path) -> None:
    """A function with a ``/`` marker: ``a`` is
    positional-only; ``b`` is positional-or-keyword;
    ``c`` is keyword-only."""
    f = tmp_path / "a.py"
    f.write_text(
        "def f(a, /, b, *, c):\n"
        "    pass\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    func = next(r for r in records if r.kind == "function")
    assert func.signature == "(a, /, b, *, c)"


def test_signature_kwonly_with_defaults(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "def f(*, a: int = 1, b: str = 'x'):\n"
        "    pass\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    func = next(r for r in records if r.kind == "function")
    assert func.signature == "(*, a: int = 1, b: str = 'x')"


# --- 4. Decorators ---------------------------------------------------


def test_decorator_staticmethod(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "class C:\n"
        "    @staticmethod\n"
        "    def m(x):\n"
        "        return x\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    method = next(r for r in records if r.kind == "method")
    assert method.decorators == ("staticmethod",)


def test_decorator_property(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "class C:\n"
        "    @property\n"
        "    def x(self):\n"
        "        return 1\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    method = next(r for r in records if r.kind == "method")
    assert method.decorators == ("property",)


def test_decorator_multiple(tmp_path) -> None:
    f = tmp_path / "a.py"
    f.write_text(
        "class C:\n"
        "    @staticmethod\n"
        "    @functools.lru_cache(maxsize=128)\n"
        "    def m(x):\n"
        "        return x\n"
    )
    records = extract_symbols(["a.py"], tmp_path)
    method = next(r for r in records if r.kind == "method")
    # The first decorator is closest to the ``def``.
    assert method.decorators[0] == "staticmethod"
    assert method.decorators[1] == "functools.lru_cache(maxsize=128)"


# --- 5. Syntax error tolerance ---------------------------------------


def test_extract_symbols_syntax_error_in_one_file(tmp_path) -> None:
    (tmp_path / "good.py").write_text("def f():\n    pass\n")
    (tmp_path / "bad.py").write_text("def broken(:\n")
    records = extract_symbols(["good.py", "bad.py"], tmp_path)
    # The good file is parsed; the bad file is skipped.
    assert any(r.qualified_name == "good.f" for r in records)
    assert not any(r.qualified_name == "bad.broken" for r in records)


# --- 6. Non-Python file skip -----------------------------------------


def test_extract_symbols_non_python_file_skipped(tmp_path) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n")
    (tmp_path / "readme.txt").write_text("not python")
    records = extract_symbols(["a.py", "readme.txt"], tmp_path)
    assert any(r.qualified_name == "a.f" for r in records)
    assert not any("readme" in r.qualified_name for r in records)


# --- 7. Determinism -------------------------------------------------


def test_extract_symbols_deterministic(tmp_path) -> None:
    (tmp_path / "a.py").write_text("def f():\n    pass\n")
    (tmp_path / "b.py").write_text("def g():\n    pass\n")
    a = extract_symbols(["a.py", "b.py"], tmp_path)
    b = extract_symbols(["a.py", "b.py"], tmp_path)
    assert a == b
    # Sorted by (file, line, col): a before b; line 1
    # is the same; col 0 for the def.
    qualified = [r.qualified_name for r in a]
    assert qualified.index("a.f") < qualified.index("b.g")


# --- 8. Module path derivation ---------------------------------------


def test_module_root_for_nested_path(tmp_path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "mod.py").write_text(
        "def f():\n    pass\n"
    )
    records = extract_symbols(["src/pkg/mod.py"], tmp_path)
    func = next(r for r in records if r.kind == "function")
    assert func.qualified_name == "src.pkg.mod.f"
    # The module's qualified name is the dotted path
    # without the ``.py`` suffix.
    mod = next(r for r in records if r.kind == "module")
    assert mod.qualified_name == "src.pkg.mod"


def test_module_root_for_init_file(tmp_path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text(
        "def f():\n    pass\n"
    )
    records = extract_symbols(["pkg/__init__.py"], tmp_path)
    mod = next(r for r in records if r.kind == "module")
    # The ``__init__.py`` suffix is dropped; the module
    # is the package itself.
    assert mod.qualified_name == "pkg"
    func = next(r for r in records if r.kind == "function")
    assert func.qualified_name == "pkg.f"


# --- 9. Doc sync -----------------------------------------------------


def test_symbol_record_is_frozen() -> None:
    import dataclasses

    r = SymbolRecord(
        qualified_name="a.b", kind="function", file="a.py",
        line=1, col=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.qualified_name = "x"  # type: ignore[misc]
