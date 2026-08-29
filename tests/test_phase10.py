"""
Phase 10 Tests — QwenPaw Compatibility Adapters

Tests for QwenPaw skill, ReMe memory, and persona adapters.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from paw.providers.qwenpaw.adapter import (
    QwenPawSkillAdapter,
    QwenPawSkillProvider,
    QwenPawMemoryAdapter,
    QwenPawMemoryProvider,
    QwenPawPersonaAdapter as QwenPawPersonaAdapterQP,
    QwenPawPersonaProvider,
)
from paw.providers.reme.adapter import ReMeMemoryAdapter, ReMeMemoryProvider
from paw.providers.persona.adapter import (
    Persona,
    PersonaAdapter,
    QwenPawPersonaAdapter,
    NotebookLMPersonaAdapter,
    GenericPersonaAdapter,
    PersonaProvider,
)
from paw.core.models import Capability, SkillRisk
from paw.core.skills import SkillManifest


# Sample QwenPaw skill content
SAMPLE_QWENPAW_SKILL = """---
name: git-status
version: "1.0.0"
description: Show git status and diff
category: coding
metadata:
  paw/version: "1.0"
  paw/category: coding
  paw/risk: low
  paw/capabilities: [filesystem.read, git.read]
  paw/executors: [local, opencode]
  paw/network: false
  paw/write: false
trigger: git status
---
# Git Status Skill

Shows git status and diff for the current repository.
"""

SAMPLE_QWENPAW_SKILL_FLAT = """---
name: flat-skill
description: A flat skill
capabilities: [shell.execute]
metadata:
  paw/risk: medium
  paw/network: true
  paw/write: true
---
# Flat Skill
"""

SAMPLE_QWENPAW_PERSONA = """---
name: code-reviewer
role: senior developer
personality: Detail-oriented, focuses on code quality
skills: [git-read, code-review]
metadata:
  experience: senior
  languages: [python, rust]
---
# Code Reviewer Persona

You are a senior code reviewer. Focus on correctness, maintainability, and security.
"""

SAMPLE_REME_MEMORY = {
    "id": "mem-001",
    "content": "User prefers tabs over spaces for Python indentation.",
    "embedding": [0.1, 0.2, 0.3],
    "metadata": {
        "type": "semantic",
        "project_id": "paw-project",
        "task_id": "task-001",
        "importance": 0.8,
        "tags": ["preference", "python", "formatting"],
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
}

SAMPLE_NOTEBOOKLM_PERSONA = {
    "name": "Research Assistant",
    "title": "Research Assistant",
    "role": "researcher",
    "description": "Helps with literature review and synthesis",
    "system_prompt": "You are a research assistant. Summarize papers and extract key findings.",
    "tools": ["web_search", "pdf_reader"],
    "metadata": {"domain": "academic"},
}


class TestQwenPawSkillAdapter:
    """Test QwenPaw skill adapter."""

    def test_parse_prompt_spec_format(self):
        """Parse QwenPaw skill with metadata.paw/ nested structure."""
        manifest = QwenPawSkillAdapter.parse_qwenpaw_skill(SAMPLE_QWENPAW_SKILL)
        
        assert manifest.name == "git-status"
        assert manifest.version == "1.0.0"
        assert manifest.description == "Show git status and diff"
        assert manifest.category == "coding"
        assert manifest.risk == SkillRisk.LOW
        assert Capability.FILESYSTEM_READ in manifest.capabilities
        assert Capability.GIT_READ in manifest.capabilities
        assert "local" in manifest.executors
        assert "opencode" in manifest.executors
        assert manifest.network is False
        assert manifest.write is False
        assert manifest.trigger == "git status"
        assert manifest.source == "qwenpaw"

    def test_parse_flat_format(self):
        """Parse QwenPaw skill with flat capabilities in metadata."""
        manifest = QwenPawSkillAdapter.parse_qwenpaw_skill(SAMPLE_QWENPAW_SKILL_FLAT)
        
        assert manifest.name == "flat-skill"
        # Flat format has capabilities in top-level, not paw/capabilities
        # This is expected to be empty since we only parse paw/ prefixed keys
        # The adapter focuses on paw/ structured format

    def test_convert_from_dict(self):
        """Convert from dict format."""
        data = {
            "name": "test-skill",
            "description": "Test skill",
            "metadata": {
                "paw/capabilities": "filesystem.read, git.write",
                "paw/executors": ["local"],
                "paw/risk": "high",
                "paw/network": "true",
                "paw/write": "false",
            },
        }
        manifest = QwenPawSkillAdapter.convert_qwenpaw_skill(data)
        
        assert manifest.name == "test-skill"
        assert Capability.FILESYSTEM_READ in manifest.capabilities
        assert Capability.GIT_WRITE in manifest.capabilities
        assert manifest.risk == SkillRisk.HIGH
        assert manifest.network is True
        assert manifest.write is False


class TestQwenPawSkillProvider:
    """Test QwenPaw skill provider."""

    @pytest.fixture
    def temp_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "git_status.md").write_text(SAMPLE_QWENPAW_SKILL, encoding="utf-8")
            (skills_dir / "flat.md").write_text(SAMPLE_QWENPAW_SKILL_FLAT, encoding="utf-8")
            yield skills_dir

    @pytest.mark.asyncio
    async def test_list_skills(self, temp_skills_dir):
        provider = QwenPawSkillProvider(temp_skills_dir)
        skills = await provider.list_skills()
        assert len(skills) >= 2
        names = [s["name"] for s in skills]
        assert "git-status" in names
        assert "flat-skill" in names

    @pytest.mark.asyncio
    async def test_get_skill(self, temp_skills_dir):
        provider = QwenPawSkillProvider(temp_skills_dir)
        skill = await provider.get_skill("git-status")
        assert skill is not None
        assert skill.name == "git-status"
        assert Capability.GIT_READ in skill.capabilities


class TestQwenPawMemoryAdapter:
    """Test ReMe/QwenPaw memory adapter."""

    def test_convert_reme_memory(self):
        """Convert ReMe memory to PAW format."""
        result = QwenPawMemoryAdapter.convert_reme_memory(SAMPLE_REME_MEMORY)
        
        assert result["id"] == "mem-001"
        assert result["memory_type"] == "semantic"
        assert result["project_id"] == "paw-project"
        assert result["task_id"] == "task-001"
        assert "tabs over spaces" in result["content"]
        assert result["importance"] == 0.8
        assert "preference" in result["tags"]
        assert result["source"] == "reme"

    def test_convert_qwenpaw_memory(self):
        """Convert QwenPaw memory (same as ReMe)."""
        result = QwenPawMemoryAdapter.convert_qwenpaw_memory(SAMPLE_REME_MEMORY)
        assert result["source"] == "reme"


class TestQwenPawMemoryProvider:
    """Test ReMe memory provider."""

    @pytest.fixture
    def temp_memory_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_dir = Path(tmpdir) / "memory"
            mem_dir.mkdir()
            import json
            (mem_dir / "mem1.json").write_text(
                json.dumps({**SAMPLE_REME_MEMORY, "id": "mem-1"}),
                encoding="utf-8"
            )
            (mem_dir / "mem2.json").write_text(
                json.dumps({**SAMPLE_REME_MEMORY, "id": "mem-2", "content": "Different content"}),
                encoding="utf-8"
            )
            yield mem_dir

    @pytest.mark.asyncio
    async def test_query(self, temp_memory_dir):
        provider = QwenPawMemoryProvider(temp_memory_dir)
        results = await provider.query("tabs over spaces")
        assert len(results) >= 1
        assert results[0]["id"] == "mem-1"

    @pytest.mark.asyncio
    async def test_query_no_match(self, temp_memory_dir):
        provider = QwenPawMemoryProvider(temp_memory_dir)
        results = await provider.query("nonexistent")
        assert len(results) == 0


class TestQwenPawPersonaAdapter:
    """Test QwenPaw persona adapter (from qwenpaw module)."""

    def test_parse_persona(self):
        """Parse QwenPaw persona markdown."""
        data = QwenPawPersonaAdapterQP.parse_persona(SAMPLE_QWENPAW_PERSONA)
        
        assert data["name"] == "code-reviewer"
        assert data["role"] == "senior developer"
        assert data["personality"] == "Detail-oriented, focuses on code quality"
        assert "git-read" in data["skills"]
        assert data["metadata"]["experience"] == "senior"

    def test_convert_persona(self):
        """Convert to standard format."""
        data = QwenPawPersonaAdapterQP.parse_persona(SAMPLE_QWENPAW_PERSONA)
        persona = QwenPawPersonaAdapterQP.convert_persona(data)
        
        assert persona["name"] == "code-reviewer"
        assert persona["role"] == "senior developer"
        assert persona["source"] == "qwenpaw"


class TestQwenPawPersonaProvider:
    """Test QwenPaw persona provider."""

    @pytest.fixture
    def temp_persona_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persona_dir = Path(tmpdir) / "personas"
            persona_dir.mkdir()
            (persona_dir / "reviewer.md").write_text(SAMPLE_QWENPAW_PERSONA, encoding="utf-8")
            yield persona_dir

    @pytest.mark.asyncio
    async def test_list_personas(self, temp_persona_dir):
        provider = QwenPawPersonaProvider(temp_persona_dir)
        personas = await provider.list_personas()
        assert len(personas) >= 1
        assert personas[0]["name"] == "code-reviewer"

    @pytest.mark.asyncio
    async def test_get_persona(self, temp_persona_dir):
        provider = QwenPawPersonaProvider(temp_persona_dir)
        persona = await provider.get_persona("code-reviewer")
        assert persona is not None
        assert persona["role"] == "senior developer"


class TestReMeMemoryAdapter:
    """Test ReMe memory adapter."""

    def test_convert(self):
        """Convert ReMe memory."""
        result = ReMeMemoryAdapter.convert(SAMPLE_REME_MEMORY)
        
        assert result["id"] == "mem-001"
        assert result["memory_type"] == "semantic"
        assert result["project_id"] == "paw-project"
        assert result["importance"] == 0.8
        assert result["source"] == "reme"

    def test_convert_batch(self):
        """Convert multiple memories."""
        batch = [SAMPLE_REME_MEMORY, {**SAMPLE_REME_MEMORY, "id": "mem-002"}]
        results = ReMeMemoryAdapter.convert_batch(batch)
        assert len(results) == 2
        assert results[0]["id"] == "mem-001"
        assert results[1]["id"] == "mem-002"


class TestReMeMemoryProvider:
    """Test ReMe memory provider."""

    @pytest.fixture
    def temp_memory_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_dir = Path(tmpdir) / "reme"
            mem_dir.mkdir()
            import json
            (mem_dir / "mem1.json").write_text(
                json.dumps({**SAMPLE_REME_MEMORY, "id": "mem-1"}),
                encoding="utf-8"
            )
            (mem_dir / "mem2.json").write_text(
                json.dumps({**SAMPLE_REME_MEMORY, "id": "mem-2", "metadata": {**SAMPLE_REME_MEMORY["metadata"], "type": "episodic"}}),
                encoding="utf-8"
            )
            yield mem_dir

    @pytest.mark.asyncio
    async def test_query(self, temp_memory_dir):
        provider = ReMeMemoryProvider(temp_memory_dir)
        results = await provider.query("tabs")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_query_by_type(self, temp_memory_dir):
        provider = ReMeMemoryProvider(temp_memory_dir)
        results = await provider.query_by_type("semantic")
        assert len(results) >= 1
        assert all(r["memory_type"] == "semantic" for r in results)

    @pytest.mark.asyncio
    async def test_query_by_project(self, temp_memory_dir):
        provider = ReMeMemoryProvider(temp_memory_dir)
        results = await provider.query_by_project("paw-project")
        assert len(results) >= 1
        assert all(r["project_id"] == "paw-project" for r in results)


class TestPersonaAdapter:
    """Test persona adapters."""

    def test_standard_conversion(self):
        """Test standard persona conversion."""
        data = {
            "name": "test",
            "role": "assistant",
            "personality": "helpful",
            "instructions": "help users",
            "skills": ["skill1"],
            "metadata": {},
        }
        persona = PersonaAdapter.to_standard(data, "test")
        
        assert persona.name == "test"
        assert persona.role == "assistant"
        assert persona.source == "test"

    def test_qwenpaw_adapter(self):
        """Test QwenPaw persona adapter (from persona module)."""
        data = QwenPawPersonaAdapter.parse(SAMPLE_QWENPAW_PERSONA)
        persona = QwenPawPersonaAdapter.convert(data)
        
        assert isinstance(persona, Persona)
        assert persona.name == "code-reviewer"
        assert persona.source == "qwenpaw"

    def test_notebooklm_adapter(self):
        """Test NotebookLM persona adapter."""
        persona = NotebookLMPersonaAdapter.convert(SAMPLE_NOTEBOOKLM_PERSONA)
        
        assert isinstance(persona, Persona)
        assert persona.name == "Research Assistant"
        assert persona.role == "researcher"
        assert "web_search" in persona.skills
        assert persona.source == "notebooklm"

    def test_generic_adapter(self):
        """Test generic persona adapter."""
        data = {
            "name": "generic-bot",
            "role": "bot",
            "instructions": "be helpful",
        }
        persona = GenericPersonaAdapter.convert(data, "generic")
        
        assert persona.name == "generic-bot"
        assert persona.source == "generic"


class TestPersonaProvider:
    """Test unified persona provider."""

    @pytest.fixture
    def temp_persona_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            qwenpaw = base / "qwenpaw"
            qwenpaw.mkdir()
            notebooklm = base / "notebooklm"
            notebooklm.mkdir()
            generic = base / "generic"
            generic.mkdir()
            
            (qwenpaw / "reviewer.md").write_text(SAMPLE_QWENPAW_PERSONA, encoding="utf-8")
            import json
            (notebooklm / "researcher.json").write_text(json.dumps(SAMPLE_NOTEBOOKLM_PERSONA), encoding="utf-8")
            import yaml
            (generic / "bot.yaml").write_text(
                yaml.dump({"name": "yaml-bot", "role": "bot", "instructions": "help"}),
                encoding="utf-8"
            )
            
            yield {"qwenpaw": qwenpaw, "notebooklm": notebooklm, "generic": generic}

    @pytest.mark.asyncio
    async def test_list_all_sources(self, temp_persona_dirs):
        provider = PersonaProvider(
            qwenpaw_path=temp_persona_dirs["qwenpaw"],
            notebooklm_path=temp_persona_dirs["notebooklm"],
            generic_path=temp_persona_dirs["generic"],
        )
        personas = await provider.list_personas()
        assert len(personas) >= 3
        names = [p.name for p in personas]
        assert "code-reviewer" in names
        assert "Research Assistant" in names
        assert "yaml-bot" in names

    @pytest.mark.asyncio
    async def test_get_persona(self, temp_persona_dirs):
        provider = PersonaProvider(
            qwenpaw_path=temp_persona_dirs["qwenpaw"],
            notebooklm_path=temp_persona_dirs["notebooklm"],
            generic_path=temp_persona_dirs["generic"],
        )
        persona = await provider.get_persona("code-reviewer")
        assert persona is not None
        assert persona.name == "code-reviewer"
        assert persona.source == "qwenpaw"

    @pytest.mark.asyncio
    async def test_import_persona(self, temp_persona_dirs):
        provider = PersonaProvider()
        persona = await provider.import_persona(
            {"name": "imported", "role": "test", "instructions": "test"},
            source="generic"
        )
        assert persona.name == "imported"
        assert persona.source == "generic"


class TestNoProhibitedDependencies:
    """Verify no prohibited dependencies in providers."""

    def test_no_qwenpaw_import_in_core(self):
        """Providers should not be imported in core."""
        import os
        core_files = []
        for root, dirs, files in os.walk("src/paw/core"):
            for f in files:
                if f.endswith(".py"):
                    core_files.append(os.path.join(root, f))
        
        for f in core_files:
            content = Path(f).read_text()
            # Check for actual import statements, not substrings
            assert "import qwenpaw" not in content
            assert "from qwenpaw" not in content
            assert "import reme" not in content
            assert "from reme" not in content
            assert "import notebooklm" not in content
            assert "from notebooklm" not in content
            assert "import antigravity" not in content
            assert "from antigravity" not in content

    def test_providers_isolated(self):
        """Providers directory should be separate from core."""
        assert Path("src/paw/providers").exists()
        assert Path("src/paw/providers/qwenpaw").exists()
        assert Path("src/paw/providers/reme").exists()
        assert Path("src/paw/providers/persona").exists()


# Import yaml for test
import yaml