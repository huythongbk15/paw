"""The local web surface: a fixed, read-only route table.

Every route is a ``GET``. The mutating routes are deliberately absent:
the write admission is process-wide until the storage concurrency
question (F02) is settled, and a surface that offers a mutation cannot
honestly promise one effect at a time.

The handlers are thin: they take the request context, call a projection
from ``paw.application.web_projection`` and render the answer. The
projections own the bounding, the redaction and the error codes.
"""

from __future__ import annotations

from typing import Any

from ..application import web_projection
from ..application.web_projection import ProjectionError
from .asgi import Route, WebApplication, WebRequestContext, WebResponse

__all__ = ["build_application"]

API = "/api/v1"


def _error(exc: ProjectionError) -> WebResponse:
    """Render a projection refusal with a stable code."""
    status = 404 if exc.code.endswith("_not_found") else 400
    return WebResponse(status=status, body={"code": exc.code, "message": str(exc).split(": ", 1)[-1]})


def _not_found(message: str = "no such route") -> WebResponse:
    return WebResponse(
        status=404, body={"code": "web.route_not_found", "message": message},
    )


async def _capabilities(_ctx: WebRequestContext) -> WebResponse:
    return WebResponse(body=web_projection.capabilities_projection())


def _health_handler(revision: str, schema_version: int):
    """The health view, bound to this build's identity."""

    async def _health(_ctx: WebRequestContext) -> WebResponse:
        body = await web_projection.health_projection(
            revision=revision, schema_version=schema_version,
        )
        return WebResponse(body=body)

    return _health


async def _sessions(ctx: WebRequestContext) -> WebResponse:
    page = await web_projection.sessions_projection(
        limit=ctx.query_one("limit"), cursor=ctx.query_one("cursor"),
    )
    return WebResponse(body=page.to_dict())


async def _session(ctx: WebRequestContext) -> WebResponse:
    try:
        body = await web_projection.session_projection(ctx.param("session_id"))
    except ProjectionError as exc:
        return _error(exc)
    return WebResponse(body=body)


async def _messages(ctx: WebRequestContext) -> WebResponse:
    try:
        page = await web_projection.messages_projection(
            ctx.param("session_id"),
            limit=ctx.query_one("limit"), cursor=ctx.query_one("cursor"),
        )
    except ProjectionError as exc:
        return _error(exc)
    return WebResponse(body=page.to_dict())


async def _task(ctx: WebRequestContext) -> WebResponse:
    try:
        body = await web_projection.task_projection(ctx.param("task_id"))
    except ProjectionError as exc:
        return _error(exc)
    return WebResponse(body=body)


async def _events(ctx: WebRequestContext) -> WebResponse:
    try:
        page = await web_projection.tasks_events_projection(
            ctx.param("task_id"),
            limit=ctx.query_one("limit"), cursor=ctx.query_one("cursor"),
        )
    except ProjectionError as exc:
        return _error(exc)
    return WebResponse(body=page.to_dict())


async def _inspect(ctx: WebRequestContext) -> WebResponse:
    try:
        body = await web_projection.inspect_projection(
            ctx.param("task_id"), ctx.param("kind"),
        )
    except ProjectionError as exc:
        return _error(exc)
    return WebResponse(body=body)


def build_application(
    *,
    guard: Any = None,
    revision: str = "",
    schema_version: int = 0,
) -> WebApplication:
    """The application, with its read-only routes."""
    app = WebApplication(
        guard=guard,
        revision=revision,
        schema_version=schema_version,
    )
    app.add(Route("GET", f"{API}/capabilities", _capabilities, "capabilities"))
    app.add(Route("GET", f"{API}/health", _health_handler(revision, schema_version), "health"))
    app.add(Route("GET", f"{API}/sessions", _sessions, "sessions"))
    app.add(Route("GET", f"{API}/sessions/{{session_id}}", _session, "session"))
    app.add(
        Route("GET", f"{API}/sessions/{{session_id}}/messages", _messages, "messages"),
    )
    app.add(Route("GET", f"{API}/tasks/{{task_id}}", _task, "task"))
    app.add(Route("GET", f"{API}/tasks/{{task_id}}/events", _events, "events"))
    app.add(
        Route("GET", f"{API}/tasks/{{task_id}}/inspect/{{kind}}", _inspect, "inspect"),
    )
    return app
