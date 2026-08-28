---
name: systematic-bug-fix
description: >
  Diagnose and fix software defects using evidence-driven debugging.
  Reproduce the failure, localize the first incorrect state, identify the root cause,
  apply the smallest correct fix, prove the regression test detects the defect,
  verify related boundaries, and search for sibling defects when justified.
  Use for runtime errors, failing tests, regressions, incorrect behavior,
  integration failures, packaging problems, state bugs, concurrency bugs,
  security defects, and difficult-to-reproduce failures.

version: "2.0.0"
category: software-engineering

tags:
  - debugging
  - bug-fix
  - root-cause
  - regression
  - testing
  - verification
  - reliability

capabilities:
  - filesystem.read
  - filesystem.write
  - search
  - git.read
  - shell.execute
  - testing
  - reasoning

risk: medium
network: optional
write: true
---

# Systematic Bug Fix

## Mission

Fix the defect, not merely the visible symptom.

A bug is considered fixed only when there is sufficient evidence that:

```text
the failure is understood
+
the root cause is identified
+
the intended invariant is restored
+
the fix is verified
+
reasonable regression risks are checked
```

A green test alone is not proof of correctness.

---

# 1. Operating Model

Use this debugging loop:

```text
OBSERVE
   ↓
REPRODUCE
   ↓
LOCALIZE
   ↓
HYPOTHESIZE
   ↓
DISPROVE / CONFIRM
   ↓
ROOT CAUSE
   ↓
MINIMAL FIX
   ↓
PROVE
   ↓
REGRESSION CHECK
```

Do not start by editing code unless the defect and affected path are already sufficiently understood.

Avoid:

```text
error message
→ guess
→ patch
→ tests green
→ done
```

Prefer:

```text
error
→ evidence
→ first incorrect state
→ root cause
→ invariant
→ repair
→ proof
```

---

# 2. Adaptive Debugging Depth

Not every bug requires the same amount of investigation.

Choose one mode.

## QUICK

Use when:

- defect is trivial and deterministic;
- affected code is isolated;
- root cause is obvious and directly observable;
- change has very small blast radius.

Still require:

```text
reproduce
root cause
fix
regression verification
```

---

## STANDARD

Default mode.

Use:

```text
reproduce
localize
hypotheses
root cause
regression test
minimal fix
boundary checks
broader tests
diff review
```

---

## DEEP

Use when:

- root cause is unclear;
- multiple components are involved;
- bug is intermittent;
- previous fixes failed;
- state crosses process/service boundaries;
- affected code is high-impact.

Add:

```text
data/control-flow tracing
git history
sibling-pattern search
failure injection
expanded boundary analysis
broader caller analysis
```

---

## CRITICAL

Use for:

```text
security
data corruption
destructive behavior
authorization
financial actions
secrets
concurrency causing corruption
production-critical reliability
```

Require:

```text
adversarial testing
negative controls
fail-closed review
rollback consideration
broader sibling search
stronger regression evidence
```

---

# 3. Establish the Bug Contract

Before fixing, determine:

```text
INPUT
ENVIRONMENT
EXPECTED
ACTUAL
REPRODUCTION
IMPACT
```

Record the smallest known reproduction.

Example:

```text
Input:
...

Expected:
...

Actual:
...

Command:
...

Observed failure:
...
```

If expected behavior is unclear, infer it only from reliable sources such as:

```text
existing tests
public API contract
documentation
callers
schemas
established system invariants
```

Do not invent desired behavior merely to make the implementation easier.

---

# 4. Reproduce the Failure

Whenever practical, reproduce before editing production code.

Prefer the smallest command or test that demonstrates the defect.

Capture:

```text
exit status
exception
assertion
logs
state before
state after
```

For intermittent failures, record frequency and conditions.

Example:

```text
8 failures / 100 runs
only under parallel execution
```

---

# 5. Validate the Reproduction

Before trusting a failing scenario, verify it actually exercises the intended implementation.

Check:

```text
correct repository
correct branch
correct package
correct runtime
correct environment
correct configuration
correct dependency versions
correct working directory
```

Watch for:

```text
stale build
cached result
wrong fixture
test double replacing real implementation
source-tree import masking packaging problems
```

A test that fails in an unrelated layer is not yet a valid reproduction of the reported bug.

---

# 6. Classify the Defect

Classify only to guide investigation.

Possible classes:

```text
logic
boundary
state
data
persistence
concurrency
integration
configuration
dependency
packaging
compatibility
performance
security
test defect
```

Classification is not the diagnosis.

---

# 7. Localize the First Incorrect State

Trace from known-good input toward the visible failure.

Ask repeatedly:

> At what earliest point does the system state diverge from what should be true?

Trace:

```text
input
↓
validation
↓
transformation
↓
state mutation
↓
boundary crossing
↓
failure
```

The line that raises an exception may only be the place where an earlier defect becomes visible.

Example:

```text
Visible failure:
IndexError

Earlier incorrect state:
candidate list unexpectedly empty

Root origin:
filter rejects valid candidates
```

Fix the origin, not the crash site, unless the crash-site behavior is itself incorrect.

---

# 8. Maintain Explicit Hypotheses for Non-Trivial Bugs

When root cause is uncertain, write a short hypothesis set.

Example:

```text
H1 cache contains stale data
H2 parser drops an optional field
H3 query filters the correct row
H4 caller passes wrong identifier
```

For each:

```text
prediction
experiment
evidence
status
```

Status:

```text
CONFIRMED
REJECTED
UNRESOLVED
```

Prefer experiments that distinguish multiple hypotheses at once.

Do not keep changing production code while the causal model is unclear.

---

# 9. Distinguish Symptom, Trigger, and Root Cause

Always separate:

```text
SYMPTOM
TRIGGER
ROOT CAUSE
```

Example:

```text
Symptom:
null dereference

Trigger:
empty response

Root cause:
API adapter converts valid HTTP 204 into malformed result
```

A guard such as:

```python
if response is None:
    return []
```

may suppress the symptom while leaving the real defect untouched.

---

# 10. State the Broken Invariant

Before implementing the final fix, state:

```text
ROOT CAUSE:
...

BROKEN INVARIANT:
...

CORRECT INVARIANT:
...
```

Examples:

```text
Every routing score must preserve the candidate identity.

A committed transaction must never expose partially serialized state.

Context size after insertion must never exceed configured budget.
```

The fix should restore the invariant, not merely handle one observed input.

---

# 11. Design the Smallest Correct Fix

Prefer fixes that are:

```text
local
explicit
typed
testable
observable
backwards-compatible where appropriate
```

Avoid unnecessary:

```text
large refactors
new frameworks
new dependencies
new abstraction layers
silent fallback logic
```

Do not use broad exception swallowing as a fix.

Incorrect:

```python
try:
    operation()
except Exception:
    pass
```

unless ignoring that failure is explicitly part of the contract.

---

# 12. Prove the Regression

For deterministic defects, create or strengthen a regression test.

Ideal proof:

```text
BEFORE FIX → FAIL
AFTER FIX  → PASS
```

When practical:

1. create the reproduction test;
2. run it against buggy behavior;
3. confirm failure;
4. apply fix;
5. confirm success.

If the test already passed before the fix, it is weak evidence.

---

# 13. Test the Test

For important defects ask:

> Would this regression test detect the old bug?

Use one of:

```text
temporary revert
mutation of relevant condition
negative control
deliberately invalid fixture
```

This is especially important for:

```text
security invariants
filesystem scans
routing
packaging
filters
empty collections
permission checks
```

Never allow checks such as:

```python
for file in files:
    assert ...
```

to silently pass if `files` is unexpectedly empty.

Add:

```python
assert files
```

when non-empty input is an invariant.

---

# 14. Check Relevant Boundaries

Do not blindly execute every possible edge case.

Select boundaries relevant to the defect.

Typical sets:

## Numeric

```text
limit - 1
limit
limit + 1
```

## Collection

```text
empty
one
many
duplicates
```

## Text

```text
empty
whitespace
Unicode
large input
```

## Filesystem

```text
missing
file
directory
relative
absolute
parent traversal
symlink
permission failure
```

## API

```text
success
empty success
timeout
malformed body
missing fields
client error
server error
```

## State

```text
initial
repeat
retry
partial failure
resume
```

Test only cases that can reasonably violate the restored invariant.

---

# 15. Activate Specialized Investigation When Needed

## Packaging

Verify from outside source checkout:

```text
build
wheel contents
isolated install
imports
entry points
working-directory independence
```

---

## Persistence

Inspect:

```text
transactions
commit
rollback
constraints
serialization
migration
ordering
timezone
nullability
```

---

## Concurrency

Inspect:

```text
shared mutable state
race windows
atomicity
locking
cancellation
retry
idempotency
```

Do not use arbitrary sleep as the final synchronization fix.

---

## Security

Inspect:

```text
authorization
path traversal
command injection
symlink escape
secret access
deserialization
permission escalation
fail-open behavior
```

Security fixes should prefer fail-closed behavior.

---

## Performance

First obtain evidence.

Measure:

```text
baseline
hot path
allocation/query counts
latency
throughput
```

Do not label slow-looking code as the cause without measurement.

---

# 16. Search for Sibling Defects

After identifying the root pattern, search nearby code for the same assumption.

Examples:

```text
same helper
same comparison
same parser
same boundary calculation
same query pattern
same validation omission
same permission check
```

Use judgment.

If the same defect exists elsewhere and can be fixed safely within scope, include it.

If addressing it would create a large unrelated refactor:

record it separately.

Do not expand every bug fix into project-wide cleanup.

---

# 17. Inspect Change History When Useful

For regressions inspect:

```text
recent commits
diff
dependency changes
schema changes
configuration changes
```

History provides evidence, not truth.

Do not assume the newest commit caused the bug merely because it is new.

Use history to answer:

```text
What assumption changed?
What behavior changed?
Was the previous behavior deliberate?
```

---

# 18. Verification Pyramid

After the fix, verify from narrow to broad.

```text
1. exact reproduction
2. regression test
3. affected module/subsystem tests
4. caller/integration tests
5. relevant full suite
6. lint/type/build/package checks
```

The size of the fix determines how far up the pyramid is necessary.

Critical fixes should normally reach the top.

---

# 19. Inspect the Final Diff

Before declaring success inspect every changed file.

Ask:

```text
Did the patch actually address the root cause?

Did unrelated code change?

Was validation weakened?

Were exceptions hidden?

Was public behavior accidentally changed?

Was dead code introduced?

Was a dependency added unnecessarily?

Were debug statements or temporary files left behind?

Did the change create another inconsistent implementation elsewhere?
```

Prefer a smaller diff when it provides equal correctness.

---

# 20. Caller and Contract Analysis

When modifying shared code, inspect its callers.

Check whether they depend on:

```text
return values
exceptions
ordering
mutation
side effects
serialization
timing
```

A locally correct fix may still break upstream or downstream contracts.

---

# 21. Failure Semantics

Preserve meaningful errors.

Do not transform:

```text
operation failed
```

into:

```text
empty successful result
```

unless the API contract explicitly requires that behavior.

Prefer typed/explicit failures where available.

Observability must not decrease because of a bug fix.

---

# 22. Fix vs Refactor

Separate:

```text
REQUIRED FOR CORRECTNESS
```

from:

```text
DESIRABLE ARCHITECTURE IMPROVEMENT
```

Perform the latter only when necessary to eliminate the root cause or when the user explicitly requested broader cleanup.

Otherwise record it as technical debt.

---

# 23. Stop Conditions

Do not invent certainty.

Use `PARTIAL` or `NOT REPRODUCED` when:

```text
the failure cannot be reproduced
required environment is unavailable
required dependency cannot be inspected
multiple root causes remain equally plausible
the proposed fix cannot be verified
```

State:

```text
what is known
what was tested
what remains unknown
```

Do not claim a bug is fixed based only on plausible reasoning.

---

# 24. Confidence

At completion assign a confidence level.

## HIGH

```text
reproduction confirmed
root cause demonstrated
regression proved
relevant suites pass
```

## MEDIUM

```text
root cause strongly supported
fix verified
but some environment/integration path unavailable
```

## LOW

```text
failure not reproduced
or root cause remains partially inferred
```

Never report `FIXED` with LOW confidence.

---

# 25. Severity

Use when useful:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

Severity should reflect impact, not debugging difficulty.

---

# 26. Definition of Done

Status `FIXED` requires:

```text
valid reproduction or equivalent evidence
+
root cause
+
correct invariant
+
minimal repair
+
regression proof where practical
+
relevant boundary verification
+
relevant regression suite
+
final diff review
```

---

# 27. Required Final Report

Return:

```text
BUG
...

CLASSIFICATION
...

SEVERITY
...

DEBUG MODE
QUICK | STANDARD | DEEP | CRITICAL

REPRODUCTION
...

EXPECTED
...

ACTUAL
...

ROOT CAUSE
...

BROKEN INVARIANT
...

FIX
...

REGRESSION PROOF
BEFORE:
AFTER:

BOUNDARIES VERIFIED
...

SIBLING PATTERNS CHECKED
...

TEST RESULTS
...

FILES CHANGED
...

REMAINING RISKS
...

CONFIDENCE
HIGH | MEDIUM | LOW

STATUS
FIXED | PARTIAL | NOT REPRODUCED
```

Do not claim FIXED unless the evidence supports it.