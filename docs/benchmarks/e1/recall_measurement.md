# E1-23 Budgeted, source-bound recall

Current contract, 2026-09-07. Supersedes the unlimited-budget and text-only
matching rules. Owner: `paw.bench.recall.measure_recall`.

- Compile with the compiler's configured budget; never inflate it for recall.
- Integration supplies the same manifest to recall and token measurement.
- Every expected item contributes to the denominator, even when values repeat.
- Match the exact source path (knowledge external_id, otherwise reference)
  relative to repo_root; file_contains additionally requires its value in content.
- file_exists measures source presence in context, not existence on disk.
- Reject empty evidence, unsupported runtime evidence kinds and targets outside
  repo_root. Runtime evidence needs its own evaluator; text matching is not proof.
- Propagate compilation errors; no unbudgeted fallback.
- Recall target is >= 0.95 in both cold and warm samples.

These measurements require a caller-prepared, revision-pinned corpus. The
measurement API does not ingest fixtures or certify corpus freshness.
