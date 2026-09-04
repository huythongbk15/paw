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

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


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
    "PROVIDER_CLOUD_APPROVED",
    "PROVIDER_CLOUD_UNAPPROVED",
    "PROVIDER_KINDS",
    "PROVIDER_LOCAL",
    "REMOTE_DISCLOSURE_DEFAULTS",
    "PrivacyClass",
    "can_disclose_to_provider",
]
