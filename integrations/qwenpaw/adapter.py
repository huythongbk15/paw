"""
PAW Providers — QwenPaw Adapter

Converts QwenPaw skills, memory, and personas to PAW Core formats.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

import yaml

from paw.core.models import Capability, SkillRisk
from paw.core.skills import SkillManifest


@dataclass
class QwenPawSkillAdapter:
    """Adapter to convert QwenPaw skill format to PAW SkillManifest."""

    @staticmethod
    def parse_qwenpaw_skill(content: str) -> SkillManifest:
        """
        Parse QwenPaw skill format.

        QwenPaw skills typically have:
        - name, description, instructions
        - parameters (JSON schema)
        - metadata with capabilities, executors
        """
        # Try YAML frontmatter first
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                body = parts[2].strip()
                try:
                    data = yaml.safe_load(fm_text) or {}
                except yaml.YAMLError:
                    data = {}
            else:
                data = {}
                body = content
        else:
            data = {}
            body = content

        # Extract capabilities from metadata.paw/ or direct fields
        caps = []
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            # Check paw/ prefixed keys
            for key, val in metadata.items():
                if key == "paw/capabilities":
                    if isinstance(val, str) and val.startswith("["):
                        import ast
                        cap_list = ast.literal_eval(val)
                    elif isinstance(val, list):
                        cap_list = val
                    else:
                        cap_list = [c.strip() for c in str(val).split(",")]
                    caps = [Capability(c) for c in cap_list]
                    break
                elif key.startswith("paw/"):
                    # Single capability
                    pass

        # Extract executors
        executors = []
        if isinstance(metadata, dict):
            for key, val in metadata.items():
                if key == "paw/executors":
                    executors = val if isinstance(val, list) else [val]
                    break

        # Parse risk
        risk = SkillRisk.LOW
        if isinstance(metadata, dict):
            for key, val in metadata.items():
                if key == "paw/risk":
                    risk = SkillRisk(str(val))
                    break

        # Network/write flags
        network = False
        write = False
        if isinstance(metadata, dict):
            for key, val in metadata.items():
                if key == "paw/network":
                    network = str(val).lower() == "true"
                elif key == "paw/write":
                    write = str(val).lower() == "true"

        # Build manifest
        return SkillManifest(
            name=data.get("name", "unnamed"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            capabilities=caps,
            risk=risk,
            network=network,
            write=write,
            trigger=data.get("trigger", data.get("name", "")),
            body=body,
            source="qwenpaw",
            enabled=True,
            executors=executors,
        )

    @staticmethod
    def convert_qwenpaw_skill(skill_data: dict[str, Any]) -> SkillManifest:
        """Convert QwenPaw skill dict to PAW SkillManifest."""
        # QwenPaw skill structure typically has:
        # name, description, instructions, parameters, metadata
        caps = []
        executors = []
        risk = SkillRisk.LOW
        network = False
        write = False

        metadata = skill_data.get("metadata", {})
        if isinstance(metadata, dict):
            # Handle paw/ prefixed keys
            for key, val in metadata.items():
                if key == "paw/capabilities":
                    if isinstance(val, str) and val.startswith("["):
                        import ast
                        cap_list = ast.literal_eval(val)
                    elif isinstance(val, list):
                        cap_list = val
                    else:
                        cap_list = [c.strip() for c in str(val).split(",")]
                    caps = [Capability(c) for c in cap_list]
                elif key == "paw/executors":
                    executors = val if isinstance(val, list) else [val]
                elif key == "paw/risk":
                    risk = SkillRisk(str(val))
                elif key == "paw/network":
                    network = str(val).lower() == "true"
                elif key == "paw/write":
                    write = str(val).lower() == "true"

        return SkillManifest(
            name=skill_data.get("name", "unnamed"),
            version=skill_data.get("version", "1.0.0"),
            description=skill_data.get("description", ""),
            category=skill_data.get("category", "general"),
            capabilities=caps,
            risk=risk,
            network=network,
            write=write,
            trigger=skill_data.get("trigger", skill_data.get("name", "")),
            body=skill_data.get("instructions", skill_data.get("body", "")),
            source="qwenpaw",
            enabled=True,
            executors=executors,
        )


class QwenPawSkillProvider:
    """Provider to load and convert QwenPaw skills."""

    def __init__(self, skills_path: str | Path):
        self.skills_path = Path(skills_path)

    async def list_skills(self) -> list[dict[str, Any]]:
        """List all QwenPaw skills."""
        skills = []
        for skill_file in self.skills_path.rglob("*.md"):
            if skill_file.is_file():
                content = skill_file.read_text(encoding="utf-8")
                try:
                    manifest = QwenPawSkillAdapter.parse_qwenpaw_skill(content)
                    skills.append({
                        "name": manifest.name,
                        "path": str(skill_file),
                        "category": manifest.category,
                        "capabilities": [c.value for c in manifest.capabilities],
                    })
                except Exception:
                    pass
        return skills

    async def get_skill(self, name: str) -> SkillManifest | None:
        """Get a specific QwenPaw skill by name."""
        for skill_file in self.skills_path.rglob("*.md"):
            content = skill_file.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        data = yaml.safe_load(parts[1].strip()) or {}
                        if data.get("name") == name:
                            return QwenPawSkillAdapter.parse_qwenpaw_skill(content)
                    except yaml.YAMLError:
                        pass
        return None


class QwenPawMemoryAdapter:
    """Adapter to convert QwenPaw/ReMe memory format to PAW MemoryRecord."""

    @staticmethod
    def convert_reme_memory(memory_data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert ReMe memory format to PAW MemoryRecord format.

        ReMe format typically has:
        - content, embedding, metadata, created_at
        - importance, tags, project_id
        """
        from datetime import datetime

        content = memory_data.get("content", "")
        metadata = memory_data.get("metadata", {})

        return {
            "id": memory_data.get("id", ""),
            "memory_type": metadata.get("type", "episodic"),
            "project_id": metadata.get("project_id", "default"),
            "task_id": metadata.get("task_id"),
            "content": content,
            "embedding": memory_data.get("embedding"),
            "importance": metadata.get("importance", 0.5),
            "tags": metadata.get("tags", []),
            "created_at": memory_data.get("created_at", datetime.now(UTC).isoformat()),
            "updated_at": memory_data.get("updated_at", datetime.now(UTC).isoformat()),
            "source": "reme",
        }

    @staticmethod
    def convert_qwenpaw_memory(memory_data: dict[str, Any]) -> dict[str, Any]:
        """Convert QwenPaw memory to PAW MemoryRecord."""
        return QwenPawMemoryAdapter.convert_reme_memory(memory_data)


class QwenPawMemoryProvider:
    """Provider to load and convert QwenPaw/ReMe memories."""

    def __init__(self, memory_path: str | Path):
        self.memory_path = Path(memory_path)

    async def query(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Query ReMe memories."""
        memories = []
        for mem_file in self.memory_path.rglob("*.json"):
            try:
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                # Simple text search
                if query.lower() in data.get("content", "").lower():
                    memories.append(QwenPawMemoryAdapter.convert_reme_memory(data))
            except Exception:
                pass
        return memories[:limit]

    async def store(self, memory: dict[str, Any]) -> str:
        """Store a memory (not implemented for read-only adapter)."""
        raise NotImplementedError("QwenPaw adapter is read-only")


class QwenPawPersonaAdapter:
    """Adapter to convert QwenPaw persona format to PAW format."""

    @staticmethod
    def parse_persona(content: str) -> dict[str, Any]:
        """
        Parse QwenPaw persona format.

        Typical format:
        ---
        name: "Assistant"
        role: "helpful assistant"
        personality: "..."
        skills: [...]
        ---
        """
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
    def convert_persona(persona_data: dict[str, Any]) -> dict[str, Any]:
        """Convert QwenPaw persona to PAW persona format."""
        return {
            "name": persona_data.get("name", "default"),
            "role": persona_data.get("role", "assistant"),
            "personality": persona_data.get("personality", ""),
            "instructions": persona_data.get("instructions", persona_data.get("_body", "")),
            "skills": persona_data.get("skills", []),
            "metadata": persona_data.get("metadata", {}),
            "source": "qwenpaw",
        }


class QwenPawPersonaProvider:
    """Provider to load and convert QwenPaw personas."""

    def __init__(self, persona_path: str | Path):
        self.persona_path = Path(persona_path)

    async def list_personas(self) -> list[dict[str, Any]]:
        """List all QwenPaw personas."""
        personas = []
        for persona_file in self.persona_path.rglob("*.md"):
            if persona_file.is_file():
                content = persona_file.read_text(encoding="utf-8")
                try:
                    data = QwenPawPersonaAdapter.parse_persona(content)
                    personas.append(QwenPawPersonaAdapter.convert_persona(data))
                except Exception:
                    pass
        return personas

    async def get_persona(self, name: str) -> dict[str, Any] | None:
        """Get a specific persona by name."""
        for persona_file in self.persona_path.rglob("*.md"):
            content = persona_file.read_text(encoding="utf-8")
            data = QwenPawPersonaAdapter.parse_persona(content)
            if data.get("name") == name:
                return QwenPawPersonaAdapter.convert_persona(data)
        return None
