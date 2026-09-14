"""E1-15: Cross-file symbol references.

Resolves references between files: import statements that connect
a consuming file to the symbol it imports, and cross-file usage
where a symbol defined in one file is called/used in another.

Spec: docs/benchmarks/e1/cross_file_references.md
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

__all__ = ["SymbolReference", "build_symbol_index", "resolve_cross_file"]


@dataclass(frozen=True)
class SymbolReference:
    """A reference from one file to a symbol defined in another.

    ``confidence`` is 1.0 for static imports, 0.8 for cross-file
    usage (a symbol used as an attribute), 0.5 for dynamic import.
    """

    from_file: str  # consumer file, POSIX relative
    to_symbol: str  # qualified name of referenced symbol (module path)
    to_file: str  # file where the symbol is defined
    line: int
    col: int
    kind: str = "import"  # "import", "from_import", "attribute_use", "dynamic"
    confidence: float = 1.0


def _module_dotted(rel_path: str) -> str:
    """Convert POSIX repo-relative path to dotted module path."""
    if rel_path.endswith("/__init__.py"):
        rel_path = rel_path[: -len("/__init__.py")]
    elif rel_path.endswith(".py"):
        rel_path = rel_path[: -len(".py")]
    parts = [p for p in rel_path.split("/") if p]
    return ".".join(parts)


@dataclass
class _SymbolIndexEntry:
    qualified_name: str
    file: str
    line: int
    col: int
    kind: str


def build_symbol_index(
    paths: list[str],
    repo_root: str,
) -> dict[str, list[_SymbolIndexEntry]]:
    """Build a symbol-name -> [entries] index across all paths.

    Used to resolve cross-file references quickly.
    """
    from .symbols import extract_symbols

    index: dict[str, list[_SymbolIndexEntry]] = {}

    for p in paths:
        try:
            symbols = extract_symbols([p], Path(repo_root))
        except Exception:
            continue

        for s in symbols:
            bare = s.qualified_name.rsplit(".", 1)[-1] if s.qualified_name else ""
            if bare:
                index.setdefault(bare, []).append(
                    _SymbolIndexEntry(
                        qualified_name=s.qualified_name,
                        file=s.file,
                        line=s.line,
                        col=s.col,
                        kind=s.kind,
                    )
                )
            if s.qualified_name:
                parts = s.qualified_name.split(".")
                for i in range(len(parts)):
                    partial = ".".join(parts[i:])
                    if partial:
                        index.setdefault(partial, []).append(
                            _SymbolIndexEntry(
                                qualified_name=s.qualified_name,
                                file=s.file,
                                line=s.line,
                                col=s.col,
                                kind=s.kind,
                            )
                        )

    return index


def resolve_cross_file(
    consumer_files: list[str],
    symbol_index: dict[str, list[_SymbolIndexEntry]],
    repo_root: str,
) -> list[SymbolReference]:
    """Resolve cross-file references for a set of consumer files.

    Parses import statements in consumer_files, resolves them against
    the symbol_index, and returns SymbolReferences.
    """
    references: list[SymbolReference] = []
    seen: set[tuple[str, str]] = set()

    for rel in consumer_files:
        full = str(Path(repo_root) / rel)
        try:
            source = Path(full).read_text(encoding="utf-8")
        except Exception:
            continue

        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    entry = _lookup_in_index(name, symbol_index)
                    if entry and entry.file != rel:
                        key = (rel, entry.qualified_name)
                        if key not in seen:
                            seen.add(key)
                            references.append(SymbolReference(
                                from_file=rel,
                                to_symbol=entry.qualified_name,
                                to_file=entry.file,
                                line=node.lineno,
                                col=node.col_offset,
                                kind="import",
                                confidence=1.0,
                            ))

            elif isinstance(node, ast.ImportFrom):
                module = _module_dotted(node.module or "")
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    entry = _lookup_in_index(full_name, symbol_index)
                    if not entry:
                        entry = _lookup_in_index(alias.name, symbol_index)
                    if entry and entry.file != rel:
                        key = (rel, entry.qualified_name)
                        if key not in seen:
                            seen.add(key)
                            references.append(SymbolReference(
                                from_file=rel,
                                to_symbol=entry.qualified_name,
                                to_file=entry.file,
                                line=node.lineno,
                                col=node.col_offset,
                                kind="from_import",
                                confidence=1.0,
                            ))

    references.sort(key=lambda r: (r.from_file, r.line, r.col))
    return references


def _lookup_in_index(
    name: str,
    index: dict[str, list[_SymbolIndexEntry]],
) -> _SymbolIndexEntry | None:
    """Look up a symbol by dotted name in the index."""
    entries = index.get(name)
    if entries:
        return entries[0]
    bare = name.rsplit(".", 1)[-1]
    entries = index.get(bare)
    if entries:
        return entries[0]
    return None
