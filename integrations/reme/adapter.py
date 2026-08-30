"""
PAW Providers — ReMe Memory Adapter

Converts ReMe memory format to PAW MemoryRecord.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ReMeMemoryAdapter:
    """Adapter to convert ReMe memory format to PAW MemoryRecord format."""

    @staticmethod
    def convert(memory_data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert ReMe memory format to PAW MemoryRecord format.

        ReMe format typically has:
        - id, content, embedding, metadata
        - metadata: type, project_id, task_id, importance, tags
        - created_at, updated_at
        """
        metadata = memory_data.get("metadata", {})

        return {
            "id": memory_data.get("id", ""),
            "memory_type": metadata.get("type", "episodic"),
            "project_id": metadata.get("project_id", "default"),
            "task_id": metadata.get("task_id"),
            "content": memory_data.get("content", ""),
            "embedding": memory_data.get("embedding"),
            "importance": metadata.get("importance", 0.5),
            "tags": metadata.get("tags", []),
            "created_at": memory_data.get("created_at", datetime.now(UTC).isoformat()),
            "updated_at": memory_data.get("updated_at", datetime.now(UTC).isoformat()),
            "source": "reme",
        }

    @staticmethod
    def convert_batch(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert multiple ReMe memories."""
        return [ReMeMemoryAdapter.convert(m) for m in memories]


class ReMeMemoryProvider:
    """Provider to load and convert ReMe memories from file storage."""

    def __init__(self, memory_path: str | Path):
        self.memory_path = Path(memory_path)

    async def query(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Query ReMe memories by text search."""
        memories = []
        for mem_file in self.memory_path.rglob("*.json"):
            try:
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                # Simple text search in content
                if query.lower() in data.get("content", "").lower():
                    memories.append(ReMeMemoryAdapter.convert(data))
            except Exception:
                pass
        # Sort by importance and recency
        memories.sort(key=lambda m: (-m.get("importance", 0), m.get("created_at", "")), reverse=True)
        return memories[:limit]

    async def query_by_type(self, memory_type: str, limit: int = 10) -> list[dict[str, Any]]:
        """Query memories by type."""
        memories = []
        for mem_file in self.memory_path.rglob("*.json"):
            try:
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                metadata = data.get("metadata", {})
                if metadata.get("type") == memory_type:
                    memories.append(ReMeMemoryAdapter.convert(data))
            except Exception:
                pass
        return memories[:limit]

    async def query_by_project(self, project_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Query memories by project."""
        memories = []
        for mem_file in self.memory_path.rglob("*.json"):
            try:
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                metadata = data.get("metadata", {})
                if metadata.get("project_id") == project_id:
                    memories.append(ReMeMemoryAdapter.convert(data))
            except Exception:
                pass
        return memories[:limit]

    async def store(self, memory: dict[str, Any]) -> str:
        """Store a memory (not implemented for read-only adapter)."""
        raise NotImplementedError("ReMe adapter is read-only")

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory (not implemented for read-only adapter)."""
        raise NotImplementedError("ReMe adapter is read-only")


class ReMeMemoryIterator:
    """Iterator for streaming ReMe memories."""

    def __init__(self, memory_path: str | Path):
        self.memory_path = Path(memory_path)

    def __iter__(self):
        for mem_file in self.memory_path.rglob("*.json"):
            try:
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                yield ReMeMemoryAdapter.convert(data)
            except Exception:
                pass

    async def async_iter(self):
        """Async iteration."""
        for mem_file in self.memory_path.rglob("*.json"):
            try:
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                yield ReMeMemoryAdapter.convert(data)
            except Exception:
                pass
