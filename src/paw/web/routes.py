"""The local web surface: a fixed route table.

Every read is a ``GET``. The mutations are deliberately narrow: they are
the two operations a person needs to *drive* the agent - send a turn, and
answer the pending approval. Everything else is either a projection of
durable state or not offered at all.

A mutation is admitted only after the boundary has checked it: the exact
``Host``, the exact ``Origin``, the local CSRF token, the body bound, and
the absence of a credential in the query string. The **request key** then
makes the turn idempotent: it determines the task's identity, so a retry
resolves to the same durable operation rather than a second attempt.
"""

from __future__ import annotations

import json
from typing import Any

from ..application import web_projection
from ..application.web_projection import ProjectionError
from .asgi import Route, WebApplication, WebRequestContext, WebRequestError, WebResponse
from .requests import RequestKeyPolicy

__all__ = ["build_application"]

API = "/api/v1"

#: The request key policy. A key identifies a turn, so it is bounded and
#: has a shape.
KEY_POLICY = RequestKeyPolicy()


def _error(exc: ProjectionError) -> WebResponse:
    """Render a projection refusal with a stable code."""
    status = 404 if exc.code.endswith("_not_found") else 400
    return WebResponse(status=status, body={"code": exc.code, "message": str(exc).split(": ", 1)[-1]})


def _body(ctx: WebRequestContext) -> dict[str, Any]:
    """The request body as an object, or a typed refusal."""
    if not ctx.body:
        return {}
    try:
        payload = json.loads(ctx.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise WebRequestError(
            "web.body_not_json", "the request body is not valid JSON",
        ) from None
    if not isinstance(payload, dict):
        raise WebRequestError(
            "web.body_not_object", "the request body must be a JSON object",
        )
    return payload


async def _capabilities(_ctx: WebRequestContext) -> WebResponse:
    return WebResponse(body=web_projection.capabilities_projection())


def _health_handler(app_holder: dict[str, WebApplication]):
    """The build's identity and its diagnostics."""

    async def _handler(_ctx: WebRequestContext) -> WebResponse:
        app = app_holder["app"]
        body = await web_projection.health_projection(
            revision=app.revision,
            schema_version=app.schema_version,
        )
        return WebResponse(body=body)

    return _handler


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


# --- the mutations --------------------------------------------------------


def _csrf_handler(app_holder: dict[str, WebApplication]):
    """The local CSRF token, for the shell to hold in memory."""

    async def _handler(_ctx: WebRequestContext) -> WebResponse:
        app = app_holder["app"]
        if not app.csrf_token:
            raise WebRequestError(
                "web.csrf_unavailable",
                "this surface has no local token, so it does not accept mutations",
                status=503,
            )
        return WebResponse(body={"csrf_token": app.csrf_token})

    return _handler


def _current_session_handler(chat: Any):
    """The session this surface drives."""

    async def _handler(_ctx: WebRequestContext) -> WebResponse:
        session = getattr(chat, "session", None)
        if session is None:
            raise WebRequestError(
                "web.session_not_found", "this surface has no session",
                status=404,
            )
        body = await web_projection.session_projection(session.session_id)
        return WebResponse(body=body)

    return _handler


def _send_message_handler(chat: Any):
    """Send one turn. The request key makes it idempotent."""

    async def _handler(ctx: WebRequestContext) -> WebResponse:
        payload = _body(ctx)
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise WebRequestError("web.text_required", "the request needs a message")
        raw_key = payload.get("request_key")
        try:
            key = KEY_POLICY.validate(raw_key)
        except ValueError as exc:
            raise WebRequestError("web.request_key_invalid", str(exc)) from None
        reply = await chat.send(text, request_key=key)
        return WebResponse(body=reply.to_dict())

    return _handler


def _decide_approval_handler(chat: Any):
    """Answer the pending approval for a session."""

    async def _handler(ctx: WebRequestContext) -> WebResponse:
        from ..core.approval import ApprovalStatus, ApprovalStore

        payload = _body(ctx)
        approval_id = payload.get("approval_id")
        decision = str(payload.get("decision", "")).strip().lower()
        if not isinstance(approval_id, str) or not approval_id:
            raise WebRequestError(
                "web.approval_id_required", "the request needs the approval id",
            )
        if decision not in ("approve", "deny"):
            raise WebRequestError(
                "web.decision_invalid", "the decision must be approve or deny",
            )
        try:
            KEY_POLICY.validate(payload.get("request_key"))
        except ValueError as exc:
            raise WebRequestError("web.request_key_invalid", str(exc)) from None
        approval = await ApprovalStore.get(approval_id)
        if approval is None:
            raise WebRequestError(
                "web.approval_not_found", "no such approval", status=404,
            )
        if approval.status != ApprovalStatus.PENDING:
            raise WebRequestError(
                "web.approval_not_pending", "that approval was already decided",
            )
        if decision == "approve":
            # The chat service owns the effect: it approves the exact
            # operation and resumes the task that was waiting for it.
            reply = await chat.approve(approval_id)
            return WebResponse(body=reply.to_dict())
        await ApprovalStore.deny(approval_id, "web-human")
        return WebResponse(body={"approval_id": approval_id, "decision": decision})

    return _handler


# --- the packaged shell ---------------------------------------------------


def _asset_response(request_path: str) -> WebResponse:
    """A packaged asset, resolved under the asset policy."""
    from .assets import AssetError, AssetPolicy

    try:
        asset = AssetPolicy().resolve(request_path)
    except AssetError as exc:
        return WebResponse(status=404, body=exc.to_dict())
    return WebResponse(
        status=200,
        body=asset.body,
        content_type=asset.content_type,
        headers={"etag": f'"{asset.etag}"'},
    )


async def _index(_ctx: WebRequestContext) -> WebResponse:
    """The packaged shell."""
    return _asset_response("index.html")


async def _asset(ctx: WebRequestContext) -> WebResponse:
    """A packaged asset, named by the request path."""
    return _asset_response(ctx.param("asset_path"))


# --- the application ------------------------------------------------------


def build_application(
    *,
    guard: Any = None,
    revision: str = "",
    schema_version: int = 0,
    csrf_token: str = "",
    chat: Any = None,
) -> WebApplication:
    """The application, with its routes and the packaged shell."""
    app = WebApplication(
        guard=guard,
        revision=revision,
        schema_version=schema_version,
        csrf_token=csrf_token,
    )
    app.add(Route("GET", f"{API}/capabilities", _capabilities, "capabilities"))
    app.add(Route("GET", f"{API}/health", _health_handler({"app": app}), "health"))
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
    # The local token the shell needs to make a mutation.
    app.add(
        Route("GET", f"{API}/csrf-token", _csrf_handler({"app": app}), "csrf-token"),
    )
    # The mutations. They are the two operations a person needs to drive
    # the agent: send a turn, and answer the pending approval.
    if chat is not None:
        app.add(
            Route("GET", f"{API}/session", _current_session_handler(chat), "session"),
        )
        app.add(
            Route(
                "POST", f"{API}/sessions/{{session_id}}/messages",
                _send_message_handler(chat), "send-message",
            ),
        )
        app.add(
            Route(
                "POST", f"{API}/sessions/{{session_id}}/approvals",
                _decide_approval_handler(chat), "decide-approval",
            ),
        )
    # The packaged shell. It is same-origin, carries no credential in a
    # URL, and the asset policy refuses anything outside the package's own
    # static directory.
    app.add(Route("GET", "/", _index, "index"))
    app.add(Route("GET", "/index.html", _index, "index.html"))
    app.add(Route("GET", "/static/{asset_path*}", _asset, "asset"))
    return app
