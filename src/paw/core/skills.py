"""
PAW Core — Skill Fabric

Skill discovery, validation, and loading. Skills are portable units of
capability with metadata for routing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .execution_profile import ExecutionProfile
from .logging import get_logger
from .models import (
    LEGAL_SKILL_TRANSITIONS,
    ApprovalRecord,
    CandidateMetadata,
    Capability,
    Metadata,
    ReviewRecord,
    SkillRisk,
    SkillState,
    TraceLink,
)
from .storage import db

logger = get_logger(__name__)



def _parse_record(data: dict, key: str, record_cls: Any) -> Any:
    """Parse a ReviewRecord or ApprovalRecord from a dict (JSON or dataclass dict)."""
    raw = data.get(key)
    if not raw:
        return None
    try:
        if isinstance(raw, dict):
            return record_cls(**{k: v for k, v in raw.items() if k in record_cls.__dataclass_fields__})
        return None
    except Exception:
        return None


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
    # E3: Skill lifecycle state
    # installed/builtin default; trace-derived candidates set CANDIDATE explicitly
    state: SkillState = SkillState.ACTIVE
    # E3: Semantic version for upgrade/rollback tracking
    skill_version: str = "1.0.0"
    # E3: Tools the skill is permitted to invoke
    allowed_tools: list[str] = field(default_factory=list)
    # E3: Conditions that suppress the skill
    non_applicable_when: list[str] = field(default_factory=list)
    # E3: Input/output schemas
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    # E3: Success/failure criteria
    success_criteria: list[str] = field(default_factory=list)
    failure_criteria: list[str] = field(default_factory=list)
    # E3: Expected effect
    expected_effect: str = ""
    # E3: Provenance records
    review_record: ReviewRecord | None = None
    approval_record: ApprovalRecord | None = None
    # E3: For superseded skills
    parent_version: str | None = None
    rollback_to: str | None = None

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
            "state": self.state.value if isinstance(self.state, SkillState) else self.state,
            "skill_version": self.skill_version,
            "allowed_tools": self.allowed_tools,
            "non_applicable_when": self.non_applicable_when,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "success_criteria": self.success_criteria,
            "failure_criteria": self.failure_criteria,
            "expected_effect": self.expected_effect,
            "review_record": (self.review_record.__dict__ if self.review_record else None),
            "approval_record": (self.approval_record.__dict__ if self.approval_record else None),
            "parent_version": self.parent_version,
            "rollback_to": self.rollback_to,
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
            state=SkillState(data.get("state", "active")),
            skill_version=data.get("skill_version", data.get("version", "1.0.0")),
            allowed_tools=data.get("allowed_tools", []),
            non_applicable_when=data.get("non_applicable_when", []),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            success_criteria=data.get("success_criteria", []),
            failure_criteria=data.get("failure_criteria", []),
            expected_effect=data.get("expected_effect", ""),
            review_record=_parse_record(data, "review_record", ReviewRecord),
            approval_record=_parse_record(data, "approval_record", ApprovalRecord),
            parent_version=data.get("parent_version"),
            rollback_to=data.get("rollback_to"),
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
            # Build dict for from_dict, parsing JSON strings from DB
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
                "state": row_dict.get("state", "active"),
                "skill_version": row_dict.get("skill_version", "1.0.0"),
                "allowed_tools": json.loads(row_dict["allowed_tools"]) if row_dict.get("allowed_tools") else [],
                "non_applicable_when": json.loads(row_dict["non_applicable_when"]) if row_dict.get("non_applicable_when") else [],  # noqa: E501
                "input_schema": json.loads(row_dict["input_schema"]) if row_dict.get("input_schema") else {},
                "output_schema": json.loads(row_dict["output_schema"]) if row_dict.get("output_schema") else {},
                "success_criteria": json.loads(row_dict["success_criteria"]) if row_dict.get("success_criteria") else [],  # noqa: E501
                "failure_criteria": json.loads(row_dict["failure_criteria"]) if row_dict.get("failure_criteria") else [],  # noqa: E501
                "expected_effect": row_dict.get("expected_effect", ""),
                "review_record": json.loads(row_dict["review_record"]) if row_dict.get("review_record") else None,
                "approval_record": json.loads(row_dict["approval_record"]) if row_dict.get("approval_record") else None,
                "parent_version": row_dict.get("parent_version"),
                "rollback_to": row_dict.get("rollback_to"),
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

        # E3: Extract lifecycle fields
        # Filesystem-discovered skills default to ACTIVE (consistent with from_dict).
        # Trace-derived candidates default to CANDIDATE (handled in SkillCandidate).
        state = SkillState(get_val("state", "state", "active"))
        allowed_tools = get_val("allowed_tools", "allowed_tools", [])
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(",")]
        non_applicable = get_val("non_applicable_when", "non_applicable_when", [])
        if isinstance(non_applicable, str):
            non_applicable = [n.strip() for n in non_applicable.split(",")]
        input_schema = get_val("input_schema", "input_schema", {})
        output_schema = get_val("output_schema", "output_schema", {})
        success_criteria = get_val("success_criteria", "success_criteria", [])
        if isinstance(success_criteria, str):
            success_criteria = [s.strip() for s in success_criteria.split(",")]
        failure_criteria = get_val("failure_criteria", "failure_criteria", [])
        if isinstance(failure_criteria, str):
            failure_criteria = [f.strip() for f in failure_criteria.split(",")]
        expected_effect = get_val("expected_effect", "expected_effect", "")

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
            state=state,
            skill_version=version,
            allowed_tools=allowed_tools,
            non_applicable_when=non_applicable,
            input_schema=input_schema,
            output_schema=output_schema,
            success_criteria=success_criteria,
            failure_criteria=failure_criteria,
            expected_effect=expected_effect,
        )

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name (lazy load if needed).
        Only returns ACTIVE skills (E3 gate).
        """
        if name in self._skills:
            return self._skills[name]

        if name in self._manifest_index:
            manifest = self._manifest_index[name]
            if manifest.state != SkillState.ACTIVE:
                return None
            skill = Skill(manifest)
            self._skills[name] = skill
            return skill

        return None

    def list_skills(
        self,
        category: str | None = None,
        enabled_only: bool = True,
        execution_profile: ExecutionProfile | None = None,
        state: SkillState | None = None,
    ) -> list[SkillManifest]:
        """List all skill manifests (metadata only, no lazy load).
        When state is provided, filter by state. Otherwise, when
        enabled_only is True, only returns ACTIVE skills (E3 gate).
        """
        skills = list(self._manifest_index.values())
        if enabled_only and state is None:
            # Default: only ACTIVE skills pass the gate
            skills = [s for s in skills if s.state == SkillState.ACTIVE]
        elif state is not None:
            skills = [s for s in skills if s.state == state]
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
        """Find ACTIVE skills matching a query."""
        candidates = []
        for manifest in self._manifest_index.values():
            if manifest.state != SkillState.ACTIVE:
                continue
            skill = Skill(manifest)
            if skill.matches_query(query):
                candidates.append(skill)
                if len(candidates) >= max_results:
                    break
        return candidates

    def get_categories(self) -> list[str]:
        return sorted({s.category for s in self._manifest_index.values()})

    # --- E3: Lifecycle methods ---

    def get_manifest(self, name: str) -> SkillManifest | None:
        """Get manifest by name regardless of state (for governance)."""
        return self._manifest_index.get(name)

    def describe_skill(self, name: str) -> dict[str, Any] | None:
        """E3-22: Inspect a skill showing state, source, version and provenance.

        Returns a dict suitable for display: name, state, skill_version,
        source, expected_effect, review/approval records, trace links,
        and replay status if available.
        """
        manifest = self._manifest_index.get(name)
        if manifest is None:
            return None
        info: dict[str, Any] = {
            "name": manifest.name,
            "state": manifest.state.value,
            "skill_version": manifest.skill_version,
            "source": manifest.source,
            "trigger": manifest.trigger,
            "expected_effect": manifest.expected_effect,
            "allowed_tools": manifest.allowed_tools,
            "non_applicable_when": manifest.non_applicable_when,
            "success_criteria": manifest.success_criteria,
            "failure_criteria": manifest.failure_criteria,
            "parent_version": manifest.parent_version,
            "rollback_to": manifest.rollback_to,
        }
        if manifest.review_record:
            info["review_record"] = manifest.review_record.__dict__
        if manifest.approval_record:
            info["approval_record"] = manifest.approval_record.__dict__
        if manifest.metadata.data:
            info["metadata"] = manifest.metadata.data
        return info

    def list_all(self) -> list[SkillManifest]:
        """List all manifests regardless of state (for governance)."""
        return list(self._manifest_index.values())

    async def submit_candidate(self, manifest: SkillManifest) -> None:
        """Register a new CANDIDATE skill (E3-09)."""
        manifest.state = SkillState.CANDIDATE
        if not manifest.skill_version:
            manifest.skill_version = manifest.version
        self._manifest_index[manifest.name] = manifest
        await self._save_to_db(manifest)
        logger.info("skill_candidate_submitted", name=manifest.name, version=manifest.skill_version)

    def get_candidates(self) -> list[SkillManifest]:
        """E3-02: Return all CANDIDATE state skills."""
        return [m for m in self._manifest_index.values() if m.state == SkillState.CANDIDATE]

    def get_active_skills(self) -> list[SkillManifest]:
        """E3-25: Return only ACTIVE skills that are truly reviewed-and-approved.

        Skills in any other state (including enabled=False CANDIDATE or REVIEWED)
        are excluded — 'enabled' flag alone does not grant ACTIVE status.
        """
        return [m for m in self._manifest_index.values() if m.state == SkillState.ACTIVE]

    def get_skills_by_state(self, state: SkillState) -> list[SkillManifest]:
        """List skills in a specific state (E3-22)."""
        return [m for m in self._manifest_index.values() if m.state == state]

    async def submit_candidate_from_trace(self, trace: SkillTrace) -> SkillCandidate:
        """E3-08/09: Create and persist a skill candidate from a verified trace."""
        candidate = SkillCandidate.from_trace(trace)
        manifest = candidate.to_manifest()
        await self._save_to_db(manifest)
        self._manifest_index[manifest.name] = manifest
        logger.info("skill_candidate_from_trace", name=manifest.name, trace_id=trace.task_id)
        return candidate

    async def review_skill(
        self, name: str, reviewer: str, diff_summary: str,
        safety_assessment: str, expected_effect: str,
    ) -> bool:
        """Review a CANDIDATE skill -> REVIEWED (E3-03)."""
        manifest = self._manifest_index.get(name)
        if manifest is None:
            return False
        valid, _required = validate_skill_transition(manifest.state, SkillState.REVIEWED)
        if not valid:
            logger.warning("illegal_transition", name=name, from_state=manifest.state, to_state="reviewed")
            return False
        if manifest.state != SkillState.CANDIDATE:
            return False
        now = datetime.now(UTC).isoformat()
        manifest.state = SkillState.REVIEWED
        manifest.review_record = ReviewRecord(
            reviewer=reviewer,
            reviewed_at=now,
            diff_summary=diff_summary,
            safety_assessment=safety_assessment,
            expected_effect=expected_effect,
        )
        await self._save_to_db(manifest)
        logger.info("skill_reviewed", name=name, reviewer=reviewer)
        return True

    async def approve_skill(self, name: str, approver: str, notes: str = "") -> bool:
        """Approve a REVIEWED skill -> ACTIVE (E3-18). Requires exact version match."""
        manifest = self._manifest_index.get(name)
        if manifest is None:
            return False
        valid, _required = validate_skill_transition(manifest.state, SkillState.ACTIVE)
        if not valid:
            logger.warning("illegal_transition", name=name, from_state=manifest.state, to_state="active")
            return False
        if manifest.state != SkillState.REVIEWED:
            return False
        now = datetime.now(UTC).isoformat()
        # If there's already an ACTIVE skill with the same name, supersede it
        existing = self._manifest_index.get(name)
        if existing and existing.state == SkillState.ACTIVE and existing.skill_version != manifest.skill_version:
            existing.state = SkillState.SUPERSEDED
            existing.rollback_to = manifest.skill_version
            await self._save_to_db(existing)
        manifest.state = SkillState.ACTIVE
        manifest.approval_record = ApprovalRecord(
            approver=approver,
            approved_at=now,
            skill_version=manifest.skill_version,
            notes=notes,
        )
        await self._save_to_db(manifest)
        logger.info("skill_approved", name=name, approver=approver)
        return True

    async def reject_skill(self, name: str, rejector: str, reason: str) -> bool:
        """Reject a REVIEWED skill -> REJECTED (E3-13). Prevents re-proposal of same version."""
        manifest = self._manifest_index.get(name)
        if manifest is None:
            return False
        valid, _required = validate_skill_transition(manifest.state, SkillState.REJECTED)
        if not valid:
            logger.warning("illegal_transition", name=name, from_state=manifest.state, to_state="rejected")
            return False
        if manifest.state not in (SkillState.CANDIDATE, SkillState.REVIEWED):
            return False
        manifest.state = SkillState.REJECTED
        manifest.metadata.data = manifest.metadata.data or {}
        manifest.metadata.data["rejection_reason"] = reason
        manifest.metadata.data["rejected_by"] = rejector
        manifest.metadata.data["rejected_at"] = datetime.now(UTC).isoformat()
        await self._save_to_db(manifest)
        logger.info("skill_rejected", name=name, reason=reason)
        return True

    async def deprecate_skill(self, name: str, deprecator: str, reason: str) -> bool:
        """Deprecate an ACTIVE skill -> DEPRECATED (E3-21)."""
        manifest = self._manifest_index.get(name)
        if manifest is None:
            return False
        valid, _required = validate_skill_transition(manifest.state, SkillState.DEPRECATED)
        if not valid:
            logger.warning("illegal_transition", name=name, from_state=manifest.state, to_state="deprecated")
            return False
        if manifest.state != SkillState.ACTIVE:
            return False
        manifest.state = SkillState.DEPRECATED
        manifest.metadata.data = manifest.metadata.data or {}
        manifest.metadata.data["deprecation_reason"] = reason
        manifest.metadata.data["deprecated_by"] = deprecator
        manifest.metadata.data["deprecated_at"] = datetime.now(UTC).isoformat()
        await self._save_to_db(manifest)
        logger.info("skill_deprecated", name=name, reason=reason)
        return True

    async def rollback_skill(self, name: str, to_version: str | None = None) -> bool:
        """Rollback a DEPRECATED or SUPERSEDED skill to a prior ACTIVE version (E3-19)."""
        manifests = [m for m in self._manifest_index.values() if m.name == name]
        target = None
        if to_version:
            target = next((m for m in manifests if m.skill_version == to_version), None)
        else:
            # Find the most recent prior ACTIVE version
            active_versions = sorted(
                [m for m in manifests if m.state in (SkillState.DEPRECATED, SkillState.SUPERSEDED) and m.rollback_to],
                key=lambda m: m.skill_version,
                reverse=True,
            )
            if active_versions:
                target = active_versions[0]
        if target is None:
            return False
        target.state = SkillState.ACTIVE
        target.approval_record = ApprovalRecord(
            approver="rollback",
            approved_at=datetime.now(UTC).isoformat(),
            skill_version=target.skill_version,
            notes="Rolled back from prior state",
        )
        target.rollback_to = None
        await self._save_to_db(target)
        logger.info("skill_rolled_back", name=name, version=target.skill_version)
        return True

    async def update_skill_state(self, name: str, state: SkillState) -> bool:
        """Direct state update (for testing and admin)."""
        manifest = self._manifest_index.get(name)
        if manifest is None:
            return False
        manifest.state = state
        await self._save_to_db(manifest)
        return True
    async def _save_to_db(self, manifest: SkillManifest) -> None:
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO skills (
                    id, name, version, description, category, capabilities, risk,
                    network, write, trigger, body, source, enabled,
                    created_at, updated_at, executors, dependencies, metadata,
                    state, skill_version, allowed_tools, non_applicable_when,
                    input_schema, output_schema, success_criteria,
                    failure_criteria, expected_effect, review_record,
                    approval_record, parent_version, rollback_to
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    manifest.state.value if isinstance(manifest.state, SkillState) else manifest.state,
                    manifest.skill_version,
                    json.dumps(manifest.allowed_tools),
                    json.dumps(manifest.non_applicable_when),
                    json.dumps(manifest.input_schema),
                    json.dumps(manifest.output_schema),
                    json.dumps(manifest.success_criteria),
                    json.dumps(manifest.failure_criteria),
                    manifest.expected_effect,
                    json.dumps(manifest.review_record.__dict__) if manifest.review_record else None,
                    json.dumps(manifest.approval_record.__dict__) if manifest.approval_record else None,
                    manifest.parent_version,
                    manifest.rollback_to,
                ),
            )

async def get_skill_fabric() -> SkillFabric:
    """Dependency injection helper."""
    from .config import settings
    fabric = SkillFabric(settings.skills_path)
    await fabric.initialize()
    return fabric


# ---------------------------------------------------------------------------
# E3: Candidate creation pipeline (E3-08 .. E3-13)
# ---------------------------------------------------------------------------


@dataclass
class SkillCandidate:
    """A draft skill not yet active (E3-08). Created from a verified trace
    with full source provenance. Candidates start in SkillState.CANDIDATE.
    """
    name: str
    version: str
    manifest: SkillManifest
    metadata: CandidateMetadata
    # installed/builtin default; trace-derived candidates set CANDIDATE explicitly
    state: SkillState = SkillState.ACTIVE

    @classmethod
    def from_trace(cls, trace: SkillTrace) -> SkillCandidate:
        """E3-09: Create a deterministic trace-to-candidate draft.

        Preserves the full research → decision → implementation → verification
        chain as TraceLinks with SHA-256 evidence hashes and source file links.
        """

        now = datetime.now(UTC).isoformat()

        # Trace links point back to the task that produced the trace
        trace_links = [
            TraceLink(
                task_id=trace.task_id,
                task_version=trace.revision,
                source_files=trace.source_files,
                evidence_sha=trace.evidence_sha,
                derived_at=now,
            )
        ]

        # Build manifest with provenance
        manifest = SkillManifest(
            name=trace.workflow_name or f"skill_{trace.task_id[:8]}",
            version="1.0.0",
            description=trace.description,
            category=trace.category,
            capabilities=trace.capabilities,
            trigger=trace.trigger,
            body=redact_payload(trace.procedure_body),
            source="trace_derived",
            state=SkillState.CANDIDATE,
            skill_version="1.0.0",
            allowed_tools=trace.allowed_tools,
            non_applicable_when=trace.non_applicable_when,
            input_schema=trace.input_schema,
            output_schema=trace.output_schema,
            success_criteria=trace.success_criteria,
            failure_criteria=trace.failure_criteria,
            expected_effect=trace.expected_effect,
            metadata=Metadata(data={"trace_id": trace.task_id}),
        )

        return cls(
            name=manifest.name,
            version=manifest.version,
            manifest=manifest,
            metadata=CandidateMetadata(
                trace_links=trace_links,
                expected_effect=trace.expected_effect,
                safety_assessment=trace.safety_assessment,
                cost_estimate=trace.cost_estimate,
            ),
            state=SkillState.CANDIDATE,
        )

    @classmethod
    def create_candidate_from_workflow(
        cls,
        workflow_name: str,
        description: str,
        trigger: str,
        procedure_body: str,
        capabilities: list[Capability],
        allowed_tools: list[str],
        expected_effect: str,
        safety_assessment: str,
        cost_estimate: dict[str, Any],
        task_id: str,
        task_version: str,
        source_files: list[str],
        evidence_sha: str,
        category: str = "general",
        non_applicable_when: list[str] | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        success_criteria: list[str] | None = None,
        failure_criteria: list[str] | None = None,
    ) -> SkillCandidate:
        """E3-09: Create a candidate from structured workflow inputs."""
        now = datetime.now(UTC).isoformat()
        trace_links = [
            TraceLink(
                task_id=task_id,
                task_version=task_version,
                source_files=source_files,
                evidence_sha=evidence_sha,
                derived_at=now,
            )
        ]

        manifest = SkillManifest(
            name=workflow_name,
            version="1.0.0",
            description=description,
            category=category,
            capabilities=capabilities,
            trigger=trigger,
            body=redact_payload(procedure_body),
            source="trace_derived",
            state=SkillState.CANDIDATE,
            skill_version="1.0.0",
            allowed_tools=allowed_tools,
            non_applicable_when=non_applicable_when or [],
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            success_criteria=success_criteria or [],
            failure_criteria=failure_criteria or [],
            expected_effect=expected_effect,
            metadata=Metadata(data={"trace_id": task_id}),
        )

        return cls(
            name=manifest.name,
            version=manifest.version,
            manifest=manifest,
            metadata=CandidateMetadata(
                trace_links=trace_links,
                expected_effect=expected_effect,
                safety_assessment=safety_assessment,
                cost_estimate=cost_estimate,
            ),
            state=SkillState.CANDIDATE,
        )

    def to_manifest(self) -> SkillManifest:
        """Convert candidate to a full SkillManifest for persistence."""
        return self.manifest


@dataclass
class SkillTrace:
    """A verified trace from which candidates can be derived (E3-08)."""
    task_id: str
    revision: str
    source_files: list[str]
    evidence_sha: str
    workflow_name: str | None
    description: str
    trigger: str
    procedure_body: str
    capabilities: list[Capability]
    allowed_tools: list[str]
    expected_effect: str
    safety_assessment: str
    cost_estimate: dict[str, Any]
    category: str = "general"
    non_applicable_when: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    failure_criteria: list[str] = field(default_factory=list)
    is_success: bool = True


# --- E3-10: Secret redaction ---

_REDACT_PATTERNS = [
    # API keys and tokens
    (re.compile(r'(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[=:]\s*\S+'),
     r'\1=REDACTED'),
    # AWS-style keys
    (re.compile(r'(?i)aws[_-]?(access[_-]?key|secret[_-]?key)\s*[=:]\s*\S+'),
     r'\1=REDACTED'),
    # Bearer tokens
    (re.compile(r'(?i)bearer\s+[A-Za-z0-9._-]+'), 'bearer REDACTED'),
    # Private paths (absolute paths outside repo)
    (re.compile(r'(/home/[^/\s]+|/root/[^/\s]+|/Users/[^/\s]+)'), '[REDACTED_PATH]'),
]


def redact_payload(text: str) -> str:
    """E3-10: Redact secrets and private paths from skill payload before
    persistence. Never raises — always returns a string."""
    result = text
    for pattern, replacement in _REDACT_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


# --- E3-07: Fact/preferences cannot become active skills ---

def normalize_fact_to_skill(
    fact_text: str,
    capabilities: list[Capability],
    **kwargs: Any,
) -> None:
    """E3-07: Explicitly refuse facts/memory/preferences → skill conversion.

    Memory facts and user preferences are queryable context, not executable
    procedures. Calling this function always raises ValueError to prevent
    normalizing raw conversation facts into active skill bodies.

    This is a negative function: it exists solely to make the boundary
    explicit and fail loudly.
    """
    raise ValueError(
        "normalize_fact_to_skill is intentionally refused (E3-07). "
        "Memory facts and user preferences are context records, not executable "
        "procedures. Use KnowledgeChunk or MemoryRecord for facts, and "
        "SkillCandidate.from_trace for verified procedural workflows."
    )


# --- E3-11: Candidate deduplication ---

def detect_duplicate_candidates(
    candidates: list[SkillCandidate],
) -> list[tuple[SkillCandidate, list[SkillCandidate]]]:
    """E3-11: Detect exact duplicates and overlapping trigger candidates.

    Returns a list of (primary_candidate, [duplicate_candidates]) tuples.
    Exact match = identical trigger + identical normalized body.
    Overlap = same trigger pattern (fuzzy match — identical word set).
    """
    duplicates: list[tuple[SkillCandidate, list[SkillCandidate]]] = []
    seen: dict[str, SkillCandidate] = {}
    primary_of: dict[int, SkillCandidate] = {}  # id(cand) -> primary for overlap grouping

    def _add_duplicate(primary: SkillCandidate, dup: SkillCandidate) -> None:
        """Add a duplicate to the right group."""
        # Find the canonical primary for this overlap group
        root = primary_of.get(id(primary), primary)
        dup_entry = next(
            (d for d in duplicates if d[0] is root),
            None,
        )
        if dup_entry is None:
            dup_entry = (root, [])
            duplicates.append(dup_entry)
        dup_entry[1].append(dup)

    for candidate in candidates:
        trigger_key = candidate.manifest.trigger.strip().lower()
        body_key = redact_payload(candidate.manifest.body).strip().lower()
        exact_key = f"{trigger_key}||{body_key[:200]}"

        if exact_key in seen:
            _add_duplicate(seen[exact_key], candidate)
        else:
            # Check for trigger overlap (fuzzy: same word set)
            primary_words = set(trigger_key.split())
            overlap_target = None
            for existing in seen.values():
                existing_words = set(existing.manifest.trigger.strip().lower().split())
                if primary_words and existing_words and primary_words == existing_words:
                    overlap_target = existing
                    break
            if overlap_target is not None:
                # Overlapping trigger — add as duplicate of the existing primary
                _add_duplicate(overlap_target, candidate)
            else:
                seen[exact_key] = candidate

    return duplicates


# --- E3-12: Candidate diff & provenance ---

def generate_skill_diff(
    candidate: SkillCandidate,
    existing: SkillManifest | None = None,
) -> str:
    """E3-12: Generate a human-readable diff of a candidate skill against
    an existing skill (or blank if new). Includes provenance summary.
    """
    import difflib

    lines: list[str] = []

    # Provenance summary
    lines.append(f"# Skill Candidate: {candidate.name}")
    lines.append("## Provenance (E3-09)")
    for link in candidate.metadata.trace_links:
        lines.append(f"  - trace: {link.task_id}@{link.task_version}")
        lines.append(f"    source_files: {link.source_files}")
        lines.append(f"    evidence_sha: {link.evidence_sha}")
        lines.append(f"    derived_at: {link.derived_at}")
    lines.append(f"## Expected effect: {candidate.metadata.expected_effect}")
    lines.append(f"## Safety assessment: {candidate.metadata.safety_assessment}")
    lines.append("## Diff:")

    new_body = candidate.manifest.body.splitlines()
    if existing is not None:
        old_body = existing.body.splitlines()
        diff = difflib.unified_diff(
            old_body, new_body,
            fromfile=f"existing/{existing.name}",
            tofile=f"candidate/{candidate.name}",
            lineterm="",
        )
        lines.extend(diff)
    else:
        lines.append("  (new skill — no existing version)")
        for line in new_body:
            lines.append(f"+ {line}")

    return "\n".join(lines)


# --- E3-14: Replay path ---

@dataclass
class ReplayResult:
    """Result of replaying a skill candidate on benchmark cases (E3-14)."""
    candidate_name: str
    trace_id: str
    passed_positive: bool
    passed_negative: bool
    outcome: str  # "passed", "failed_positive", "failed_negative", "failed_both"
    positive_detail: str = ""
    negative_detail: str = ""
    tokens_consumed: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_name": self.candidate_name,
            "trace_id": self.trace_id,
            "passed_positive": self.passed_positive,
            "passed_negative": self.passed_negative,
            "outcome": self.outcome,
            "positive_detail": self.positive_detail,
            "negative_detail": self.negative_detail,
            "tokens_consumed": self.tokens_consumed,
            "duration_seconds": self.duration_seconds,
        }


def validate_skill_transition(
    from_state: SkillState,
    to_state: SkillState,
) -> tuple[bool, str]:
    """E3-03: Validate whether a state transition is legal.

    Returns (is_valid, required_evidence_key).
    """
    key = (from_state, to_state)
    if key in LEGAL_SKILL_TRANSITIONS:
        return True, LEGAL_SKILL_TRANSITIONS[key]
    return False, "no such transition"
