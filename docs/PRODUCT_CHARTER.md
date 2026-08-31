# PAW product charter

## Product statement

PAW is a local-first personal agent runtime that turns a user goal into a
bounded, policy-authorized, observable and resumable sequence of actions.

PAW is not a wrapper around one model vendor or agent framework. Providers and
executors may supply capabilities, but PAW owns the decision and state model.

## User promise

A user should be able to submit one task and understand:

- what PAW plans to do;
- what context and skills it selected, and why;
- which action requires permission;
- which model and executor were selected, and why;
- what happened, what failed and what artifacts changed;
- why the loop continued, replanned, waited or stopped;
- how the task resumes without repeating completed side effects.

The default path must work locally with SQLite and deterministic fallbacks. A
cloud provider may improve quality but must not become the owner of task state,
policy or resume semantics.

## Core ownership

PAW exclusively owns these concepts:

- Identity and preferences
- Session and Task
- Plan and Task Graph
- Skill Fabric
- Context Compiler
- Memory and Knowledge primitives
- Policy Engine and approval state
- Autonomy budget, progress and stop decisions
- Capability Router and Model Router
- Executor and provider ports
- Observation, Task Ledger and artifacts
- Checkpoint, operation record and resume semantics

An external system may implement a port. It may not introduce a parallel task,
policy, memory, context or checkpoint model inside PAW Core.

## Product principles

1. Safety before side effects.
2. One canonical contract per concept.
3. Explicit state and typed boundaries.
4. Deterministic behavior before model-assisted behavior.
5. Minimum sufficient, explainable context.
6. Bounded autonomy with visible stop reasons.
7. Durable state before acknowledging progress.
8. Replaceable providers and executors.
9. CLI and library first; no daemon required.
10. Evidence over phase labels or feature counts.

## Core completion scenarios

The core is not considered stable until all of these scenarios are verified in
an isolated environment:

1. A local task runs from creation to terminal result through the canonical
   runtime entry point.
2. DENY and ASK both prevent the pending side effect; an approved ASK resumes
   exactly that operation once.
3. Context selection respects token and fragment budgets while explaining each
   inclusion and exclusion.
4. Capability routing selects an executor independently of model routing.
5. A process restart resumes a checkpoint without repeating completed external
   operations.
6. A valid DAG executes in dependency order; a cycle is rejected; a failed
   required node blocks dependents and prevents a false successful task result.
7. The ledger reconstructs proposals, gates, execution, observations and the
   terminal decision.
8. A wheel installs in a clean environment and its CLI works outside the
   repository.

## Scope lock during Core Stabilization

Until the exit gate in `ROADMAP.md` passes, PAW will not expand into:

- additional cloud/model providers or coding-agent executors;
- MCP implementation, browser/GUI automation or multi-agent orchestration;
- distributed workers, queues, Redis, PostgreSQL, Kafka or Kubernetes;
- vector databases or learned/adaptive routing;
- background daemons or hosted control planes;
- new historical “phases” used as a substitute for acceptance criteria.

Existing Ollama support remains an adapter to stabilize, not a pattern for new
provider expansion.

## Change test

A proposed feature belongs in the core only if at least one core completion
scenario cannot be satisfied without it. Otherwise it is deferred until the
core exit gate passes. This test is intentionally strict: PAW currently needs
convergence more than surface area.
