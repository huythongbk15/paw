"""Request identity and reconnect semantics for the local web surface.

Two questions the surface has to answer, and the rules for both.

**What is the identity of a mutation?** A browser that retries, double
clicks, or reconnects must not produce a second effect. The contract
says the request key must *reuse the existing durable operation
identity* where that is valid, and that an in-memory dedup map cannot
claim restart safety. So there is no new store here: a request key
determines an operation identity, and the operation identity is the one
the runtime already records durably.

**What does a reconnect do?** A disconnect is neither a completion nor a
cancellation. On reconnect the surface *inspects* the durable task. It
never re-runs an effect, and it never marks a task complete because the
browser went away. A mutation is only ever resumed with the same
request key, which resolves to the same operation identity, and the
runtime's own replay safety decides whether the effect is repeated.

These are decisions, not I/O: the module is transport-agnostic and
holds no database handle, so the rules are provable on their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = [
    "ReconnectAction",
    "RequestKeyPolicy",
    "WebRequestKeyError",
]


class WebRequestKeyError(ValueError):
    """A request key that cannot be used.

    The message is safe to show: it never echoes the key itself, because
    a key is application-supplied text and may carry something sensitive.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


# A request key is opaque application text: printable, bounded, and
# without control characters. It is not a credential, and it must never
# travel in a query string (the security boundary refuses that).
_KEY_RE = re.compile(r"^[A-Za-z0-9._:\-]{8,128}$")


@dataclass(frozen=True)
class RequestKeyPolicy:
    """How a request key becomes a durable operation identity."""

    #: The longest accepted key.
    max_length: int = 128
    #: The shortest accepted key. Short keys collide too easily.
    min_length: int = 8

    def validate(self, key: str | None) -> str:
        """Validate a request key, or refuse it with a stable reason."""
        if key is None or not str(key).strip():
            raise WebRequestKeyError(
                "web.request_key_missing",
                "a mutating request must carry a request key",
            )
        text = str(key).strip()
        if len(text) < self.min_length:
            raise WebRequestKeyError(
                "web.request_key_too_short",
                f"the request key must be at least {self.min_length} characters",
            )
        if len(text) > self.max_length:
            raise WebRequestKeyError(
                "web.request_key_too_long",
                f"the request key must be at most {self.max_length} characters",
            )
        if not _KEY_RE.match(text):
            raise WebRequestKeyError(
                "web.request_key_malformed",
                "the request key may contain only letters, digits, '.', '_', ':' and '-'",
            )
        return text

    def operation_identity(self, task_id: str, key: str) -> str:
        """The durable operation identity a request key resolves to.

        It is derived, not stored: the same task and the same key always
        give the same identity, and a different key gives a different
        one. That is what makes a retry the *same* operation rather than
        a new one, and it is why the runtime's existing operation record
        - which is durable and already survives a restart - can be the
        dedup record.
        """
        return f"web-op-{task_id}-{self.validate(key)}"


class ReconnectAction(StrEnum):
    """What a reconnect does with a durable task.

    There is deliberately no "re-run" and no "complete". A browser that
    went away did not finish the work, and it did not cancel it.
    """

    #: The task is still running. Report its durable state.
    INSPECT = "inspect"
    #: The task is waiting for a human decision. Report the pending
    #: approval; do not act on the user's behalf.
    AWAIT_APPROVAL = "await_approval"
    #: The task finished. Report the durable outcome.
    COMPLETED = "completed"
    #: The task failed. Report the durable failure.
    FAILED = "failed"
    #: The task is paused. Report that it is paused.
    PAUSED = "paused"


@dataclass(frozen=True)
class ReconnectPolicy:
    """Turns a durable task state into a reconnect action.

    The mapping is deliberately total and boring: a reconnect reads
    state and reports it. It never decides that work is finished
    because the client stopped listening.
    """

    def action_for(self, status: str, *, waiting_for_approval: bool = False) -> ReconnectAction:
        """The action for a durable task status."""
        if waiting_for_approval:
            return ReconnectAction.AWAIT_APPROVAL
        value = str(status or "").strip().lower()
        if value in ("completed", "succeeded", "success", "done"):
            return ReconnectAction.COMPLETED
        if value in ("failed", "error", "cancelled", "canceled"):
            return ReconnectAction.FAILED
        if value in ("paused", "awaiting_approval"):
            return ReconnectAction.AWAIT_APPROVAL if value == "awaiting_approval" \
                else ReconnectAction.PAUSED
        # running, pending, queued, anything unknown: report the state.
        return ReconnectAction.INSPECT

    def may_retry(self, action: ReconnectAction, *, same_request_key: bool) -> bool:
        """Whether a client may retry the request.

        Only a mutation that failed may be retried, and only with the
        **same** request key, so the retry resolves to the same durable
        operation and the runtime's replay safety decides whether the
        effect is repeated. A disconnect is not a failure: it is
        inspected, not retried.
        """
        if action is not ReconnectAction.FAILED:
            return False
        return same_request_key


@dataclass(frozen=True)
class WebRequest:
    """A validated inbound request, ready for the application layer."""

    method: str
    path: str
    request_key: str = ""
    body: dict[str, Any] = None  # type: ignore[assignment]
    task_id: str = ""

    def __post_init__(self) -> None:
        if self.body is None:
            object.__setattr__(self, "body", {})

    @property
    def is_mutation(self) -> bool:
        return self.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
