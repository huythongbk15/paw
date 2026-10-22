"""The local web server: one foreground ASGI process, on loopback.

This is the whole deployment. A local, single-user, foreground process
that serves the packaged shell and the read-only surface, and accepts the
two mutations - on a loopback address, with the boundary in front of
everything.

The server is **optional**. It is the only part of the surface that
needs a package the core does not: an ASGI server. The application
itself - the routes, the boundary, the projections - has no such
dependency, and is proved by driving the ASGI callable directly.

The token is minted here, per process, and handed to the shell over the
same origin. The shell keeps it in memory; it is never in a query string
and never in browser storage.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

__all__ = ["LocalWebServer", "serve"]


class LocalWebServer:
    """The local web adapter.

    It owns the token, the guard and the application. Nothing else in
    PAW knows about the web surface.
    """

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        provider_mode: str = "local",
        session_id: str | None = None,
        host: str = "127.0.0.1",
        port: int = 8765,
        revision: str = "",
        schema_version: int = 0,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.provider_mode = provider_mode
        self.session_id = session_id
        self.host = host
        self.port = port
        self.revision = revision
        self.schema_version = schema_version
        #: A fresh token per process. A page loaded before a restart has a
        #: stale token and its mutations are refused - which is correct.
        self.csrf_token = secrets.token_urlsafe(32)
        self._chat: Any = None
        self._app: Any = None

    async def _build_chat(self) -> Any:
        from ..application.chat import ChatService

        service = ChatService(
            provider_mode=self.provider_mode,
            workspace_root=self.workspace_root,
        )
        await service.open(session_id=self.session_id)
        return service

    def build(self, *, chat: Any = None) -> Any:
        """The ASGI application, with its boundary and its routes."""
        from .routes import build_application
        from .security import LocalWebGuard, WebSecurityConfig

        guard = LocalWebGuard(
            WebSecurityConfig(
                bind_host=self.host,
                bind_port=self.port,
                csrf_token=self.csrf_token,
            )
        )
        self._app = build_application(
            guard=guard,
            revision=self.revision,
            schema_version=self.schema_version,
            csrf_token=self.csrf_token,
            chat=chat,
        )
        return self._app

    async def serve(self) -> None:
        """Serve until interrupted. Foreground, one process, loopback."""
        try:
            import uvicorn
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "the local web server needs an ASGI server: "
                "install the optional extra with `pip install 'paw[web]'`"
            ) from exc

        chat = await self._build_chat()
        app = self.build(chat=chat)
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        try:
            await server.serve()
        finally:
            await chat.close()


def serve(**kwargs: Any) -> None:
    """Run the local web server (blocking)."""
    import asyncio

    server = LocalWebServer(**kwargs)
    asyncio.run(server.serve())
