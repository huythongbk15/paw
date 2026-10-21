"""The local web surface, driven directly as an ASGI application.

An ASGI application is a callable, so the surface is proved here
**without a server, a socket, a test client or a network**. That is the
property the transport decision bought: the same suite that proves the
security boundary also proves the routes.

What is pinned:

* every route answers, and every answer carries the security headers;
* the surface is **read-only** - there is no mutating route, and a
  mutation is refused rather than silently ignored;
* a request that the boundary refuses never reaches a handler;
* an unknown route, an unknown task and an unknown inspect kind are
  typed refusals with stable codes, not stack traces;
* the payload is bounded and redacted.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from paw.core.storage import db, set_db_path
from paw.web.asgi import CONTENT_SECURITY_POLICY, WebApplication
from paw.web.routes import build_application
from paw.web.security import LocalWebGuard, WebSecurityConfig, WebSecurityError


class _Driver:
    """Drives an ASGI application the way a server would."""

    def __init__(self, app: WebApplication) -> None:
        self.app = app
        self.sent: list[dict[str, Any]] = []
        self.received: list[dict[str, Any]] = []

    async def _receive(self) -> dict[str, Any]:
        if self.received:
            return self.received.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: str = "",
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> tuple[int, dict[str, str], Any]:
        raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": query.encode("latin-1"),
            "headers": raw_headers,
        }
        self.sent = []
        self.received = [{"type": "http.request", "body": body, "more_body": False}]
        await self.app(scope, self._receive, self._send)
        start = next((m for m in self.sent if m["type"] == "http.response.start"), None)
        end = next((m for m in self.sent if m["type"] == "http.response.body"), None)
        assert start is not None, "the application sent no response start"
        headers_out = {
            k.decode(): v.decode() for k, v in start.get("headers", [])
        }
        raw = (end or {}).get("body", b"")
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = raw
        return start["status"], headers_out, parsed


def _app(**kwargs) -> WebApplication:
    guard = LocalWebGuard(WebSecurityConfig(csrf_token="tok", **kwargs.pop("config", {})))
    return build_application(guard=guard, **kwargs)


# ── 1. The routes ───────────────────────────────────────────────────────


class TestTheRoutes:
    @pytest.mark.asyncio
    async def test_capabilities(self):
        driver = _Driver(_app())
        status, _headers, body = await driver.request(
            "GET", "/api/v1/capabilities", headers={"Host": "127.0.0.1:8765"},
        )
        assert status == 200
        assert body["supported"]
        assert body["mutations_enabled"] is False

    @pytest.mark.asyncio
    async def test_health_carries_the_build_identity(self):
        driver = _Driver(_app(revision="abc123", schema_version=8))
        status, _headers, body = await driver.request(
            "GET", "/api/v1/health", headers={"Host": "127.0.0.1:8765"},
        )
        assert status == 200
        assert body["revision"] == "abc123"
        assert body["schema_version"] == 8

    @pytest.mark.asyncio
    async def test_an_unknown_route_is_a_typed_refusal(self):
        driver = _Driver(_app())
        status, _headers, body = await driver.request(
            "GET", "/api/v1/nope", headers={"Host": "127.0.0.1:8765"},
        )
        assert status == 404
        assert body["code"] == "web.route_not_found"
        assert "Traceback" not in json.dumps(body)

    @pytest.mark.asyncio
    async def test_an_unknown_task_is_a_typed_refusal(self):
        await set_db_path("/tmp/paw-web-test-unknown.db")
        await db.initialize()
        driver = _Driver(_app())
        status, _headers, body = await driver.request(
            "GET", "/api/v1/tasks/does-not-exist",
            headers={"Host": "127.0.0.1:8765"},
        )
        assert status == 404
        assert body["code"] == "web.task_not_found"
        await db.close()


# ── 2. The surface is read-only ─────────────────────────────────────────


class TestTheSurfaceIsReadOnly:
    @pytest.mark.asyncio
    async def test_there_is_no_mutating_route(self):
        app = _app()
        for route in app.routes:
            assert route.method == "GET", route.pattern

    @pytest.mark.asyncio
    async def test_a_mutation_is_refused_by_the_boundary(self):
        """A POST has no route *and* no token, so it cannot happen."""
        driver = _Driver(_app())
        status, _headers, body = await driver.request(
            "POST", "/api/v1/sessions",
            headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"},
        )
        assert status == 400
        assert body["code"] in ("web.csrf_invalid", "web.route_not_found")

    @pytest.mark.asyncio
    async def test_a_mutation_with_a_token_still_has_no_route(self):
        """Even a valid token cannot reach a mutation: there is no route."""
        driver = _Driver(_app())
        status, _headers, body = await driver.request(
            "POST", "/api/v1/sessions",
            headers={
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:8765",
                "X-CSRF-Token": "tok",
            },
        )
        assert status == 404
        assert body["code"] == "web.route_not_found"


# ── 3. The boundary runs first ──────────────────────────────────────────


class TestTheBoundaryRunsFirst:
    @pytest.mark.asyncio
    async def test_a_bad_host_never_reaches_a_handler(self):
        driver = _Driver(_app())
        status, _headers, body = await driver.request(
            "GET", "/api/v1/capabilities", headers={"Host": "evil.example"},
        )
        assert status == 400
        assert body["code"] == "web.host_not_allowed"

    @pytest.mark.asyncio
    async def test_a_credential_in_the_query_never_reaches_a_handler(self):
        driver = _Driver(_app())
        status, _headers, body = await driver.request(
            "GET", "/api/v1/sessions", query="token=supersecret",
            headers={"Host": "127.0.0.1:8765"},
        )
        assert status == 400
        assert body["code"] == "web.credential_in_query"
        assert "supersecret" not in json.dumps(body)

    @pytest.mark.asyncio
    async def test_an_oversized_body_never_reaches_a_handler(self):
        driver = _Driver(_app(config={"max_body_bytes": 16}))
        status, _headers, body = await driver.request(
            "GET", "/api/v1/capabilities",
            headers={"Host": "127.0.0.1:8765"},
            body=b"x" * 100,
        )
        assert status == 400
        assert body["code"] == "web.body_too_large"


# ── 4. Every response carries the security headers ─────────────────────


class TestTheResponseHeaders:
    @pytest.mark.asyncio
    async def test_the_headers_are_present(self):
        driver = _Driver(_app())
        _status, headers, _body = await driver.request(
            "GET", "/api/v1/capabilities", headers={"Host": "127.0.0.1:8765"},
        )
        assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        assert headers["cache-control"] == "no-store"
        assert headers["x-correlation-id"]

    @pytest.mark.asyncio
    async def test_a_refusal_carries_the_headers_too(self):
        driver = _Driver(_app())
        _status, headers, _body = await driver.request(
            "GET", "/api/v1/capabilities", headers={"Host": "evil.example"},
        )
        assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert headers["x-correlation-id"]

    @pytest.mark.asyncio
    async def test_a_correlation_id_is_echoed_when_the_caller_sends_one(self):
        driver = _Driver(_app())
        _status, headers, _body = await driver.request(
            "GET", "/api/v1/capabilities",
            headers={"Host": "127.0.0.1:8765", "X-Correlation-Id": "abc-123"},
        )
        assert headers["x-correlation-id"] == "abc-123"


# ── 5. The payload is bounded ──────────────────────────────────────────


class TestThePayloadIsBounded:
    @pytest.mark.asyncio
    async def test_a_limit_is_clamped_not_trusted(self):
        await set_db_path("/tmp/paw-web-test-limit.db")
        await db.initialize()
        from paw.application import web_projection

        page = await web_projection.sessions_projection(limit=100000)
        assert page.limit <= web_projection.MAX_LIMIT

        page = await web_projection.sessions_projection(limit="not a number")
        assert page.limit == web_projection.DEFAULT_LIMIT

        page = await web_projection.sessions_projection(limit=-5)
        assert page.limit == web_projection.DEFAULT_LIMIT
        await db.close()

    @pytest.mark.asyncio
    async def test_a_credential_shaped_field_is_redacted(self):
        from paw.application.web_projection import redact

        out = redact({"api_key": "sk-secret", "nested": {"token": "t"}, "ok": 1})
        assert out["api_key"] == "<redacted>"
        assert out["nested"]["token"] == "<redacted>"
        assert out["ok"] == 1
