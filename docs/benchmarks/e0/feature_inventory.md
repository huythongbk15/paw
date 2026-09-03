# PAW Feature Inventory (E0-23)

This document is the **E0-23 deliverable**. It enumerates
every public surface in the PAW repository and assigns
each item a unique handle for the E0-24..26 disposition
pass.

## Inventory scope

The inventory covers:

1. **CLI commands** — every `@app.command()` in
   `src/paw/cli/__init__.py`.
2. **Library API entry points** — every symbol re-exported
   from a top-level module (`src/paw/__init__.py`,
   `src/paw/bench/__init__.py`, `src/paw/core/__init__.py`,
   `src/paw/cli/__init__.py`).
3. **Adapters** — every provider and executor currently
   registered (Ollama provider, local filesystem executor).
4. **Knowledge / memory / skills** — every public factory
   in `paw.core.skills`, `paw.core.memory`, `paw.knowledge`.

The inventory is **read-only**: this document does not
mark items for quarantine or removal (that is E0-24..26).
A reviewer can use the handles in this document to
reference the same item from any future doc.

## CLI commands

Five commands, registered through Typer in
`src/paw/cli/__init__.py`.

| Handle | Command | Purpose | Source |
|---|---|---|---|
| `CLI-01` | `paw doctor` | Run local environment health checks (Python, deps, model). | `src/paw/cli/__init__.py` |
| `CLI-02` | `paw init` | Initialize the local paw.db and skills registry. | `src/paw/cli/__init__.py` |
| `CLI-03` | `paw config` | Show or update configuration values. | `src/paw/cli/__init__.py` |
| `CLI-04` | `paw profiles` | List or show execution profiles. | `src/paw/cli/__init__.py` |
| `CLI-05` | `paw chat` | Interactive chat session with the runtime loop. | `src/paw/cli/__init__.py` |

## Library API — `paw.core`

Eleven runtime-contract symbols, frozen by the E0-23a
guard test (`test_paw_core_public_surface_unchanged_after_e0_02`
and its siblings).

| Handle | Symbol | Type | Source |
|---|---|---|---|
| `API-01` | `AutonomyDecision` | enum (StrEnum) | `src/paw/core/models.py` |
| `API-02` | `Capability` | enum (StrEnum) | `src/paw/core/models.py` |
| `API-03` | `ExecutionObservation` | dataclass | `src/paw/core/models.py` |
| `API-04` | `PawRuntime` | class | `src/paw/core/runtime.py` |
| `API-05` | `PolicyDecision` | enum (StrEnum) | `src/paw/core/models.py` |
| `API-06` | `ProposedAction` | dataclass | `src/paw/core/models.py` |
| `API-07` | `ResourceUsage` | dataclass | `src/paw/core/models.py` |
| `API-08` | `RuntimeOutcome` | dataclass | `src/paw/core/runtime.py` |
| `API-09` | `StopReason` | enum (StrEnum) | `src/paw/core/models.py` |
| `API-10` | `TaskResult` | dataclass | `src/paw/core/models.py` |
| `API-11` | `TaskStatus` | enum (StrEnum) | `src/paw/core/models.py` |

## Library API — `paw.bench`

Twenty-three symbols exported from the E0 benchmark
contract. The E0-23a guard test asserts this set is a
superset of the eleven `paw.core` symbols; the twelve
additional symbols here are benchmark-only and not part
of the runtime surface.

| Handle | Symbol | Source |
|---|---|---|
| `BENCH-01` | `CASE_MANIFEST_SCHEMA_VERSION` | `src/paw/bench/__init__.py` |
| `BENCH-02` | `CaseCategory` | `src/paw/bench/__init__.py` |
| `BENCH-03` | `CaseManifest` | `src/paw/bench/__init__.py` |
| `BENCH-04` | `CaseRunResult` | `src/paw/bench/runner.py` |
| `BENCH-05` | `ExpectedEvidence` | `src/paw/bench/__init__.py` |
| `BENCH-06` | `FixtureRef` | `src/paw/bench/__init__.py` |
| `BENCH-07` | `PrivacyClass` | `src/paw/bench/__init__.py` |
| `BENCH-08` | `RunRow` | `src/paw/bench/runner.py` |
| `BENCH-09` | `RunnerError` | `src/paw/bench/runner.py` |
| `BENCH-10` | `SchemaError` | `src/paw/bench/__init__.py` |
| `BENCH-11` | `case_manifest_from_dict` | `src/paw/bench/__init__.py` |
| `BENCH-12` | `case_manifest_to_dict` | `src/paw/bench/__init__.py` |
| `BENCH-13` | `is_valid_case_manifest` | `src/paw/bench/__init__.py` |
| `BENCH-14` | `load_case` | `src/paw/bench/runner.py` |
| `BENCH-15` | `run_case` | `src/paw/bench/runner.py` |
| `BENCH-16` | `run_case_file` | `src/paw/bench/runner.py` |
| `BENCH-17` | `validate_case_manifest` | `src/paw/bench/__init__.py` |
| `BENCH-18` | `write_runs_jsonl` | `src/paw/bench/runner.py` |

## Adapters

Three adapter categories, each with a unique handle.

| Handle | Adapter | Source | Notes |
|---|---|---|---|
| `ADP-01` | `OllamaProvider` | `src/paw/providers/ollama/provider.py` | The only model provider adapter; required for the local-first provider requirement. |
| `ADP-02` | `LocalFilesystemExecutor` | `src/paw/executors/filesystem.py` | The only built-in executor; required for the S4 "real side effect behind policy" scenario. |
| `ADP-03` | `ChatService` | `src/paw/application/chat.py` | The composition root that wires the runtime loop into the CLI; required for `paw chat`. |

## Skills, Memory, Knowledge

Public factories and registries.

| Handle | Symbol | Source | Notes |
|---|---|---|---|
| `KNO-01` | `KnowledgeIndex` | `src/paw/knowledge/index.py` | Required for the ContextCompiler's knowledge path. |
| `KNO-02` | `normalize_knowledge_result` | `src/paw/knowledge/normalization.py` | Required for the E0-04 result contract; no second path. |
| `MEM-01` | `AdvancedMemoryRetriever` | `src/paw/core/memory.py` | Required for the ContextCompiler's memory path. |
| `SKI-01` | `SkillFabric` | `src/paw/core/skills.py` | Sole skill registry; E0-23a-equivalent guard for skills. |
| `SKI-02` | `AdvancedSkillSelector` | `src/paw/core/semantic.py` | Required for hybrid lexical + semantic skill selection. |

## Internal-only (not part of the inventory)

The following modules are *not* in the public surface and
do not receive a handle. A reviewer who needs to
reference one of them should use the file path, not a
handle.

- `src/paw/core/storage.py` — internal DB proxy.
- `src/paw/core/ledger.py` — internal ledger writer.
- `src/paw/core/checkpoint.py` — internal checkpoint store.
- `src/paw/core/autonomy.py` — internal autonomy controller.
- `src/paw/core/policy.py` — internal policy guard.
- `src/paw/core/runtime_persistence.py` — internal atomic
  boundary coordinator.
- `src/paw/core/context_compiler.py` — internal context
  builder.
- `src/paw/core/decomposition.py` — internal planner
  helper.
- `src/paw/core/execution_profile.py` — internal profile
  registry.
- `src/paw/core/identity/` — internal preference record.
- `src/paw/core/detectors.py` — internal repetition / stall
  / progress detectors.
- `src/paw/core/executor.py` — internal capability router.
- `src/paw/core/model_router.py` — internal model router.
- `src/paw/core/task.py` — internal task manager.
- `src/paw/core/session.py` — internal session manager.
- `src/paw/core/approval.py` — internal approval store.
- `src/paw/core/task_scheduler.py` — internal DAG scheduler.
- `src/paw/core/models.py` — internal model definitions
  (only the eleven re-exports via `paw.core` are public).
- `src/paw/core/selector.py` — internal skill selector
  compatibility shim.
- `src/paw/core/embeddings.py` — internal embedding
  provider.
- `src/paw/utils/`, `src/paw/memory/`, `src/paw/models/`,
  `src/paw/skills/`, `src/paw/storage/` — all internal
  re-exports / shims.

## How to use the inventory

A reviewer writing an E0-25 disposition table can
reference any item by its handle (e.g. `CLI-05` for
`paw chat`) and a future doc (e.g. the E0-25 disposition
table) does not need to re-enumerate the surface. The
inventory is the single source of truth for "what does
PAW expose today".
