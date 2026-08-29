"""
PAW Core — Skill Fabric

Skill discovery, validation, and loading. Skills are portable units of
capability with metadata for routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .execution_profile import ExecutionProfile
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
      paw/executors: [local, mock]
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

    def __post_init__(self):
        """Convert string risk to SkillRisk enum if needed."""
        if isinstance(self.risk, str):
            self.risk = SkillRisk(self.risk)

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
        # Extract capabilities from top-level or nested metadata.paw
        capabilities_source = data.get("capabilities")
        if not capabilities_source:
            # Check metadata.paw/ prefixed keys
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                # Try nested paw dict
                paw_meta = metadata.get("paw", {}) if isinstance(metadata.get("paw"), dict) else {}
                if paw_meta:
                    capabilities_source = paw_meta.get("capabilities")
                else:
                    # Check paw/ prefixed keys
                    for key, val in metadata.items():
                        if key == "paw/capabilities":
                            capabilities_source = val
                            break

        caps = []
        if capabilities_source:
            cap_list = capabilities_source
            if isinstance(cap_list, str):
                if cap_list.startswith("["):
                    import ast
                    cap_list = ast.literal_eval(cap_list)
                else:
                    cap_list = [c.strip() for c in cap_list.split(",")]
            elif not isinstance(cap_list, list):
                cap_list = [cap_list]
            caps = [Capability(c) for c in cap_list]

        meta = Metadata()
        paw_meta = {}
        if data.get("metadata"):
            meta.data = data["metadata"]
            if isinstance(data["metadata"], dict):
                # Try nested paw dict first
                paw_meta = data["metadata"].get("paw", {}) if isinstance(data["metadata"].get("paw"), dict) else {}
                # Also handle paw/ prefixed keys
                if not paw_meta:
                    for key, val in data["metadata"].items():
                        if key.startswith("paw/"):
                            field_name = key.split("/", 1)[1]
                            paw_meta[field_name] = val

        # Extract executors from top-level or nested metadata.paw/executors
        executors = data.get("executors", [])
        if not executors and paw_meta:
            raw_execs = paw_meta.get("executors")
            if raw_execs:
                executors = raw_execs if isinstance(raw_execs, list) else [raw_execs]

        # Extract category, risk, network, write from metadata.paw or top-level
        category = data.get("category", paw_meta.get("category", "general"))
        risk = data.get("risk", paw_meta.get("risk", "low"))
        network = data.get("network", paw_meta.get("network", False))
        write = data.get("write", paw_meta.get("write", False))
        version = data.get("version", paw_meta.get("version", "1.0.0"))

        # Convert string booleans
        if isinstance(network, str):
            network = network.lower() == "true"
        if isinstance(write, str):
            write = write.lower() == "true"

        return cls(
            name=data.get("name", "unnamed"),
            version=str(version),
            description=data.get("description", ""),
            category=category,
            capabilities=caps,
            risk=SkillRisk(risk),
            network=network,
            write=write,
            trigger=data.get("trigger", ""),
            body=data.get("body", ""),
            source=data.get("source", "installed"),
            enabled=data.get("enabled", True),
            dependencies=data.get("dependencies", []),
            metadata=meta,
            executors=executors,
        )


# Builtin skills (always available) - defined after SkillManifest class
BUILTIN_SKILLS = [
    SkillManifest(
        name="echo",
        version="1.0.0",
        description="Echo back the input for testing",
        category="utility",
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

        # Register builtin skills first
        for manifest in BUILTIN_SKILLS:
            if manifest.name not in self._manifest_index:
                self._manifest_index[manifest.name] = manifest

        # Load from database first
        await self._load_from_db()

        # Then discover from filesystem
        await self._discover_filesystem()

        self._initialized = True
        logger.info("skill_fabric_initialized", count=len(self._skills))

    async def _load_from_db(self) -> None:
        rows = await db.fetchall("SELECT * FROM skills WHERE enabled = 1")
        for row in rows:
            row_dict = dict(row)
            # Handle migration: 'manifest' column -> 'body' column
            body = row_dict.get("body") or row_dict.get("manifest") or ""
            manifest = SkillManifest.from_dict({
                "name": row_dict["name"],
                "version": row_dict["version"],
                "description": row_dict["description"] or "",
                "category": row_dict["category"] or "general",
                "capabilities": json.loads(row_dict["capabilities"]) if row_dict["capabilities"] else [],
                "risk": row_dict["risk"],
                "network": bool(row_dict["network"]),
                "write": bool(row_dict["write"]),
                "trigger": row_dict["trigger"],
                "body": body,
                "source": row_dict["source"],
                "enabled": bool(row_dict["enabled"]),
                "executors": json.loads(row_dict["executors"]) if row_dict["executors"] else [],
                "dependencies": json.loads(row_dict["dependencies"]) if row_dict.get("dependencies") else [],
                "metadata": json.loads(row_dict["metadata"]) if row_dict.get("metadata") else {},
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
        """Parse SKILL.md frontmatter and body using PyYAML.
        Supports prompt spec metadata.paw/ nested structure:
        ---
        metadata:
          paw/version: "1.0"
          paw/category: coding
          paw/capabilities: [filesystem.read]
          paw/executors: [local, mock]
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
                # Parse YAML frontmatter
                try:
                    frontmatter = yaml.safe_load(fm_text) or {}
                except yaml.YAMLError:
                    # Fallback to simple parsing
                    for line in fm_text.split("\n"):
                        if ":" in line:
                            key, val = line.split(":", 1)
                            frontmatter[key.strip()] = val.strip()

        name = frontmatter.get("name")
        if not name:
            # Try to extract title from body (# Title)
            import re
            title_match = re.search(r'^#\s+(.+)$', body.strip(), re.MULTILINE)
            name = title_match.group(1).strip() if title_match else path.stem
        trigger = frontmatter.get("trigger", "")
        if not trigger and frontmatter.get("description"):
            trigger = frontmatter["description"]

        # Parse capabilities - support multiple formats
        caps = []
        # Format 1: flat capabilities list
        capabilities_source = frontmatter.get("capabilities")
        # Format 2: prompt spec metadata.paw/ nested
        if not capabilities_source:
            metadata = frontmatter.get("metadata", {})
            if isinstance(metadata, dict):
                # Handle paw/ prefixed keys
                for key, val in metadata.items():
                    if key.startswith("paw/"):
                        field_name = key.split("/", 1)[1]
                        if field_name == "capabilities":
                            capabilities_source = val
                            break
                # Also handle nested paw dict
                if not capabilities_source and "paw" in metadata:
                    paw = metadata["paw"]
                    if isinstance(paw, dict):
                        capabilities_source = paw.get("capabilities")

        if capabilities_source:
            cap_list = capabilities_source
            if isinstance(cap_str := capabilities_source, str):
                if cap_str.startswith("["):
                    import ast
                    cap_list = ast.literal_eval(cap_str)
                else:
                    cap_list = [c.strip() for c in cap_str.split(",")]
            elif not isinstance(cap_list, list):
                cap_list = [cap_list]
            caps = [Capability(c) for c in cap_list]

        # Parse executors
        executors = []
        executors_source = frontmatter.get("executors")
        if not executors_source:
            metadata = frontmatter.get("metadata", {})
            if isinstance(metadata, dict):
                for key, val in metadata.items():
                    if key.startswith("paw/"):
                        field_name = key.split("/", 1)[1]
                        if field_name == "executors":
                            executors_source = val
                            break
                if not executors_source and "paw" in metadata:
                    paw = metadata["paw"]
                    if isinstance(paw, dict):
                        executors_source = paw.get("executors")

        if executors_source:
            executors = executors_source if isinstance(executors_source, list) else [executors_source]

        # Parse metadata.paw/ nested structure
        metadata_obj = Metadata()
        paw_meta: dict[str, Any] = {}
        metadata_raw = frontmatter.get("metadata", {})
        if isinstance(metadata_raw, dict):
            # Convert paw/ prefixed keys to nested paw dict
            for key, val in metadata_raw.items():
                if key.startswith("paw/"):
                    field_name = key.split("/", 1)[1]
                    paw_meta[field_name] = val
            # Also include nested paw dict if present
            if "paw" in metadata_raw and isinstance(metadata_raw["paw"], dict):
                paw_meta.update(metadata_raw["paw"])
            metadata_obj.data = {"paw": paw_meta} if paw_meta else metadata_raw

        # Extract values from metadata.paw/ or frontmatter
        def get_val(frontmatter_key: str, paw_key: str, default: Any) -> Any:
            # Try frontmatter first
            if frontmatter_key in frontmatter:
                return frontmatter[frontmatter_key]
            # Then paw meta
            if paw_key in paw_meta:
                return paw_meta[paw_key]
            return default

        category = get_val("category", "category", "general")
        risk_str = str(get_val("risk", "risk", "low"))
        network = get_val("network", "network", "false")
        write = get_val("write", "write", "false")
        version = str(get_val("version", "version", "1.0.0"))

        # Convert string booleans
        if isinstance(network, str):
            network = network.lower() == "true"
        if isinstance(write, str):
            write = write.lower() == "true"

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
            metadata=metadata_obj,
        )

    async def _save_to_db(self, manifest: SkillManifest) -> None:
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO skills (
                    id, name, version, description, category, capabilities, risk,
                    network, write, trigger, body, source, enabled,
                    created_at, updated_at, executors, dependencies, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.name,  # Use name as ID
                    manifest.name,
                    manifest.version,
                    manifest.description,
                    manifest.category,
                    json.dumps([c.value for c in manifest.capabilities]),
                    manifest.risk.value,
                    manifest.network,
                    manifest.write,
                    manifest.trigger,
                    manifest.body,
                    manifest.source,
                    manifest.enabled,
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                    json.dumps(manifest.executors),
                    json.dumps(manifest.dependencies),
                    json.dumps(manifest.metadata.data),
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

    def list_skills(
        self,
        category: str | None = None,
        enabled_only: bool = True,
        execution_profile: ExecutionProfile | None = None,
    ) -> list[SkillManifest]:
        """List all skill manifests (metadata only, no lazy load)."""
        skills = list(self._manifest_index.values())
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        if category:
            skills = [s for s in skills if s.category == category]
        # Apply execution profile filters
        if execution_profile is not None:
            if execution_profile.skill_categories:
                skills = [s for s in skills if s.category in execution_profile.skill_categories]
            # Filter by risk tolerance
            risk_order = {"low": 0, "medium": 1, "high": 2}
            max_risk = risk_order.get(execution_profile.skill_risk_tolerance.value, 0)
            skills = [s for s in skills if risk_order.get(s.risk.value, 0) <= max_risk]
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
        return sorted({s.category for s in self._manifest_index.values()})


async def get_skill_fabric() -> SkillFabric:
    """Dependency injection helper."""
    from .config import settings
    fabric = SkillFabric(settings.skills_path)
    await fabric.initialize()
    return fabric
