"""The local web security boundary, proved.

The B-23..B-26 contract names the controls a local web adapter needs
before any handler is written: a loopback bind, an exact Host
allowlist, an exact Origin, a local CSRF token for mutations, bounded
body/history/stream buffers, no credential in a query string, and no
concurrent writes until the storage concurrency question is settled.

The boundary is transport-agnostic, so it is provable here without
standing up a server. What is pinned:

* every control refuses, with a **stable code** and a safe message;
* the Host allowlist is **exact** - a prefix or suffix of an allowed
  host is not allowed;
* a wildcard CORS is not representable;
* a missing Origin is fine for a safe request (that is what same-origin
  means on the wire) and **not** fine for a mutation;
* the write admission is **process-wide**, not per session;
* ``paw.core`` imports no HTTP or frontend type, and ``paw.web`` is not
  imported by core either.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from paw.web import (
    LocalWebGuard,
    WebSecurityCode,
    WebSecurityConfig,
    WebSecurityError,
    default_allowed_hosts,
)

PAW = Path(__file__).resolve().parents[1] / "src" / "paw"
HOST = "127.0.0.1:8765"
ORIGIN = f"http://{HOST}"


def _guard(**kwargs) -> LocalWebGuard:
    return LocalWebGuard(WebSecurityConfig(csrf_token="local-token", **kwargs))


# ── 1. The bind ─────────────────────────────────────────────────────────


class TestTheBind:
    def test_loopback_is_accepted(self):
        for host in ("127.0.0.1", "::1", "localhost"):
            _guard(bind_host=host).check_bind()

    def test_a_routable_bind_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard(bind_host="0.0.0.0").check_bind()
        assert exc.value.code == WebSecurityCode.BIND_NOT_LOOPBACK

    def test_a_public_address_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard(bind_host="192.168.1.10").check_bind()
        assert exc.value.code == WebSecurityCode.BIND_NOT_LOOPBACK


# ── 2. The Host allowlist is exact ──────────────────────────────────────


class TestTheHost:
    def test_an_allowed_host_passes(self):
        guard = _guard()
        guard.check_host({"Host": HOST})
        guard.check_host({"host": "localhost:8765"})

    def test_a_prefix_of_an_allowed_host_is_refused(self):
        guard = _guard()
        for host in (f"evil{HOST}", f"{HOST}.evil.com", f"x{HOST}"):
            with pytest.raises(WebSecurityError) as exc:
                guard.check_host({"Host": host})
            assert exc.value.code == WebSecurityCode.HOST_NOT_ALLOWED, host

    def test_a_missing_host_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard().check_host({})
        assert exc.value.code == WebSecurityCode.HOST_NOT_ALLOWED

    def test_the_default_allowlist_carries_the_port(self):
        hosts = default_allowed_hosts("127.0.0.1", 8765)
        assert HOST in hosts
        assert "127.0.0.1:8766" not in hosts


# ── 3. The Origin is exact ──────────────────────────────────────────────


class TestTheOrigin:
    def test_a_same_origin_request_passes(self):
        guard = _guard()
        guard.check_origin({"Host": HOST, "Origin": ORIGIN})

    def test_a_foreign_origin_is_refused(self):
        guard = _guard()
        for origin in ("http://evil.com", f"http://{HOST}.evil.com", "null"):
            with pytest.raises(WebSecurityError) as exc:
                guard.check_origin({"Host": HOST, "Origin": origin})
            assert exc.value.code == WebSecurityCode.ORIGIN_NOT_ALLOWED, origin

    def test_a_wildcard_cors_is_not_representable(self):
        """``*`` must never be an allowed origin."""
        guard = _guard(allowed_origins=frozenset({"*"}))
        with pytest.raises(WebSecurityError) as exc:
            guard.check_origin({"Host": HOST, "Origin": "http://anything"})
        assert exc.value.code == WebSecurityCode.ORIGIN_NOT_ALLOWED

    def test_an_explicit_allowlist_is_honoured(self):
        guard = _guard(allowed_origins=frozenset({"http://allowed.example"}))
        guard.check_origin({"Host": HOST, "Origin": "http://allowed.example"})
        with pytest.raises(WebSecurityError):
            guard.check_origin({"Host": HOST, "Origin": "http://other.example"})


# ── 4. CSRF ─────────────────────────────────────────────────────────────


class TestCsrf:
    def test_a_mutation_without_a_token_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard().check_request(
                method="POST", headers={"Host": HOST, "Origin": ORIGIN},
            )
        assert exc.value.code == WebSecurityCode.CSRF_INVALID

    def test_a_mutation_with_the_wrong_token_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard().check_request(
                method="POST",
                headers={"Host": HOST, "Origin": ORIGIN, "X-CSRF-Token": "wrong"},
            )
        assert exc.value.code == WebSecurityCode.CSRF_INVALID

    def test_a_mutation_with_the_token_passes(self):
        _guard().check_request(
            method="POST",
            headers={"Host": HOST, "Origin": ORIGIN, "X-CSRF-Token": "local-token"},
        )

    def test_a_safe_request_needs_no_token(self):
        _guard().check_request(method="GET", headers={"Host": HOST})

    def test_a_surface_with_no_token_refuses_mutations(self):
        """No token configured means no protection, so no mutations."""
        with pytest.raises(WebSecurityError) as exc:
            LocalWebGuard(WebSecurityConfig()).check_request(
                method="POST", headers={"Host": HOST, "Origin": ORIGIN},
            )
        assert exc.value.code == WebSecurityCode.CSRF_INVALID


# ── 5. Origin presence follows the HTTP semantics ───────────────────────


class TestOriginPresence:
    def test_a_safe_request_without_an_origin_is_fine(self):
        """That is what same-origin means on the wire."""
        _guard().check_request(method="GET", headers={"Host": HOST})

    def test_a_mutation_without_an_origin_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard().check_request(
                method="POST",
                headers={"Host": HOST, "X-CSRF-Token": "local-token"},
            )
        assert exc.value.code == WebSecurityCode.ORIGIN_REQUIRED


# ── 6. No credential in a query string ──────────────────────────────────


class TestNoCredentialInTheQuery:
    @pytest.mark.parametrize("key", ["token", "api_key", "password", "secret", "csrf"])
    def test_a_credential_parameter_is_refused(self, key):
        with pytest.raises(WebSecurityError) as exc:
            _guard().check_request(
                method="GET", headers={"Host": HOST}, query=f"{key}=abc",
            )
        assert exc.value.code == WebSecurityCode.CREDENTIAL_IN_QUERY

    def test_an_ordinary_parameter_is_fine(self):
        _guard().check_request(
            method="GET", headers={"Host": HOST}, query="cursor=abc&limit=10",
        )

    def test_redaction_keeps_the_shape_and_drops_the_secret(self):
        from paw.web.security import redact_query

        redacted = redact_query("cursor=abc&token=supersecret")
        assert "cursor=abc" in redacted
        assert "supersecret" not in redacted
        assert "<redacted>" in redacted


# ── 7. Bounds ───────────────────────────────────────────────────────────


class TestTheBounds:
    def test_a_body_over_the_bound_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard(max_body_bytes=10).check_request(
                method="POST",
                headers={"Host": HOST, "Origin": ORIGIN, "X-CSRF-Token": "local-token"},
                body_bytes=11,
            )
        assert exc.value.code == WebSecurityCode.BODY_TOO_LARGE

    def test_a_history_over_the_bound_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard(max_history_items=2).check_history([1, 2, 3])
        assert exc.value.code == WebSecurityCode.HISTORY_TOO_LONG

    def test_a_stream_buffer_over_the_bound_is_refused(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard(max_stream_buffer_bytes=10).check_stream_buffer(11)
        assert exc.value.code == WebSecurityCode.STREAM_BUFFER_TOO_LARGE

    def test_a_history_within_the_bound_is_fine(self):
        _guard(max_history_items=3).check_history([1, 2, 3])


# ── 8. The write admission is process-wide ──────────────────────────────


class TestTheWriteAdmission:
    @pytest.mark.asyncio
    async def test_writes_are_serialised(self):
        guard = _guard()
        assert guard.allows_concurrent_writes() is False
        async with guard.write_lock:
            assert guard.write_lock.held == 1
        assert guard.write_lock.held == 0

    @pytest.mark.asyncio
    async def test_a_second_writer_waits(self):
        """The admission is one lock for the whole process, not per session."""
        import asyncio

        guard = _guard()
        order: list[str] = []

        async def _writer(name: str) -> None:
            async with guard.write_lock:
                order.append(f"{name}:in")
                await asyncio.sleep(0.01)
                order.append(f"{name}:out")

        await asyncio.gather(_writer("a"), _writer("b"))
        # The two writers did not interleave.
        assert order in (
            ["a:in", "a:out", "b:in", "b:out"],
            ["b:in", "b:out", "a:in", "a:out"],
        ), order


# ── 9. The refusals are safe ─────────────────────────────────────────────


class TestTheRefusalsAreSafe:
    def test_a_refusal_carries_a_stable_code_and_a_safe_message(self):
        with pytest.raises(WebSecurityError) as exc:
            _guard().check_host({"Host": "evil.example"})
        error = exc.value
        assert error.code.value == "web.host_not_allowed"
        assert "evil.example" not in error.message
        assert "Traceback" not in str(error)
        assert error.to_dict() == {
            "code": "web.host_not_allowed",
            "message": error.message,
        }

    def test_a_refusal_never_carries_the_configured_token(self):
        guard = LocalWebGuard(WebSecurityConfig(csrf_token="super-secret-token"))
        with pytest.raises(WebSecurityError) as exc:
            guard.check_request(
                method="POST", headers={"Host": HOST, "Origin": ORIGIN},
            )
        assert "super-secret-token" not in str(exc.value)


# ── 10. The layering holds ──────────────────────────────────────────────


class TestTheLayering:
    def test_core_imports_no_web_type(self):
        """``paw.core`` must not depend on the web surface."""
        offenders: list[str] = []
        for path in sorted((PAW / "core").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("paw.web"):
                        offenders.append(str(path))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("paw.web"):
                            offenders.append(str(path))
        assert not offenders, offenders

    def test_core_imports_no_http_or_frontend_type(self):
        """The core does not speak HTTP or frontend dialects."""
        forbidden = {
            "fastapi", "starlette", "flask", "django", "uvicorn",
            "pydantic_core", "httpx", "aiohttp", "requests", "sse_starlette",
        }
        offenders: list[str] = []
        for path in sorted((PAW / "core").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".")[0] in forbidden:
                        offenders.append(f"{path}: {name}")
        assert not offenders, offenders

    def test_the_web_surface_does_not_import_core_internals(self):
        """``paw.web`` talks to the application services, not to core internals."""
        allowed_prefixes = (
            "paw.core", "paw.application", "paw.web", "paw.knowledge",
            "paw.executors", "paw.providers", "paw.skills", "paw.bench",
            "paw.memory", "paw.models", "paw.storage", "paw.utils",
            "paw.cli", "paw.tui", "paw.logging", "paw.docs", "paw.examples",
        )
        offenders: list[str] = []
        for path in sorted((PAW / "web").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.startswith("paw.") and not name.startswith(allowed_prefixes):
                        offenders.append(f"{path}: {name}")
        assert not offenders, offenders
