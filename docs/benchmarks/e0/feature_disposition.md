# PAW Feature Disposition (E0-25)

This document is the **E0-25 deliverable**. It assigns
each item in the E0-23 inventory one of three
dispositions and records the rationale. An item is
`core` (keep and grow), `compatibility-only` (keep with
a removal date), or `quarantine` (defer with a re-review
date).

## Disposition rules

The reviewer applies the following rules in order:

1. **`core`** if the item is required by at least one
   E0 minimum scenario and removing it would break the
   `paw.core` 11-symbol contract or the E0 contract.
2. **`compatibility-only`** if the item is required by an
   external user (a library, a CLI script) that we have
   committed to support for a named release, but the
   item is on the removal list for a future major
   version. The removal date is recorded.
3. **`quarantine`** if the item is not required by any
   E0 scenario, is not used by any external caller, and
   has not been touched in the last 30 days. The
   re-review date is recorded.

If none of the rules apply, the item is `core` (the
default for a project that is being stabilized).

## CLI commands

| Handle | Disposition | Rationale | Removal / re-review |
|---|---|---|---|
| `CLI-01` `paw doctor` | `core` | Required by the "project is healthy" scenario; removing it removes the only way to detect a broken local install. | — |
| `CLI-02` `paw init` | `core` | Required by the "user needs a working DB" scenario; the only command that creates the durable state. | — |
| `CLI-03` `paw config` | `core` | Required by the "show what the runtime is configured with" scenario. | — |
| `CLI-04` `paw profiles` | `core` | Required by the "architecture decision" scenario; profiles are the four canonical engineering choices. | — |
| `CLI-05` `paw chat` | `core` | Required by every user-visible scenario; the integration entry point. | — |

## Library API — `paw.core`

Every symbol is `core`. The 11-symbol surface is frozen
by the E0-23a contract test; removing any of them
breaks the runtime contract and is outside the scope
of the E0 track.

| Handle | Symbol | Disposition | Rationale |
|---|---|---|---|
| `API-01..11` | All 11 | `core` | Frozen runtime contract. |

## Library API — `paw.bench`

Every symbol is `core` for the E0 track. The benchmark
contract is new (added in this track) and every symbol
is required by the E0-08..16 deliverable sequence.

| Handle | Symbol | Disposition | Rationale |
|---|---|---|---|
| `BENCH-01..18` | All 18 | `core` | New contract, every symbol required by the E0 deliverables. |

## Adapters

| Handle | Adapter | Disposition | Rationale | Removal / re-review |
|---|---|---|---|---|
| `ADP-01` `OllamaProvider` | `core` | The only model provider; required for the local-first + privacy-negative scenarios. | — |
| `ADP-02` `LocalFilesystemExecutor` | `core` | The only executor; required for the S4 "real side effect behind policy" scenario. | — |
| `ADP-03` `ChatService` | `core` | The composition root for `CLI-05`. | — |

## Skills, Memory, Knowledge

| Handle | Symbol | Disposition | Rationale | Removal / re-review |
|---|---|---|---|---|
| `KNO-01` `KnowledgeIndex` | `core` | Sole owner of the knowledge path; no second registry. | — |
| `KNO-02` `normalize_knowledge_result` | `core` | E0-04 result contract boundary; no second path. | — |
| `MEM-01` `AdvancedMemoryRetriever` | `core` | Sole owner of the memory path. | — |
| `SKI-01` `SkillFabric` | `core` | Sole skill registry. | — |
| `SKI-02` `AdvancedSkillSelector` | `core` | Sole hybrid selector (lexical + semantic). | — |

## Items marked `compatibility-only` (none)

No item is `compatibility-only`. The project has no
external library consumers in this version; the
removal-list-for-future-major-version rule does not
apply.

## Items marked `quarantine` (none)

No item is `quarantine`. Every public surface maps to at
least one E0 scenario per the E0-24 ownership map, and
removing any of them would break the contract.

This is the **right outcome for a pre-BETA project**:
there is no public surface to remove. The E0-26 removal-
candidate review is therefore a no-op; the E0-25
disposition pass is complete.

## Phase 4 sync contract

This document is the **source of truth** for E0-25. The
E0-26 removal-candidate review references each item by
its handle; if E0-26 promotes any item to `quarantine`,
it must update the `Disposition` column here first, and
the change is recorded in the same commit.

A future post-BETA review may add `compatibility-only`
items when the project has external consumers; the
table format above is forward-compatible with that
addition.
