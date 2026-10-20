"""PAW Core — privacy classes and remote-disclosure defaults (E1-03).

This module is the **canonical owner** of the project
privacy taxonomy. ``PrivacyClass`` is a closed enum
defined here; ``REMOTE_DISCLOSURE_DEFAULTS`` is the
single source of truth for what a context manifest
carrying a given class is allowed to be sent to;
``can_disclose_to_provider`` is the runtime-side helper
the context compiler and the policy gate consult before
building a manifest.

E0-02 originally defined the enum inside ``paw.bench``;
E1-03 promotes it here so the runtime can import it
without going through the benchmark module. ``paw.bench``
re-exports the same enum for backward compatibility
with the E0-02 contract tests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any


class RemoteDisclosureRefusedError(Exception):
    """Raised when gate_remote_disclosure refuses to send context
    to a remote provider. This is a hard runtime gate: the
    exception propagates up to stop the execution loop.
    """
    def __init__(self, provider_kind: str, refused: tuple) -> None:
        self.provider_kind = provider_kind
        self.refused = refused
        # Two shapes reach this exception: the per-candidate
        # ``(candidate, reason)`` pairs from ``gate_remote_disclosure`` and
        # the ``(reason, detail)`` pairs from ``bind_remote_payload``. The
        # reason is whichever element is a known refusal reason.
        reasons: list[str] = []
        for pair in refused or ():
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                continue
            first, second = str(pair[0]), str(pair[1])
            if first in DISCLOSURE_REFUSED_REASONS:
                reasons.append(first)
            elif second in DISCLOSURE_REFUSED_REASONS:
                reasons.append(second)
            else:
                reasons.append(second)
        summary = ", ".join(reasons) if reasons else "unknown"
        super().__init__(
            f"Remote disclosure refused for provider '{provider_kind}': {summary}"
        )

if TYPE_CHECKING:
    from .context_compiler import ContextManifest


class PrivacyClass(StrEnum):
    """Where a project's source may be sent.

    The values are ordered from least to most restricted so
    that ``PrivacyClass`` can be used as a key in
    benchmark-level rules (the E0-02 ``min_privacy``
    mechanism) and in the runtime-level
    ``REMOTE_DISCLOSURE_DEFAULTS`` table (this module).
    """

    PUBLIC = "public"             # May be sent to any provider.
    INTERNAL = "internal"         # May be sent to approved cloud.
    WORKSPACE = "workspace"        # Workspace only; no remote.
    SECRET = "secret"             # Never sent off-box.

    @classmethod
    def parse(cls, raw: str) -> PrivacyClass:
        """Strict parse: unknown values raise ``ValueError``."""
        try:
            return cls(raw)
        except ValueError as exc:
            raise ValueError(
                f"unknown privacy class: {raw!r}; "
                f"expected one of {[p.value for p in cls]}"
            ) from exc


# --- Provider kinds ------------------------------------------------------
# Closed set the contract test pins. Adding a new kind is a
# change-control surface: it changes the disclosure table
# and requires a code review.

PROVIDER_LOCAL = "local"                 # On-box (ollama, vllm, offline)
PROVIDER_CLOUD_APPROVED = "cloud_approved"  # Charter-admitted cloud
PROVIDER_CLOUD_UNAPPROVED = "cloud_unapproved"  # Everything else

# Providers that run on the user's machine. This is the canonical list
# behind ``ModelManifest.local``; the two must not drift.
LOCAL_PROVIDER_NAMES: frozenset[str] = frozenset(
    {"local", "offline", "vllm", "ollama"}
)

# Providers the product charter admits as cloud destinations. The E1-03
# contract fixes this set as **empty by default**: the cloud baseline was
# deferred, so no cloud provider is approved and every non-local provider
# is ``cloud_unapproved``. Adding a name here is a charter change, not a
# configuration change.
APPROVED_CLOUD_PROVIDERS: frozenset[str] = frozenset()

PROVIDER_KINDS: frozenset[str] = frozenset(
    {
        PROVIDER_LOCAL,
        PROVIDER_CLOUD_APPROVED,
        PROVIDER_CLOUD_UNAPPROVED,
    }
)


# --- Remote-disclosure defaults (the single source of truth) -------------

# Each value is the set of provider kinds that class is
# allowed to be sent to. The contract test asserts the
# table is complete (every PrivacyClass is a key) and the
# values are frozen sets of valid provider kinds.
REMOTE_DISCLOSURE_DEFAULTS: Mapping[PrivacyClass, frozenset[str]] = MappingProxyType(
    {
        PrivacyClass.PUBLIC:    frozenset({PROVIDER_LOCAL, PROVIDER_CLOUD_APPROVED, PROVIDER_CLOUD_UNAPPROVED}),
        PrivacyClass.INTERNAL:  frozenset({PROVIDER_LOCAL, PROVIDER_CLOUD_APPROVED}),
        PrivacyClass.WORKSPACE: frozenset({PROVIDER_LOCAL}),
        # SECRET is on-box only; local is allowed because the
        # workspace itself is local, but the context compiler
        # still filters it out of any remote-capable decision.
        PrivacyClass.SECRET:    frozenset({PROVIDER_LOCAL}),
    }
)


def provider_kind_for(provider_name: str) -> str:
    """Map a provider name to the disclosure provider kind.

    The disclosure table is keyed by *kind*, not by provider name. The
    runtime previously used the provider name itself as the kind, which
    produced a value outside ``PROVIDER_KINDS`` for every real cloud
    provider. That made every remote call refuse as
    ``unknown_provider_kind``, so the class table never actually decided
    anything.

    The mapping is the E1-03 contract: an on-box provider is ``local``,
    a charter-admitted cloud provider is ``cloud_approved``, and everything
    else is ``cloud_unapproved``.
    """
    name = (provider_name or "").strip().lower()
    if name in LOCAL_PROVIDER_NAMES:
        return PROVIDER_LOCAL
    if name in APPROVED_CLOUD_PROVIDERS:
        return PROVIDER_CLOUD_APPROVED
    return PROVIDER_CLOUD_UNAPPROVED



def can_disclose_to_provider(privacy_class: PrivacyClass, provider_kind: str) -> bool:
    """Return True iff the privacy class may be sent to the
    named provider kind.

    This is the helper the context compiler calls when it
    is about to put a candidate into a manifest for a
    provider invocation. The helper is a thin wrapper over
    ``REMOTE_DISCLOSURE_DEFAULTS``; the table is the
    single source of truth.

    An unknown ``provider_kind`` returns ``False`` (fail
    closed: the runtime refuses to send a class to a kind
    it does not recognize).
    """
    if provider_kind not in PROVIDER_KINDS:
        return False
    return provider_kind in REMOTE_DISCLOSURE_DEFAULTS[privacy_class]


__all__ = [
    "DISCLOSURE_REFUSED_REASONS",
    "PROVIDER_CLOUD_APPROVED",
    "PROVIDER_CLOUD_UNAPPROVED",
    "PROVIDER_KINDS",
    "PROVIDER_LOCAL",
    "REMOTE_DISCLOSURE_DEFAULTS",
    "DisclosureResult",
    "PayloadBindingResult",
    "PrivacyClass",
    "RemoteDisclosureRefusedError",
    "bind_remote_payload",
    "can_disclose_to_provider",
    "gate_remote_disclosure",
]


# --- E1-21: gate_remote_disclosure ------------------------------------


# Closed set of refusal reasons the gate can record.
# Adding a new reason is a change-control surface that
# requires updating this set and the contract test in
# the same change.
DISCLOSURE_REFUSED_REASONS: frozenset[str] = frozenset(
    {
        "class_workspace_remote",
        "class_secret_remote",
        "class_internal_unapproved_cloud",
        "class_none_unapproved_cloud",
        "unknown_provider_kind",
        "source_stale",
        # B-19/F05: the outbound payload is not bound to the
        # reviewed manifest, or the manifest cannot be trusted
        # for this call at all.
        "manifest_missing",
        "foreign_manifest",
        "payload_not_approved",
        "payload_oversized",
    }
)


@dataclass(frozen=True)
class DisclosureResult:
    """The result of ``gate_remote_disclosure``.

    ``allowed`` is True iff every included item in the
    manifest may be sent to the named provider kind.
    ``refused`` is a tuple of ``(candidate, reason)``
    pairs for every item that is refused; empty when
    ``allowed`` is True.
    """
    allowed: bool
    refused: tuple = ()


def _refusal_reason(privacy_class: PrivacyClass | None, provider_kind: str) -> str:
    """Map a (class, provider) pair to the closed refusal
    reason the gate records. ``None`` is treated as
    ``INTERNAL`` (the E1-03 default)."""
    cls = privacy_class if privacy_class is not None else PrivacyClass.INTERNAL
    if provider_kind not in PROVIDER_KINDS:
        return "unknown_provider_kind"
    if cls == PrivacyClass.WORKSPACE and provider_kind != PROVIDER_LOCAL:
        return "class_workspace_remote"
    if cls == PrivacyClass.SECRET and provider_kind != PROVIDER_LOCAL:
        return "class_secret_remote"
    if cls == PrivacyClass.INTERNAL and provider_kind == PROVIDER_CLOUD_UNAPPROVED:
        return "class_internal_unapproved_cloud"
    return ""  # allowed


def gate_remote_disclosure(
    manifest: ContextManifest,
    *,
    provider_kind: str,
) -> DisclosureResult:
    """Check every included item in ``manifest`` against
    the E1-03 ``can_disclose_to_provider`` table.

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
    refused: list = []
    for cand in manifest.included:
        # Stale sources must not be disclosed to non-local providers
        if getattr(cand, "is_stale", False) and provider_kind != PROVIDER_LOCAL:
            refused.append((cand, "source_stale"))
            continue
        reason = _refusal_reason(cand.privacy_class, provider_kind)
        if reason:
            refused.append((cand, reason))
    return DisclosureResult(
        allowed=not refused,
        refused=tuple(refused),
    )


# --- B-19/F05: bind the outbound payload to the reviewed manifest ------


@dataclass(frozen=True)
class PayloadBindingResult:
    """The result of ``bind_remote_payload``.

    ``allowed`` is True iff the exact outbound payload may be sent to the
    named provider kind. ``refused`` is a tuple of ``(reason, detail)``
    pairs. ``payload_digest`` is the SHA-256 of the serialised payload and
    ``manifest_digest`` the SHA-256 of the manifest identity, so an audit
    record can name the exact bytes and the exact evidence that covered
    them.
    """

    allowed: bool
    refused: tuple[tuple[str, str], ...] = ()
    payload_digest: str = ""
    manifest_digest: str = ""


def _payload_text(payload: Any) -> str:
    """Flatten a provider payload into the text that would be transmitted."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Mapping):
        return "\n".join(_payload_text(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return "\n".join(_payload_text(value) for value in payload)
    return "" if payload is None else str(payload)


def _manifest_digest(manifest: Any) -> str:
    """Stable identity of a manifest: its task and the items it covers."""
    parts = [str(getattr(manifest, "task_id", ""))]
    for cand in getattr(manifest, "included", ()) or ():
        parts.append(
            f"{getattr(cand, 'source', '')}:"
            f"{getattr(cand, 'source_id', '')}:"
            f"{getattr(cand, 'revision', '')}:"
            f"{getattr(cand, 'source_hash', '')}"
        )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def bind_remote_payload(
    manifest: Any,
    *,
    provider_kind: str,
    task_id: str,
    payload: Any,
) -> PayloadBindingResult:
    """Bind the exact outbound payload to the manifest that was reviewed.

    ``gate_remote_disclosure`` answers "may this manifest go to this
    provider?". It does not answer "are the bytes about to be sent the
    ones that manifest covers?". Those are different questions, and the
    runtime used to ask only the first one: the messages handed to the
    provider came from an independent channel, so a manifest that
    correctly refused a SECRET record did not stop that same SECRET from
    reaching the provider through the message list.

    This function closes that gap. It refuses, in order:

    * ``manifest_missing`` - a remote call with no manifest is not
      authorized by anything. The previous behaviour skipped the gate
      entirely in that case.
    * ``foreign_manifest`` - the manifest belongs to a different task.
    * the per-candidate disclosure reasons, reused from
      ``gate_remote_disclosure``.
    * ``payload_not_approved`` - the payload carries text that the
      disclosure decision refused, or text from a non-disclosable record
      the compiler saw but did not include. This is the binding: the
      reviewed evidence must actually describe what is sent.
    * ``payload_oversized`` - the payload exceeds the manifest's own
      token budget, so it cannot be the payload the manifest budgeted.

    The function is pure. It does not raise; the caller refuses the
    invocation when ``allowed`` is False.
    """
    text = _payload_text(payload)
    payload_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    refused: list[tuple[str, str]] = []

    if manifest is None:
        refused.append(("manifest_missing", "no compiled manifest for this task"))
        return PayloadBindingResult(
            allowed=False,
            refused=tuple(refused),
            payload_digest=payload_digest,
        )

    manifest_digest = _manifest_digest(manifest)

    # An unknown provider kind fails closed even when the manifest is
    # empty: the disclosure table does not recognise the destination, so
    # nothing is authorized.
    if provider_kind not in PROVIDER_KINDS:
        refused.append(("unknown_provider_kind", provider_kind))

    manifest_task = str(getattr(manifest, "task_id", "") or "")
    if manifest_task and manifest_task != str(task_id):
        refused.append(
            ("foreign_manifest", f"manifest belongs to task {manifest_task!r}")
        )

    disclosure = gate_remote_disclosure(manifest, provider_kind=provider_kind)
    for cand, reason in disclosure.refused:
        refused.append((reason, str(getattr(cand, "source_id", ""))))

    # The binding check: text that the disclosure refused must not appear
    # in the payload through any other channel.
    non_disclosable: list[str] = []
    for cand, _reason in disclosure.refused:
        content = str(getattr(cand, "content", "") or "")
        if content.strip():
            non_disclosable.append(content)
    for cand in getattr(manifest, "excluded", ()) or ():
        cls = getattr(cand, "privacy_class", None)
        if cls in (PrivacyClass.SECRET, PrivacyClass.WORKSPACE):
            content = str(getattr(cand, "content", "") or "")
            if content.strip():
                non_disclosable.append(content)
    for content in non_disclosable:
        if content in text:
            refused.append(("payload_not_approved", "payload carries refused content"))
            break

    budget = getattr(manifest, "budget", None)
    max_tokens = getattr(budget, "max_tokens", None)
    # A token is roughly four characters; the bound is a ceiling on the
    # payload, not an estimate of its cost.
    if max_tokens and len(text) > int(max_tokens) * 4:
        refused.append(("payload_oversized", "payload exceeds the manifest budget"))

    return PayloadBindingResult(
        allowed=not refused,
        refused=tuple(refused),
        payload_digest=payload_digest,
        manifest_digest=manifest_digest,
    )
