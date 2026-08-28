"""
PAW Core — Skill Fabric

Skill discovery, validation, and loading. Skills are portable units of
capability with metadata for routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .logging import get_logger
from .models import Capability, Metadata, SkillRisk
from .storage import db

logger = get_logger(__name__)


@dataclass
class SkillManifest:
    """Parsed skill manifest from SKILL.md frontmatter + body.
    Compatible with prompt spec metadata structure:
    ---
    metadata:
      paw/version: "1.0"
      paw/category: coding
      paw/risk: low
      paw/capabilities: [filesystem.read, git.read]
      paw/executors: [local, opencode]
      paw/network: false
      paw/write: false
    ---
    """
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: str = "general"
    capabilities: list[Capability] = field(default_factory=list)
    risk: SkillRisk = SkillRisk.LOW
    network: bool = False
    write: bool = False
    trigger: str = ""
    body: str = ""
    source: str = "installed"  # 'builtin', 'installed', 'imported'
    enabled: bool = True
    dependencies: list[str] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
    # Prompt spec: paw/executors field
    executors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "capabilities": [c.value for c in self.capabilities],
            "risk": self.risk.value,
            "network": self.network,
            "write": self.write,
            "trigger": self.trigger,
            "body": self.body,
            "source": self.source,
            "enabled": self.enabled,
            "dependencies": self.dependencies,
            "metadata": self.metadata.data,
            "executors": self.executors,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SkillManifest:
        caps = []
        if data.get("capabilities"):
            caps = [Capability(c) for c in data["capabilities"]]
        meta = Metadata()
        if data.get("metadata"):
            meta.data = data["metadata"]
        # Extract executors from top-level or nested metadata.paw/executors
        executors = data.get("executors", [])
        if not executors and data.get("metadata"):
            paw_meta = data["metadata"].get("paw", {}) if isinstance(data["metadata"], dict) else {}
            if isinstance(paw_meta, dict):
                raw_execs = paw_meta.get("executors")
                if raw_execs:
                    executors = raw_execs if isinstance(raw_execs, list) else [raw_execs]
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            capabilities=caps,
            risk=SkillRisk(data.get("risk", "low")),
            network=data.get("network", False),
            write=data.get("write", False),
            trigger=data.get("trigger", ""),
            body=data.get("body", ""),
            source=data.get("source", "installed"),
            enabled=data.get("enabled", True),
            dependencies=data.get("dependencies", []),
            metadata=meta,
            executors=executors,
        )


class Skill:
    """Runtime skill instance with manifest and executable logic."""

    def __init__(self, manifest: SkillManifest, module: Any = None):
        self.manifest = manifest
        self.module = module  # Optional Python module for skills with code

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def trigger(self) -> str:
        return self.manifest.trigger

    @property
    def capabilities(self) -> list[Capability]:
        return self.manifest.capabilities

    def matches_query(self, query: str) -> bool:
        """Check if skill matches a natural language query."""
        query_lower = query.lower()
        trigger_lower = self.trigger.lower()
        desc_lower = self.manifest.description.lower()

        # Simple keyword matching - Phase 2 will enhance with semantic search
        return (
            trigger_lower in query_lower
            or any(word in query_lower for word in trigger_lower.split())
            or any(word in desc_lower for word in query_lower.split() if len(word) > 3)
        )


class SkillFabric:
    """Skill registry with lazy loading and metadata indexing."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: dict[str, Skill] = {}
        self._manifest_index: dict[str, SkillManifest] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Discover and index all skills."""
        if self._initialized:
            return

        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Load from database first
        await self._load_from_db()

        # Then discover from filesystem
        await self._discover_filesystem()

        self._initialized = True
        logger.info("skill_fabric_initialized", count=len(self._skills))

    async def _load_from_db(self) -> None:
        rows = await db.fetchall("SELECT * FROM skills WHERE enabled = 1")
        for row in rows:
            manifest = SkillManifest.from_dict({
                "name": row["name"],
                "version": row["version"],
                "description": row["description"] or "",
                "category": row["category"] or "general",
                "capabilities": json.loads(row["capabilities"]) if row["capabilities"] else [],
                "risk": row["risk"],
                "network": bool(row["network"]),
                "write": bool(row["write"]),
                "trigger": row["manifest"][:200] if row["manifest"] else "",
                "body": row["manifest"],
                "source": row["source"],
                "enabled": bool(row["enabled"]),
                "executors": json.loads(row["executors"]) if row.get("executors") else [],
            })
            self._manifest_index[manifest.name] = manifest

    async def _discover_filesystem(self) -> None:
        """Discover .md skill files in skills directory."""
        for skill_file in self.skills_dir.rglob("*.md"):
            try:
                manifest = self._parse_skill_file(skill_file)
                if manifest.name not in self._manifest_index:
                    self._manifest_index[manifest.name] = manifest
                    await self._save_to_db(manifest)
            except Exception as e:
                logger.warning("skill_parse_failed", file=str(skill_file), error=str(e))

    def _parse_skill_file(self, path: Path) -> SkillManifest:
        """Parse SKILL.md frontmatter and body.
        Supports prompt spec metadata.paw/ nested structure:
        ---
        metadata:
          paw/version: "1.0"
          paw/category: coding
          paw/capabilities: [filesystem.read]
          paw/executors: [local, opencode]
          paw/network: false
          paw/write: false
        ---
        """
        content = path.read_text(encoding="utf-8")

        frontmatter = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                body = parts[2].strip()
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        frontmatter[key.strip()] = val.strip()

        name = frontmatter.get("name", path.stem)
        trigger = frontmatter.get("trigger", "")
        if not trigger and frontmatter.get("description"):
            trigger = frontmatter["description"]

        # Parse capabilities — support both flat and nested paw/capabilities
        caps = []
        capabilities_source = None
        if "capabilities" in frontmatter:
            capabilities_source = frontmatter["capabilities"]
        elif (
            "metadata" in frontmatter
            and isinstance(frontmatter["metadata"], dict)
            and "paw" in frontmatter["metadata"]
            and "capabilities" in frontmatter["metadata"]["paw"]
        ):
            capabilities_source = frontmatter["metadata"]["paw"]["capabilities"]

        if capabilities_source:
            cap_str = capabilities_source
            if isinstance(cap_str, str):
                if cap_str.startswith("["):
                    import ast
                    cap_list = ast.literal_eval(cap_str)
                else:
                    cap_list = [c.strip() for c in cap_str.split(",")]
            else:
                cap_list = cap_str if isinstance(cap_str, list) else [cap_str]
            caps = [Capability(c) for c in cap_list]

        # Parse executors
        executors = []
        if "executors" in frontmatter:
            raw = frontmatter["executors"]
            executors = raw if isinstance(raw, list) else [raw]
        elif (
            "metadata" in frontmatter
            and isinstance(frontmatter["metadata"], dict)
            and "paw" in frontmatter["metadata"]
            and "executors" in frontmatter["metadata"]["paw"]
        ):
            raw = frontmatter["metadata"]["paw"]["executors"]
            executors = raw if isinstance(raw, list) else [raw]

        # Parse metadata.paw/ nested structure
        metadata = Metadata()
        paw_meta: dict[str, Any] = {}
        if "metadata" in frontmatter:
            meta_val = frontmatter["metadata"]
            if isinstance(meta_val, dict):
                if "paw" in meta_val and isinstance(meta_val["paw"], dict):
                    paw_meta = meta_val["paw"]
                    metadata.data = {"paw": paw_meta}
                else:
                    metadata.data = meta_val

        # Extract values from metadata.paw/ or frontmatter
        category = frontmatter.get("category", "general")
        if paw_meta and "category" in paw_meta:
            category = paw_meta["category"]

        risk_str = frontmatter.get("risk", "low")
        if paw_meta and "risk" in paw_meta:
            risk_str = str(paw_meta["risk"])

        network = frontmatter.get("network", "false")
        if paw_meta and "network" in paw_meta:
            network = paw_meta["network"]
        if isinstance(network, str):
            network = network.lower() == "true"

        write = frontmatter.get("write", "false")
        if paw_meta and "write" in paw_meta:
            write = paw_meta["write"]
        if isinstance(write, str):
            write = write.lower() == "true"

        version = frontmatter.get("version", "1.0.0")
        if paw_meta and "version" in paw_meta:
            version = str(paw_meta["version"])

        return SkillManifest(
            name=name,
            version=version,
            description=frontmatter.get("description", ""),
            category=category,
            capabilities=caps,
            risk=SkillRisk(risk_str),
            network=network,
            write=write,
            trigger=trigger,
            body=body,
            source="installed",
            enabled=True,
            executors=executors,
            metadata=metadata,
        )

    async def _save_to_db(self, manifest: SkillManifest) -> None:
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO skills (
                    name, version, description, category, capabilities, risk,
                    network, write, manifest, source, enabled, created_at, updated_at, executors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.name,
                    manifest.version,
                    manifest.description,
                    manifest.category,
                    json.dumps([c.value for c in manifest.capabilities]),
                    manifest.risk.value,
                    manifest.network,
                    manifest.write,
                    manifest.body,
                    manifest.source,
                    manifest.enabled,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                    json.dumps(manifest.executors),
                ),
            )

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name (lazy load if needed)."""
        if name in self._skills:
            return self._skills[name]

        if name in self._manifest_index:
            skill = Skill(self._manifest_index[name])
            self._skills[name] = skill
            return skill

        return None

    def list_skills(self, category: str | None = None, enabled_only: bool = True) -> list[SkillManifest]:
        """List all skill manifests (metadata only, no lazy load)."""
        skills = list(self._manifest_index.values())
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        if category:
            skills = [s for s in skills if s.category == category]
        return skills

    def find_candidates(self, query: str, max_results: int = 10) -> list[Skill]:
        """Find skills matching a query."""
        candidates = []
        for manifest in self._manifest_index.values():
            if not manifest.enabled:
                continue
            skill = Skill(manifest)
            if skill.matches_query(query):
                candidates.append(skill)
                if len(candidates) >= max_results:
                    break
        return candidates

    def get_categories(self) -> list[str]:
        return sorted(set(s.category for s in self._manifest_index.values()))


# Builtin skills (always available)
BUILTIN_SKILLS = [
    SkillManifest(
        name="echo",
        version="1.0.0",
        description="Echo back the input for testing",
        category="testing",
        capabilities=[],
        risk=SkillRisk.LOW,
        trigger="echo",
        body="# Echo Skill\n\nEchoes back input.",
        source="builtin",
        executors=["local"],
    ),
    SkillManifest(
        name="datetime",
        version="1.0.0",
        description="Get current date and time",
        category="utility",
        capabilities=[],
        risk=SkillRisk.LOW,
        trigger="datetime",
        body="# Datetime Skill\n\nReturns current datetime.",
        source="builtin",
        executors=["local"],
    ),
]


async def get_skill_fabric() -> SkillFabric:
    """Dependency injection helper."""
    from .config import settings
    fabric = SkillFabric(settings.skills_path)
    await fabric.initialize()

    # Register builtin skills
    for manifest in BUILTIN_SKILLS:
        if manifest.name not in fabric._manifest_index:
            fabric._manifest_index[manifest.name] = manifest

    return fabric