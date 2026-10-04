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

## Execution status (2026-10-03): E0-21 BLOCKED on account credit

Both configured cloud accounts authenticate but have no balance:

| Provider | `GET /models` | `POST /chat/completions` |
|---|---|---|
| OpenAI (`sk-proj-...`) | HTTP 200, 127 models | `credit_balance_exhausted` (HTTP 429) |
| DeepSeek (`sk-879...`) | HTTP 200, 2 models | `Insufficient Balance` (HTTP 402) |

The keys are valid; the accounts are empty. E0-21 therefore measured nothing
and must not be reported as run. Re-run once a balance exists — the profile
above is otherwise ready.

Note on the provider choice: OpenAI was the first choice and was replaced only
because its account is exhausted. That is an account fact, not a property of the
platform. If OpenAI credit returns, re-evaluate rather than assuming DeepSeek
is the permanent baseline.
