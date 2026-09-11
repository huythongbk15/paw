# E4 — Controlled local model adaptation

## Goal

Train only where verified history proves a stable, narrow and valuable local
role.

## Entry conditions

- E0–E3 pass and a sufficient set of successful, reviewed traces exists
- Memory correction, retention and deletion semantics are operational
- The same role has a non-trained local baseline and a cloud teacher baseline

## Scope

**Implemented (E4-01..10):** Dataset governance foundation + local baseline
measurement. These are useful independently and do not require cloud provider
integration.

**Blocked (E4-11 onward):** Cloud teacher baseline measurement and bounded
training experiment require provider integration (explicitly out of scope per
AGENTS.md: "do not add new model providers or external executor integrations").
The dataset governance framework is built so that E4-11+ can be added once
a cloud provider adapter is available outside the core.

## Contract

### Dataset example (E4-04)

`DatasetExample` — a single training example derived from a verified skill trace:
- `trace_id` — links back to the source trace
- `skill_name`, `skill_version` — skill provenance
- `input_prompt`, `target_completion` — the example pair
- `source_files`, `capabilities` — context
- `redacted: bool` — always True (E4-06)

### Deterministic filter (E4-05)

`export_trace_to_example(trace)` — only exports traces where `is_success=True`.
Raises `ValueError` for failed traces. Every exported example has `redacted=True`.

### Redaction (E4-06)

`redact_payload()` (E3-10) is applied to both `input_prompt` and
`target_completion`. Credentials, private paths, and raw conversation are
redacted before example persistence.

### Dataset splits (E4-08)

`build_dataset()` splits examples deterministically using SHA-256 of
`trace_id` mod 100: 70% train, 15% validation, 15% test.
Reproducible across runs.

### Dataset manifest (E4-09)

`DatasetManifest` — frozen descriptor with:
- `content_hash` — SHA-256 of sorted examples (immutability proof)
- `version` — semantic version
- `consent_statement` — explicit consent text
- `retention_days`, `deletion_policy` — data lifecycle
- `source_trace_ids`, `excluded_trace_ids` — lineage
- `base_model`, `environment` — reproducibility

### Local baseline (E4-10)

`measure_local_baseline()` — measures a non-trained local model using
existing `PawRuntime._execute_unit`. Returns accuracy, latency, token usage.

## Acceptance

- Dataset can only be built from successful reviewed traces
- All examples are redacted before storage
- Dataset hash is reproducible and frozen
- Local baseline measurement works without training
- Cloud teacher baseline is documented as blocked (out of scope)
