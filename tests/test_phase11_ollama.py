"""
PAW Phase 11 — Ollama Provider Layer

Tests the Ollama model provider and its integration with the ModelRegistry
and ModelExecutor. Ollama may not be running in CI, so we exercise the real
HTTP path against a local mock server and verify graceful degradation when
Ollama is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from paw.core.model_executor import LocalModelExecutor, ModelExecutor
from paw.core.model_router import ModelRegistry, ModelRouter
from paw.core.models import ModelCapability, ModelManifest
from paw.providers.ollama.provider import (
    OllamaProvider,
    _infer_capabilities,
    _infer_roles,
)


# --- Pure inference logic (no network) ---


def test_infer_roles_from_name():
    assert "coding" in _infer_roles("codellama:7b")
    assert "reasoning" in _infer_roles("deepseek-coder")
    assert "vision" in _infer_roles("llava")
    assert "embedding" in _infer_roles("nomic-embed-text")
    # Unknown models fall back to a default role
    assert _infer_roles("some-unknown-model") == ["fast"]


def test_infer_capabilities_from_name():
    caps = _infer_capabilities("deepseek-coder")
    assert caps[ModelCapability.REASONING.value] == 7.0
    assert caps[ModelCapability.CODING.value] == 7.0
    # structured output is always present
    assert caps[ModelCapability.STRUCTURED_OUTPUT.value] == 6.0


# --- Mock Ollama server ---


class _MockOllamaHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence test server logs
        pass

    def _send(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send(
                {
                    "models": [
                        {"name": "llama3:8b", "size": 1000, "modified_at": "2024-01-01"},
                        {"name": "codellama:7b", "size": 2000, "modified_at": "2024-01-02"},
                    ]
                }
            )
        else:
            self._send({"error": "not found"}, status=404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            req = {}
        if self.path == "/api/show":
            self._send({"name": req.get("name"), "details": {"family": "llama"}})
        elif self.path == "/api/generate":
            if req.get("stream"):
                # streaming: one JSON object per line
                body = (
                    json.dumps({"response": "hello ", "done": False}) + "\n"
                    + json.dumps({"response": "world", "done": True}) + "\n"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send({"model": req.get("model"), "response": "hello world", "done": True})
        else:
            self._send({"error": "not found"}, status=404)


@pytest.fixture
def mock_ollama():
    server = HTTPServer(("127.0.0.1", 0), _MockOllamaHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.mark.asyncio
async def test_ollama_list_models(mock_ollama):
    provider = OllamaProvider(base_url=mock_ollama)
    await provider.initialize()
    assert provider.available is True
    models = await provider.list_models()
    assert len(models) == 2
    names = {m["name"] for m in models}
    assert names == {"llama3:8b", "codellama:7b"}


@pytest.mark.asyncio
async def test_ollama_discover_manifests(mock_ollama):
    provider = OllamaProvider(base_url=mock_ollama)
    await provider.initialize()
    manifests = await provider.discover_manifests()
    assert len(manifests) == 2
    by_name = {m.name: m for m in manifests}
    assert by_name["llama3:8b"].provider == "ollama"
    assert "coding" in by_name["codellama:7b"].roles
    assert by_name["llama3:8b"].cost["monetary"] == "free"


@pytest.mark.asyncio
async def test_ollama_complete(mock_ollama):
    provider = OllamaProvider(base_url=mock_ollama)
    await provider.initialize()
    result = await provider.complete({"model": "llama3:8b", "prompt": "hi"})
    assert result["response"] == "hello world"
    assert result["done"] is True


@pytest.mark.asyncio
async def test_ollama_stream(mock_ollama):
    provider = OllamaProvider(base_url=mock_ollama)
    await provider.initialize()
    chunks = [c async for c in provider.stream({"model": "llama3:8b", "prompt": "hi"})]
    assert len(chunks) == 2
    assert chunks[0]["response"] == "hello "
    assert chunks[1]["done"] is True


@pytest.mark.asyncio
async def test_ollama_unavailable_graceful():
    # Point at a port that is not listening
    provider = OllamaProvider(base_url="http://127.0.0.1:1")
    await provider.initialize()
    assert provider.available is False
    # list_models must not raise
    assert await provider.list_models() == []
    # complete must return an error dict, not raise
    result = await provider.complete({"model": "x", "prompt": "y"})
    assert "error" in result


# --- Registry integration ---


@pytest.mark.asyncio
async def test_registry_register_ollama_models(mock_ollama):
    registry = ModelRegistry()
    registry.register_defaults()
    base_count = len(registry.list())
    added = await registry.register_ollama_models(OllamaProvider(base_url=mock_ollama))
    assert added == 2
    assert len(registry.list()) == base_count + 2
    ollama_models = [m for m in registry.list() if m.provider == "ollama"]
    assert len(ollama_models) == 2


@pytest.mark.asyncio
async def test_registry_register_ollama_unavailable():
    registry = ModelRegistry()
    registry.register_defaults()
    added = await registry.register_ollama_models(OllamaProvider(base_url="http://127.0.0.1:1"))
    assert added == 0  # graceful: returns 0, core keeps working


# --- ModelExecutor dispatch ---


@pytest.mark.asyncio
async def test_model_executor_local_fallback():
    executor = ModelExecutor()
    await executor.initialize_all()
    selection = ModelRouter().route_with_explain if False else None
    # Build a minimal selection with a "local" manifest
    manifest = ModelManifest(name="local-fast", provider="local", roles=["fast"])
    selection = type("_S", (), {})()
    selection.model_name = "local-fast"
    selection.model_manifest = manifest
    selection.role = "fast"
    selection.reason = ""
    selection.fallback_chain = []
    selection.score = 0.0
    result = await executor.complete(selection, [{"role": "user", "content": "translate hello"}])
    assert "local-standin" in result["response"]


@pytest.mark.asyncio
async def test_model_executor_ollama_dispatch(mock_ollama):
    executor = ModelExecutor()
    from paw.providers.ollama.provider import OllamaProvider

    provider = OllamaProvider(base_url=mock_ollama)
    await provider.initialize()
    executor.register(provider)
    await executor.initialize_all()

    manifest = ModelManifest(name="llama3:8b", provider="ollama", roles=["fast"])
    selection = type("_S", (), {})()
    selection.model_name = "llama3:8b"
    selection.model_manifest = manifest
    selection.role = "fast"
    selection.reason = ""
    selection.fallback_chain = []
    selection.score = 0.0

    result = await executor.complete(selection, [{"role": "user", "content": "hi"}])
    assert result["response"] == "hello world"


@pytest.mark.asyncio
async def test_model_executor_unknown_provider_falls_back():
    executor = ModelExecutor()
    await executor.initialize_all()
    # provider "openrouter" is not registered -> falls back to local
    manifest = ModelManifest(name="gpt-x", provider="openrouter", roles=["fast"])
    selection = type("_S", (), {})()
    selection.model_name = "gpt-x"
    selection.model_manifest = manifest
    selection.role = "fast"
    selection.reason = ""
    selection.fallback_chain = []
    selection.score = 0.0
    result = await executor.complete(selection, [{"role": "user", "content": "hi"}])
    assert "local-standin" in result["response"]
