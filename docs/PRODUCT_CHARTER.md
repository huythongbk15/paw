# PAW product charter

## Product statement

PAW is a local-first engineering agent runtime for researching, understanding,
designing, changing and verifying complex software projects. It turns a
technical goal into a bounded, evidence-backed, policy-authorized, observable
and resumable sequence of decisions and actions.

PAW is not a wrapper around one model vendor or agent framework. Providers and
executors may supply capabilities, but PAW owns the decision and state model.
"Local-first" means that PAW keeps authoritative task state, project context,
memory, policy and recovery under the user's control. It does not mean that a
local model must perform every difficult inference.

## User promise

A user should be able to submit one task and understand:

- how deeply PAW researched the task and which constraints bounded the search;
- what current-project and external evidence supports or challenges the work;
- which alternatives were considered and why the selected approach is ready
  for implementation, needs clarification, requires a spike or should stop;
- what PAW plans to do;
- what context and skills it selected, and why;
- which action requires permission;
- which model and executor were selected, and why;
- what project evidence was sent to a cloud model and what remained local;
- what happened, what failed and what artifacts changed;
- why the loop continued, replanned, waited or stopped;
- how the task resumes without repeating completed side effects;
- how prior project decisions and working preferences reduce repeated
  explanation without silently becoming execution authority.

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
- Implementation readiness and engineering decision artifacts
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
11. Engineering outcome quality before token, latency or feature-count
    optimization.
12. Local intelligence prepares, remembers and verifies; difficult or novel
    reasoning may escalate to a cloud model through an explicit gate.
13. Evidence and a reviewable decision before implementation.

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
- multi-user tenancy, shared-workspace authorization or tenant isolation;
- new historical “phases” used as a substitute for acceptance criteria.

Existing Ollama support remains an adapter to stabilize, not a pattern for new
provider expansion.

Recorded scope decision (2026-08-31): a built-in, workspace-scoped local
filesystem adapter is permitted because the S4 core scenario requires one real
side effect behind Policy. This does not authorize shell execution, external
executor integrations, additional providers or writes outside the configured
workspace.

Recorded scope decision (2026-09-01): through BETA, PAW has one local user
authority. Projects, sessions and tasks may be distinct, but `Identity` is a
preference/profile record rather than an authentication tenant. PAW makes no
multi-user isolation claim. Shared or hosted tenancy requires a separate product
decision, threat model and persistence partitioning review.

## Recorded product direction: engineering intelligence

Decision date: 2026-09-01. This records the direction after Core Stabilization;
it does not authorize implementation before the current exit gate passes.

PAW will specialize in code, systems and software architecture rather than
compete as a broad consumer assistant. Its central product loop is:

```text
technical goal -> bounded research -> evidence-backed decision
               -> specification/plan -> authorized execution
               -> verification -> durable learning
```

The target division of responsibility is:

- **local control plane:** durable state, policy, approvals, project indexing,
  retrieval, context reduction, deterministic tools, verification and private
  memory;
- **local inference support:** bounded classification, summarization, ranking
  and other narrow work whose quality is proven against an evaluation set;
- **cloud reasoning:** architecture analysis, novel debugging, cross-module
  planning, difficult review and synthesis when local capability is
  insufficient;
- **PAW runtime:** decides what evidence is needed, gates every model/tool call,
  records the decision and verifies the resulting work. Neither a local nor a
  cloud model owns policy or task state.

PAW will learn a user's work through explicit, source-backed memory and
verified task traces before considering model training. Raw activity is not a
training set. Any later distillation or fine-tuning must use a versioned,
redacted, reviewable dataset, an evaluation gate and a reversible model
artifact. Continuous self-training from unreviewed interaction is out of
scope.

Repeated verified work may produce a candidate personal skill, but never an
automatically trusted one. Promotion requires provenance, replay against a
reviewed case, explicit user acceptance, versioning and rollback. Facts,
preferences and skills remain separate records with separate correction rules.

### Recorded decision: evidence before implementation

Decision date: 2026-09-01. This is a post-stabilization product contract and
does not claim that the current runtime implements it.

Every engineering idea or task starts with bounded research proportional to
novelty, impact, uncertainty and reversibility. Research begins with current
project source, tests, contracts and history; external prior art is added when
the decision depends on unstable, unfamiliar or comparative information. The
goal is not an abstract optimum. It is the simplest option that satisfies all
hard product, architecture, safety, compatibility and verification constraints
within an explicit time/token appetite.

Research produces a durable, source-backed decision artifact and one readiness
outcome: `NEEDS_RESEARCH`, `NEEDS_CLARIFICATION`, `SPIKE_REQUIRED`, `READY` or
`REJECTED`. An implementation plan or mutating implementation proposal requires
`READY`. A research-only operation or isolated, disposable spike still passes
Policy and the canonical runtime, cannot be presented as product implementation
and cannot silently become production code.

There is still one canonical `Task`; PAW does not introduce a `ResearchTask` or
a second planner. A Plan declares one purpose: `RESEARCH`, `SPIKE` or
`IMPLEMENTATION`. Research and spike Plans may gather evidence but cannot contain
production mutation. An `IMPLEMENTATION` Plan must reference the current
`READY` decision for the same Task and project revision.

The depth is risk-based:

- `FAST`: deterministic, low-impact work; inspect the current owner, behavior
  and invariant, normally without external research;
- `STANDARD`: localized defect, feature or refactor; reproduce/localize, compare
  at least two viable approaches and define verification;
- `DEEP`: architecture, schema, public contract, security, multi-module or
  product idea; research prior art, compare distinct options including the
  smallest/do-nothing alternative, record risks/rollback and use a reviewed
  spike or decision record when uncertainty remains.

External material is untrusted evidence, never executable instruction. Claims
without a source are labelled assumptions, and every `STANDARD` or `DEEP`
assessment records the strongest evidence against proceeding. Research stops
on an explicit sufficiency or budget condition; exhausted budget with a
blocking unknown yields clarification, spike or rejection rather than a guess.

“Verified” is not synonymous with “an executor returned success.” PAW separates
operation observation, engineering verification against declared acceptance
checks, and benchmark/release evaluation. Only a trace with committed operations,
passing required engineering checks, current provenance and no unresolved unsafe
effect may be used to promote a personal skill or build a training dataset.

This direction deliberately deprioritizes general chat features, provider
breadth, agent swarms, large skill marketplaces and integrations that do not
improve the central engineering loop. Existing features that cannot be tied to
an engineering completion scenario and a measurable outcome are candidates
for quarantine, compatibility-only support or removal.

## Product outcome tests

Post-stabilization work must be judged against a versioned engineering
benchmark, not a feature checklist. The benchmark must cover repository
understanding, defect localization, cross-module change, refactoring,
architecture design and recovery from an interrupted task. It must measure:

- verified task success and architecture/invariant correctness;
- recall of the evidence required to solve the task;
- cloud input/output tokens, cost and latency;
- unsafe, unauthorized or unreconciled actions;
- whether recalled user/project memory is correct, scoped and traceable;
- whether readiness decisions used the required evidence, rejected unsafe or
  unjustified implementation and selected the simplest conforming option;
- research time/tokens and the rate of implementation later invalidated by a
  missed constraint or unsupported assumption;
- whether the final result includes executable verification evidence.

Token reduction is accepted only when task quality and safety do not regress.
Local training is accepted only when it beats the non-trained local baseline
for a named narrow role and preserves the cloud-escalation path.

## Change test

During Core Stabilization, a proposed feature belongs in the core only if at
least one current core completion scenario cannot be satisfied without it.
Otherwise it is deferred until the exit gate passes. After the gate, a retained
or proposed capability must improve the central engineering loop on the E0
benchmark, have one canonical owner and justify its ongoing context, safety and
maintenance cost. This test is intentionally strict: PAW needs outcome quality,
not surface area.
