"""The local web transport: a minimal ASGI application.

**No framework.** The reasons are recorded in
``docs/adr/0001-local-web-adapter.md``; the short version is that the
surface is read-only and small, the safety boundary already owns every
rule that matters, and ASGI is the standard interface - so the adapter
stays a thin shell and the *server* remains an optional runtime extra
rather than a dependency of the core.

The application is provable without a server. An ASGI application is a
callable::

    async def app(scope, receive, send) -> None

so a test drives it directly with a scope, a receive and a send. That is
how ``tests/test_local_web_asgi_contract.py`` proves the routes, and it
is why the surface needs no test client, no second dependency and no
network.

What it does:

* every request meets the security boundary first;
* the routes are a fixed, read-only table;
* every response carries a stable content type, a correlation id and a
  Content-Security-Policy;
* every refusal is the boundary's stable code with a safe message.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from .security import (
    LocalWebGuard,
    WebSecurityCode,
    WebSecurityConfig,
    WebSecurityError,
)

__all__ = [
    "Route",
    "WebApplication",
    "WebRequestContext",
    "WebResponse",
]

# The Content-Security-Policy every response carries. The surface is
# same-origin, packaged assets only, and it never executes remote code.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)

# The API prefix. Everything is under it; the root serves the shell.
API_PREFIX = "/api/v1"

_SEGMENT = re.compile(r"^\{([a-zA-Z_][a-zA-Z0-9_]*)\}$")


@dataclass(frozen=True)
class Route:
    """One route: a method, a path pattern and a handler."""

    method: str
    pattern: str
    handler: Callable[[WebRequestContext], Awaitable[WebResponse]]
    name: str = ""

    def match(self, path: str) -> dict[str, str] | None:
        """Match a path, returning its parameters, or None."""
        route_parts = [p for p in self.pattern.strip("/").split("/") if p]
        path_parts = [p for p in path.strip("/").split("/") if p]
        if len(route_parts) != len(path_parts):
            return None
        params: dict[str, str] = {}
        for route_part, path_part in zip(route_parts, path_parts, strict=True):
            match = _SEGMENT.match(route_part)
            if match:
                if not path_part:
                    return None
                params[match.group(1)] = path_part
                continue
            if route_part != path_part:
                return None
        return params


@dataclass
class WebResponse:
    """A response the transport renders."""

    status: int = 200
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str = "application/json"

    def rendered(self) -> bytes:
        if self.body is None:
            return b""
        if isinstance(self.body, bytes):
            return self.body
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return json.dumps(self.body, default=str, ensure_ascii=False).encode("utf-8")


@dataclass
class WebRequestContext:
    """What a handler is given."""

    method: str
    path: str
    params: dict[str, str]
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes
    correlation_id: str

    def param(self, name: str) -> str:
        return self.params.get(name, "")

    def query_one(self, name: str, default: str = "") -> str:
        values = self.query.get(name) or []
        return values[0] if values else default


class WebApplication:
    """The local web application.

    One instance per process. It owns the guard, so the write admission
    and the security rules are process-wide rather than per request.
    """

    def __init__(
        self,
        routes: list[Route] | None = None,
        *,
        guard: LocalWebGuard | None = None,
        static_dir: Path | None = None,
        revision: str = "",
        schema_version: int = 0,
    ) -> None:
        self.guard = guard or LocalWebGuard(WebSecurityConfig())
        self.routes = list(routes or [])
        self.static_dir = static_dir
        self.revision = revision
        self.schema_version = schema_version
        self._static_cache: dict[str, bytes] = {}

    # -- routing ----------------------------------------------------------

    def add(self, route: Route) -> None:
        self.routes.append(route)

    def _match(self, method: str, path: str) -> tuple[Route, dict[str, str]] | None:
        for route in self.routes:
            if route.method.upper() != method.upper():
                continue
            params = route.match(path)
            if params is not None:
                return route, params
        return None

    # -- the ASGI callable ------------------------------------------------

    async def __call__(self, scope: Mapping[str, Any], receive: Any, send: Any) -> None:
        """The ASGI entry point."""
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._lifespan(receive, send)
            return
        if scope_type != "http":
            return
        await self._http(scope, receive, send)

    async def _lifespan(self, receive: Any, send: Any) -> None:
        """Own the startup and shutdown of what the adapter holds.

        The adapter owns the provider and database lifecycle; a lifespan
        server asks it to start and stop them.
        """
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await self.on_startup()
                except Exception as exc:  # pragma: no cover - defensive
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                try:
                    await self.on_shutdown()
                except Exception as exc:  # pragma: no cover - defensive
                    await send({"type": "lifespan.shutdown.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def on_startup(self) -> None:
        """Start what the adapter owns. The default owns nothing."""

    async def on_shutdown(self) -> None:
        """Stop what the adapter owns. The default owns nothing."""

    async def _http(self, scope: Mapping[str, Any], receive: Any, send: Any) -> None:
        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", "/"))
        headers = _headers(scope.get("headers") or [])
        raw_query = scope.get("query_string", "") or ""
        if isinstance(raw_query, bytes):
            raw_query = raw_query.decode("latin-1")
        query = parse_qs(str(raw_query))
        correlation_id = headers.get("x-correlation-id") or _correlation_id()

        body = b""
        try:
            body = await self._read_body(receive)
        except WebSecurityError as exc:
            await self._send_error(send, exc, correlation_id)
            return

        try:
            self.guard.check_request(
                method=method,
                headers=headers,
                query=query,
                body_bytes=len(body),
            )
        except WebSecurityError as exc:
            await self._send_error(send, exc, correlation_id)
            return

        matched = self._match(method, path)
        if matched is None:
            await self._send(
                send,
                WebResponse(
                    status=404,
                    body={"code": "web.route_not_found", "message": "no such route"},
                ),
                correlation_id,
            )
            return

        route, params = matched
        context = WebRequestContext(
            method=method,
            path=path,
            params=params,
            query=query,
            headers=headers,
            body=body,
            correlation_id=correlation_id,
        )
        try:
            response = await route.handler(context)
        except WebSecurityError as exc:
            await self._send_error(send, exc, correlation_id)
            return
        except Exception:  # pragma: no cover - defensive
            # A handler failure is a safe refusal, not a stack trace.
            await self._send(
                send,
                WebResponse(
                    status=500,
                    body={
                        "code": "web.internal_error",
                        "message": "the request could not be completed",
                    },
                ),
                correlation_id,
            )
            return
        await self._send(send, response, correlation_id)

    async def _read_body(self, receive: Any) -> bytes:
        """Read the body, bounded. The bound is the boundary's."""
        limit = self.guard.config.max_body_bytes
        body = b""
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body") or b""
            body += chunk
            if len(body) > limit:
                raise WebSecurityError(
                    WebSecurityCode.BODY_TOO_LARGE,
                    f"the request body is over {limit} bytes",
                )
            if not message.get("more_body"):
                break
        return body

    async def _send_error(
        self, send: Any, exc: WebSecurityError, correlation_id: str,
    ) -> None:
        await self._send(
            send,
            WebResponse(status=400, body=exc.to_dict()),
            correlation_id,
        )

    async def _send(
        self, send: Any, response: WebResponse, correlation_id: str,
    ) -> None:
        """Render a response, with the headers every response carries."""
        body = response.rendered()
        headers = {
            "content-type": f"{response.content_type}; charset=utf-8",
            "content-length": str(len(body)),
            "content-security-policy": CONTENT_SECURITY_POLICY,
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "referrer-policy": "no-referrer",
            "x-correlation-id": correlation_id,
            "cache-control": "no-store",
            **response.headers,
        }
        await send({
            "type": "http.response.start",
            "status": response.status,
            "headers": [
                (name.encode("latin-1"), value.encode("latin-1"))
                for name, value in headers.items()
            ],
        })
        await send({"type": "http.response.body", "body": body})


def _headers(raw: Any) -> dict[str, str]:
    """ASGI headers (a list of byte pairs) as a case-insensitive dict."""
    out: dict[str, str] = {}
    for name, value in raw or []:
        if isinstance(name, bytes):
            name = name.decode("latin-1")
        if isinstance(value, bytes):
            value = value.decode("latin-1")
        out[str(name).lower()] = str(value)
    return out


def _correlation_id() -> str:
    import uuid

    return uuid.uuid4().hex[:16]
