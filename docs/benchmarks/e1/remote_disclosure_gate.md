# E1-21 Gate Remote Disclosure from the Final Manifest

This document is the **E1-21 deliverable**. It defines
the contract for the `gate_remote_disclosure` function
the runtime calls immediately before any cloud
provider invocation: the function checks every
included item in the `ContextManifest` against the
E1-03 `can_disclose_to_provider` table and refuses
the invocation if any item cannot be disclosed.

## Why this contract exists

The E1-03 `PrivacyClass` / `can_disclose_to_provider`
helper is the *content* policy: a class may or may not
be sent to a provider kind. The E1-20 budget gate
ensures the manifest is bounded. The E1-21 gate is
the *transport* policy: the runtime checks the manifest
*just before* it sends the payload, and refuses to send
if any included item is private to a kind that the
remote provider does not support.

The gate is the change-control surface for the
"minimum cloud disclosure" Architecture invariant. A
reviewer who inspects the gate can be sure that no
`SECRET` / `WORKSPACE` / `INTERNAL` item reaches a
provider that does not allow it.

## Canonical location

`gate_remote_disclosure` is a new function in
`paw.core.privacy` (the existing module that owns
`PrivacyClass` and `can_disclose_to_provider`). The
function is pure: it takes a `ContextManifest` + a
`provider_kind` and returns a `DisclosureResult`
record. The runtime caller is responsible for
invoking the gate; the gate does not send anything.

## Signature

```python
def gate_remote_disclosure(
    manifest: ContextManifest,
    *,
    provider_kind: str,
) -> DisclosureResult:
    """Check every included item in ``manifest``
    against the E1-03 ``can_disclose_to_provider`` table.

    Returns a ``DisclosureResult`` with two fields:
    - ``allowed``: True iff every included item may be
      sent to ``provider_kind``; False if any item is
      refused.
    - ``refused``: a tuple of ``(candidate, reason)``
      pairs for every item that is refused; empty when
      ``allowed`` is True.

    The function is pure: it does not raise on a
    refused item; the caller is responsible for
    inspecting ``allowed`` and refusing the
    invocation when it is False.
    """
```

## `DisclosureResult` shape

```python
@dataclass(frozen=True)
class DisclosureResult:
    allowed: bool
    refused: tuple[tuple[ContextCandidate, str], ...] = ()
```

`refused` is a tuple of `(candidate, reason)` pairs;
`reason` is a stable string the runtime can log. The
closed set of reasons:

| Reason | Meaning |
|---|---|
| `class_workspace_remote` | The candidate's `privacy_class` is `WORKSPACE`; the provider is remote. |
| `class_secret_remote` | The candidate's `privacy_class` is `SECRET`; the provider is remote. |
| `class_internal_unapproved_cloud` | The candidate's `privacy_class` is `INTERNAL`; the provider is unapproved cloud. |
| `class_none_unapproved_cloud` | The candidate's `privacy_class` is `None`; the default is `INTERNAL`; the provider is unapproved cloud. |
| `unknown_provider_kind` | The `provider_kind` is not in the E1-03 closed set; the gate fails closed. |

## Negative cases

| Case | Expected result |
|---|---|
| All items `PUBLIC` to a `local` provider | `allowed=True`, `refused=()`. |
| One item `SECRET` to a `cloud_unapproved` provider | `allowed=False`, `refused` has one entry. |
| `provider_kind` is not in the closed set | `allowed=False`, the unknown kind is recorded as the reason. |
| Empty manifest | `allowed=True`, `refused=()`. |
| `ContextManifest` with `excluded` items that are private | `allowed=True` (the excluded list is filtered; only `included` is checked). |

## Phase 4 sync contract

This document is the **source of truth** for E1-21.
The companion contract test
`tests/test_e1_21_remote_disclosure_contract.py`
enforces the cases above.