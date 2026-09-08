# E2-01 — Model Router + Executor + Provider Protocol audit

**Date**: 2026-09-07
**HEAD**: `30ed2ac`
**Scope**: `src/paw/core/model_router.py`, `src/paw/core/model_executor.py`,
`src/paw/providers/__init__.py` (ModelProvider Protocol).
**Status**: READ-ONLY audit. No code changes; this document is the
input for any subsequent E2-02..E2-50 work that touches the router.

---

## 1. Public surface

### 1.1 Types (`src/paw/core/models.py`)

| Type | Fields | Notes |
|------|--------|-------|
| `ModelManifest` | name, provider, roles, model_capabilities, cost, features, max_context_tokens, latency_tier, enabled | Immutable Pydantic model. Carries everything the router needs to score. |
| `ModelSelection` | model_name, model_manifest, role, reason, fallback_chain, score | Pydantic. `model_manifest` is optional; on `route()` failure the selection may have empty `model_name`. |

### 1.2 Router surface (`src/paw/core/model_router.py`)

| Symbol | Lines | Purpose |
|--------|-------|---------|
| `ModelScore` (dataclass) | 36-58 | Per-dimension score + composite |
| `ModelScorer` (class) | 60-256 | 5 dimensions: capability / complexity / privacy / cost / latency + composite |
| `ModelRegistry` (class) | 257-454 | In-memory model store: `register` / `unregister` / `get` / `list` / `list_by_role` / `list_enabled` / `find_for_role` / `find_by_capability` / `find_best_for_task` / `fallback_chain` / `load_from_db` / `register_defaults` |
| `ProviderRegistry` (class) | 459-503 | Aggregates `ModelProvider` instances; `register` / `get` / `list` / `initialize_all` / `discover_models` |
| `ModelRouter` (class) | 506-869 | `route` / `route_with_explain` / `score_model_for_task` / `_available_provider_names` / `_filter_for_availability` / `persist_selection` |
| `ModelSelection` constructor | reused from `models.py` | Used as the return type of `route()` and `route_with_explain()` |

### 1.3 Executor surface (`src/paw/core/model_executor.py`)

| Symbol | Lines | Purpose |
|--------|-------|---------|
| `LocalModelExecutor` (class) | 27-67 | Offline stand-in. Echoes the last user turn. NOT a `ModelProvider`. |
| `ModelExecutor` (class) | 71-166 | `register` / `get_provider` / `initialize_all` / `shutdown_all` / `_resolve_provider` / `complete` / `stream` |

### 1.4 Provider Protocol (`src/paw/providers/__init__.py`)

| Symbol | Lines | Members |
|--------|-------|---------|
| `Provider` (Protocol) | 26-30 | `name`, `version`, `initialize()`, `shutdown()` |
| `ModelProvider` (Protocol, `@runtime_checkable`) | 36-49 | `name`, `version`, `available` (property), `list_models()`, `get_model(name)`, `discover_manifests()`, `complete(request)`, `stream(request)` |
| `SkillProvider`, `MemoryProvider`, `PersonaProvider` | 52-74 | Out of scope for E2-01 |

---

## 2. Callers of the router / executor

### 2.1 Production callers

| Caller | File:Line | Method | Inputs | Output |
|--------|-----------|--------|--------|--------|
| `ChatService` (init) | `src/paw/application/chat.py:253` | `ModelRouter(providers=...)` | ProviderRegistry (or list) | Router instance |
| `ChatService` (init) | `src/paw/application/chat.py:254` | `ModelExecutor(...)` | ProviderRegistry | Executor instance |
| `ChatService` (shutdown) | `src/paw/application/chat.py:283` | `await self._model_executor.shutdown_all()` | — | — |
| `PawRuntime._execute_action` | `src/paw/core/runtime.py:1635` | `await self.model_router.route(...)` | `task_id, goal, role, context_size, complexity, privacy_required, execution_profile, preferred_provider` | `ModelSelection` |
| `PawRuntime._execute_action` | `src/paw/core/runtime.py:1685, 1690` | `await self.model_executor.complete(selection, messages)` | selection, messages list | result dict |

### 2.2 Test callers (sample)

| Test | What it does |
|------|--------------|
| `tests/test_phase15_model_router_v2.py` | Provider protocol conformance, provider-aware routing |
| `tests/test_phase19_model_executor.py` | Shared `ProviderRegistry` between router and executor; `local` fallback; `LocalModelExecutor` does not enter the registry |
| `tests/test_p1_router_filter_availability.py` | Role filtering + descending score in `_filter_for_availability` (Phase 21 patch) |
| `tests/test_runtime_privacy_proof.py` | Hard-gate proof: SECRET + remote yields 0 provider + 0 executor calls |
| `tests/test_phase20_agent_runtime_loop.py` | Full agent loop wiring |

### 2.3 Internal call sites

| Caller | Method | Notes |
|--------|--------|-------|
| `ModelRouter.route` | `self._filter_for_availability` | Drops candidates whose provider is unavailable; falls back to local in score order. |
| `ModelRouter.route` | `self.registry.find_best_for_task` | Filters by role + enabled, sorts by score desc. |
| `ModelRouter.route` | `self.registry.register_defaults` + `self._provider_registry.discover_models` | Lazy one-shot bootstrap on first call. |
| `ModelExecutor.complete` | `self._resolve_provider` | Looks up provider by `selection.model_manifest.provider`; falls back to `LocalModelExecutor` if not registered. |

---

## 3. Inputs / outputs contract

### 3.1 `ModelRouter.route` signature

```python
async def route(
    self,
    task_id: str,                                   # opaque routing key (used in ledger + persist_selection)
    goal: str,                                      # natural-language task description (NOT used in scoring; only logged)
    role: str = "fast",                             # required role (one of ModelManifest.roles)
    context_size: int = 0,                          # prompt token estimate
    complexity: str = "medium",                      # "low" | "medium" | "high"
    privacy_required: bool = False,                 # when True, _score_privacy scores local > local-only-cloud
    prefer_cheap: bool = True,                      # cost dimension weight
    execution_profile: ExecutionProfile | None = None,  # optional overrides
    preferred_provider: str | None = None,          # if set, post-filter to that provider
) -> ModelSelection
```

Returns a `ModelSelection` (Pydantic) with `model_manifest`, `role`, `reason`,
`fallback_chain`, `score`. On failure: `model_name=""`, `reason="No model
available for role: <role>"`.

### 3.2 `ModelRouter.route_with_explain` signature

Same as `route`, but returns `(ModelSelection, list[ModelScore])` where
the second element is the per-candidate score list (for ledger + UI).

### 3.3 `ModelRouter.score_model_for_task` signature

```python
def score_model_for_task(
    self,
    manifest: ModelManifest,
    role: str = "fast",
    context_size: int = 0,
    complexity: str = "medium",
    privacy_required: bool = False,
    prefer_cheap: bool = True,
) -> ModelScore
```

Canonical entry point used by both `route()` and `_filter_for_availability()`.
Score is the composite `(0..1]`. `ModelScore.reason` is a pipe-separated
string of per-dimension values.

### 3.4 `ModelExecutor.complete` signature

```python
async def complete(
    self, selection: ModelSelection, messages: list[dict[str, Any]], **kwargs
) -> dict[str, Any]
```

Looks up `selection.model_manifest.provider` in the shared
`ProviderRegistry`; if not registered, falls back to
`LocalModelExecutor`. Returns whatever the provider's `complete()`
returns (provider-defined schema).

### 3.5 `ProviderRegistry.discover_models`

```python
async def discover_models(self, registry: ModelRegistry) -> int
```

Iterates registered providers; for each, if `provider.available` is
truthy, calls `await provider.discover_manifests()` and registers
the returned manifests. Returns the count registered. Skips
unavailable providers (graceful degradation).

---

## 4. Behavioural invariants

These are **the contract** for the router/executor; any E2-02+ work
must preserve them.

### 4.1 Router invariants

1. **Single source of truth for providers**: the router and the
   executor share the same `ProviderRegistry` instance (Phase 19
   hardening). `_provider_registry` on the router is the only
   registry consulted.
2. **Provider-availability gating**: models whose provider reports
   `available == False` are excluded before scoring in
   `_filter_for_availability` (Phase 15).
3. **Local fallback**: when the upstream `find_best_for_task`
   returns nothing reachable, the local-fallback branch
   re-scores local models via the canonical `score_model_for_task`
   entry point, filters by `m.supports_role(role)`, and sorts by
   `score` descending (Phase 21 fix).
4. **Role filtering**: every candidate in the local-fallback
   result passes `m.supports_role(role)`. Wrong-role models cannot
   leak through (Phase 21 contract test).
5. **Sorted output**: the local-fallback result is in descending
   score order. `sorted(reverse=True)` produces descending order
   because `ContextCandidate.__lt__` is correct (Phase 21 fix).
6. **Lazy bootstrap**: `register_defaults` + `discover_models` run
   on the first `route()` call, not in `__init__`. This keeps
   the constructor synchronous and side-effect-free.
7. **Preferred-model precedence**: when `execution_profile.preferred_models`
   is non-empty AND `preferred` model supports the role AND
   `preferred.provider` is available, the preferred model wins.
   Falls through to scored path otherwise.
8. **Preferred-provider post-filter**: when `preferred_provider`
   is set (and not in the execution-profile path), the scored
   list is post-filtered to that provider; if empty, falls through.
9. **Local-as-last-resort**: after the upstream filter, the `local`
   stand-in is moved to the END of the candidate list — it is the
   last-resort fallback, never preferred over a real provider.
10. **Selection persistence**: every successful `route()` writes a
    row to `model_selections` via `persist_selection`. The
    `task_id` is the routing key.
11. **Ledger side effect**: every successful `route()` records a
    `MODEL_SELECTED` event with `stage="execution"`. This is the
    runtime's "executed by" trail.

### 4.2 Executor invariants

1. **Shared registry**: the executor holds a reference to the same
   `ProviderRegistry` as the router (Phase 19). The
   `provider_registry` property exposes the shared instance.
2. **No duplicate providers**: the executor does NOT keep a
   second `dict` of providers (Phase 19 change; before that it
   did and could desync from the router).
3. **Local fallback isolation**: `LocalModelExecutor` is kept
   OUTSIDE the registry. It is the executor's last-resort
   backend for `provider="local"` selections, not a registered
   model provider.
4. **`_resolve_provider` is the single dispatch point**: every
   call to `complete()` / `stream()` resolves the provider
   through this one function. If the provider is not registered,
   a `provider_not_registered` warning is logged and the
   `LocalModelExecutor` is used.
5. **`messages` is the contract**: `complete()` receives the full
   `messages` list and forwards it verbatim to the provider. The
   previous "prompt-only" mode is gone (Phase 19 fix).

### 4.3 Provider Protocol invariants

1. **`@runtime_checkable`**: `ModelProvider` is runtime-checkable
   so `isinstance(provider, ModelProvider)` works in tests
   (Phase 15).
2. **`available` is a property**: a provider reports liveness via
   the `available` property (not a method). This lets the
   registry do `if not provider.available: continue` cheaply.
3. **Discovery + execution are paired**: every `ModelProvider`
   both `discover_manifests()` (for routing) and `complete()`
   (for execution). The protocol does NOT allow a "discover-only"
   or "execute-only" provider.
4. **No core import**: providers live in `src/paw/providers/`;
   `paw.core` never imports a concrete provider (zero vendor
   lock-in, Phase 11 + Phase 15).

---

## 5. Current limitations and known gaps (for E2-02..E2-50)

These are the items the audit found that any subsequent E2 work
should address. None are blockers for E2-01 itself.

### 5.1 Gaps

1. **Minimum cognitive roles are a pre-gate draft** —
   `core/reasoning_contracts.py` reuses the existing `ModelRole` vocabulary and
   identifies FAST/REASONING/CODING/TOOLS as the minimum engineering roles.
   VISION/EMBEDDING are modalities and FALLBACK is a routing marker. Activation
   waits for E1 `VERIFIED`.
2. **No role/capability eligibility matrix** — still open. E2-05 owns local
   eligibility and explicit OOD conditions.
3. **No novelty / OOD / impact signal** — `route()` consumes `goal`, `context_size`, `complexity`, `privacy_required`, `execution_profile`, `preferred_provider`; none carries a "novelty" or "OOD" signal. E2-04 territory.
4. **No trajectory-aware re-evaluation** — `route()` is a single-shot decision. E2-10 introduces trajectory-aware routing.
5. **No verifier-policy selection** — `route()` always picks the best-scoring model for the role. E2-18 introduces verifier-policy selection.
6. **No retryable / capability-mismatch distinction** — `ModelExecutor.complete()` has no retry logic. E2-17 introduces the retryable-vs-mismatch distinction.
7. **No cost / token ceilings in the router** — `prefer_cheap` boolean is the only cost signal. E2-15 introduces per-role ceilings.
8. **Role output/evidence/uncertainty is a pre-gate draft** — one immutable
   `RoleContract` registry requires evidence/citations for REASONING and CODING,
   records a bounded confidence threshold and a typed low-confidence
   disposition. It is not wired to provider output validation or escalation.
9. **No model-side explainability hook** — `route_with_explain` returns per-candidate score list but `reason`/`fallback_chain` strings are not user-readable beyond raw scores. E2-23 introduces a richer explainability surface.
10. **Embedding remains outside this E2 routing slice** — the optional E1
    embedding re-ranker is separate from Model Router. E2-31 actually owns local
    project reconnaissance before external research; it does not authorize
    embedding-aware routing or another provider capability.

### 5.2 Risk inventory

| Risk | Severity | Where | Mitigation |
|------|----------|-------|------------|
| `sorted(reverse=True)` bug returns | **fixed** | `ContextCandidate.__lt__` | `tests/test_context_compiler_sort.py` (3 tests) |
| Wrong-role model leaks through | **fixed** | `_filter_for_availability` local-fallback | `tests/test_p1_router_filter_availability.py` (9 tests) |
| Hard-gate (privacy) bypassed | **fixed** | `_execute_action` privacy branch | `tests/test_runtime_privacy_proof.py` (7 tests) |
| Provider desync router vs executor | **fixed** | `ModelExecutor.__init__` | `tests/test_phase19_model_executor.py` |
| Cloud provider unreachable | graceful | `_filter_for_availability` + `_resolve_provider` | `tests/test_phase15_model_router_v2.py` |
| Manifest drift (router reads from one DB, executor from another) | **N/A** | single shared `ModelRegistry` (in-memory) | `tests/test_phase19_model_executor.py` |
| `register_defaults` / `discover_models` race on first call | latent | `ModelRouter._providers_discovered` | no test pins this; consider in E2-07 |

---

## 6. Boundary map (for E2-02..E2-50)

```
                       +---------------------+
   chat.py             |     ModelRouter     |      core/runtime.py
   (ChatService)       |   (src/paw/core/     |     (PawRuntime._execute_action)
        |              |    model_router.py)  |              |
        v              +----------+----------+              v
+-----------------+                |                 +-----------------+
| ModelRouter()   | --- shares --->|                 | model_router.    |
| providers=[...]  |                v                 |   route(task_id, |
+-----------------+     +---------------------+       |   goal, role,    |
        |              |   ProviderRegistry   |       |   context_size,  |
        v              |     (model_router)   |       |   complexity,    |
+-----------------+     +----------+----------+       |   privacy,       |
| ModelExecutor() | --- shares --->|                 |   execution_     |
| provider_        |                v                 |   profile,       |
|   registry=...   |     +---------------------+       |   preferred_     |
+-----------------+     |  ModelProvider 1    |       |   provider)      |
                       +---------------------+       +-----------------+
                       |  ModelProvider 2    |                  |
                       +---------------------+                  v
                       |  ModelProvider N    |       +-----------------+
                       +---------------------+       |  ModelExecutor  |
                                                     |  .complete(     |
                                                     |   selection,    |
                                                     |   messages)      |
                                                     +--------+--------+
                                                              |
                                                              v
                                                +---------------------+
                                                | shared              |
                                                | ProviderRegistry    |
                                                |  .get(provider_name)|
                                                +---------+-----------+
                                                          |
                                                          v
                                                     provider.complete(request)
                                                          |
                                            +-------------+-------------+
                                            |                           |
                                            v                           v
                                     Real provider                LocalModelExecutor
                                     (Ollama etc)                (echo / stand-in)
```

**Key boundary**: the shared `ProviderRegistry` is the only
authoritative source of provider instances. Router and executor
both call `provider_registry.get(name)`; the router scores via
`manifest`, the executor executes via `provider`. The
`LocalModelExecutor` is executor-side only and does NOT enter the
registry.

---

## 7. Audit summary

| Item | Value |
|------|-------|
| Lines audited | 1110 (router 869 + executor 166 + providers 75) |
| Public types | 8 (`ModelManifest`, `ModelSelection`, `ModelScore`, `ModelRegistry`, `ProviderRegistry`, `ModelRouter`, `LocalModelExecutor`, `ModelExecutor`) |
| Public Protocol members | 5 (`Provider`) + 7 (`ModelProvider`) |
| Production callers | 3 (`ChatService` init/shutdown, `PawRuntime._execute_action` x2) |
| Internal call sites (router+executor) | 7 |
| Critical invariants | 11 router + 5 executor + 4 protocol |
| Known gaps | 10 (catalogued for E2-02..E2-50) |
| Open risks | 1 latent (race on first call); rest fixed/pinned |

The audited router/executor boundary is usable input to E2, but E2 is currently
blocked because E1 is `PARTIAL`. Isolated E2-02..04 value-contract drafts exist
and have focused tests; they do not make the router trajectory-aware and have no
runtime/persistence/provider authority. After a real-source E1 freeze, the safe
sequence is to re-ratify E2-02..04, define E2-05 eligibility/OOD conditions,
then extend the existing router under E2-06 and add ledger evidence under E2-07.

---

*Audit performed 2026-09-07. No code changes; this document is the
input for E2-02..E2-50.*
