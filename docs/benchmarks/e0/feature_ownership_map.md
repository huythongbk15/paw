# PAW Feature Ownership Map (E0-24)

This document is the **E0-24 deliverable**. It maps every
item in the E0-23 inventory to one engineering scenario
and one canonical owner. An item that cannot be mapped is
flagged for the E0-26 removal-candidate list.

## Mapping rules

A mapping is **complete** when an item has:

1. A scenario from the E0 product outcome tests
   (repository understanding, defect localization,
   cross-module change, refactoring, architecture
   decision, interrupted recovery, privacy-negative,
   insufficient context).
2. A canonical owner: the single source file that
   owns the implementation; no other module may
   re-implement the same behavior.
3. A status: `core` (keep), `compatibility-only` (keep
   with documented removal date), or `quarantine`
   (deferred until E0-25 marks it explicitly).

## CLI commands

| Handle | Command | Scenario | Owner | Status |
|---|---|---|---|---|
| `CLI-01` | `paw doctor` | E0 product outcome: repository understanding (project is healthy enough to reason about). | `src/paw/cli/__init__.py:doctor` | `core` |
| `CLI-02` | `paw init` | E0 product outcome: cross-module change (the user needs a working DB to do anything else). | `src/paw/cli/__init__.py:init` | `core` |
| `CLI-03` | `paw config` | E0 product outcome: insufficient context (show what the runtime is configured with). | `src/paw/cli/__init__.py:config` | `core` |
| `CLI-04` | `paw profiles` | E0 product outcome: architecture decision (the four profiles are documented engineering choices). | `src/paw/cli/__init__.py:profiles` | `core` |
| `CLI-05` | `paw chat` | E0 product outcome: repository understanding, defect localization, refactoring — the chat session is the user-visible entry point that drives every other scenario. | `src/paw/application/chat.py:ChatService` | `core` |

## Library API — `paw.core`

| Handle | Symbol | Scenario | Owner | Status |
|---|---|---|---|---|
| `API-01` | `AutonomyDecision` | Every scenario: the autonomy controller emits decisions, and the contract is what tests assert. | `src/paw/core/models.py:AutonomyDecision` | `core` |
| `API-02` | `Capability` | privacy_negative + interrupted_recovery: the capability string is what the policy gate matches. | `src/paw/core/models.py:Capability` | `core` |
| `API-03` | `ExecutionObservation` | Every scenario: the observation is the artifact the runner scores. | `src/paw/core/models.py:ExecutionObservation` | `core` |
| `API-04` | `PawRuntime` | Every scenario: the runtime loop is the integration authority. | `src/paw/core/runtime.py:PawRuntime` | `core` |
| `API-05` | `PolicyDecision` | privacy_negative + insufficient_context: the verdict tells the runner whether an action was allowed. | `src/paw/core/models.py:PolicyDecision` | `core` |
| `API-06` | `ProposedAction` | Every scenario: the proposal is the unit the gate consumes. | `src/paw/core/models.py:ProposedAction` | `core` |
| `API-07` | `ResourceUsage` | E0-05 measurement: tokens, latency, cost, and human-intervention counts are computed from this. | `src/paw/core/models.py:ResourceUsage` | `core` |
| `API-08` | `RuntimeOutcome` | Every scenario: the outcome tells the caller whether to continue, ask, or stop. | `src/paw/core/runtime.py:RuntimeOutcome` | `core` |
| `API-09` | `StopReason` | Every scenario: the reason explains why the loop stopped. | `src/paw/core/models.py:StopReason` | `core` |
| `API-10` | `TaskResult` | Every scenario: the result carries the final artifact and the terminal status. | `src/paw/core/models.py:TaskResult` | `core` |
| `API-11` | `TaskStatus` | Every scenario: the status is the terminal-state enum the E0-04 outcome rules consult. | `src/paw/core/models.py:TaskStatus` | `core` |

## Library API — `paw.bench`

| Handle | Symbol | Scenario | Owner | Status |
|---|---|---|---|---|
| `BENCH-01..18` | All 18 symbols | All eight E0 minimum scenarios: the contract is what the runner consumes. | `src/paw/bench/__init__.py` + `src/paw/bench/runner.py` | `core` |

## Adapters

| Handle | Adapter | Scenario | Owner | Status |
|---|---|---|---|---|
| `ADP-01` | `OllamaProvider` | All scenarios that need a model: a local provider is required for the local-first / privacy-negative / workspace cases. | `src/paw/providers/ollama/provider.py` | `core` |
| `ADP-02` | `LocalFilesystemExecutor` | refactoring, cross_module_change, defect_localization: the executor is the only way to commit a workspace edit behind policy. | `src/paw/executors/filesystem.py` | `core` |
| `ADP-03` | `ChatService` | All scenarios via `CLI-05`: the composition root that wires the runtime into the chat loop. | `src/paw/application/chat.py` | `core` |

## Skills, Memory, Knowledge

| Handle | Symbol | Scenario | Owner | Status |
|---|---|---|---|---|
| `KNO-01` | `KnowledgeIndex` | defect_localization, architecture_decision, refactoring: the ContextCompiler's knowledge path supplies the case material the runtime reasons about. | `src/paw/knowledge/index.py` | `core` |
| `KNO-02` | `normalize_knowledge_result` | All scenarios (the result contract): the E0-04 outcome rules read the normalized result. | `src/paw/knowledge/normalization.py` | `core` |
| `MEM-01` | `AdvancedMemoryRetriever` | All scenarios that need memory: the ContextCompiler's memory path. | `src/paw/core/memory.py` | `core` |
| `SKI-01` | `SkillFabric` | All scenarios that need a skill: the sole registry. | `src/paw/core/skills.py` | `core` |
| `SKI-02` | `AdvancedSkillSelector` | All scenarios (hybrid selection): the lexical + semantic selector. | `src/paw/core/semantic.py` | `core` |

## Items without a scenario (none)

Every item in the E0-23 inventory maps to at least one
E0 scenario. **No item is quarantine-flagged at E0-24.**

This is intentional: the E0-24 pass checks that every
public surface the user sees is justified by an
engineering outcome. The E0-25 pass then marks each
item as `core` (keep and grow), `compatibility-only`
(keep with a removal date), or `quarantine` (defer and
revisit). The absence of a `quarantine` row here means
"the public surface is currently justified; the E0-25
reviewer may still promote any item to `quarantine` if
it finds a reason".

## Items without a canonical owner (none)

Every item points to exactly one source file. If two
items had shared an owner, the E0-24 pass would have
split them; the absence of a "shared" note means the
ownership map is already 1:1.

## Phase 4 sync contract

This document is the **source of truth** for E0-24. The
E0-25 disposition pass references each item by its
handle and may change only the `Status` column; the
`Scenario` and `Owner` columns are stable until the
next inventory.
