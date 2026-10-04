# E0-20 — Cloud baseline profile (approved)

Decision date: 2026-10-03. Status: `APPROVED`. Unblocks E0-21.

## What a "cloud baseline" means here

One reproducible reference point: a cloud model, given the same reviewed task and
the same budgeted context manifest PAW gives a local model, scored on the same
cases. Its purpose is not to be the product. It answers one question — *how much
headroom does the local model actually have?* — and it is the teacher signal for
the later loop that teaches local.

## Profile

| Field | Value |
|---|---|
| Provider | DeepSeek (`https://api.deepseek.com`, OpenAI-compatible) |
| Model | `deepseek-v4-pro` |
| Why this one | A baseline must be the cheapest *credible* reference, or it becomes unaffordable to re-run every time local changes. Selected after the OpenAI account returned `credit_balance_exhausted` (no credits), which is an account fact and not a property of PAW. `deepseek-v4-pro` is strong enough that a miss cannot be blamed on a weak teacher, and cheap enough to re-run per measurement. |
| Transport | `POST /chat/completions`, JSON, `stream: false` |
| Determinism | `temperature: 0`, fixed `seed` where supported |

## Disclosure limits (binding)

1. **Minimum disclosure.** Only the compiled context manifest is sent — the
   fragments PAW selected, each carrying its provenance. The workspace is never
   sent wholesale.
2. **No secrets.** Any candidate marked `PrivacyClass.SECRET` is removed before
   any request. `SECRET` never leaves the machine.
3. **No stale or unowned sources.** Only fresh, revision-pinned sources are
   eligible, matching the existing `gate_remote_disclosure` rule.
4. **Every call is gated and logged.** Each request is recorded in the ledger
   with the disclosure class and the observed token usage.
5. **Local-first default is unchanged.** Cloud is opt-in for a measurement run;
   nothing in the default `paw chat` path requires it.

## Cost ceiling

**Hard cap for the E0-21 run: USD 1.00.** The run aborts if projected spend
exceeds it. Expected spend is a small fraction of that; the cap exists so a
misconfigured loop cannot run up a bill.

Token counts come from the provider's own `usage` block and are **observed**.
Cost depends on a per-token rate that DeepSeek does not return in the response,
so cost is reported as an **estimate at a stated rate** and is never presented as
observed. The ceiling is enforced on observed tokens, not on the estimate.

## What this does NOT authorize

- No cloud provider becomes a runtime default.
- No continuous or unattended cloud calls.
- No training spend. `E4-10` (cloud teacher baseline) is unblocked but still
  unchecked, and fine-tuning is priced separately and separately approved.

## Execution status (2026-10-03): E0-21 RUN on a free routed provider

The direct cloud accounts are empty (`credit_balance_exhausted` on OpenAI,
`Insufficient Balance` on DeepSeek), so the baseline is routed through
**OpenRouter** onto its **free tier**. Cost is genuinely zero rather than
deferred, and OpenRouter returns a real `cost` field, so usage and cost are both
**observed** rather than estimated.

| Field | Value |
|---|---|
| Router | `https://openrouter.ai/api/v1` |
| Model | `nvidia/nemotron-3.5-lightning:free` (free tier) |
| Fallbacks | `qwen/qwen3.8-27b:free`, `google/gemma-4-31b-it:free` |
| Observed cost | **$0.000000** across 6 cases |
| Observed tokens | 30,442 |

Free-tier models are rate limited; `qwen/qwen3.8-27b:free` returned HTTP 429 on
probe. The runner therefore declares a fallback list and records which model
actually answered each case. On this run Nemotron answered all six and no retry
was needed.

### Result — two runs, and they disagree

| Case | run 1 | run 2 |
|---|---|---|
| edit_family | 1.00 | 0.33 |
| ngram_utils | 1.00 | 1.00 |
| counter_helpers | 0.67 | 1.00 |
| token_based | 0.25 | 0.00 |
| algorithm_families | 0.00 | 0.00 |
| public_api | 0.00 | 0.00 |
| **mean** | **0.4861** | **0.3889** |
| observed cost | $0.000000 | $0.000000 |
| observed tokens | 30,442 | 30,269 |

**This is the most important finding of the run.** Both used `temperature: 0`
and the same model, and the mean moved by ~0.10 with individual cases swinging
from 1.00 to 0.00. A routed free-tier model is therefore **not a stable
baseline**: a single run cannot be quoted as the number. E0-21 needs repeated
runs (the E0-06 spec's `pass_rate` / `flakiness_score` machinery is the right
instrument) before any claim about cloud-vs-local headroom is defensible.

Reporting only the better run would have been the easy and dishonest choice.

Two things this does and does not show.

It **does** show a cloud model is not automatically better at this task when it
is given PAW's retrieved context: two cases score 0.00. For `public_api` the
cause is upstream of the model — the import-only `__init__.py` is not in the
manifest at all, so a stronger model would fail the same way. That is evidence
for fixing retrieval rather than for escalating the model.

It **does not** compare against local. PAW's own local figure measures whether
retrieval put the evidence in the manifest; this one measures whether the model
reproduced it. The two numbers are different quantities and must not be compared
directly.

Harness: `benchmarks/e0/run_cloud_baseline.py`. Manual and opt-in; it makes
network calls and never runs in the default suite.
