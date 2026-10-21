"""The local web security boundary.

This module is **transport-agnostic on purpose**. The controls are a
pure function of the request facts - the method, the headers, the
query, the body size - so they are provable without standing up a
server, and the choice of HTTP framework stays an open decision (see
``docs/adr/0001-local-web-adapter.md``).

The rules come from the B-23..B-26 contract:

* bind ``127.0.0.1`` by default and refuse a non-loopback bind;
* an **exact** Host allowlist - no suffix or prefix matching;
* an **exact** Origin allowlist - no wildcard CORS;
* a local CSRF token for mutations, compared in constant time;
* bounded body, history and stream buffers;
* no credential or token in a query string;
* no concurrent write requests until the storage concurrency question is
  settled, so the write admission is **process-wide**, not per session.

Every refusal has a stable code and a safe message. No refusal carries
a stack trace, a credential or an internal path.
"""

from __future__ import annotations

import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "LocalWebGuard",
    "WebSecurityCode",
    "WebSecurityConfig",
    "WebSecurityError",
    "default_allowed_hosts",
]


class WebSecurityCode(StrEnum):
    """Stable refusal codes. These are part of the API contract."""

    BIND_NOT_LOOPBACK = "web.bind_not_loopback"
    HOST_NOT_ALLOWED = "web.host_not_allowed"
    ORIGIN_NOT_ALLOWED = "web.origin_not_allowed"
    CSRF_INVALID = "web.csrf_invalid"
    BODY_TOO_LARGE = "web.body_too_large"
    HISTORY_TOO_LONG = "web.history_too_long"
    STREAM_BUFFER_TOO_LARGE = "web.stream_buffer_too_large"
    CREDENTIAL_IN_QUERY = "web.credential_in_query"
    METHOD_NOT_ALLOWED = "web.method_not_allowed"
    ORIGIN_REQUIRED = "web.origin_required"


class WebSecurityError(Exception):
    """A refusal by the local web boundary.

    The code is stable and safe to show; the message is safe to show
    too. Neither carries a stack trace, a credential or a path.
    """

    def __init__(self, code: WebSecurityCode, message: str = "") -> None:
        self.code = code
        self.message = message or code.value.replace(".", " ")
        super().__init__(f"{self.code.value}: {self.message}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message}


# The loopback addresses the adapter may bind to.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

# Query parameters that would carry a credential into a URL.
_CREDENTIAL_QUERY_KEYS = frozenset({
    "token", "access_token", "api_key", "apikey", "key",
    "password", "passwd", "secret", "csrf", "csrf_token", "auth",
})

# Methods that change state and therefore need the CSRF token.
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def default_allowed_hosts(bind_host: str, port: int) -> frozenset[str]:
    """The exact Host values the adapter answers to.

    The port is part of the Host header, so the allowlist carries it.
    Matching is exact: ``127.0.0.1:8765`` is allowed and
    ``evil-127.0.0.1:8765`` is not.
    """
    return frozenset({
        f"{bind_host}:{port}",
        f"localhost:{port}",
        f"[::1]:{port}",
    })


@dataclass(frozen=True)
class WebSecurityConfig:
    """The boundary's configuration. Everything is explicit."""

    bind_host: str = "127.0.0.1"
    bind_port: int = 8765
    allowed_hosts: frozenset[str] = field(default_factory=set)
    #: An empty set means "same-origin only": the Origin must match the
    #: request's own Host. Wildcards are not representable.
    allowed_origins: frozenset[str] = field(default_factory=set)
    #: The local bootstrap token. Empty means mutations are refused:
    #: a surface with no token has no protection, so it is not offered.
    csrf_token: str = ""
    max_body_bytes: int = 64 * 1024
    max_history_items: int = 200
    max_stream_buffer_bytes: int = 256 * 1024
    #: Until the storage concurrency question is settled, writes are
    #: serialised process-wide. A per-session lock is not a database fix.
    allow_concurrent_writes: bool = False
    allowed_methods: frozenset[str] = frozenset({
        "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS",
    })

    def hosts(self) -> frozenset[str]:
        """The effective Host allowlist."""
        return self.allowed_hosts or default_allowed_hosts(
            self.bind_host, self.bind_port,
        )


def _header(headers: Mapping[str, Any], name: str) -> str:
    """Case-insensitive header lookup, tolerant of a plain dict."""
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return str(value)
    return ""


class LocalWebGuard:
    """The local web boundary.

    One instance per adapter process. It owns the process-wide write
    admission, so the "no concurrent writes" rule cannot be satisfied by
    a per-session lock.
    """

    def __init__(self, config: WebSecurityConfig | None = None) -> None:
        self.config = config or WebSecurityConfig()
        self._write_lock = _WriteLock()

    # -- startup ----------------------------------------------------------

    def check_bind(self) -> None:
        """Refuse a non-loopback bind.

        This release is a local, single-user surface. A bind on a
        routable address would expose it to the network, which the
        charter does not authorize.
        """
        host = (self.config.bind_host or "").strip().lower()
        if host not in LOOPBACK_HOSTS:
            raise WebSecurityError(
                WebSecurityCode.BIND_NOT_LOOPBACK,
                f"the local web adapter may only bind a loopback address, not {host!r}",
            )

    # -- per request ------------------------------------------------------

    def check_method(self, method: str) -> None:
        """Refuse a method the surface does not offer."""
        if method.upper() not in self.config.allowed_methods:
            raise WebSecurityError(
                WebSecurityCode.METHOD_NOT_ALLOWED,
                f"method {method.upper()!r} is not offered",
            )

    def check_host(self, headers: Mapping[str, Any]) -> None:
        """The Host header must be exactly one of the allowed values."""
        host = _header(headers, "host")
        if not host:
            raise WebSecurityError(
                WebSecurityCode.HOST_NOT_ALLOWED, "the request carries no Host header",
            )
        if host not in self.config.hosts():
            raise WebSecurityError(
                WebSecurityCode.HOST_NOT_ALLOWED, "the request Host is not allowed",
            )

    def check_origin(self, headers: Mapping[str, Any], *, required: bool = True) -> None:
        """The Origin must match exactly.

        A cross-origin browser request carries an Origin the browser
        does not let the page forge. Same-origin requests carry no
        Origin at all, which is why an empty Origin is accepted only for
        a request that is *not* a cross-origin one - and a mutating
        request must still present the CSRF token.
        """
        origin = _header(headers, "origin")
        if not origin:
            if required:
                raise WebSecurityError(
                    WebSecurityCode.ORIGIN_REQUIRED,
                    "the request carries no Origin header",
                )
            return
        allowed = self.config.allowed_origins
        if not allowed:
            # Same-origin only: the Origin must be the request's own Host.
            host = _header(headers, "host")
            if origin != f"http://{host}" and origin != f"https://{host}":
                raise WebSecurityError(
                    WebSecurityCode.ORIGIN_NOT_ALLOWED,
                    "the request Origin is not allowed",
                )
            return
        if origin not in allowed:
            raise WebSecurityError(
                WebSecurityCode.ORIGIN_NOT_ALLOWED, "the request Origin is not allowed",
            )

    def check_csrf(self, headers: Mapping[str, Any], method: str) -> None:
        """A mutating request must present the local CSRF token."""
        if method.upper() not in MUTATING_METHODS:
            return
        expected = self.config.csrf_token
        if not expected:
            raise WebSecurityError(
                WebSecurityCode.CSRF_INVALID,
                "no local token is configured, so mutations are not accepted",
            )
        presented = _header(headers, "x-csrf-token") or _header(headers, "csrf-token")
        if not presented or not hmac.compare_digest(presented, expected):
            raise WebSecurityError(
                WebSecurityCode.CSRF_INVALID, "the request token is missing or wrong",
            )

    def check_query(self, query: str | Mapping[str, Any] | None) -> None:
        """No credential may travel in a query string.

        Query strings end up in logs, browser history and Referer
        headers. A token in one is a token that leaks.
        """
        if not query:
            return
        if isinstance(query, Mapping):
            keys = [str(key).lower() for key in query]
        else:
            keys = [
                part.split("=", 1)[0].lower()
                for part in str(query).lstrip("?").split("&")
                if part
            ]
        for key in keys:
            if key in _CREDENTIAL_QUERY_KEYS:
                raise WebSecurityError(
                    WebSecurityCode.CREDENTIAL_IN_QUERY,
                    "a credential must not be carried in the query string",
                )

    def check_body_size(self, size: int) -> None:
        """Refuse a body over the bound."""
        if size > self.config.max_body_bytes:
            raise WebSecurityError(
                WebSecurityCode.BODY_TOO_LARGE,
                f"the request body is over {self.config.max_body_bytes} bytes",
            )

    def check_request(
        self,
        *,
        method: str,
        headers: Mapping[str, Any],
        query: str | Mapping[str, Any] | None = None,
        body_bytes: int = 0,
        require_origin: bool | None = None,
    ) -> None:
        """Run every per-request control, in the order a request would meet them.

        An Origin is required for a **mutating** request: a browser sends
        it for every state-changing request, so its absence means the
        request did not come from a browser form and must not be
        honoured. A safe request carries no Origin when it is same
        origin - that is what "same origin" means on the wire - so
        requiring one there would break the browser without adding
        protection.
        """
        mutating = method.upper() in MUTATING_METHODS
        self.check_method(method)
        self.check_host(headers)
        self.check_origin(
            headers,
            required=mutating if require_origin is None else require_origin,
        )
        self.check_csrf(headers, method)
        self.check_query(query)
        self.check_body_size(body_bytes)

    # -- bounded views ----------------------------------------------------

    def check_history(self, items: Any) -> None:
        """Refuse a history projection over the bound."""
        try:
            count = len(items)
        except TypeError:
            count = 0
        if count > self.config.max_history_items:
            raise WebSecurityError(
                WebSecurityCode.HISTORY_TOO_LONG,
                f"the history is over {self.config.max_history_items} items",
            )

    def check_stream_buffer(self, size: int) -> None:
        """Refuse a stream buffer over the bound."""
        if size > self.config.max_stream_buffer_bytes:
            raise WebSecurityError(
                WebSecurityCode.STREAM_BUFFER_TOO_LARGE,
                f"the stream buffer is over {self.config.max_stream_buffer_bytes} bytes",
            )

    # -- write admission --------------------------------------------------

    @property
    def write_lock(self) -> _WriteLock:
        """The process-wide write admission."""
        return self._write_lock

    def allows_concurrent_writes(self) -> bool:
        return self.config.allow_concurrent_writes


class _WriteLock:
    """A process-wide admission for mutating requests.

    Until the storage concurrency question is settled, mutating
    requests are serialised. This is deliberately **not** a per-session
    lock: a session lock is not a database fix.
    """

    def __init__(self) -> None:
        self._lock = __import__("asyncio").Lock()
        self._held = 0

    async def __aenter__(self) -> _WriteLock:
        await self._lock.acquire()
        self._held += 1
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._held -= 1
        self._lock.release()

    @property
    def held(self) -> int:
        """How many writers are inside the admission right now."""
        return self._held


def redact_query(query: str | Mapping[str, Any] | None) -> str:
    """A query string with any credential-looking value removed.

    Used for logging and error reports: the *shape* of the request is
    useful, the secret in it is not.
    """
    if not query:
        return ""
    if isinstance(query, Mapping):
        parts = [
            f"{key}=<redacted>" if str(key).lower() in _CREDENTIAL_QUERY_KEYS
            else f"{key}={value}"
            for key, value in query.items()
        ]
        return "&".join(parts)
    out = []
    for part in str(query).lstrip("?").split("&"):
        if not part:
            continue
        key = part.partition("=")[0]
        out.append(
            f"{key}=<redacted>" if key.lower() in _CREDENTIAL_QUERY_KEYS else part
        )
    return "&".join(out)


# The header names the boundary reads. Kept here so the transport layer
# and the guard agree on one list.
READ_HEADERS = ("host", "origin", "x-csrf-token", "content-length")

_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]+(:\d+)?$|\[[0-9A-Fa-f:]+\](:\d+)?$")
