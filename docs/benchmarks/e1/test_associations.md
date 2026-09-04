# E1-11 Test-to-Source Associations with Explicit Unknowns

This document is the **E1-11 deliverable**. It defines
the contract for `associate_tests`, the function that
turns a set of test files into a flat list of
test-to-source associations — one per test function /
method — with the matched source symbol or an explicit
unknown when the deterministic heuristic cannot find
a match.

## Why this contract exists

The E1-10 symbol view tells the runtime *who owns
each symbol*. E1-11 adds the *other* half of the
reviewer's question: "which test covers this symbol?"
A reviewer who sees `MemoryRecord.from_row` in a
dependency edge wants to know which test method
exercises it; the E1-11 associations are the answer.

The "with explicit unknowns" qualifier is the contract's
core invariant. The deterministic heuristic cannot
match every test to a source symbol — some tests are
integration tests, some are contract tests, some test
multiple symbols at once. The contract is that the
function always emits *some* association per test, and
the unknown cases are explicit (the caller can iterate
the list, find the unknowns, and decide what to do
with them). Silent drops would be the failure mode.

## Canonical location

`associate_tests` is a new function in
`paw.knowledge.test_associations` (a new module). The
function reuses `paw.knowledge.symbols.extract_symbols`
to parse both the test files and the source files; the
E1-10 contract is the *input* to the E1-11 contract.

## `TestAssociation` shape

```python
@dataclass(frozen=True)
class TestAssociation:
    """One test's link to a source symbol.

    ``confidence`` is the heuristic's certainty:
    - 1.0 for a direct symbol-name match.
    - 0.7 for a class-name match (test class ``TestX`` ->
      source class ``X``).
    - 0.5 for a file-name match (test file name suggests
      the source module).
    - 0.0 for an explicit unknown.
    """
    test_qualified_name: str   # e.g. 'test_e1_02.test_audit_documents_knowledge_source_real_fields'
    test_file: str            # repo-relative POSIX
    source_qualified_name: str | None  # e.g. 'paw.knowledge.source.KnowledgeSource'
    source_file: str | None   # repo-relative POSIX
    confidence: float
    reason: str = ""          # "direct_name" | "class_name" | "file_name" | "no_clear_match"
```

The `reason` field is the change-control surface: a
reviewer who disagrees with a match can see *why* the
heuristic made the call.

## `associate_tests` signature

```python
def associate_tests(
    test_paths: Iterable[str],
    source_paths: Iterable[str],
    repo_root: Path,
) -> list[TestAssociation]:
    """Parse every test file in ``test_paths`` and
    every source file in ``source_paths`` (under
    ``repo_root``) and produce one ``TestAssociation``
    per test function / method.

    The function is deterministic: same input -> same
    output, in the same order. The output is sorted
    by ``(test_qualified_name,)`` so two calls produce
    the same list.

    The function emits an explicit unknown for every
    test function / method the heuristic cannot match;
    it never silently drops a test.
    """
```

The function does not resolve imports or call the
test framework; it parses the AST and applies the
heuristic. The caller is the E1-12 recent-change view
and the future change-impact analysis.

## Heuristic (deterministic, in priority order)

The function builds two indexes up-front:

- a map from `(module, qualified_name)` to the source
  `SymbolRecord` (for direct matches);
- a map from `qualified_name` (just the bare name) to
  the list of source records with that bare name (for
  heuristic matches).

For each test function / method:

1. **Direct name match** (confidence 1.0): if the test's
   bare name (e.g. ``test_audit_documents_knowledge_source``)
   or a ``test_<X>`` form (e.g. ``X = audit_documents``)
   matches a source symbol's bare name, emit one
   association per match. If multiple source symbols
   share the same name, emit one per match (the caller's
   downstream consumer picks the right one).

2. **Class-name match** (confidence 0.7): if the test is
   a method on a class (e.g. ``TestX.test_y``), look
   for a source class ``X`` with a method ``y``. If
   found, emit one association per match.

3. **File-name match** (confidence 0.5): if the test
   file is ``test_foo.py`` and the source has a module
   ``foo.py`` or ``foo/__init__.py``, look for a
   top-level symbol in that module whose name matches
   the test's bare name. If found, emit one association.

4. **Explicit unknown** (confidence 0.0): if none of
   the above matches, emit an association with
   ``source_qualified_name=None``,
   ``source_file=None``, ``reason="no_clear_match"``.

The function is *read-only*: it never imports the test
or source modules. It only parses AST.

## Negative cases

| Case | Expected result |
|---|---|
| Empty test paths | `[]`. |
| A test file with a single function `def test_foo(): pass` | One association for `test_foo`; the heuristic matches `foo` if it exists in the source set, else an explicit unknown. |
| A test file with a class `TestX` containing `test_y` | One association for `TestX.test_y`; class-name match against `X.y` if it exists. |
| A test function whose name does not match any source | Explicit unknown with `reason="no_clear_match"`. |
| A test that explicitly asserts the heuristic cannot match (e.g. a meta-test) | The function still emits an association; the unknown is the contract. |
| Determinism | Two calls produce the same list (same order, same content). |
| Multiple source matches | One association per match; the caller picks the right one. |

## Boundary exposure (E1-12 + future change-impact)

`associate_tests` is consumed by:

- the E1-12 recent-change view (which joins VCS file
  changes to the affected tests);
- the future change-impact analysis (which uses the
  E1-09 edges + the E1-10 symbols + the E1-11 test
  associations to answer "if I change
  `KnowledgeSource.mark_invalid`, which tests should
  I run?").

The boundary is the `TestAssociation` list; every
consumer reads the same six fields.

## Phase 4 sync contract

This document is the **source of truth** for E1-11.
The companion contract test
`tests/test_e1_11_test_associations_contract.py`
enforces the cases above.