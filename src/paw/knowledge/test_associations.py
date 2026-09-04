"""PAW Knowledge — test-to-source associations (E1-11).

``associate_tests`` turns a set of test files into a
flat list of test-to-source associations — one per test
function / method — with the matched source symbol or
an explicit unknown when the deterministic heuristic
cannot find a match. The function reuses the E1-10
``extract_symbols`` to parse both test files and source
files; the AST is the single source of truth.

The function never silently drops a test: every test
function / method produces an association, and the
cases the heuristic cannot match are surfaced as
``TestAssociation`` records with
``source_qualified_name=None`` and
``reason="no_clear_match"``. The "explicit unknowns"
is the contract's core invariant.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .symbols import SymbolRecord, extract_symbols


@dataclass(frozen=True)
class TestLink:
    """One test's link to a source symbol.

    The class is named ``TestLink`` (not ``TestAssociation``)
    so pytest's collector does not mistake it for a test
    class (any class whose name starts with ``Test`` is
    collected by default). The ``__test__ = False``
    attribute is a defensive belt-and-suspenders: even
    if pytest's collector sees the import, the attribute
    tells it "this is not a test class".

    See ``docs/benchmarks/e1/test_associations.md`` for
    the full contract.
    """

    __test__ = False  # tell pytest this is not a test class

    test_qualified_name: str
    test_file: str
    source_qualified_name: str | None
    source_file: str | None
    confidence: float
    reason: str = ""


def _strip_test_prefix(name: str) -> str:
    """``test_audit`` -> ``audit``; ``testFoo`` -> ``Foo``.

    The heuristic matches by bare name; the prefix
    ``test_`` (snake-case tests) or ``test`` (camelCase
    tests) is stripped. If the strip leaves an empty
    string, the original name is returned so the
    caller can still match it (some tests are named
    just ``test``).
    """
    if name.startswith("test_") and len(name) > 5:
        return name[5:]
    if name.startswith("test") and len(name) > 4 and not name[4].isalpha():
        # ``test_foo`` already covered; this branch is
        # for ``test$foo``-style edge cases the project
        # does not use.
        return name[4:]
    return name


def _build_source_index(
    source_paths: Iterable[str],
    repo_root: Path,
) -> tuple[
    dict[str, list[SymbolRecord]],
    dict[str, list[SymbolRecord]],
    dict[str, list[SymbolRecord]],
]:
    """Build three indexes from the source symbols:

    - ``by_qualified``: qualified_name -> records
      (used for direct matches).
    - ``by_bare``: bare_name -> records
      (used for class-name and direct-name matches).
    - ``by_module``: module_root -> records in that
      module (used for file-name matches).
    """
    by_qualified: dict[str, list[SymbolRecord]] = {}
    by_bare: dict[str, list[SymbolRecord]] = {}
    by_module: dict[str, list[SymbolRecord]] = {}
    for r in extract_symbols(source_paths, repo_root):
        by_qualified.setdefault(r.qualified_name, []).append(r)
        # Bare name: last part of the qualified name
        # (``"a.b.c"`` -> ``"c"``).
        bare = r.qualified_name.rsplit(".", 1)[-1]
        by_bare.setdefault(bare, []).append(r)
        # Module root: every record has the same
        # module root (the file's dotted path). We
        # group by that for the file-name match.
        module_root = r.parent or r.qualified_name.rsplit(".", 1)[0]
        by_module.setdefault(module_root, []).append(r)
    return by_qualified, by_bare, by_module


def _emit(
    test_qname: str,
    test_file: str,
    sources: list[SymbolRecord],
    *,
    confidence: float,
    reason: str,
) -> list[TestLink]:
    """Build a list of associations, one per source
    record. A single test can match multiple source
    symbols (a name clash); the caller picks the right
    one downstream."""
    out: list[TestLink] = []
    for s in sources:
        out.append(
            TestLink(
                test_qualified_name=test_qname,
                test_file=test_file,
                source_qualified_name=s.qualified_name,
                source_file=s.file,
                confidence=confidence,
                reason=reason,
            )
        )
    return out


def _emit_unknown(
    test_qname: str,
    test_file: str,
) -> TestLink:
    return TestLink(
        test_qualified_name=test_qname,
        test_file=test_file,
        source_qualified_name=None,
        source_file=None,
        confidence=0.0,
        reason="no_clear_match",
    )


def _match_test(
    test_record: SymbolRecord,
    by_qualified: dict[str, list[SymbolRecord]],
    by_bare: dict[str, list[SymbolRecord]],
    by_module: dict[str, list[SymbolRecord]],
) -> list[TestLink]:
    """Match one test record against the source indexes.

    The function returns either a non-empty list of
    associations (one per source match) or a
    single-element list with the explicit unknown. The
    caller flattens these into the final output.
    """
    bare = test_record.qualified_name.rsplit(".", 1)[-1]
    # 1. Direct name match: ``test_foo`` -> ``foo`` (also
    # the bare name itself, for test classes named
    # ``TestFoo``).
    stripped = _strip_test_prefix(bare)
    candidates: list[SymbolRecord] = []
    confidence = 1.0
    reason = "direct_name"
    # If the stripped name matches a source bare name,
    # we have a hit. If the bare name itself (without
    # the prefix strip) matches, that's also a hit.
    if stripped and stripped != bare and stripped in by_bare:
        candidates = list(by_bare[stripped])
    elif bare in by_bare:
        # The test's bare name is itself a source name
        # (e.g. a test helper function named
        # ``audit_records`` is in the same name-space
        # as the function it tests).
        candidates = list(by_bare[bare])
        reason = "direct_name"
    else:
        candidates = []
    if candidates:
        return _emit(
            test_record.qualified_name,
            test_record.file,
            candidates,
            confidence=confidence,
            reason=reason,
        )
    # 2. Class-name match: ``TestX.test_y`` -> ``X.y``.
    # The test record's parent is the test class's
    # qualified name (``a.b.TestX``); the bare class
    # name is ``TestX``. Strip the ``Test`` prefix and
    # look for a source class with that name; the
    # method name is the test method's bare name.
    parent_qname = test_record.parent
    if parent_qname:
        parent_bare = parent_qname.rsplit(".", 1)[-1]
        if parent_bare.startswith("Test") and len(parent_bare) > 4:
            class_name = parent_bare[4:]
            method_name = bare
            # Find source ``class_name`` (or any
            # symbol whose name == class_name), then
            # look for a method ``method_name`` on it.
            class_records = by_bare.get(class_name, [])
            method_hits: list[SymbolRecord] = []
            for cr in class_records:
                if cr.kind != "class":
                    continue
                # The source class's qualified name
                # is ``cr.qualified_name``; methods on
                # it have qualified_name == ``<class_q>.<m>``.
                # We use the module index to find
                # methods under that class's module.
                # Simpler: iterate by_bare[method_name]
                # and keep those whose ``parent`` ==
                # class's qualified name.
                for candidate in by_bare.get(method_name, []):
                    if candidate.parent == cr.qualified_name:
                        method_hits.append(candidate)
            if method_hits:
                return _emit(
                    test_record.qualified_name,
                    test_record.file,
                    method_hits,
                    confidence=0.7,
                    reason="class_name",
                )
    # 3. File-name match: test file ``test_foo.py``
    # suggests a source module ``foo.py``. Look in
    # the source module's records for the test's
    # stripped name.
    test_file = test_record.file
    if test_file.startswith("test_") and test_file.endswith(".py"):
        guessed = test_file[len("test_"): -len(".py")]
        # ``guessed`` may be a dotted module path
        # (``test_paw_memory.py`` -> ``paw_memory``).
        # We try a few candidates: the exact stripped
        # name, and a Python-name-style conversion
        # (``paw_memory`` -> ``paw.memory``).
        module_guesses = [guessed]
        if "_" in guessed:
            module_guesses.append(guessed.replace("_", "/"))
        # Also try stripping a ``_contract`` /
        # ``_integration`` suffix the project uses for
        # test names.
        for suffix in ("_contract", "_integration"):
            if guessed.endswith(suffix):
                module_guesses.append(guessed[: -len(suffix)])
        hits: list[SymbolRecord] = []
        for mg in module_guesses:
            # The source module root looks like
            # ``src.paw.memory`` for ``src/paw/memory.py``.
            module_guesses_dot = mg.replace("/", ".")
            target = module_guesses_dot + "." + stripped
            for sym in by_module.get(module_guesses_dot, []):
                if sym.qualified_name.endswith("." + stripped) or sym.qualified_name == target:
                    hits.append(sym)
        if hits:
            return _emit(
                test_record.qualified_name,
                test_record.file,
                hits,
                confidence=0.5,
                reason="file_name",
            )
    # 4. Explicit unknown.
    return [_emit_unknown(test_record.qualified_name, test_record.file)]


def associate_tests(
    test_paths: Iterable[str],
    source_paths: Iterable[str],
    repo_root: Path,
) -> list[TestLink]:
    """Parse every test file in ``test_paths`` and
    every source file in ``source_paths`` and produce
    one ``TestAssociation`` per test function / method.

    The result is sorted by ``(test_qualified_name,)``
    so two calls produce the same list. Every test
    function / method produces an association; the
    cases the heuristic cannot match are surfaced as
    ``TestAssociation`` records with
    ``source_qualified_name=None`` and
    ``reason="no_clear_match"``.
    """
    by_qualified, by_bare, by_module = _build_source_index(
        source_paths, repo_root
    )
    test_records = extract_symbols(test_paths, repo_root)
    out: list[TestLink] = []
    for tr in test_records:
        # The E1-10 symbol view emits a ``module`` record
        # for every file plus a record per function /
        # method. We only want to associate functions /
        # methods (and classes) — never the implicit
        # ``module`` record. The implicit module record
        # has ``signature == ""`` and ``kind == "module"``
        # and ``parent is None``; the contract only
        # associates functions, methods, and classes.
        if tr.kind == "module":
            continue
        out.extend(
            _match_test(
                tr,
                by_qualified,
                by_bare,
                by_module,
            )
        )
    out.sort(key=lambda a: a.test_qualified_name)
    return out


__all__ = ["TestLink", "associate_tests"]
