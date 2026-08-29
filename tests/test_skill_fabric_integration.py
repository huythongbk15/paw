"""
Skill Fabric Integration Tests — Real SKILL.md parsing, create/discover/persist/reload.

Tests the complete skill lifecycle with actual SKILL.md files.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from paw.core import SkillManifest, SkillFabric, Capability, SkillRisk
from paw.core.storage import db, set_db_path
from paw.core.config import settings


# Sample SKILL.md content per prompt spec
SAMPLE_SKILL_MD = """---
metadata:
  paw/version: "1.0"
  paw/category: coding
  paw/risk: low
  paw/capabilities: [filesystem.read, git.read]
  paw/executors: [local, opencode]
  paw/network: false
  paw/write: false
---
# Git Status Skill

Shows git status and diff for the current repository.

## Usage

Trigger with: "git status" or "what changed"
"""

SAMPLE_SKILL_MD_FLAT = """---
name: flat-skill
version: "2.0.0"
description: A skill with flat frontmatter
category: testing
capabilities: [filesystem.write, shell.execute]
risk: medium
network: true
write: true
executors: [mock]
trigger: flat skill test
---
# Flat Skill

This skill uses flat frontmatter format.
"""

SAMPLE_SKILL_MD_MINIMAL = """---
name: minimal-skill
trigger: minimal
---
# Minimal Skill

Just name and trigger.
"""

SAMPLE_SKILL_MD_NESTED = """---
metadata:
  paw/version: "1.0"
  paw/category: coding
  paw/risk: medium
  paw/capabilities: [filesystem.read, git.write]
  paw/executors: [local]
  paw/network: false
  paw/write: true
---
# Nested Coding Skill

A nested skill for testing subdirectory discovery.
"""


class TestSkillManifestParsing:
    """Test SkillManifest.from_dict and YAML parsing."""

    def _parse_frontmatter(self, content: str) -> dict:
        """Helper to parse frontmatter like _parse_skill_file does."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                return yaml.safe_load(fm_text) or {}
        return {}

    def test_parse_prompt_spec_format(self):
        """Parse prompt spec metadata.paw/ nested structure."""
        frontmatter = self._parse_frontmatter(SAMPLE_SKILL_MD)
        manifest = SkillManifest.from_dict(frontmatter)
        # from_dict doesn't extract title from body - name comes from filename or frontmatter
        # The actual skill name will be from filename when loaded via _parse_skill_file
        assert manifest.name is not None  # At least something
        assert manifest.version == "1.0"  # paw/version: "1.0" preserved
        assert manifest.category == "coding"
        assert manifest.risk == SkillRisk.LOW
        assert Capability.FILESYSTEM_READ in manifest.capabilities
        assert Capability.GIT_READ in manifest.capabilities
        assert "local" in manifest.executors
        assert "opencode" in manifest.executors
        assert manifest.network is False
        assert manifest.write is False

    def test_parse_flat_format(self):
        """Parse flat frontmatter format."""
        frontmatter = self._parse_frontmatter(SAMPLE_SKILL_MD_FLAT)
        manifest = SkillManifest.from_dict(frontmatter)
        assert manifest.name == "flat-skill"
        assert manifest.version == "2.0.0"
        assert manifest.description == "A skill with flat frontmatter"
        assert manifest.category == "testing"
        assert Capability.FILESYSTEM_WRITE in manifest.capabilities
        assert Capability.SHELL_EXECUTE in manifest.capabilities
        assert manifest.risk == SkillRisk.MEDIUM
        assert manifest.network is True
        assert manifest.write is True
        assert "mock" in manifest.executors
        assert manifest.trigger == "flat skill test"

    def test_parse_minimal(self):
        """Parse minimal frontmatter."""
        frontmatter = self._parse_frontmatter(SAMPLE_SKILL_MD_MINIMAL)
        manifest = SkillManifest.from_dict(frontmatter)
        assert manifest.name == "minimal-skill"
        assert manifest.trigger == "minimal"
        assert manifest.capabilities == []
        assert manifest.executors == []

    def test_string_risk_conversion(self):
        """String risk should convert to SkillRisk enum."""
        manifest = SkillManifest(name="test", risk="high")
        assert manifest.risk == SkillRisk.HIGH
        manifest2 = SkillManifest(name="test", risk=SkillRisk.MEDIUM)
        assert manifest2.risk == SkillRisk.MEDIUM


class TestSkillFabricLifecycle:
    """Test complete skill lifecycle: create -> discover -> persist -> reload."""

    @pytest.fixture
    async def temp_skills_dir(self):
        """Create a temporary skills directory with sample skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()

            # Write sample skill files
            (skills_dir / "git_status.md").write_text(SAMPLE_SKILL_MD, encoding="utf-8")
            (skills_dir / "flat_skill.md").write_text(SAMPLE_SKILL_MD_FLAT, encoding="utf-8")
            (skills_dir / "minimal.md").write_text(SAMPLE_SKILL_MD_MINIMAL, encoding="utf-8")

            # Also create a subdirectory with a different skill
            subdir = skills_dir / "coding"
            subdir.mkdir()
            (subdir / "nested.md").write_text(SAMPLE_SKILL_MD_NESTED, encoding="utf-8")

            yield skills_dir

    @pytest.fixture
    async def temp_db(self, temp_skills_dir):
        """Set up temporary database.

        NOTE: kept per-test (file + schema build) on purpose — PAW's schema
        contains an FTS5 virtual table (``skill_fts``) that corrupts
        (``database disk image is malformed`` / ``vtable constructor failed``)
        when shared/reconnected across tests. The other four consolidated
        modules use the Cấp 2 shared fixture in tests/conftest.py.
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        await set_db_path(db_path)
        await db.initialize()

        yield db_path

        await db.close()
        db_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_discover_filesystem(self, temp_skills_dir, temp_db):
        """Discover skills from filesystem."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        # Should find 4 skills (3 in root + 1 in subdir) + 2 builtin = 6+
        skills = fabric.list_skills()
        assert len(skills) >= 4

        # Check specific skills
        git_skill = fabric.get_skill("Git Status Skill")
        assert git_skill is not None
        assert Capability.FILESYSTEM_READ in git_skill.capabilities

        flat_skill = fabric.get_skill("flat-skill")
        assert flat_skill is not None
        assert flat_skill.manifest.risk == SkillRisk.MEDIUM

        minimal_skill = fabric.get_skill("minimal-skill")
        assert minimal_skill is not None

        nested_skill = fabric.get_skill("Nested Coding Skill")
        assert nested_skill is not None

    @pytest.mark.asyncio
    async def test_persist_to_db(self, temp_skills_dir, temp_db):
        """Skills discovered from filesystem should be persisted to DB."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        # Check DB has the skills (4 filesystem + 2 builtin = 6)
        rows = await db.fetchall("SELECT * FROM skills WHERE enabled = 1")
        assert len(rows) >= 4  # At least the 4 filesystem skills

        # Verify data integrity
        for row in rows:
            assert row["name"] is not None
            assert row["body"] is not None
            assert row["source"] in ("installed", "builtin")

    @pytest.mark.asyncio
    async def test_reload_from_db(self, temp_skills_dir, temp_db):
        """Second initialization should load from DB, not re-parse files."""
        # First initialization
        fabric1 = SkillFabric(temp_skills_dir)
        await fabric1.initialize()
        count1 = len(fabric1.list_skills())

        # Second initialization (new fabric instance, same DB)
        fabric2 = SkillFabric(temp_skills_dir)
        await fabric2.initialize()
        count2 = len(fabric2.list_skills())

        # Should have same count (loaded from DB)
        assert count2 == count1

    @pytest.mark.asyncio
    async def test_find_candidates(self, temp_skills_dir, temp_db):
        """Find skills matching query."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        candidates = fabric.find_candidates("git status")
        assert len(candidates) >= 1
        assert any(Capability.GIT_READ in c.capabilities for c in candidates)

    @pytest.mark.asyncio
    async def test_builtin_skills_present(self, temp_skills_dir, temp_db):
        """Builtin skills should always be available."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        echo_skill = fabric.get_skill("echo")
        assert echo_skill is not None
        assert echo_skill.manifest.source == "builtin"

        datetime_skill = fabric.get_skill("datetime")
        assert datetime_skill is not None

    @pytest.mark.asyncio
    async def test_category_filter(self, temp_skills_dir, temp_db):
        """Filter skills by category."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        coding_skills = fabric.list_skills(category="coding")
        assert len(coding_skills) >= 2  # git_status + nested

        testing_skills = fabric.list_skills(category="testing")
        assert len(testing_skills) >= 1  # flat_skill

    @pytest.mark.asyncio
    async def test_get_categories(self, temp_skills_dir, temp_db):
        """Get all categories."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        categories = fabric.get_categories()
        assert "coding" in categories
        assert "testing" in categories
        assert "utility" in categories  # from builtin


class TestSkillFabricYAMLParsing(TestSkillFabricLifecycle):
    """Test proper YAML parsing with PyYAML."""

    @pytest.mark.asyncio
    async def test_yaml_parsing_with_nested_metadata(self, temp_skills_dir, temp_db):
        """YAML parser should handle nested metadata.paw correctly."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        git_skill = fabric.get_skill("Git Status Skill")
        assert git_skill is not None
        # Nested metadata.paw should be in manifest.metadata.data
        paw_meta = git_skill.manifest.metadata.data.get("paw", {})
        assert paw_meta.get("category") == "coding"
        assert paw_meta.get("risk") == "low"
        assert "filesystem.read" in str(paw_meta.get("capabilities", ""))

    @pytest.mark.asyncio
    async def test_yaml_parsing_boolean_values(self, temp_skills_dir, temp_db):
        """YAML parser should handle boolean values correctly."""
        fabric = SkillFabric(temp_skills_dir)
        await fabric.initialize()

        flat_skill = fabric.get_skill("flat-skill")
        assert flat_skill is not None
        assert flat_skill.manifest.network is True
        assert flat_skill.manifest.write is True

        # Prompt spec format uses string "false"
        git_skill = fabric.get_skill("Git Status Skill")
        assert git_skill.manifest.network is False
        assert git_skill.manifest.write is False


class TestNoProhibitedDependencies:
    """Verify no prohibited dependencies."""

    def test_no_qwenpaw_in_skills(self):
        skills_file = Path(__file__).parent.parent / "src" / "paw" / "core" / "skills.py"
        content = skills_file.read_text()
        assert "qwenpaw" not in content.lower()

    def test_no_deepseek_in_skills(self):
        skills_file = Path(__file__).parent.parent / "src" / "paw" / "core" / "skills.py"
        content = skills_file.read_text()
        assert "deepseek" not in content.lower()

    def test_no_notebooklm_in_skills(self):
        skills_file = Path(__file__).parent.parent / "src" / "paw" / "core" / "skills.py"
        content = skills_file.read_text()
        assert "notebooklm" not in content.lower()

    def test_no_antigravity_in_skills(self):
        skills_file = Path(__file__).parent.parent / "src" / "paw" / "core" / "skills.py"
        content = skills_file.read_text()
        assert "antigravity" not in content.lower()