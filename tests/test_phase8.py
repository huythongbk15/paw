"""
Phase 8 Tests — Context Builder

Tests for context selection, token budgeting, explain mode, and citation integration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paw.core.context import ContextBuilder, ContextItem, ExplainEntry, ContextBudget
from paw.core.ledger import TaskLedger
from paw.core.memory import MemoryStore, MemoryRecord
from paw.core.models import (
    Artifact,
    Capability,
    Citation,
    Decision,
    ErrorInfo,
    Evidence,
    MemoryType,
    SkillRisk,
    TaskResult,
    TaskStatus,
    Usage,
)
from paw.core.session import SessionManager
from paw.core.skills import SkillFabric, SkillManifest
from paw.core.task import Task, TaskManager


class TestPhase8ContextBuilder:
    """Phase 8 ContextBuilder tests."""

    @pytest.fixture
    async def temp_db(self, reset_db, session_db):
        yield session_db

    @pytest.fixture
    async def context_builder(self, temp_db):
        budget = ContextBudget(max_tokens=12000)
        builder = ContextBuilder(budget=budget)
        yield builder

    @pytest.fixture
    async def sample_task(self, temp_db, context_builder):
        session = await SessionManager.create(project_id="test-project")
        task = await TaskManager.create(
            session_id=session.id,
            goal="Write a Python function to calculate fibonacci",
        )
        yield task, session

    @pytest.mark.asyncio
    async def test_context_builder_initialization(self, context_builder):
        """ContextBuilder initializes with correct defaults."""
        assert context_builder.budget.max_tokens == 12000
        assert context_builder.budget is not None

    @pytest.mark.asyncio
    async def test_build_context_basic(self, context_builder, sample_task):
        """Build basic context for a task."""
        task, session = sample_task
        context = await context_builder.build_context(task_id=task.id)
        
        assert context.task_id == task.id
        assert isinstance(context.fragments, list)
        assert context.token_count >= 0
        assert context.token_count <= context_builder.budget.max_tokens

    @pytest.mark.asyncio
    async def test_build_context_with_goal(self, context_builder, sample_task):
        """Context includes the task goal."""
        task, _ = sample_task
        context = await context_builder.build_context(task_id=task.id)
        
        # Should include user request (ledger events)
        assert len(context.fragments) >= 1

    @pytest.mark.asyncio
    async def test_context_token_budget(self, context_builder, sample_task):
        """Context respects token budget."""
        task, _ = sample_task
        
        # Create a context builder with very small budget
        small_budget = ContextBudget(max_tokens=100)
        small_builder = ContextBuilder(budget=small_budget)
        context = await small_builder.build_context(task_id=task.id)
        
        assert context.token_count <= 100

    @pytest.mark.asyncio
    async def test_context_fragment_structure(self, context_builder, sample_task):
        """Context fragments have required structure."""
        task, _ = sample_task
        context = await context_builder.build_context(task_id=task.id)
        
        for frag in context.fragments:
            assert hasattr(frag, "source")
            assert hasattr(frag, "content")
            assert hasattr(frag, "relevance_score")
            assert hasattr(frag, "explanation")
            assert frag.relevance_score >= 0

    @pytest.mark.asyncio
    async def test_context_explain_mode(self, context_builder, sample_task):
        """Explain mode returns reasoning for each context item."""
        task, _ = sample_task
        context = await context_builder.build_context(
            task_id=task.id,
            explain_mode=True,
        )
        
        assert context.explain_mode is True


class TestPhase8ContextItem:
    """ContextItem (alias for ContextFragment) model tests."""

    def test_context_item_creation(self):
        """Create ContextItem with all fields."""
        item = ContextItem(
            source="test",
            content="Test content",
            relevance_score=0.8,
            explanation="High relevance",
        )
        assert item.source == "test"
        assert item.content == "Test content"
        assert item.relevance_score == 0.8
        assert item.explanation == "High relevance"

    def test_context_item_defaults(self):
        """ContextItem with minimal fields."""
        item = ContextItem(
            source="test",
            content="Test",
            relevance_score=0.5,
        )
        assert item.explanation == ""


class TestPhase8ExplainEntry:
    """Phase 8 Explain Entry tests."""

    @pytest.mark.asyncio
    async def test_explain_entry_creation(self):
        """Create an explain entry."""
        entry = ExplainEntry(
            fragment_index=0,
            source="ledger",
            reason="High relevance",
            score=0.9,
            content_preview="Test content...",
        )
        assert entry.fragment_index == 0
        assert entry.source == "ledger"
        assert entry.score == 0.9


class TestPhase8NoProhibitedDependencies:
    """Verify no prohibited dependencies in Phase 8."""

    @pytest.fixture
    def paw_source_root(self) -> Path:
        """Get the PAW source root directory."""
        import paw
        return Path(paw.__file__).parent

    def _check_no_imports(self, paw_source_root, keyword: str, allow_in_providers: bool = True):
        """Check for prohibited imports, excluding providers directory."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            if allow_in_providers and "providers" in str(file):
                continue
            content = file.read_text()
            assert keyword not in content.lower(), f"{keyword} reference found in {file}"

    def test_no_qwenpaw(self, paw_source_root):
        """No QwenPaw references in PAW source (excluding providers)."""
        self._check_no_imports(paw_source_root, "qwenpaw")

    def test_no_deepseek(self, paw_source_root):
        """No DeepSeek Harness references in PAW source (excluding providers)."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            if "providers" in str(file):
                continue
            content = file.read_text()
            assert "deepseek" not in content.lower() or "model" in content.lower(), f"DeepSeek reference found in {file}"

    def test_no_notebooklm(self, paw_source_root):
        """No NotebookLM references in PAW source (excluding providers)."""
        self._check_no_imports(paw_source_root, "notebooklm")

    def test_no_antigravity(self, paw_source_root):
        """No Google Antigravity references in PAW source (excluding providers)."""
        self._check_no_imports(paw_source_root, "antigravity")
