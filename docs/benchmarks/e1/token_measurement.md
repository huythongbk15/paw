# E1-24 Budgeted token estimates

Current contract, 2026-09-07. Owner: `paw.bench.tokens.measure_tokens`.

The metric is ContextManifest.final_tokens, an estimate of selected context,
not provider-billed cloud input tokens or total prompt cost. Baseline and
measurement must use the same estimator, corpus, scope and declared configuration.

Supply a reviewed positive integer baseline per case. Standalone legacy callers
may register one with set_baseline_tokens; integration requires an explicit
per-run mapping and never falls back to the process registry. Missing, zero,
negative, boolean or noninteger baselines raise ValueError.

Reduction = (baseline - measured) / baseline. Preserve negative results.
Do not clamp regressions or use the measurement as its own baseline.
Measured tokens must be a nonnegative integer.

Cold is the first compilation on caller-prepared state; warm is a repeated
compilation on that same compiler/corpus. No cache hydration or isolation is
implied. The caller must prepare/reset state and record configuration. Errors
propagate. Integration compares the median warm reduction against 30%.

No reviewed dataset baseline run is established by these unit tests.
