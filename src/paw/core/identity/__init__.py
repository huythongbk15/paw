"""PAW Core — Identity module (Phase 4 spec).

The agent's own identity (name, version, persona, preferences) is persisted in
the key/value ``identity`` table. This module provides a typed :class:`Identity`
view plus an :class:`IdentityManager` for durable get/set/list/bootstrap.

Zero vendor lock-in: identity is purely local SQLite — no external dependency.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..logging import get_logger
from ..storage import db

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


DEFAULT_IDENTITY: dict[str, Any] = {
    "name": "PAW",
    "version": "0.1.0",
    "description": "Personal Agent Workstation — independent personal agent runtime",
    "persona": "precise",
}


@dataclass
class Identity:
    """Typed view of the agent's self-identity.

    Backed by a plain dict; persist changes through :class:`IdentityManager`.
    """

    data: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_IDENTITY))

    @property
    def name(self) -> str:
        return str(self.data.get("name", DEFAULT_IDENTITY["name"]))

    @property
    def version(self) -> str:
        return str(self.data.get("version", DEFAULT_IDENTITY["version"]))

    @property
    def description(self) -> str:
        return str(self.data.get("description", DEFAULT_IDENTITY["description"]))

    @property
    def persona(self) -> str:
        return str(self.data.get("persona", DEFAULT_IDENTITY["persona"]))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)


class IdentityManager:
    """Durable key/value identity store over the ``identity`` table."""

    def __init__(self, defaults: dict[str, Any] | None = None):
        self._defaults = dict(DEFAULT_IDENTITY)
        if defaults:
            self._defaults.update(defaults)

    async def bootstrap(self, overwrite: bool = False) -> None:
        """Seed default identity keys if missing (or overwrite all when True)."""
        for key, value in self._defaults.items():
            existing = await db.fetch_one(
                "SELECT value FROM identity WHERE key = ?", (key,)
            )
            if existing is None or overwrite:
                await self.set(key, value)

    @staticmethod
    def _serialize(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _coerce(raw: str) -> Any:
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw

    async def set(self, key: str, value: Any) -> None:
        async with db.transaction():
            await db.write(
                "INSERT OR REPLACE INTO identity (key, value, updated_at) "
                "VALUES (?, ?, ?)",
                (key, self._serialize(value), _now()),
            )

    async def get(self, key: str, default: Any = None) -> Any:
        row = await db.fetch_one("SELECT value FROM identity WHERE key = ?", (key,))
        if row is None:
            return default
        return self._coerce(row["value"])

    async def get_all(self) -> dict[str, Any]:
        rows = await db.fetch_all("SELECT key, value FROM identity")
        return {r["key"]: self._coerce(r["value"]) for r in rows}

    async def delete(self, key: str) -> None:
        async with db.transaction():
            await db.write("DELETE FROM identity WHERE key = ?", (key,))

    async def load(self) -> Identity:
        """Load the persisted identity into a typed :class:`Identity` object."""
        return Identity(await self.get_all())
