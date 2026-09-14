"""E1-16: Inheritance and method resolution.

Analyzes class inheritance relationships: which classes inherit from which,
method resolution order, and which file defines a given method.

Spec: docs/benchmarks/e1/inheritance.md
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["ClassInfo", "InheritanceEdge", "extract_inheritance"]


@dataclass(frozen=True)
class InheritanceEdge:
    """An inheritance relationship: sub_class inherits from base_class.

    ``confidence`` is 1.0 for explicit inheritance (ast base), 0.7 for
    duck-typing (structural), 0.0 for unknown.
    """

    sub_class: str  # qualified name of subclass
    sub_file: str
    base_class: str  # qualified name of base class
    base_file: str | None  # file where base is defined (None if unresolved)
    line: int
    confidence: float = 1.0


@dataclass
class ClassInfo:
    """Inheritance info for a single class."""

    qualified_name: str
    file: str
    bases: list[str] = field(default_factory=list)
    methods: list[tuple[str, int]] = field(default_factory=list)  # (name, line)
    mro: list[str] = field(default_factory=list)  # method resolution order


def _extract_bases(bases: list[ast.expr]) -> list[str]:
    """Extract base class names from AST base expressions."""
    result = []
    for b in bases:
        if isinstance(b, ast.Name):
            result.append(b.id)
        elif isinstance(b, ast.Attribute):
            result.append(ast.unparse(b))
        elif isinstance(b, ast.Call):
            # e.g., Generic[T] — capture the callable name
            if isinstance(b.func, ast.Name):
                result.append(b.func.id)
            elif isinstance(b.func, ast.Attribute):
                result.append(ast.unparse(b.func))
        elif isinstance(b, ast.Name):
            result.append(b.id)
    return result


def _class_mro(class_name: str, all_classes: dict[str, ClassInfo]) -> list[str]:
    """Compute MRO for a class using C3 linearization (simplified).

    Only handles simple single/multiple inheritance chains. Falls back
    to just [class_name] if the chain is incomplete.
    """
    if class_name in _seen:
        return []  # cycle detection
    _seen.add(class_name)

    if class_name not in all_classes:
        return []

    info = all_classes[class_name]
    mro = [class_name]
    for base in info.bases:
        base_mro = _class_mro(base, all_classes)
        for b in base_mro:
            if b not in mro:
                mro.append(b)
    return mro


_seen: set[str] = set()


def extract_inheritance(
    file_path: str,
    source: str,
    repo_root: Path,
) -> list[ClassInfo]:
    """Extract class inheritance info from a single file.

    Returns ClassInfo for each class defined in the file.
    """
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []

    from .symbols import _module_root  # noqa: F401 (available for future use)

    module_path = _module_dotted(file_path)

    classes: dict[str, ClassInfo] = {}
    result: list[ClassInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            qualified = f"{module_path}.{node.name}" if module_path else node.name
            bases = _extract_bases(node.bases)
            methods = []

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append((item.name, item.lineno))

            info = ClassInfo(
                qualified_name=qualified,
                file=file_path,
                bases=bases,
                methods=methods,
            )
            classes[qualified] = info
            result.append(info)

    # Now compute MRO for each class
    global _seen
    _seen = set()

    for info in result:
        _seen = set()
        info.mro = _compute_mro(info.qualified_name, classes)

    return result


def _compute_mro(
    class_name: str,
    all_classes: dict[str, ClassInfo],
) -> list[str]:
    """Compute MRO for a class (BFS-based, cycle-safe)."""
    if class_name in _seen:
        return []
    _seen.add(class_name)

    if class_name not in all_classes:
        return []

    info = all_classes[class_name]
    mro = [class_name]
    for base in info.bases:
        # Resolve base to qualified name if possible
        resolved = _resolve_base(base, info, all_classes)
        base_mro = _compute_mro(resolved, all_classes)
        for b in base_mro:
            if b not in mro:
                mro.append(b)
    return mro


def _resolve_base(
    base: str,
    info: ClassInfo,
    all_classes: dict[str, ClassInfo],
) -> str:
    """Try to resolve a base class name to its qualified name."""
    # Try exact match
    if base in all_classes:
        return base
    # Try module_prefix.name
    module = info.file.replace("/", ".").replace(".py", "")
    qualified = f"{module}.{base}"
    if qualified in all_classes:
        return qualified
    return base


def _module_dotted(rel_path: str) -> str:
    if rel_path.endswith("/__init__.py"):
        rel_path = rel_path[: -len("/__init__.py")]
    elif rel_path.endswith(".py"):
        rel_path = rel_path[: -len(".py")]
    parts = [p for p in rel_path.split("/") if p]
    return ".".join(parts)
