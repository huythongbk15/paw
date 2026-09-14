"""E1-17: Type annotation linking.

Extracts type annotations from function signatures and variable
annotations, and links them to symbol records for cross-reference.

Spec: docs/benchmarks/e1/type_annotations.md
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

__all__ = ["AnnotationLink", "extract_annotations"]


@dataclass(frozen=True)
class AnnotationLink:
    """A type annotation linking a variable/parameter to its type.

    ``confidence`` is 1.0 for static annotations, 0.5 for inferred.
    """

    file: str  # repo-relative POSIX path
    qualified_name: str  # variable/param name in context
    symbol_qualified_name: str  # qualified name of the type (linked symbol)
    line: int
    col: int
    annotation_text: str  # raw annotation string
    kind: str = "param"  # "param", "var", "return", "attribute"
    confidence: float = 1.0


def _render_annotation(node: ast.expr | None) -> str:
    """Render an AST annotation node to string."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _module_dotted(rel_path: str) -> str:
    """Convert POSIX repo-relative path to dotted module path."""
    if rel_path.endswith("/__init__.py"):
        rel_path = rel_path[: -len("/__init__.py")]
    elif rel_path.endswith(".py"):
        rel_path = rel_path[: -len(".py")]
    parts = [p for p in rel_path.split("/") if p]
    return ".".join(parts)


def extract_annotations(
    file_path: str,
    source: str,
    repo_root: Path,
) -> list[AnnotationLink]:
    """Extract type annotations from a Python file.

    Captures:
    - Function parameters with annotations
    - Return type annotations
    - Variable annotations (e.g., x: int = 5)
    - Annotated assignments

    Returns AnnotationLinks for each annotated item.
    """
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []

    module_path = _module_dotted(file_path)
    links: list[AnnotationLink] = []
    seen: set[tuple[str, int, int]] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            # x: int = 5
            if isinstance(node.target, ast.Name):
                ann = _render_annotation(node.annotation)
                if ann:
                    key = (file_path, node.lineno, node.col_offset)
                    if key not in seen:
                        seen.add(key)
                        links.append(AnnotationLink(
                            file=file_path,
                            qualified_name=f"{module_path}.{node.target.id}" if module_path else node.target.id,
                            symbol_qualified_name=ann,
                            line=node.lineno,
                            col=node.col_offset,
                            annotation_text=ann,
                            kind="var",
                        ))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = f"{module_path}.{node.name}" if module_path else node.name

            # Return annotation
            if node.returns:
                ann = _render_annotation(node.returns)
                if ann:
                    key = (file_path, node.returns.lineno, node.returns.col_offset)
                    if key not in seen:
                        seen.add(key)
                        links.append(AnnotationLink(
                            file=file_path,
                            qualified_name=func_name,
                            symbol_qualified_name=ann,
                            line=node.returns.lineno,
                            col=node.returns.col_offset,
                            annotation_text=ann,
                            kind="return",
                        ))

            # Parameters
            args = node.args
            for arg in args.args:
                if arg.annotation:
                    ann = _render_annotation(arg.annotation)
                    if ann:
                        key = (file_path, arg.lineno, arg.col_offset)
                        if key not in seen:
                            seen.add(key)
                            links.append(AnnotationLink(
                                file=file_path,
                                qualified_name=f"{func_name}.{arg.arg}",
                                symbol_qualified_name=ann,
                                line=arg.lineno,
                                col=arg.col_offset,
                                annotation_text=ann,
                                kind="param",
                            ))

            # Keyword-only args
            for arg in args.kwonlyargs:
                if arg.annotation:
                    ann = _render_annotation(arg.annotation)
                    if ann:
                        key = (file_path, arg.lineno, arg.col_offset)
                        if key not in seen:
                            seen.add(key)
                            links.append(AnnotationLink(
                                file=file_path,
                                qualified_name=f"{func_name}.{arg.arg}",
                                symbol_qualified_name=ann,
                                line=arg.lineno,
                                col=arg.col_offset,
                                annotation_text=ann,
                                kind="param",
                            ))

    links.sort(key=lambda r: (r.file, r.line, r.col))
    return links
