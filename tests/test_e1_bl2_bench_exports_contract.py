"""E1-BL2 contract test: paw.bench wildcard exports (D0).

The contract is: ``paw.bench.__all__`` contains exactly the twelve
benchmark-contract symbols — the case manifest types and helpers —
and does **not** re-export stdlib types (``Any``, ``ClassVar``,
``StrEnum``, ``dataclass``, ``field``) or runner/verification
implementation symbols (``run_case``, ``load_case``,
``run_case_file``, ``write_runs_jsonl``, ``RunRow``,
``RunnerError``, ``VerificationRecord``, ...).

Submodule symbols stay importable via their explicit path:
``from paw.bench.runner import ...`` /
``from paw.bench.verification import ...``.

The contract test pins:
- the exact ``__all__`` contents;
- no stdlib type names appear in ``__all__``;
- no runner or verification symbol names appear in ``__all__``;
- ``from paw.bench import *`` yields exactly the ``__all__`` symbols;
- the runner and verification submodules remain importable via
  their explicit path.
"""

from __future__ import annotations

import importlib

import pytest

import paw.bench
from paw.bench import __all__ as bench_all


# The twelve benchmark-contract symbols that must appear in
# ``paw.bench.__all__``. Any change to this list must be reflected
# in the implementation and this test together.
EXPECTED_ALL: frozenset[str] = frozenset(
    {
        "CASE_MANIFEST_SCHEMA_VERSION",
        "CaseCategory",
        "CaseManifest",
        "ExpectedEvidence",
        "FixtureRef",
        "PrivacyClass",
        "SchemaError",
        "case_manifest_from_dict",
        "case_manifest_to_dict",
        "is_valid_case_manifest",
        "validate_case_manifest",
        "CaseRunResult",
    }
)

# Symbols that must NOT appear in ``__all__`` because they are
# stdlib types or implementation details of the runner/verification
# submodules.
FORBIDDEN: frozenset[str] = frozenset(
    {
        # stdlib types that were previously leaked via wildcard re-exports
        "Any",
        "ClassVar",
        "StrEnum",
        "dataclass",
        "field",
        # runner implementation symbols
        "load_case",
        "run_case",
        "run_case_file",
        "write_runs_jsonl",
        "RunRow",
        "RunnerError",
        # verification implementation symbols
        "VerificationRecord",
        "VerificationResult",
        "VerificationSpec",
        "make_spec_from_evidence",
    }
)


def test_all_exact_contents() -> None:
    """``paw.bench.__all__`` must contain exactly the twelve
    benchmark-contract symbols, in any order."""
    assert set(bench_all) == EXPECTED_ALL


def test_all_is_list_of_strings() -> None:
    """``__all__`` must be a list of strings."""
    assert isinstance(bench_all, list)
    assert all(isinstance(s, str) for s in bench_all)


@pytest.mark.parametrize("forbidden_symbol", sorted(FORBIDDEN))
def test_no_forbidden_in_all(forbidden_symbol: str) -> None:
    """No stdlib type or runner/verification symbol may appear
    in ``__all__``."""
    assert forbidden_symbol not in bench_all, (
        f"{forbidden_symbol!r} is forbidden from ``__all__``; "
        f"import it explicitly from its submodule instead"
    )


def test_star_import_yields_exact_symbols() -> None:
    """``from paw.bench import *`` must yield exactly the symbols
    listed in ``__all__`` (and nothing more).

    Note: ``Any``, ``ClassVar``, ``StrEnum``, ``dataclass``,
    ``field`` are module-level TYPE ANNOTATIONS (imported from
    ``typing``/``dataclasses``) and remain accessible as
    ``paw.bench.Any`` etc., but they are NOT in ``__all__``,
    so they are excluded from ``import *``. This is the
    intended contract: wildcard import must not leak stdlib
    helper names."""
    # Perform the wildcard import in a fresh namespace.
    ns: dict = {}
    exec("from paw.bench import *", ns)
    # Only __all__ symbols should appear (exec adds __builtins__).
    ns_filtered = {k: v for k, v in ns.items() if k != "__builtins__"}
    assert set(ns_filtered) == set(EXPECTED_ALL), (
        f"wildcard import yielded extra={set(ns_filtered) - EXPECTED_ALL}; "
        f"missing={EXPECTED_ALL - set(ns_filtered)}; "
        f"expected exactly {EXPECTED_ALL}"
    )


@pytest.mark.parametrize(
    "submodule,symbols",
    [
        ("paw.bench.runner", ("load_case", "run_case")),
        ("paw.bench.verification", ("VerificationRecord",)),
    ],
)
def test_submodules_importable(submodule: str, symbols: tuple[str, ...]) -> None:
    """Runner and verification submodules remain importable via
    their explicit path after the wildcard export is narrowed."""
    mod = importlib.import_module(submodule)
    for sym in symbols:
        assert hasattr(mod, sym), (
            f"{sym!r} missing from {submodule}"
        )


def test_star_import_does_not_leak_runner_symbols() -> None:
    """``from paw.bench import *`` must NOT bring in runner
    implementation symbols."""
    import sys

    # Capture current runner-related names in the namespace.
    before = {key for key in sys.modules if key.startswith("paw.bench")}
    # Perform the wildcard import in a fresh namespace.
    ns: dict = {}
    exec("from paw.bench import *", ns)
    # The runner function symbols must not appear in the result.
    for forbidden in ("load_case", "run_case", "run_case_file",
                      "write_runs_jsonl", "RunRow", "RunnerError"):
        assert forbidden not in ns, (
            f"{forbidden!r} leaked via ``from paw.bench import *``"
        )
    for forbidden in ("VerificationRecord", "VerificationResult",
                      "VerificationSpec", "make_spec_from_evidence"):
        assert forbidden not in ns, (
            f"{forbidden!r} leaked via ``from paw.bench import *``"
        )
