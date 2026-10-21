"""The runtime's layers must never spawn a process.

The product charter records that the local filesystem adapter "does not
authorize shell execution". That boundary is easy to state and easy to
erode: an executor that shells out would run commands with no policy
gate, and a workflow step that shelled out would do it inside the
runtime loop.

The boundary is therefore checked mechanically here rather than trusted:

* ``paw/core``, ``paw/executors`` and ``paw/application`` - the layers
  the runtime's effect path runs in - may not import ``subprocess`` or
  call ``os.system`` / ``os.exec*`` / ``os.spawn*`` / ``os.popen``;
* the two places that *do* spawn a process are declared exceptions, and
  the exceptions are checked to be the ones that are allowed:
  ``paw.knowledge.changes`` runs read-only ``git log`` for the recent
  changes view, and ``paw.bench.runner`` is the benchmark tier, which is
  explicitly separate from the runtime.

A verification that needs to run a test suite is therefore supplied by
the **application** through the workflow's verification port, not by PAW.
``demos/demo_engineering_workflow.py`` shows that integration.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PAW = Path(__file__).resolve().parents[1] / "src" / "paw"

# The layers the runtime's effect path runs in.
RUNTIME_LAYERS = ("core", "executors", "application")

# The only modules allowed to spawn a process, and why.
ALLOWED = {
    "knowledge/changes.py": "read-only `git log` for the E1-12 recent-changes view",
    "bench/runner.py": "the E0 benchmark tier, explicitly separate from the runtime",
    "bench/e1_production.py": "the E1-27 production measurement runner, also a benchmark tier",
}

# Calls that spawn a process.
_SPAWN_CALLS = {
    "system": "os.system",
    "popen": "os.popen",
    "execv": "os.execv",
    "execve": "os.execve",
    "execvp": "os.execvp",
    "execvpe": "os.execvpe",
    "execl": "os.execl",
    "execle": "os.execle",
    "execlp": "os.execlp",
    "execlpe": "os.execlpe",
    "spawnl": "os.spawnl",
    "spawnle": "os.spawnle",
    "spawnv": "os.spawnv",
    "spawnve": "os.spawnve",
    "spawnlp": "os.spawnlp",
    "spawnlpe": "os.spawnlpe",
    "spawnvpe": "os.spawnvpe",
    "posix_spawn": "os.posix_spawn",
}


def _relative(path: Path) -> str:
    return str(path.relative_to(PAW)).replace("\\", "/")


def _process_spawns(tree: ast.AST) -> list[str]:
    """Every process-spawning construct in an AST."""
    found: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    found.append("import subprocess")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "subprocess":
                found.append("from subprocess import ...")
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                if node.attr in _SPAWN_CALLS:
                    found.append(_SPAWN_CALLS[node.attr])
            if node.attr == "run" and isinstance(node.value, ast.Name) and node.value.id == "subprocess":
                found.append("subprocess.run")
    return found


def _python_files(layer: str) -> list[Path]:
    return sorted((PAW / layer).rglob("*.py"))


@pytest.mark.parametrize("layer", RUNTIME_LAYERS)
def test_the_runtime_layers_never_spawn_a_process(layer: str) -> None:
    """No module in the runtime's effect path may spawn a process."""
    offenders: list[str] = []
    for path in _python_files(layer):
        rel = _relative(path)
        if rel in ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for found in _process_spawns(tree):
            offenders.append(f"{rel}: {found}")
    assert not offenders, (
        "the runtime's effect path must not spawn a process; the charter does "
        "not authorize shell execution.\n" + "\n".join(offenders)
    )


def test_the_only_process_spawners_are_the_declared_ones() -> None:
    """The exceptions are exactly the two declared modules."""
    spawners: set[str] = set()
    for path in sorted(PAW.rglob("*.py")):
        rel = _relative(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _process_spawns(tree):
            spawners.add(rel)
    assert spawners == set(ALLOWED), (
        "the set of modules that spawn a process changed; a new one needs a "
        f"charter decision.\nfound: {sorted(spawners)}\n"
        f"allowed: {sorted(ALLOWED)}"
    )


def _uses_shell_true(path: Path) -> bool:
    """Whether any call in the file passes ``shell=True``.

    Checked at the AST level: the phrase appears in prose in these
    modules, and prose is not a call.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                    if keyword.value.value is True:
                        return True
    return False


def test_the_declared_exceptions_never_run_a_shell_string() -> None:
    """No declared exception passes ``shell=True``."""
    offenders = [
        rel for rel in sorted(ALLOWED) if _uses_shell_true(PAW / rel)
    ]
    assert not offenders, (
        "a declared exception runs a shell string: " + ", ".join(offenders)
    )


def test_the_benchmark_tier_never_enables_a_shell() -> None:
    """The benchmark runners pass an argv list, never a shell string.

    ``shell=False`` is the default, so a module that never mentions
    ``shell`` is safe; what must not exist is ``shell=True``.
    """
    for rel in ("bench/runner.py", "bench/e1_production.py"):
        assert not _uses_shell_true(PAW / rel), rel
