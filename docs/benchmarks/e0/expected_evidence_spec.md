# E0 Expected-Evidence Verification Spec (E0-03)

This document is the **E0-03 deliverable**. It defines how
the E0-16 runner verifies each kind of expected evidence
**without reading or scoring any model output**.

The contract is intentionally narrow: every evidence kind
maps to a single deterministic check against a source
artifact (file, command exit code, ledger row, task
status, policy decision). The runner never has to
"interpret" what the model said; it either matches the
spec exactly, or it does not.

## Why "independent of model output"

A benchmark that scores a model by re-reading the model's
output is circular: the model can produce a fluent answer
that matches itself but does not match the truth. The
expected-evidence spec breaks the circle by anchoring
every PASS/FAIL to an artifact that exists whether or not
the model ever ran.

Concretely, every check below can be re-run with no model
in the loop, and a reviewer can confirm the PASS/FAIL by
eye against the same artifact.

## The five evidence kinds

Each subsection gives the **kind** name (from
`paw.bench.ExpectedEvidence.ALLOWED_KINDS`), the
**target** field semantics, the **value** field
semantics, and the deterministic verify command the
runner must run.

---

### 1. `file_contains`

The artifact is a repository-relative file. The runner
asserts that the file exists, that the runner has read
access to it (per the case's `privacy_class`), and that
the file's content contains `value` as a substring (or,
if `value` is multi-line, that every line in `value` is
present in the file in order).

| Field | Semantics |
|---|---|
| `target` | Repository-relative file path (e.g. `docs/api.md`). |
| `value`  | A substring (single line) or a line list (multi line). |
| `reviewer` | The human who reviewed the substring against the file. |

**Verify command (deterministic)**:
```bash
test -f "<target>" \
  && grep -F -q -- "<value>" "<target>" \
  && echo PASS || echo FAIL
```

Privacy: `privacy_class == "secret"` forces the runner to
read the file in a sandboxed subprocess and never include
its content in any cloud-bound payload.

---

### 2. `command_exit`

The artifact is a deterministic, read-only command that the
runner runs in a sandbox. The runner asserts that the
command exits with the integer given in `value`.

| Field | Semantics |
|---|---|
| `target` | A Python list literal of arguments (e.g. `["grep", "-F", "-q", "--", "src/<package_name>", "fixture.txt"]`). The runner parses the literal via `ast.literal_eval` and runs the argv with `subprocess.run(..., shell=False)`. Shell strings are rejected: the deny-list cannot catch every metacharacter, and `shell=False` is the only way to guarantee the runner never invokes a shell. The reviewer signs that they ran the argv list and saw the exit code. |
| `value`  | The integer exit code as a string (e.g. `"0"`, `"1"`). |
| `reviewer` | The human who ran the command. |

**Verify command (deterministic)**:
```python
import ast, subprocess
argv = ast.literal_eval(evidence.target)
result = subprocess.run(argv, shell=False, check=False, capture_output=True, timeout=10)
assert result.returncode == int(evidence.value)
```

Safety rules the runner enforces before running:
- The target must start with `[` and parse as a Python
  list of strings; a non-list target (shell string) is
  rejected with a clear diagnostic.
- The first token (program name) is checked against
  `paw.bench.runner.DEFAULT_DENY_LIST` (`rm`, `mkfs`,
  `dd`, `shutdown`, `reboot`, `poweroff`). Defense-in-depth:
  the list is small and shell=False already prevents
  shell expansion, but the check stays.
- The command runs with a 10-second wall-clock cap;
  timeout = FAIL.

---

### 3. `ledger_event`

The artifact is a single row in the `task_events` table
emitted by the runtime. The runner queries SQLite, finds
the row that matches `(task_id, event_type, payload)`, and
asserts the payload contains `value`.

| Field | Semantics |
|---|---|
| `target` | The `TaskEventType` value (e.g. `TASK_COMPLETED`, `POLICY_GATE_EVALUATED`). |
| `value`  | A JSONPath-like selector over the payload, or a literal substring the runner must find in the JSON-serialized payload. |
| `reviewer` | The human who reviewed the event log. |

**Verify command (deterministic)**:
```bash
sqlite3 paw.db \
  "SELECT json_extract(payload, '$<value>') \
   FROM task_events \
   WHERE event_type = '<target>' AND task_id = '<task_id>' \
   ORDER BY created_at DESC LIMIT 1" \
  | grep -q -F -- "<expected_substring>" \
  && echo PASS || echo FAIL
```

The runner pulls `task_id` from the case's task record; the
spec is per-case so the same `kind=ledger_event,
target=TASK_COMPLETED` evidence can apply to every case.

---

### 4. `task_status`

The artifact is the terminal status of a Task. The runner
queries the `tasks` table for the case's `task_id` and
asserts the `status` column equals the literal in
`value`.

| Field | Semantics |
|---|---|
| `target` | The `TaskStatus` value expected at the end of the run (e.g. `COMPLETED`, `FAILED`, `BLOCKED`, `WAITING_APPROVAL`). |
| `value`  | The literal `TaskStatus` value as a string. |
| `reviewer` | The human who reviewed the lifecycle. |

**Verify command (deterministic)**:
```bash
sqlite3 paw.db \
  "SELECT status FROM tasks WHERE id = '<task_id>'" \
  | grep -F -q -- "<value>" \
  && echo PASS || echo FAIL
```

This is **never** satisfied by `PARTIAL` or by an
in-progress status; the runner's verify refuses to write
`PASS` until the task is terminal.

---

### 5. `policy_decision`

The artifact is a `RequestVerdict` row emitted by the
policy gate. The runner queries `task_events` for the
most recent `POLICY_GATE_EVALUATED` event and asserts the
verdict matches `value`.

| Field | Semantics |
|---|---|
| `target` | The capability string the decision applied to (e.g. `FILESYSTEM_WRITE`). |
| `value`  | The verdict string: one of `go`, `ask`, `block`. |
| `reviewer` | The human who reviewed the policy trace. |

**Verify command (deterministic)**:
```bash
sqlite3 paw.db \
  "SELECT json_extract(payload, '$.details.\\\"<target>\\\".decision') \
   FROM task_events \
   WHERE event_type = 'POLICY_GATE_EVALUATED' AND task_id = '<task_id>' \
   ORDER BY created_at DESC LIMIT 1" \
  | grep -F -q -- "<value>" \
  && echo PASS || echo FAIL
```

The verdict is one of the three literal values; anything
else (e.g. an unrecognized string) is a runner bug, not a
case failure.

---

## Why a model output is never the artifact

The contract above covers every evidence kind E0 cases
will need. Each is anchored to an artifact the runtime
already produces (a file the runtime wrote, a command
the reviewer ran, a ledger row the runtime committed, a
task status the runtime transitioned, a policy verdict
the runtime recorded). Adding a new kind requires:

1. A new value in `paw.bench.ExpectedEvidence.ALLOWED_KINDS`.
2. A new clause in the runner's verify dispatcher.
3. A new sub-section in this spec with the verify command.

No kind may be "the model said X" or "the response
contained Y". A reviewer must be able to re-verify the
PASS/FAIL by running the verify command by hand against
the same artifact.

## Reviewer discipline

Every evidence entry carries a `reviewer` field. A case
with an empty `reviewer` is rejected by
`paw.bench.case_manifest_from_dict` (verified by
`test_evidence_without_reviewer_is_rejected`). The
reviewer is the human who:

- Read the spec subsection above.
- Ran the verify command by hand.
- Saved the artifact (commit SHA, command transcript,
  ledger query result) under their own name.
- Marked the case `REVIEWED` in the case lifecycle
  (added in E0-08..15).

A reviewer who cannot produce the saved artifact cannot
promote a case to `VERIFIED`.

## Worked example (E0-03 acceptance)

A reviewer wants to add a case for `E0-15
insufficient-context`. They write:

```yaml
expected_evidence:
  - kind: task_status
    target: BLOCKED
    value: BLOCKED
    reviewer: alice@example.com
  - kind: ledger_event
    target: POLICY_GATE_EVALUATED
    value: '$.details.FILESYSTEM_READ.decision'
    reviewer: alice@example.com
```

The two evidence entries assert:

1. The task ended `BLOCKED` (verifiable by `sqlite3` on
   the `tasks` table).
2. The policy gate for `FILESYSTEM_READ` recorded a
   decision (verifiable by `sqlite3` on `task_events`).

No model output is read. The reviewer can re-verify by
running the two `sqlite3` commands by hand after the
case finishes.

## Phase 4 sync contract

This spec is the **source of truth** for E0-03 and for
the future E0-16 runner. Any change to the verify
command above is a **breaking change** to the E0 contract
and must be reflected in:

- `docs/EXECUTION_CHECKLIST.md` — E0-03 evidence.
- `docs/IMPLEMENTATION_MAP.md` — component map row for
  `paw.bench.runner` (added in E0-16).
- The future `tests/test_e0_evidence_verifier.py` (E0-16)
  that asserts the verify commands behave as documented.

If the runner's implementation drifts from this spec,
the spec is the contract; the implementation is wrong.
