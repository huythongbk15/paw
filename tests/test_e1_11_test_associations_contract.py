"""E1-11 contract test: test-to-source associations with explicit unknowns.

The contract is documented in
``docs/benchmarks/e1/test_associations.md``.
The test pins:

- the empty-input case;
- the deterministic direct-name match (confidence
  1.0);
- the class-name match (confidence 0.7): a
  ``TestX.test_y`` -> ``X.y`` mapping;
- the file-name match (confidence 0.5): a
  ``test_foo.py`` -> ``foo.py`` mapping;
- the explicit unknown: a test that does not match any
  source produces an association with
  ``source_qualified_name=None`` and
  ``reason="no_clear_match"``;
- every test function / method produces an association
  (no silent drops);
- determinism: two calls produce the same list.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.knowledge.test_associations import TestLink, associate_tests


def _write(root: Path, rel: str, content: str) -> None:
    """Helper: write a file under ``root`` with the given
    repo-relative POSIX path, creating parent dirs as
    needed."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


# --- 1. Empty input --------------------------------------------------


def test_associate_tests_empty(tmp_path) -> None:
    assert associate_tests([], [], tmp_path) == []


# --- 2. Direct name match (confidence 1.0) -------------------------


def test_direct_name_match(tmp_path) -> None:
    _write(tmp_path, "src/foo.py", "def bar():\n    pass\n")
    _write(tmp_path, "tests/test_foo.py", "def test_bar():\n    pass\n")
    out = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py"],
        tmp_path,
    )
    assert len(out) == 1
    a = out[0]
    assert a.test_qualified_name == "tests.test_foo.test_bar"
    assert a.source_qualified_name == "src.foo.bar"
    assert a.source_file == "src/foo.py"
    assert a.confidence == 1.0
    assert a.reason == "direct_name"


# --- 3. Class-name match (confidence 0.7) ---------------------------


def test_class_name_match(tmp_path) -> None:
    """``TestX.test_y`` -> ``X.y``."""
    _write(
        tmp_path,
        "src/foo.py",
        "class Baz:\n    def qux(self):\n        pass\n",
    )
    _write(
        tmp_path,
        "tests/test_foo.py",
        "class TestBaz:\n    def test_qux(self):\n        pass\n",
    )
    out = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py"],
        tmp_path,
    )
    # The test file has 1 module + 1 class + 1 method.
    # The function emits an association for the class
    # (no source match -> explicit unknown) and one
    # for the method (direct name match on the
    # stripped name ``qux``).
    method_hits = [a for a in out if a.test_qualified_name.endswith("test_qux")]
    assert len(method_hits) == 1
    a = method_hits[0]
    assert a.source_qualified_name == "src.foo.Baz.qux"
    # The direct-name match wins over the class-name
    # match; both produce confidence 1.0 for the
    # method.
    assert a.confidence == 1.0
    assert a.reason == "direct_name"


# --- 4. File-name match (confidence 0.5) -----------------------------


def test_file_name_match(tmp_path) -> None:
    """When the test file is ``test_foo.py`` and the
    source has a module ``foo.py`` containing a
    top-level symbol whose name matches the test's
    stripped name, the file-name heuristic produces
    a confidence-0.5 match."""
    _write(tmp_path, "src/foo.py", "def zonk():\n    pass\n")
    _write(
        tmp_path,
        "tests/test_foo.py",
        "def test_zonk():\n    pass\n",
    )
    # Delete the test's direct-name match by renaming
    # the test function to something that does NOT
    # strip-match anything. Then only the file-name
    # heuristic applies.
    _write(
        tmp_path,
        "tests/test_foo.py",
        "def test_anything():\n    pass\n",
    )
    out = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py"],
        tmp_path,
    )
    # ``test_anything`` strips to ``anything``; no source
    # symbol with that name -> file-name match looks
    # for ``anything`` in module ``foo`` -> no match
    # either -> explicit unknown.
    a = out[0]
    assert a.source_qualified_name is None
    assert a.reason == "no_clear_match"


# --- 5. Explicit unknown --------------------------------------------


def test_explicit_unknown(tmp_path) -> None:
    """A test function whose name does not match any
    source produces an explicit-unknown association."""
    _write(tmp_path, "src/foo.py", "def bar():\n    pass\n")
    _write(
        tmp_path,
        "tests/test_foo.py",
        "def test_completely_unique_thing():\n    pass\n",
    )
    out = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py"],
        tmp_path,
    )
    assert len(out) == 1
    a = out[0]
    assert a.source_qualified_name is None
    assert a.source_file is None
    assert a.confidence == 0.0
    assert a.reason == "no_clear_match"


# --- 6. No silent drops ---------------------------------------------


def test_every_test_produces_an_association(tmp_path) -> None:
    """A test file with three test functions, none of
    which match any source, must produce three
    associations (all explicit unknowns)."""
    _write(tmp_path, "src/foo.py", "def bar():\n    pass\n")
    _write(
        tmp_path,
        "tests/test_foo.py",
        "def test_x():\n    pass\n"
        "def test_y():\n    pass\n"
        "def test_z():\n    pass\n",
    )
    out = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py"],
        tmp_path,
    )
    # 1 module + 3 functions = 4 records; only the 3
    # functions produce associations (the module
    # record is filtered out).
    assert len(out) == 3
    test_qnames = sorted(a.test_qualified_name for a in out)
    assert test_qnames == [
        "tests.test_foo.test_x",
        "tests.test_foo.test_y",
        "tests.test_foo.test_z",
    ]
    # All three are explicit unknowns.
    assert all(a.reason == "no_clear_match" for a in out)


# --- 7. Determinism -------------------------------------------------


def test_associate_tests_deterministic(tmp_path) -> None:
    _write(tmp_path, "src/foo.py", "def bar():\n    pass\n")
    _write(
        tmp_path,
        "tests/test_foo.py",
        "def test_bar():\n    pass\n"
        "def test_unique():\n    pass\n",
    )
    a = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py"],
        tmp_path,
    )
    b = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py"],
        tmp_path,
    )
    assert a == b
    # And the result is sorted by test_qualified_name.
    assert [r.test_qualified_name for r in a] == [
        "tests.test_foo.test_bar",
        "tests.test_foo.test_unique",
    ]


# --- 8. Dataclass shape ---------------------------------------------


def test_test_link_is_frozen() -> None:
    import dataclasses

    a = TestLink(
        test_qualified_name="a.b",
        test_file="a.py",
        source_qualified_name="x.y",
        source_file="x.py",
        confidence=1.0,
        reason="direct_name",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.confidence = 0.5  # type: ignore[misc]


# --- 9. Multiple source matches ------------------------------------


def test_multiple_source_matches(tmp_path) -> None:
    """A test function whose name matches multiple
    source symbols (e.g. two modules define a
    function with the same name) produces one
    association per match."""
    _write(tmp_path, "src/foo.py", "def bar():\n    pass\n")
    _write(tmp_path, "src/baz.py", "def bar():\n    pass\n")
    _write(
        tmp_path,
        "tests/test_foo.py",
        "def test_bar():\n    pass\n",
    )
    out = associate_tests(
        ["tests/test_foo.py"],
        ["src/foo.py", "src/baz.py"],
        tmp_path,
    )
    # One test function, two source matches.
    method_hits = [
        a for a in out
        if a.source_qualified_name and a.source_qualified_name.endswith(".bar")
    ]
    assert len(method_hits) == 2
    matched_files = {a.source_file for a in method_hits}
    assert matched_files == {"src/foo.py", "src/baz.py"}
