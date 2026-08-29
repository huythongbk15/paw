"""
PAW Providers — Persona Adapter

Converts various persona formats to PAW persona format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Persona:
    """PAW standard persona format."""
    name: str
    role: str
    personality: str
    instructions: str
    skills: list[str]
    metadata: dict[str, Any]
    source: str


class PersonaAdapter:
    """Base adapter for persona formats."""

    @staticmethod
    def to_standard(data: dict[str, Any], source: str) -> Persona:
        """Convert to standard PAW persona format."""
        return Persona(
            name=data.get("name", "default"),
            role=data.get("role", "assistant"),
            personality=data.get("personality", ""),
            instructions=data.get("instructions", data.get("body", "")),
            skills=data.get("skills", []),
            metadata=data.get("metadata", {}),
            source=source,
        )


class QwenPawPersonaAdapter(PersonaAdapter):
    """Adapter for QwenPaw persona format."""

    @staticmethod
    def parse(content: str) -> dict[str, Any]:
        """Parse QwenPaw persona markdown with YAML frontmatter."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                body = parts[2].strip()
                try:
                    data = yaml.safe_load(fm_text) or {}
                    data["_body"] = body
                    return data
                except yaml.YAMLError:
                    pass
        return {"_body": content}

    @staticmethod
    def convert(data: dict[str, Any]) -> Persona:
        """Convert QwenPaw persona to standard format."""
        return PersonaAdapter.to_standard(data, "qwenpaw")


class NotebookLMPersonaAdapter(PersonaAdapter):
    """Adapter for NotebookLM persona format (if applicable)."""

    @staticmethod
    def parse(content: str) -> dict[str, Any]:
        """Parse NotebookLM persona format."""
        # NotebookLM typically uses JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def convert(data: dict[str, Any]) -> Persona:
        """Convert NotebookLM persona to standard format."""
        # Map NotebookLM fields to PAW fields
        mapped = {
            "name": data.get("name", data.get("title", "default")),
            "role": data.get("role", "researcher"),
            "personality": data.get("description", ""),
            "instructions": data.get("system_prompt", data.get("instructions", "")),
            "skills": data.get("tools", data.get("skills", [])),
            "metadata": data.get("metadata", {}),
        }
        return PersonaAdapter.to_standard(mapped, "notebooklm")


class GenericPersonaAdapter(PersonaAdapter):
    """Adapter for generic JSON/YAML persona format."""

    @staticmethod
    def parse_file(path: Path) -> dict[str, Any]:
        """Parse persona from file."""
        content = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        elif path.suffix == ".json":
            return json.loads(content)
        elif path.suffix == ".md":
            return QwenPawPersonaAdapter.parse(content)
        return {}

    @staticmethod
    def convert(data: dict[str, Any], source: str = "generic") -> Persona:
        """Convert generic persona to standard format."""
        return PersonaAdapter.to_standard(data, source)


class PersonaProvider:
    """Unified provider for loading personas from multiple sources."""

    def __init__(
        self,
        qwenpaw_path: str | Path | None = None,
        notebooklm_path: str | Path | None = None,
        generic_path: str | Path | None = None,
    ):
        self.qwenpaw_path = Path(qwenpaw_path) if qwenpaw_path else None
        self.notebooklm_path = Path(notebooklm_path) if notebooklm_path else None
        self.generic_path = Path(generic_path) if generic_path else None

    async def list_personas(self) -> list[Persona]:
        """List all personas from all sources."""
        personas = []

        if self.qwenpaw_path:
            for persona_file in self.qwenpaw_path.rglob("*.md"):
                try:
                    content = persona_file.read_text(encoding="utf-8")
                    data = QwenPawPersonaAdapter.parse(content)
                    personas.append(QwenPawPersonaAdapter.convert(data))
                except Exception:
                    pass

        if self.notebooklm_path:
            for persona_file in self.notebooklm_path.rglob("*.json"):
                try:
                    content = persona_file.read_text(encoding="utf-8")
                    data = NotebookLMPersonaAdapter.parse(content)
                    personas.append(NotebookLMPersonaAdapter.convert(data))
                except Exception:
                    pass

        if self.generic_path:
            for persona_file in self.generic_path.rglob("*"):
                if persona_file.suffix in (".yaml", ".yml", ".json", ".md"):
                    try:
                        data = GenericPersonaAdapter.parse_file(persona_file)
                        personas.append(GenericPersonaAdapter.convert(data, "generic"))
                    except Exception:
                        pass

        return personas

    async def get_persona(self, name: str) -> Persona | None:
        """Get a specific persona by name."""
        all_personas = await self.list_personas()
        for persona in all_personas:
            if persona.name == name:
                return persona
        return None

    async def import_persona(self, persona_data: dict[str, Any], source: str = "generic") -> Persona:
        """Import a persona from raw data."""
        if source == "qwenpaw":
            return QwenPawPersonaAdapter.convert(persona_data)
        elif source == "notebooklm":
            return NotebookLMPersonaAdapter.convert(persona_data)
        else:
            return GenericPersonaAdapter.convert(persona_data, source)
