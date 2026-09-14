"""Knowledge Engine deep dive tests.

Tests cross-file symbol references, inheritance chains, and type annotation
resolution — extending E1-09 (dependency edges) and E1-10 (symbol ownership).
"""
import json
import textwrap
from pathlib import Path

import pytest

from paw.knowledge.symbols import extract_symbols
from paw.knowledge.dependencies import extract_dependencies
from paw.knowledge.source import KnowledgeSourceManager

pytestmark = pytest.mark.asyncio


def _write_file(tmp_path: Path, path: str, content: str) -> Path:
    full = tmp_path / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return full


def _index_files(tmp_path: Path, files: list[tuple[str, str]]):
    paths = []
    for rel, _ in files:
        _write_file(tmp_path, rel, "")
        paths.append(rel)
    symbols = extract_symbols(paths, tmp_path)
    deps = extract_dependencies(paths, tmp_path)
    return paths, symbols, deps


async def _populate_knowledge_db(symbols, deps):
    from paw.core.storage import db
    await db.execute("""
        CREATE TABLE IF NOT EXISTS symbol_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL, line INTEGER, col INTEGER,
            kind TEXT, name TEXT, qualified_name TEXT, metadata TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS dependency_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_path TEXT, from_line INTEGER, from_col INTEGER,
            to_path TEXT, to_name TEXT, kind TEXT
        )
    """)
    # Clear tables first for test isolation
    await db.execute("DELETE FROM symbol_registry")
    await db.execute("DELETE FROM dependency_edges")
    for sym in symbols:
        name = sym.qualified_name.rsplit(".", 1)[-1]
        await db.execute(
            "INSERT OR REPLACE INTO symbol_registry "
            "(source_file, line, col, kind, name, qualified_name, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sym.source_file if hasattr(sym, "source_file") else sym.file, sym.line, sym.col, sym.kind, name,
             sym.qualified_name, json.dumps(getattr(sym, "__dict__", {}))),
        )
    for dep in deps:
        await db.execute(
            "INSERT OR REPLACE INTO dependency_edges "
            "(from_path, from_line, from_col, to_path, to_name, kind) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dep.from_path, dep.line, dep.col, "", dep.to_module, dep.kind),
        )


@pytest.fixture
async def ksm():
    from paw.core.storage import db
    await db.execute("DELETE FROM knowledge_sources")
    # Ensure knowledge base tables exist for E4-ext methods
    await db.execute("""
        CREATE TABLE IF NOT EXISTS symbol_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL, line INTEGER, col INTEGER,
            kind TEXT, name TEXT, qualified_name TEXT, metadata TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS dependency_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_path TEXT, from_line INTEGER, from_col INTEGER,
            to_path TEXT, to_name TEXT, kind TEXT
        )
    """)
    return KnowledgeSourceManager()


class TestFindReferences:
    async def test_find_references_undefined_symbol(self, ksm):
        refs = await ksm.find_references("nonexistent.module.symbol")
        assert refs == []

    async def test_find_references_definition_found(self, tmp_path, ksm):
        content = textwrap.dedent("""
            def standalone_func():
                pass
        """)
        p = _write_file(tmp_path, "app.py", content)
        from paw.knowledge.symbols import extract_symbols
        symbols = extract_symbols(["app.py"], tmp_path)
        await _populate_knowledge_db(symbols, [])

        refs = await ksm.find_references("app.standalone_func")
        assert len(refs) == 1
        assert refs[0]["symbol_name"] == "standalone_func"

    async def test_find_references_cross_file(self, tmp_path, ksm):
        app_content = textwrap.dedent("""
            def my_function(x: int) -> str:
                return str(x)
        """)
        importer_content = textwrap.dedent("""
            from my_module import my_function
            result = my_function(42)
        """)
        _write_file(tmp_path, "my_module.py", app_content)
        _write_file(tmp_path, "importer.py", importer_content)
        symbols = extract_symbols(["my_module.py", "importer.py"], tmp_path)
        deps = extract_dependencies(["my_module.py", "importer.py"], tmp_path)
        await _populate_knowledge_db(symbols, deps)

        refs = await ksm.find_references("my_module.my_function")
        assert len(refs) >= 1


class TestInheritanceChain:
    async def test_single_inheritance(self, tmp_path, ksm):
        content = textwrap.dedent("""
            class BaseClass: pass
            class DerivedClass(BaseClass): pass
        """)
        _write_file(tmp_path, "classes.py", content)
        await _populate_knowledge_db(extract_symbols(["classes.py"], tmp_path), [])

        from paw.core.storage import db
        await db.execute(
            "UPDATE symbol_registry SET metadata = ? WHERE qualified_name = ?",
            (json.dumps({"bases": ["classes.BaseClass"]}), "classes.DerivedClass"),
        )

        chain = await ksm.get_inheritance_chain("classes.DerivedClass")
        assert "classes.DerivedClass" in chain
        assert "classes.BaseClass" in chain
        assert chain.index("classes.DerivedClass") < chain.index("classes.BaseClass")

    async def test_inheritance_unknown_class(self, ksm):
        chain = await ksm.get_inheritance_chain("nonexistent.Class")
        assert chain == ["nonexistent.Class"]

    async def test_inheritance_dedupe(self, ksm):
        from paw.core.storage import db
        await db.execute(
            "UPDATE symbol_registry SET metadata = ? WHERE qualified_name = ?",
            (json.dumps({"bases": ["base.A", "base.A"]}), "diamond.DerivedClass"),
        )
        await db.execute(
            "INSERT OR REPLACE INTO symbol_registry "
            "(source_file, line, col, kind, name, qualified_name, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("base.py", 1, 0, "class", "A", "base.A", json.dumps({"bases": []})),
        )
        chain = await ksm.get_inheritance_chain("diamond.DerivedClass")
        assert len(chain) == len(set(chain))


class TestTypeAnnotationResolution:
    async def test_resolve_annotations(self, tmp_path, ksm):
        content = textwrap.dedent("""
            def typed_function(x: int, y: str) -> bool:
                return True
        """)
        _write_file(tmp_path, "types.py", content)
        await _populate_knowledge_db(extract_symbols(["types.py"], tmp_path), [])

        from paw.core.storage import db
        await db.execute(
            "UPDATE symbol_registry SET metadata = ? WHERE qualified_name = ?",
            (json.dumps({"annotations": {"x": "int", "y": "str", "return": "bool"}}),
             "types.typed_function"),
        )

        annotations = await ksm.resolve_type_annotations("types.typed_function")
        assert annotations["x"] == "int"
        assert annotations["y"] == "str"
        assert annotations["return"] == "bool"

    async def test_resolve_annotations_missing_symbol(self, ksm):
        result = await ksm.resolve_type_annotations("nonexistent.function")
        assert result == {}


class TestSymbolRegistryIntegration:
    async def test_symbol_extraction_produces_class(self, tmp_path, ksm):
        content = textwrap.dedent("""
            class TestClass:
                def method(self, x: int) -> str:
                    return str(x)
        """)
        _write_file(tmp_path, "test_mod.py", content)
        symbols = extract_symbols(["test_mod.py"], tmp_path)
        assert len(symbols) >= 1
        class_syms = [s for s in symbols if s.kind == "class"]
        assert len(class_syms) == 1
        assert class_syms[0].qualified_name.endswith("TestClass")
