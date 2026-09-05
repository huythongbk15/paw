"""PAW Knowledge — external evidence admission (E1-34).

``admit_external_evidence`` is the gate for content
from *outside* the project (web fetches, user
messages, tool outputs). The function is the
*admission gate*: every piece of external content
the runtime uses as evidence must pass through it.

The contract is documented in
``docs/benchmarks/e1/external_evidence_admission.md``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# Closed set of source kinds. Adding a new kind is a
# change-control surface that requires updating the
# contract test in the same change.
EXTERNAL_SOURCE_KINDS: frozenset[str] = frozenset(
    {"web", "user_message", "tool_output", "unknown"}
)


# Closed list of prompt-injection patterns. A
# ``re.search`` over the text flags a match. The
# list is intentionally narrow: a reviewer who
# disagrees with a match can read the closed set
# and the reviewer who disagrees with the closed
# set can add a new pattern (with a contract test).
INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore (?:all )?(?:previous|prior) (?:instructions|prompts)",
    r"disregard (?:the )?(?:system|above) (?:prompt|message)",
    r"forget (?:everything|all) (?:above|before)",
    r"you are now (?:a|an) (?:evil|jailbroken|unrestricted)",
    r"new instructions?:",
)


@dataclass(frozen=True)
class ExternalEvidence:
    """One piece of external content the runtime
    admitted as evidence.

    The contract is the change-control surface: a
    reviewer who sees an ``ExternalEvidence`` knows
    the source kind + fingerprint + injection-suspect
    status, and can decide whether to cite it.
    """

    text: str
    fingerprint: str
    source_kind: str
    source_url: str = ""
    injection_suspected: bool = False
    matched_pattern: str = ""
    status: str = "unverified"


def _fingerprint(text: str) -> str:
    """SHA-256 hex digest of the text. An empty
    text returns the SHA-256 of the empty string
    (``e3b0c44...``)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _detect_injection(text: str) -> tuple[bool, str]:
    """Return ``(injection_suspected, matched_pattern)``.
    The first matching pattern wins. The empty pattern
    means no match."""
    for pat in INJECTION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True, pat
    return False, ""


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
    if source_kind not in EXTERNAL_SOURCE_KINDS:
        raise ValueError(
            f"unknown source_kind {source_kind!r}; "
            f"must be one of {sorted(EXTERNAL_SOURCE_KINDS)}"
        )
    suspected, matched = _detect_injection(text)
    return ExternalEvidence(
        text=text,
        fingerprint=_fingerprint(text),
        source_kind=source_kind,
        source_url=source_url,
        injection_suspected=suspected,
        matched_pattern=matched,
    )


__all__ = [
    "EXTERNAL_SOURCE_KINDS",
    "INJECTION_PATTERNS",
    "ExternalEvidence",
    "admit_external_evidence",
]
