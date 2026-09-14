"""
PAW Providers — OpenAI Cloud Provider Adapter (E4-11..14)

Provides a cloud teacher baseline and bounded training capability via the
OpenAI API. This is a replaceable adapter — injected via parameters,
not hardcoded in PAW core. Implements both ModelProvider (for baseline
measurement) and TrainingProvider (for bounded training).

Pure stdlib HTTP (urllib) wrapped in asyncio.to_thread to stay async
without adding third-party HTTP dependencies.

Requires OPENAI_API_KEY environment variable. If absent, the provider
reports available=False and all measurement functions degrade gracefully.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from collections.abc import AsyncGenerator
from typing import Any

from paw.core.logging import get_logger
from paw.core.models import ModelCapability, ModelManifest
from paw.core.privacy import PrivacyClass, can_disclose_to_provider

logger = get_logger(__name__)

DEFAULT_OPENAI_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT = 120.0


class TrainingProvider:
    """Protocol for providers that support model training (E4-12).

    Extends ModelProvider with training lifecycle methods. A provider
    implementing this interface can be used for bounded training
    experiments within the E4 framework.
    """

    # Training job status values
    JOB_QUEUED = "queued"
    JOB_RUNNING = "running"
    JOB_SUCCEEDED = "succeeded"
    JOB_FAILED = "failed"
    JOB_CANCELLED = "cancelled"


def _get_api_key() -> str | None:
    """Read OpenAI API key from environment. No key = provider unavailable."""
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")


def estimate_training_cost(
    num_examples: int,
    epochs: int = 3,
    model: str = "gpt-3.5-turbo",
) -> float:
    """E4-12: Estimate training cost for a cloud provider.

    Uses OpenAI's published pricing for fine-tuning. Returns estimated
    USD cost. This is a pure calculation — no network call.
    """
    # OpenAI fine-tuning costs (as of knowledge cutoff)
    # ~$0.03 per 1K tokens input, ~$0.06 per 1K tokens output for gpt-3.5-turbo
    # Training tokens ≈ 4 * num_examples * epochs (conservative estimate)
    tokens_per_example = 50  # avg tokens per training example
    total_tokens = num_examples * epochs * tokens_per_example
    cost_per_1k = 0.03  # input cost
    return round((total_tokens / 1000) * cost_per_1k, 4)


class OpenAITrainingProvider:
    """Cloud provider adapter for E4-11..14.

    Implements a subset of ModelProvider Protocol (available, discover_manifests,
    complete) sufficient for baseline measurement, plus training lifecycle
    methods for E4-12..14.

    Requires OPENAI_API_KEY in the environment. If absent, available=False
    and all operations degrade gracefully (no crash, zero measurement).
    """

    name = "openai"
    version = "1.0.0"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENAI_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_budget_tokens: int | None = None,
    ):
        self._api_key = api_key or _get_api_key()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._available: bool | None = None
        self._max_budget_tokens = max_budget_tokens or 50000

    # --- lifecycle ---

    async def initialize(self) -> None:
        """Verify OpenAI API is reachable. No-op if API key is absent."""
        if not self._api_key:
            self._available = False
            logger.warning("openai_provider_no_key",
                           reason="OPENAI_API_KEY not set")
            return
        try:
            await self._request("GET", "/models")
            self._available = True
            logger.info("openai_provider_initialized",
                        base_url=self.base_url,
                        model_count="available")
        except Exception as exc:
            self._available = False
            logger.warning("openai_provider_unavailable",
                           base_url=self.base_url, error=str(exc))

    async def shutdown(self) -> None:
        """No-op: OpenAI is a managed cloud service."""
        self._available = None

    @property
    def available(self) -> bool:
        return bool(self._api_key) and bool(self._available)

    # --- model discovery ---

    async def list_models(self) -> list[dict[str, Any]]:
        """List available OpenAI models."""
        if not self._api_key:
            return []
        try:
            data = await self._request("GET", "/models")
            models = data.get("data", []) if isinstance(data, dict) else []
            return [
                {
                    "id": m.get("id", ""),
                    "name": m.get("id", ""),
                    "owned_by": m.get("owned_by", ""),
                }
                for m in models
            ]
        except Exception as exc:
            logger.warning("openai_list_models_failed", error=str(exc))
            return []

    async def get_model(self, name: str) -> dict[str, Any] | None:
        """Get details for a single model."""
        if not self._api_key:
            return None
        try:
            data = await self._request("GET", f"/models/{name}")
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning("openai_get_model_failed", name=name, error=str(exc))
            return None

    async def discover_manifests(self) -> list[ModelManifest]:
        """Convert OpenAI models into PAW ModelManifests.

        Only models matching training-capable or strong-chat prefixes are
        registered, keeping the core registry clean.
        """
        raw = await self.list_models()
        manifests: list[ModelManifest] = []
        training_models = {"gpt-3.5-turbo", "gpt-4", "gpt-4o", "gpt-4o-mini"}
        for m in raw:
            name = m.get("id", "")
            if not name or name not in training_models:
                continue
            roles = ["reasoning", "coding"] if "4" in name else ["fast"]
            manifests.append(
                ModelManifest(
                    name=name,
                    provider="openai",
                    roles=roles,
                    model_capabilities={
                        ModelCapability.REASONING.value: 9.0,
                        ModelCapability.CODING.value: 8.5,
                        ModelCapability.STRUCTURED_OUTPUT.value: 8.0,
                    },
                    cost={"compute": "high", "monetary": "paid"},
                    features={"resumable": False, "streaming": True, "subagents": False},
                    max_context_tokens=128000,
                    latency_tier="fast",
                    enabled=True,
                )
            )
        return manifests

    # --- execution (for baseline measurement) ---

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a chat completion via OpenAI API.

        Normalizes response to {"response": <text>, "model": <name>,
        "usage": {...>, "thinking": <str|None>}.
        """
        if not self._api_key:
            return {"error": "no_api_key", "response": ""}
        model = request.get("model", "gpt-4o-mini")
        messages = request.get("messages", [])
        max_tokens = request.get("max_tokens", 500)
        # Enforce budget ceiling
        effective_max = min(max_tokens, self._max_budget_tokens)
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": effective_max,
        }
        if request.get("temperature") is not None:
            payload["temperature"] = request["temperature"]
        try:
            data = await self._request("POST", "/chat/completions", payload)
            if "error" in data:
                return {"error": data["error"].get("message", "unknown"), "response": ""}
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            thinking = None
            if "reasoning_content" in choice.get("message", {}):
                thinking = choice["message"]["reasoning_content"]
            return {
                "response": text,
                "model": data.get("model", model),
                "usage": usage,
                "thinking": thinking,
                "done": True,
            }
        except Exception as exc:
            logger.error("openai_complete_failed", model=model, error=str(exc))
            return {"error": str(exc), "response": ""}

    async def stream(self, request: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat completion via OpenAI.

        Yields {"response": <text>, "done": <bool>} chunks.
        """
        if not self._api_key:
            yield {"error": "no_api_key", "response": "", "done": True}
            return
        model = request.get("model", "gpt-4o-mini")
        messages = request.get("messages", [])
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": min(request.get("max_tokens", 500), self._max_budget_tokens),
        }
        url = f"{self.base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        try:
            loop = asyncio.get_running_loop()

            def _stream():
                req = urllib.request.Request(
                    url, data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return [line.decode("utf-8") for line in resp if line.strip()]

            lines = await asyncio.wait_for(
                loop.run_in_executor(None, _stream),
                timeout=self.timeout + 5,
            )
        except Exception as exc:
            logger.error("openai_stream_failed", error=str(exc))
            yield {"error": str(exc), "response": "", "done": True}
            return

        for line in lines:
            if line.startswith("data: "):
                chunk_str = line[6:].strip()
                if chunk_str == "[DONE]":
                    yield {"response": "", "done": True}
                    continue
                try:
                    data = json.loads(chunk_str)
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    text = delta.get("content", "")
                    thinking = delta.get("reasoning_content")
                    if text or thinking:
                        yield {"response": text, "thinking": thinking, "done": False}
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

    # --- training lifecycle (E4-12..14) ---

    async def create_training_job(
        self,
        training_files: list[str],
        suffix: str,
        *,
        hyperparameters: dict[str, Any] | None = None,
        validation_files: list[str] | None = None,
    ) -> str:
        """E4-12: Create a fine-tuning job.

        Returns job ID. Requires OpenAI API key + files uploaded.

        BLOCKED: if no API key or provider unavailable.
        """
        if not self._api_key:
            raise NotImplementedError(
                "E4-12 training requires an OpenAI provider adapter with "
                "OPENAI_API_KEY set. Provider unavailable."
            )
        job_payload = {
            "training_file": training_files[0],
            "suffix": suffix,
        }
        if hyperparameters:
            job_payload["hyperparameters"] = hyperparameters
        if validation_files:
            job_payload["validation_file"] = validation_files[0]
        try:
            data = await self._request("POST", "/fine_tuning/jobs", job_payload)
            job_id = data.get("id", "")
            logger.info("openai_training_job_created", job_id=job_id, suffix=suffix)
            return job_id
        except Exception as exc:
            logger.error("openai_training_job_create_failed", error=str(exc))
            raise

    async def get_training_job(self, job_id: str) -> dict[str, Any]:
        """E4-12: Get training job status."""
        if not self._api_key:
            raise NotImplementedError("E4-12 training requires OpenAI provider adapter")
        try:
            data = await self._request("GET", f"/fine_tuning/jobs/{job_id}")
            return data
        except Exception as exc:
            logger.error("openai_get_training_job_failed", job_id=job_id, error=str(exc))
            raise

    async def cancel_training_job(self, job_id: str) -> bool:
        """E4-12: Cancel a training job (bounded experiment stop)."""
        if not self._api_key:
            raise NotImplementedError("E4-12 training requires OpenAI provider adapter")
        try:
            await self._request("POST", f"/fine_tuning/jobs/{job_id}/cancel")
            logger.info("openai_training_job_cancelled", job_id=job_id)
            return True
        except Exception as exc:
            logger.error("openai_cancel_training_job_failed", job_id=job_id, error=str(exc))
            return False

    async def list_training_jobs(self) -> list[dict[str, Any]]:
        """E4-13: List training jobs (for artifact tracking)."""
        if not self._api_key:
            return []
        try:
            data = await self._request("GET", "/fine_tuning/jobs")
            jobs = data.get("data", []) if isinstance(data, dict) else []
            return jobs
        except Exception as exc:
            logger.warning("openai_list_training_jobs_failed", error=str(exc))
            return []

    # --- file upload (E4-12 dataset format) ---

    async def upload_training_file(
        self,
        file_path: str,
        purpose: str = "fine-tune",
    ) -> str:
        """E4-12: Upload a training data file.

        Returns file ID. File must be in JSONL format with
        {"prompt": "...", "completion": "..."} entries.

        BLOCKED: if no API key.
        """
        if not self._api_key:
            raise NotImplementedError(
                "E4-12 training requires OpenAI provider adapter with API key"
            )
        try:
            from pathlib import Path
            file_path_obj = Path(file_path)
            with file_path_obj.open("rb") as f:
                file_data = f.read()
            boundary = "----PAWBATCH"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{file_path_obj.name}"\r\n'
                f"Content-Type: application/jsonl\r\n\r\n"
            ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
            loop = asyncio.get_running_loop()

            def _upload():
                req = urllib.request.Request(
                    f"{self.base_url}/files",
                    data=body,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            data = await asyncio.wait_for(
                loop.run_in_executor(None, _upload), timeout=self.timeout + 10
            )
            file_id = data.get("id", "")
            logger.info("openai_file_uploaded", file_id=file_id,
                        filename=file_path_obj.name)
            return file_id
        except Exception as exc:
            logger.error("openai_upload_failed", error=str(exc))
            raise

    # --- helpers ---

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        """Perform an HTTP request to the OpenAI API (stdlib, async)."""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        loop = asyncio.get_running_loop()

        def _do() -> Any:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            }
            req = urllib.request.Request(
                url, data=data, headers=headers, method=method
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)

        return await asyncio.wait_for(
            loop.run_in_executor(None, _do), timeout=self.timeout + 5
        )

    def can_handle_request(self, privacy_class: PrivacyClass = PrivacyClass.INTERNAL) -> bool:
        """Check if this provider can handle a request of the given privacy class.

        This is a pure check — no network call. Used by the privacy gate
        to determine disclosure eligibility BEFORE making any remote call.
        """
        return can_disclose_to_provider(privacy_class, "cloud_approved")
