"""Architecture regression tests for the canonical executable-unit pipeline."""

from __future__ import annotations

import ast
from pathlib import Path


RUNTIME_SOURCE = Path(__file__).parents[1] / "src" / "paw" / "core" / "runtime.py"


def _paw_runtime_methods() -> dict[str, ast.AsyncFunctionDef]:
    assert RUNTIME_SOURCE.is_file(), f"runtime source missing: {RUNTIME_SOURCE}"
    tree = ast.parse(RUNTIME_SOURCE.read_text(encoding="utf-8"))
    runtime_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PawRuntime"
    )
    return {
        node.name: node
        for node in runtime_class.body
        if isinstance(node, ast.AsyncFunctionDef)
    }


def _self_calls(method: ast.AsyncFunctionDef, name: str) -> int:
    return sum(
        1
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr == name
    )


def test_all_runtime_modes_share_one_executable_unit_pipeline() -> None:
    """No public mode may grow a second policy/execution pipeline."""
    methods = _paw_runtime_methods()

    assert "_execute_unit" in methods
    assert _self_calls(methods["_loop"], "_execute_unit") == 1
    assert _self_calls(methods["run_graph"], "_execute_unit") == 1

    gate_callers = {
        name for name, method in methods.items() if _self_calls(method, "_gate_action")
    }
    assert gate_callers == {"_execute_unit"}

