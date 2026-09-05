# E1-22 CLI / Library Inspection Projection for the Current Manifest

This document is the **E1-22 deliverable**. It defines
the contract for `render_manifest`, the function that
turns a `ContextManifest` into a human-readable string
a CLI command or a library caller can print to stdout.

## Why this contract exists

The E1-16 `ContextManifest` is a structured snapshot
the runtime carries through the gate pipeline. A
reviewer who wants to inspect the manifest before
sending it to a provider needs a *projection* — a
deterministic, line-oriented rendering of the
manifest's contents. The projection is the
change-control surface for "what does a reviewer see
when they ask for the current manifest": a fixed text
format that a script can grep / parse, a CLI command
can print, a library caller can log.

## Canonical location

`render_manifest` is a new function in
`paw.core.context_compiler` (the existing module that
owns `ContextManifest`). The function takes a
`ContextManifest` and returns a `str`. The format is
deterministic: two calls with the same input produce
the same output.

## Format

The output is a line-oriented text:

```
# ContextManifest
task_id: <task_id>
budget.max_tokens: <int>
final_tokens: <int>
included: <N> items
  [<source>] <source_id>  relevance=<r>  priority=<p>  tokens=<t>  privacy=<class>
  ...
excluded: <N> items
  [<source>] <source_id>  reason=<reason>
  ...
recent_changes: <N> items
  <short_sha> <date> <author>  <message>
  ...
affected_areas: <N> items
  <short_sha>  affected_symbols=<N>  affected_tests=<N>
  ...
symbols: <N> items
  <qualified_name>
  ...
test_links: <N> items
  <test_qualified_name> -> <source_qualified_name> (conf=<r>, reason=<r>)
  ...
dependency_edges: <N> items
  <from_path>:<line>:<col> -> <to_module> (kind=<k>, conf=<r>)
  ...
```

The format is human-readable and line-oriented. The
exact field order and the indentation are
**implementation details** that may evolve; the
*contract* is "the output is deterministic and
reviewable".

## Phase 4 sync contract

This document is the **source of truth** for E1-22.
The companion contract test
`tests/test_e1_22_manifest_inspection_contract.py`
enforces the determinism + the "every field is
present" invariants.