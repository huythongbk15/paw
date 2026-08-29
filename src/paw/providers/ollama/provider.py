"""
PAW Providers — Ollama Model Provider (Phase 11)

Local-first model provider that talks to a running Ollama server
(http://localhost:11434). Implements the ModelProvider Protocol from
``paw.providers`` so it can be plugged into the ModelRouter without
any vendor lock-in — Ollama is a local runtime, not a cloud dependency.

Pure stdlib HTTP (urllib) wrapped in asyncio.to_thread to stay async
without adding third-party HTTP dependencies.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncGenerator
from typing import Any

from paw.core.logging import get_logger
from paw.core.models import ModelCapability, ModelManifest

logger = get_logger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Map common Ollama model-name fragments -> (roles, capability enums).
# A single source of truth keeps role inference and capability inference
# consistent (e.g. "deepseek" yields both reasoning and coding).
_MODEL_HINTS: dict[str, tuple[list[str], list[ModelCapability]]] = {
    "llama": (["fast", "tools"], [ModelCapability.TOOL_CALLING]),
    "mistral": (["fast", "tools"], [ModelCapability.TOOL_CALLING]),
    "qwen": (["fast", "tools", "coding"], [ModelCapability.CODING, ModelCapability.TOOL_CALLING]),
    "codellama": (["coding"], [ModelCapability.CODING]),
    "deepseek": (["reasoning", "coding"], [ModelCapability.REASONING, ModelCapability.CODING]),
    "phi": (["fast"], []),
    "gemma": (["fast", "tools"], [ModelCapability.TOOL_CALLING]),
    "embedding": (["embedding"], [ModelCapability.EMBEDDING]),
    "nomic-embed": (["embedding"], [ModelCapability.EMBEDDING]),
    "vision": (["vision"], [ModelCapability.VISION]),
    "llava": (["vision"], [ModelCapability.VISION]),
}


def _infer_roles(model_name: str) -> list[str]:
    """Infer PAW roles from an Ollama model name."""
    lower = model_name.lower()
    roles: set[str] = set()
    for fragment, (inferred_roles, _caps) in _MODEL_HINTS.items():
        if fragment in lower:
            roles.update(inferred_roles)
    if not roles:
        roles.add("fast")
    return sorted(roles)


def _infer_capabilities(model_name: str) -> dict[str, float]:
    """Infer PAW model capabilities from an Ollama model name."""
    lower = model_name.lower()
    caps: dict[str, float] = {}
    for fragment, (_roles, inferred_caps) in _MODEL_HINTS.items():
        if fragment in lower:
            for cap in inferred_caps:
                caps[cap.value] = 7.0
    # Every model can at least do basic structured output
    caps[ModelCapability.STRUCTURED_OUTPUT.value] = 6.0
    if ModelCapability.REASONING.value in caps:
        caps[ModelCapability.PLANNING.value] = 7.0
    return caps


class OllamaProvider:
    """Local Ollama model provider.

    Implements the ModelProvider Protocol (name, version, initialize,
    shutdown, list_models, get_model, complete, stream).
    """

    name = "ollama"
    version = "1.0.0"

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._available: bool | None = None

    # --- lifecycle ---

    async def initialize(self) -> None:
        """Verify Ollama is reachable. Sets internal availability flag."""
        try:
            await self._request("GET", "/api/tags")
            self._available = True
            logger.info("ollama_provider_initialized", base_url=self.base_url)
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            self._available = False
            logger.warning("ollama_provider_unavailable", base_url=self.base_url, error=str(exc))

    async def shutdown(self) -> None:
        """No-op: Ollama manages its own process lifecycle."""
        self._available = None

    @property
    def available(self) -> bool:
        return bool(self._available)

    # --- model discovery ---

    async def list_models(self) -> list[dict[str, Any]]:
        """List installed Ollama models via ``/api/tags``."""
        try:
            data = await self._request("GET", "/api/tags")
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            logger.warning("ollama_list_models_failed", error=str(exc))
            return []
        models = data.get("models", []) if isinstance(data, dict) else []
        return [
            {
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
                "details": m.get("details", {}),
            }
            for m in models
        ]

    async def get_model(self, name: str) -> dict[str, Any] | None:
        """Get details for a single model via ``/api/show``."""
        try:
            data = await self._request("POST", "/api/show", {"name": name})
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            logger.warning("ollama_get_model_failed", name=name, error=str(exc))
            return None
        return data

    async def discover_manifests(self) -> list[ModelManifest]:
        """Convert installed Ollama models into PAW ModelManifests."""
        raw = await self.list_models()
        manifests: list[ModelManifest] = []
        for m in raw:
            name = m.get("name", "")
            if not name:
                continue
            roles = _infer_roles(name)
            manifests.append(
                ModelManifest(
                    name=name,
                    provider="ollama",
                    roles=roles,
                    model_capabilities=_infer_capabilities(name),
                    cost={"compute": "low", "monetary": "free"},
                    features={"resumable": True, "streaming": True, "subagents": False},
                    max_context_tokens=32000,
                    latency_tier="medium",
                    enabled=True,
                )
            )
        logger.info("ollama_manifests_discovered", count=len(manifests))
        return manifests

    # --- execution ---

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a completion via ``/api/generate``.

        ``request`` must contain ``model`` and either ``prompt`` or ``messages``.
        Returns the parsed JSON response from Ollama.
        """
        payload = self._build_generate_payload(request, stream=False)
        try:
            data = await self._request("POST", "/api/generate", payload)
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            logger.error("ollama_complete_failed", model=request.get("model"), error=str(exc))
            return {"error": str(exc), "response": ""}
        return data

    async def stream(self, request: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a completion via ``/api/generate`` with ``stream=true``.

        Yields each JSON object as it arrives from Ollama.
        """
        payload = self._build_generate_payload(request, stream=True)
        url = f"{self.base_url}/api/generate"
        body = json.dumps(payload).encode("utf-8")
        try:
            loop = asyncio.get_running_loop()

            def _stream() -> list[str]:
                req = urllib.request.Request(
                    url, data=body, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return [line.decode("utf-8") for line in resp if line.strip()]

            lines = await asyncio.wait_for(loop.run_in_executor(None, _stream), timeout=self.timeout + 5)
        except (TimeoutError, OSError, urllib.error.URLError, ValueError) as exc:
            logger.error("ollama_stream_failed", model=request.get("model"), error=str(exc))
            yield {"error": str(exc)}
            return

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue

    # --- embeddings ---

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings for a batch of texts via ``/api/embeddings``.

        Returns one vector per input text. On any failure returns an empty
        list so callers fall back to lexical retrieval (never raises).
        """
        embed_model = model or "nomic-embed-text"
        out: list[list[float]] = []
        for text in texts:
            try:
                data = await self._request(
                    "POST", "/api/embeddings", {"model": embed_model, "prompt": text}
                )
                vec = data.get("embedding")
                if isinstance(vec, list):
                    out.append([float(x) for x in vec])
                else:
                    out.append([])
            except (TimeoutError, OSError, urllib.error.URLError, ValueError) as exc:
                logger.error("ollama_embed_failed", model=embed_model, error=str(exc))
                out.append([])
        return out

    # --- helpers ---

    @staticmethod
    def _build_generate_payload(request: dict[str, Any], stream: bool) -> dict[str, Any]:
        """Normalize a PAW completion request into Ollama's generate format."""
        payload: dict[str, Any] = {
            "model": request.get("model", ""),
            "stream": stream,
        }
        if "messages" in request:
            # Chat-style request -> Ollama supports `messages` natively
            payload["messages"] = request["messages"]
        elif "prompt" in request:
            payload["prompt"] = request["prompt"]
        if "options" in request:
            payload["options"] = request["options"]
        if "format" in request:
            payload["format"] = request["format"]
        if "system" in request:
            payload["system"] = request["system"]
        return payload

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        """Perform an HTTP request to the Ollama server (stdlib, async)."""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        loop = asyncio.get_running_loop()

        def _do() -> Any:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)

        return await asyncio.wait_for(
            loop.run_in_executor(None, _do), timeout=self.timeout + 5
        )
