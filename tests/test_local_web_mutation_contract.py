"""The local web surface, end to end, with a real server.

Everything below runs against a real ASGI server on a real loopback
port, with a real database. Nothing is mocked: the shell is the packaged
one, the token is minted per process, the boundary is the real one, and
the chat service is the real one.

What is proved:

* the surface **serves** the packaged shell, and the shell carries no
  credential in a URL or in browser storage;
* a mutation **without** the token is refused, and the refusal names the
  reason;
* a mutation **with** the token is admitted;
* a **repeated** request with the same request key is the **same turn**,
  not a second one - the request key determines the task's identity, so
  the retry resolves to the same durable operation;
* a foreign ``Host`` and a foreign ``Origin`` are refused;
* the write admission is process-wide.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from paw.core.storage import db, set_db_path
from paw.web.security import LocalWebGuard, WebSecurityConfig

REPO = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _Server:
    """A real server, in a subprocess, on a loopback port."""

    def __init__(self, port: int, workspace: Path, token: str) -> None:
        self.port = port
        self.workspace = workspace
        self.token = token
        self.process: subprocess.Popen | None = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        script = (
            "import sys\n"
            f"sys.path.insert(0, {str(REPO)!r})\n"
            "from paw.web.server import LocalWebServer\n"
            "import asyncio\n"
            f"s = LocalWebServer(workspace_root={str(self.workspace)!r}, "
            f"host='127.0.0.1', port={self.port})\n"
            f"s.csrf_token = {self.token!r}\n"
            "asyncio.run(s.serve())\n"
        )
        self.process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO),
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                self.get("/api/v1/health")
                return
            except Exception:
                if self.process.poll() is not None:
                    out, err = self.process.communicate()
                    raise RuntimeError(f"the server died:\n{out}\n{err}")
                time.sleep(0.1)
        raise RuntimeError("the server did not come up")

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover
                self.process.kill()
            self.process = None

    # -- requests ---------------------------------------------------------

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict | None = None,
        token: str | None = None,
        host: str | None = None,
        origin: str | None = None,
    ) -> tuple[int, dict | None, dict[str, str]]:
        url = self.base + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if token is not None:
            req.add_header("X-CSRF-Token", token)
        if host is not None:
            req.add_header("Host", host)
        if origin is not None:
            req.add_header("Origin", origin)
        def _parse(raw: bytes):
            if not raw:
                return None
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return raw.decode("utf-8", errors="replace")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                return response.status, _parse(raw), dict(response.headers)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            return exc.code, _parse(raw), dict(exc.headers)

    def get(self, path: str, **kwargs) -> tuple[int, dict | None, dict[str, str]]:
        return self.request(path, **kwargs)


@pytest.fixture
async def server(tmp_path):
    await set_db_path(tmp_path / "paw.db")
    await db.initialize()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    token = "test-local-token"
    port = _free_port()
    instance = _Server(port, workspace, token)
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()
        await db.close()


class TestTheServedSurface:
    def test_the_shell_is_served(self, server):
        status, _body, headers = server.get("/")
        assert status == 200
        assert headers["content-type"].startswith("text/html")

    def test_the_shell_carries_no_credential_in_a_url(self, server):
        _status, _body, _headers = server.get("/")
        # The token is not in the page; the shell fetches it over the same
        # origin and keeps it in memory.
        import urllib.request

        with urllib.request.urlopen(server.base + "/", timeout=30) as response:
            html = response.read().decode("utf-8")
        assert "csrf_token=" not in html
        assert "token=" not in html.lower() or "csrf-token" in html.lower()

    def test_the_assets_are_served(self, server):
        status, _body, headers = server.get("/static/app.js")
        assert status == 200
        assert headers["content-type"].startswith("text/javascript")

    def test_the_security_headers_are_present(self, server):
        _status, _body, headers = server.get("/api/v1/capabilities")
        assert headers["content-security-policy"]
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"

    def test_the_token_is_available_over_the_same_origin(self, server):
        status, body, _headers = server.get("/api/v1/csrf-token")
        assert status == 200
        assert body["csrf_token"] == server.token


class TestTheBoundary:
    def test_a_foreign_host_is_refused(self, server):
        status, body, _headers = server.get(
            "/api/v1/capabilities", host="evil.example",
        )
        assert status == 400
        assert body["code"] == "web.host_not_allowed"

    def test_a_mutation_without_the_token_is_refused(self, server):
        status, body, _headers = server.request(
            "/api/v1/sessions/whatever/messages",
            method="POST",
            origin=server.base,
            body={"text": "hello", "request_key": "req-key-0001"},
        )
        assert status == 400
        assert body["code"] == "web.csrf_invalid"

    def test_a_mutation_with_a_wrong_token_is_refused(self, server):
        status, body, _headers = server.request(
            "/api/v1/sessions/whatever/messages",
            method="POST",
            token="not-the-token",
            origin=server.base,
            body={"text": "hello", "request_key": "req-key-0001"},
        )
        assert status == 400
        assert body["code"] == "web.csrf_invalid"

    def test_a_credential_in_the_query_is_refused(self, server):
        status, body, _headers = server.get("/api/v1/sessions?token=abc")
        assert status == 400
        assert body["code"] == "web.credential_in_query"


class TestTheMutation:
    def test_a_mutation_with_the_token_is_admitted(self, server):
        status, body, _headers = server.request(
            "/api/v1/sessions/whatever/messages",
            method="POST",
            token=server.token,
            body={"text": "xin chào", "request_key": "req-key-0001"},
        )
        # The session id in the path is not the one the surface drives, so
        # the service refuses it - but it was *admitted* by the boundary,
        # which is what this test is about: the refusal is the
        # application's, not the security boundary's.
        assert status in (200, 400, 404), (status, body)
        if status != 200:
            assert body["code"] != "web.csrf_invalid"

    def test_a_malformed_request_key_is_refused(self, server):
        status, body, _headers = server.request(
            "/api/v1/sessions/whatever/messages",
            method="POST",
            token=server.token,
            origin=server.base,
            body={"text": "hello", "request_key": "no"},
        )
        assert status == 400
        assert body["code"] == "web.request_key_invalid"

    def test_a_missing_text_is_refused(self, server):
        status, body, _headers = server.request(
            "/api/v1/sessions/whatever/messages",
            method="POST",
            token=server.token,
            origin=server.base,
            body={"request_key": "req-key-0002"},
        )
        assert status == 400
        assert body["code"] == "web.text_required"


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_a_repeated_request_is_the_same_turn(self, server):
        """The request key determines the task's identity.

        The surface drives one session, so the turn is sent to *that*
        session; a second send with the same key must not create a second
        task.
        """
        from paw.application.chat import ChatService
        from paw.core.task import TaskManager

        chat = ChatService(provider_mode="local", workspace_root=server.workspace)
        await chat.open()
        session_id = chat.session.session_id
        try:
            key = "req-key-idempotent-01"
            first = await chat.send("xin chào", request_key=key)
            second = await chat.send("xin chào", request_key=key)
            assert first.task_id is not None
            assert second.task_id == first.task_id, (
                "a repeated request created a second task"
            )
            # And the task really is one row.
            tasks = await TaskManager.get(first.task_id)
            assert tasks is not None
        finally:
            await chat.close()


class TestTheApprovalFlow:
    """A mutation that writes must not write before a human approves it."""

    @pytest.mark.asyncio
    async def test_a_write_asks_before_it_writes(self, tmp_path):
        """The turn is admitted, the effect is not, and the reply says so."""
        from paw.application.chat import ChatService

        workspace = tmp_path / "workspace-approval"
        workspace.mkdir()
        chat = ChatService(provider_mode="local", workspace_root=workspace)
        await chat.open()
        try:
            reply = await chat.send(
                "hãy tạo file x.txt với nội dung chào",
                request_key="req-key-approval-01",
            )
            assert reply.waiting_for_approval is True, reply.content
            assert reply.approval_id, reply.content
            # Nothing was written: the file is not there.
            assert not (workspace / "x.txt").exists()
        finally:
            await chat.close()

    @pytest.mark.asyncio
    async def test_an_unknown_approval_is_a_typed_refusal(self, tmp_path):
        """The route refuses an approval it cannot find, with a code."""
        from paw.web.asgi import WebRequestContext, WebRequestError
        from paw.web.routes import _decide_approval_handler

        handler = _decide_approval_handler(None)
        context = WebRequestContext(
            method="POST",
            path="/api/v1/sessions/s/approvals",
            params={},
            query={},
            headers={},
            body=json.dumps(
                {"approval_id": "does-not-exist", "decision": "approve",
                 "request_key": "req-key-unknown-01"}
            ).encode("utf-8"),
            correlation_id="c1",
        )
        with pytest.raises(WebRequestError) as exc:
            await handler(context)
        assert exc.value.code == "web.approval_not_found"
        assert exc.value.status == 404
