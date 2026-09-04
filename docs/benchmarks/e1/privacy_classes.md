# E1-03 Privacy Classes and Remote-Disclosure Defaults

This document is the **E1-03 deliverable**. It defines the
project-source privacy class, the remote-disclosure
default per class, and the helper the runtime consults
before sending context to a provider.

## Why this contract exists

The E1 roadmap acceptance criteria (ROADMAP.md) require
that:

- every byte of remote project context is attributable
  to an approved context manifest;
- minimum cloud disclosure: a remote inference receives
  only an approved, budgeted context manifest with
  provenance; PAW never sends an implicit full workspace
  or raw activity history.

The existing `paw.bench.PrivacyClass` (added in E0-02)
covers *benchmark case* classification. E1-03 extends
the same concept to the runtime: every
`KnowledgeSource` row and every `MemoryRecord` row
carries a `privacy_class`; the runtime consults a
single remote-disclosure table before building a
context manifest; the policy gate is the *action*
authority and stays separate.

## Canonical location

`PrivacyClass` is the single canonical owner of the
privacy taxonomy. E1-03 promotes it from
`paw.bench.PrivacyClass` to `paw.core.privacy.PrivacyClass`
so the runtime can import it without going through the
benchmark module. `paw.bench` re-exports the same enum
for backward compatibility with the E0-02 contract.

The four levels are unchanged:

| Value | Meaning |
|---|---|
| `public` | May be sent to any provider. |
| `internal` | May be sent to approved cloud (or local). |
| `workspace` | Workspace only; no remote. |
| `secret` | Never sent off-box; on-box use only. |

## Remote-disclosure defaults

The default per class is a single frozen table in
`paw.core.privacy`:

| `PrivacyClass` | `local` | `cloud_approved` | `cloud_unapproved` |
|---|---|---|---|
| `public` | ✅ | ✅ | ✅ |
| `internal` | ✅ | ✅ | ❌ |
| `workspace` | ✅ | ❌ | ❌ |
| `secret` | ✅ (on-box) | ❌ | ❌ |

The `local` column means the provider runs on the
user's machine (the existing `ModelManifest.local`
predicate covers this: `provider in
{"local","offline","vllm","ollama"}`). The
`cloud_approved` set is the closed list of cloud
providers the product charter admits — by default the
empty set, because the E0 acceptance criteria defer
the cloud baseline. The `cloud_unapproved` set is
everything else. The table is exported as
`REMOTE_DISCLOSURE_DEFAULTS` (a `Mapping` whose values
are `frozenset[str]`); the contract test pins both the
keys and the values.

The helper the runtime calls before building a context
manifest is:

```python
from paw.core.privacy import can_disclose_to_provider

if not can_disclose_to_provider(privacy_class, provider_kind):
    raise PrivacyDisclosureError(...)
```

`provider_kind` is one of `"local"`, `"cloud_approved"`,
`"cloud_unapproved"`. The helper is a thin wrapper over
the table; the table is the source of truth.

## New fields E1-03 adds

The owner per the E1-01 ownership audit:

- `KnowledgeSource` (E1-01 owner: `KnowledgeSource`)
  gains one field:
  - `privacy_class: PrivacyClass` — default
    `PrivacyClass.INTERNAL`. This means a freshly
    registered source is conservatively assumed to be
    workspace-internal; the caller must opt up to
    `public` if the source is meant to be sharable.
- `MemoryRecord` (E1-01 owner: `MemoryStore`) gains one
  field:
  - `privacy_class: PrivacyClass` — default
    `PrivacyClass.INTERNAL`. Same conservative default;
    a memory record that the user has reviewed and
    confirmed is shareable (e.g. an open-source
    licensing fact) can be promoted to `public`.

The defaults are intentionally not the *most
restrictive* class. The product is local-first and the
E1-26 negative-control case proves the runtime refuses
to send `secret` content off-box; a default of
`INTERNAL` matches the existing `paw.bench` case-manifest
default and keeps the existing call sites working.

## SQL migration (additive only)

Two new columns, one on each table. Same additive
pattern as E1-02 (guarded by `PRAGMA table_info`):

```sql
ALTER TABLE knowledge_sources ADD COLUMN privacy_class TEXT NOT NULL DEFAULT 'internal';
ALTER TABLE memory_records  ADD COLUMN privacy_class TEXT NOT NULL DEFAULT 'internal';
```

`KnowledgeSource.from_row` parses the column with
`PrivacyClass(row["privacy_class"])` and falls back to
`PrivacyClass.INTERNAL` when the row pre-dates the
migration (defense-in-depth: the column never *should*
be missing because of the DEFAULT, but a stale SQLite
file from before this commit should still load).

## Boundary exposure (E0-40 + E1-17)

The E0-40 runtime-driven runner and the E1-17 per-item
manifest are the consumers of this contract. The
boundary that exposes the new fields is the existing
`KnowledgeSource.to_dict()` and `MemoryRecord.to_dict()`:
every field is included in the dict, and the contract
test asserts that.

The helper `can_disclose_to_provider` is the
context-compiler hook: when the compiler assembles a
manifest for a provider, it filters the candidates
according to the helper. The runtime-driven runner
verifies the filtered manifest against the case
manifest's `privacy_class`.

## Phase 4 sync contract

This document is the **source of truth** for E1-03.
The companion contract test
`tests/test_e1_03_privacy_contract.py` enforces:

- `PrivacyClass` is importable from `paw.core.privacy`
  and re-exported from `paw.bench`;
- the `REMOTE_DISCLOSURE_DEFAULTS` table is complete
  (every `PrivacyClass` value is a key) and frozen;
- `can_disclose_to_provider` returns the right answer
  for every (class, provider_kind) combination;
- the new field exists on `KnowledgeSource` and
  `MemoryRecord` with the documented default;
- the SQL migration is additive (no `DROP`, no row
  rewrite) and the new column has the documented
  default;
- the E1-01 ownership audit + the E1-02 spec doc
  list the new field on `KnowledgeSource`;
- the E1-01 ownership audit lists the new field on
  `MemoryRecord` (the audit is updated from 13 to 14
  fields).

A later E1 item that adds another privacy class must
update the enum, the disclosure table, the contract
test (`tests/test_e1_03_privacy_contract.py`), and the
ownership audit (`docs/benchmarks/e1/ownership_audit.md`)
in the same change.