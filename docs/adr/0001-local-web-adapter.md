# ADR 0001 — The local web adapter is a presentation adapter, and its safety comes first

- **Status**: accepted (READY)
- **Date**: 2026-10-21
- **Scope**: B-23..B-26 (the local web surface's decision and safety foundation)
- **Charter basis**: the recorded scope decision of 2026-10-05 in
  `docs/PRODUCT_CHARTER.md` — a single-user, loopback-only, foreground
  HTTP/static presentation adapter over the existing application services.
- **Implements**: `docs/BETA_LIMITATIONS.md` §"HTTP contract for the spike",
  §"Target architecture and cases", and the F04/F05 findings.

## Context

PAW has the pieces of an engineering agent and, since 2026-10-20, a
proved chain: research → choose → change → declared verification, with
a failure and a restart, verified against a real project's own test
suite. What it does not have is a surface a person can use.

The user asked for a web interface. That request is a real product
decision and it was recorded as a scope expansion on 2026-10-05, with
conditions: it expands the client surface, the dependency/packaging
and the threat model; it does not authorize hosted access, tenancy,
provider expansion, a daemon, a second runtime or training.

Three findings from the audit constrain the shape:

- **F04** — provider discovery happened before the gate, so opening a
  session reached a provider. Closed: discovery is now an explicit,
  Policy-admitted operation.
- **F05** — the remote path checked a manifest but sent an independent
  payload. Closed: the payload is bound to the reviewed manifest.
- **F02** — concurrent storage and cancelled streams failed. The
  concurrency question is still open, so writes are serialised
  process-wide.

And one constraint from the charter itself: **PAW does not run shells**.
That is now a mechanically checked invariant
(`tests/test_no_shell_execution_in_runtime.py`), and it shapes this
decision: the web surface cannot shell out to the CLI, and it cannot
spawn a process at all.

## Decision

### 1. The adapter is a projection, not an orchestration authority

```
browser → HTTP security + bounded DTO validation → application services
         → Task + current decision + Plan → Policy once → Autonomy
         → ports → observation → required verification → existing stores
         → read-only redacted projections + event stream
```

The CLI and the TUI reach the same services. The web surface adds no
step, no gate and no store. `paw.core` imports no HTTP type and no
`paw.web` module; that is checked mechanically.

### 2. The safety boundary comes first, and it is transport-agnostic

The controls live in `paw.web.security` as a pure function of the
request facts, so they are provable without a server and the HTTP
framework stays an open decision:

- the bind must be loopback;
- the `Host` allowlist is **exact**;
- the `Origin` is **exact**, and a wildcard CORS is not representable;
- a mutation must present the local CSRF token, compared in constant
  time;
- a mutation must carry an `Origin` (a browser always sends one);
- body, history and stream buffers are bounded;
- no credential travels in a query string;
- writes are serialised **process-wide** — a session lock is not a
  database fix.

### 3. The request key reuses the durable operation identity

No new dedup store. A request key derives an operation identity that
the runtime already records durably, so a retry, a double click and a
reconnect all resolve to the same operation, and the runtime's existing
replay safety decides whether the effect repeats. An in-memory map
cannot claim restart safety, so there isn't one.

### 4. A disconnect is neither a completion nor a cancellation

On reconnect the surface *inspects* the durable task. It never re-runs
an effect and never marks a task complete because the browser went
away. Only a **failed** task may be retried, and only with the **same**
request key.

### 5. No new runtime dependency, and no HTTP handler yet

This packet is the decision and the safety foundation. The HTTP
framework is deliberately not chosen: the boundary is transport-
agnostic, so the choice can be made against a measured requirement
rather than a preference. No runtime dependency is added.

## Alternatives considered

| Option | Why not |
|---|---|
| **Add an HTTP handler now** | The safety controls would be written against a framework's request model, and the B-25 controls would be unproven until the framework landed. The contract's order is explicit: no unsafe execution endpoints before the prior gates. |
| **Shell out to the CLI** | Forbidden by the charter, and now a mechanically checked invariant. It would also bypass the gate. |
| **A new web-side store for request keys** | The contract says to reuse the durable operation identity. A second store would be a parallel store, and it would need its own crash/retry proof. |
| **Per-session write locks** | "Session locks alone are not a database fix." The admission is process-wide. |
| **A wildcard CORS with credentials** | A wildcard origin with credentials is refused by browsers anyway, and it would defeat the Origin check. The allowlist is exact and closed. |
| **Requiring an `Origin` on every request** | A same-origin GET carries no `Origin`; requiring one would break the browser without adding protection. It is required for mutations, where a browser always sends it. |

## Consequences

**Good.**

- The controls are provable now, without a server, and the fail-positive
  discipline applies to them like any other change.
- The transport stays open: the boundary does not leak a framework's
  request model into the decisions.
- The web surface cannot become a second runtime: it has no store, no
  gate and no orchestration of its own.
- A retry is the same operation, so a double click cannot produce a
  second effect.

**Accepted costs.**

- The surface is local and single-user for this release. A shared or
  hosted deployment needs a different threat model and a different
  decision.
- Writes are serialised, which is a real throughput cost until the
  storage concurrency question (F02) is settled.
- The token is bootstrapped locally; it is a CSRF barrier, not
  authentication against a local attacker.

**Not decided here (as of the original decision).** The HTTP framework,
the packaged static assets and their CSP, and the API surface shape.
Those are the next packets, and the contract for them is in
`docs/BETA_LIMITATIONS.md`.

## Amendment — the transport is a minimal ASGI application (2026-10-21)

**Measured requirement.** The surface needs: ASGI (the contract says "one
ASGI process"), routing with path parameters, query parsing, a bounded
body, JSON responses with stable codes, and static assets from the
package. It does **not** need: a schema/validation framework, dependency
injection, an OpenAPI document, or an ORM. It is read-only, and its
routes are eight.

**Decision: no framework.** `src/paw/web/asgi.py` is a minimal ASGI
application - a route table, a bounded body reader, a JSON renderer and
the security boundary in front of them. The *server* is the only
dependency, and it is an **optional** extra: the core install stays
dependency-free, exactly as it is today.

**Why.**

* A framework's value here - validation, DI, OpenAPI - is not what an
  eight-route read-only surface needs, and adopting one would mean
  constraining its request model to the boundary's anyway.
* **The tests are the proof.** An ASGI application is a callable, so
  the surface is proved by driving it directly: no server, no socket,
  no test client, no network, no second dependency. A framework's own
  test client would add a dependency to obtain the same proof.
* The boundary was deliberately transport-agnostic so this choice could
  be made against a requirement instead of a preference. A framework
  would have made the choice for us, and the boundary would have had to
  be bent around it.
* The project is "pure Python, zero vendor lock-in"; the core install
  has no web dependency today and keeps none.

**Alternatives.**

| Option | Why not |
|---|---|
| **Starlette** (plus uvicorn) | A second dependency, and a request model the boundary would have to be bent around, for eight read-only routes whose validation is already in the projections. It would also add a test-client dependency to prove the surface, where the ASGI callable is proved directly. |
| **FastAPI** | More than the read-only surface needs: OpenAPI, a validation layer, and dependency injection. Its value is for a public API; this is a local surface. |
| **A WSGI framework** | The contract says ASGI, and WSGI has no streaming story for the event projection. |

**Accepted cost.** PAW owns a small amount of HTTP-shaped code: the route
table, the body reader and the renderer. It is bounded by the boundary
(Host, Origin, CSRF, body size, query) and it is covered by its own
contract test, so the cost is visible rather than spread.

**What this does not change.** The safety boundary, the request
semantics, the read-only scope and the rule that mutations wait for F02
are all as decided above. The transport is a shell.

## Evidence

- `tests/test_local_web_security_contract.py` (36 tests) — every control
  refuses with a stable code, the Host allowlist is exact, a wildcard
  CORS is not representable, the write admission is process-wide, and
  the layering holds.
- `tests/test_local_web_request_contract.py` — the request key and the
  reconnect rules.
