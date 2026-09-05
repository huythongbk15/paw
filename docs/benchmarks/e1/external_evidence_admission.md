# E1-34 Admit External Evidence as Untrusted Input with Provenance

This document is the **E1-34 deliverable**. It defines
the contract for `admit_external_evidence`, the
function that admits a piece of external content (a
web fetch, a user message, a file from outside the
repo) into the runtime as an `ExternalEvidence` record
with explicit provenance and a prompt-injection
negative-control.

## Why this contract exists

The E1-26 negative controls cover the case where a
*project* source goes stale. E1-34 covers the case
where a piece of content from *outside* the project
arrives in the runtime (a web fetch, a user message,
a tool output). External content is by definition
untrusted: the runtime cannot verify it, and a
reviewer who cites it must be able to trace *where it
came from*.

The E1-34 contract is the *admission gate*: every
piece of external content that the runtime uses as
evidence must pass through `admit_external_evidence`,
which records:

- **provenance** — `source_kind` (one of `web` /
  `user_message` / `tool_output` / `unknown`) +
  optional `source_url` + the content's SHA-256
  fingerprint.
- **status** — `"unverified"` (the E1-32 default).
- **prompt-injection negative control** — a regex
  pass over the content for the closed set of
  suspicious patterns. A match yields
  `injection_suspected=True` and the caller decides
  whether to use the evidence.

The function is *fail-closed*: a malformed
`source_kind` is rejected with `ValueError`. The
function does *not* refuse suspicious content
outright — the caller decides.

## Canonical location

`admit_external_evidence` is a new function in
`paw.knowledge.external` (a new module). The function
is pure: same input → same output. The `ExternalEvidence`
record is a frozen dataclass.

## Signature

```python
def admit_external_evidence(
    text: str,
    *,
    source_kind: str,
    source_url: str = "",
) -> ExternalEvidence:
    """Admit ``text`` as an untrusted ``ExternalEvidence``.

    The function records the content's SHA-256
    fingerprint, the source_kind + source_url, and
    runs the prompt-injection negative control. A
    match yields ``injection_suspected=True`` and the
    caller decides whether to use the evidence.

    The function refuses an unknown ``source_kind``
    with ``ValueError``.
    """
```

## `ExternalEvidence` shape

```python
@dataclass(frozen=True)
class ExternalEvidence:
    text: str
    fingerprint: str            # SHA-256 hex
    source_kind: str            # "web" | "user_message" | "tool_output" | "unknown"
    source_url: str = ""
    injection_suspected: bool = False
    matched_pattern: str = ""
    status: str = "unverified"
```

## Closed sets

```python
EXTERNAL_SOURCE_KINDS: frozenset[str] = frozenset(
    {"web", "user_message", "tool_output", "unknown"}
)
INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore (?:all )?(?:previous|prior) (?:instructions|prompts)",
    r"disregard (?:the )?(?:system|above) (?:prompt|message)",
    r"forget (?:everything|all) (?:above|before)",
    r"you are now (?:a|an) (?:evil|jailbroken|unrestricted)",
    r"new instructions?:",
)
```

The closed sets are the change-control surface; a new
source_kind or pattern requires updating the contract
test.

## Negative cases

| Case | Expected result |
|---|---|
| Empty text | `injection_suspected=False`, fingerprint is the SHA-256 of empty string. |
| Text with an injection pattern | `injection_suspected=True`, `matched_pattern` is the matched string. |
| Unknown `source_kind` | `ValueError`. |
| `web` with `source_url` | `source_url` is recorded. |
| `user_message` with empty `source_url` | `source_url=""` is recorded. |
| Determinism | Two calls with the same input produce the same output. |

## Phase 4 sync contract

This document is the **source of truth** for E1-34.
The companion contract test
`tests/test_e1_34_external_evidence_contract.py`
enforces the cases above.