"""
PAW Providers — Adapter layer for external systems.

Per architecture: Provider không được sở hữu abstraction của PAW Core.
Mọi integration đi qua Protocol/adapter.
"""

from __future__ import annotations

__all__ = [
    "MemoryProvider",
    "ModelProvider",
    "PersonaProvider",
    "Provider",
    "SkillProvider",
]

# Protocol definitions for provider adapters
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core.models import ModelManifest
    from ..core.skills import SkillManifest


class Provider(Protocol):
    """Base protocol for all providers."""
    name: str
    version: str

    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...


@runtime_checkable
class ModelProvider(Provider, Protocol):
    """Protocol for model providers (discovery + execution).

    A ModelProvider both discovers its models (so the ModelRegistry can be
    populated) and executes completions. ``available`` lets the ModelRouter
    exclude providers that are not reachable (e.g. Ollama server down) before
    routing, keeping the runtime loop from selecting an unusable model.
    """

    @property
    def available(self) -> bool: ...
    async def list_models(self) -> list[dict[str, Any]]: ...
    async def get_model(self, name: str) -> dict[str, Any] | None: ...
    async def discover_manifests(self) -> list[ModelManifest]: ...
    async def complete(self, request: dict[str, Any]) -> dict[str, Any]: ...
    async def stream(self, request: dict[str, Any]): ...  # AsyncGenerator


class SkillProvider(Provider, Protocol):
    """Protocol for skill providers."""

    async def list_skills(self) -> list[dict[str, Any]]: ...
    async def get_skill(self, name: str) -> dict[str, Any] | None: ...
    async def import_skill(self, skill_data: dict[str, Any]) -> SkillManifest: ...


class MemoryProvider(Provider, Protocol):
    """Protocol for memory providers."""

    async def query(self, query: str, limit: int = 10) -> list[dict[str, Any]]: ...
    async def store(self, memory: dict[str, Any]) -> str: ...
    async def delete(self, memory_id: str) -> bool: ...


class PersonaProvider(Provider, Protocol):
    """Protocol for persona providers."""

    async def list_personas(self) -> list[dict[str, Any]]: ...
    async def get_persona(self, name: str) -> dict[str, Any] | None: ...
    async def import_persona(self, persona_data: dict[str, Any]) -> dict[str, Any]: ...
