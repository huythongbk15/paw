"""
Phase 8 Tests — Context Builder with explain mode and budget.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paw.core import (
    ContextBuilder, ContextFragment, TaskContext,
    ContextBudget, ExplainEntry,
    TaskEventType,
)
from paw.core.storage import db, set_db_path


class TestPhase8ContextBudget:
    """Phase 8 Context Budget tests."""

    @pytest.mark.asyncio
    async def test_budget_defaults(self):
        """Default budget values."""
        budget = ContextBudget()
        assert budget.max_tokens == 12000
        assert budget.max_fragments == 50
        assert budget.max_sources == 10

    @pytest.mark.asyncio
    async def test_can_add_within_budget(self):
        """Can add fragments within budget."""
        budget = ContextBudget(max_tokens=100, max_fragments=5)
        assert budget.can_add_fragment(50, 2, 2) is True

    @pytest.mark.asyncio
    async def test_can_add_exceeds_tokens(self):
        """Cannot add fragments exceeding token budget."""
        budget = ContextBudget(max_tokens=100, max_fragments=5)
        assert budget.can_add_fragment(150, 2, 2) is False

    @pytest.mark.asyncio
    async def test_can_add_exceeds_fragments(self):
        """Cannot add fragments exceeding fragment budget."""
        budget = ContextBudget(max_tokens=1000, max_fragments=2)
        assert budget.can_add_fragment(50, 2, 1) is False

    @pytest.mark.asyncio
    async def test_can_add_exceeds_sources(self):
        """Cannot add fragments exceeding source budget."""
        budget = ContextBudget(max_tokens=1000, max_fragments=50, max_sources=2)
        assert budget.can_add_fragment(50, 1, 2) is False

    @pytest.mark.asyncio
    async def test_custom_weights(self):
        """Custom priority weights."""
        weights = {"ledger": 0.5, "memory": 0.5}
        budget = ContextBudget(priority_weights=weights)
        assert budget.priority_weights == weights


class TestPhase8ContextFragment:
    """Phase 8 Context Fragment tests."""

    @pytest.mark.asyncio
    async def test_fragment_creation(self):
        """Create a context fragment."""
        frag = ContextFragment(
            source="ledger",
            event_type=TaskEventType.TASK_CREATED,
            content="test content",
            relevance_score=0.8,
        )
        assert frag.source == "ledger"
        assert frag.content == "test content"
        assert frag.relevance_score == 0.8

    @pytest.mark.asyncio
    async def test_fragment_explain(self):
        """Fragment explain generates correctly."""
        frag = ContextFragment(
            source="ledger",
            event_type=TaskEventType.TASK_CREATED,
            content="test",
            relevance_score=0.8,
            explanation="Ledger event: task_created",
        )
        assert "Ledger event" in frag.explain()

    @pytest.mark.asyncio
    async def test_fragment_explain_default(self):
        """Default explain without explicit explanation."""
        frag = ContextFragment(source="memory", relevance_score=0.6)
        explain = frag.explain()
        assert "memory" in explain

    @pytest.mark.asyncio
    async def test_fragment_to_dict(self):
        """Fragment serializes correctly."""
        frag = ContextFragment(
            source="ledger",
            event_type=TaskEventType.TASK_CREATED,
            content="test",
            explanation="Test explain",
        )
        d = frag.to_dict()
        assert d["source"] == "ledger"
        assert d["explanation"] == "Test explain"
        assert d["event_type"] == "task_created"


class TestPhase8TaskContext:
    """Phase 8 Task Context tests."""

    @pytest.mark.asyncio
    async def test_context_creation(self):
        """Create a task context."""
        context = TaskContext(task_id="task-1")
        assert context.task_id == "task-1"
        assert context.fragments == []
        assert context.token_count == 0

    @pytest.mark.asyncio
    async def test_add_fragment(self):
        """Add a fragment to context."""
        context = TaskContext(task_id="task-1")
        frag = ContextFragment(source="ledger", content="test", relevance_score=0.8)
        result = context.add_fragment(frag)
        assert result is True
        assert len(context.fragments) == 1

    @pytest.mark.asyncio
    async def test_add_fragment_budget_exceeded(self):
        """Fragment rejected when budget exceeded."""
        budget = ContextBudget(max_tokens=10, max_fragments=1, max_sources=1)
        context = TaskContext(task_id="task-1", budget=budget)
        frag1 = ContextFragment(source="ledger", content="x" * 100, relevance_score=0.8)
        context.add_fragment(frag1)
        frag2 = ContextFragment(source="memory", content="y" * 100, relevance_score=0.7)
        result = context.add_fragment(frag2)
        assert result is False
        assert context.exceeded is True

    @pytest.mark.asyncio
    async def test_add_fragment_sorts_by_relevance(self):
        """Fragments sorted by relevance score."""
        context = TaskContext(task_id="task-1")
        context.add_fragment(ContextFragment(source="a", content="x", relevance_score=0.3))
        context.add_fragment(ContextFragment(source="b", content="y", relevance_score=0.9))
        assert context.fragments[0].relevance_score == 0.9
        assert context.fragments[1].relevance_score == 0.3

    @pytest.mark.asyncio
    async def test_get_explain_report(self):
        """Generate explain report."""
        context = TaskContext(task_id="task-1")
        context.explain_mode = True
        context.add_fragment(
            ContextFragment(source="ledger", content="test", relevance_score=0.8,
                          explanation="Ledger event")
        )
        report = context.get_explain_report()
        assert "task-1" in report
        assert "Ledger event" in report
        assert "Fragment Details" in report

    @pytest.mark.asyncio
    async def test_context_to_dict(self):
        """Context serializes correctly."""
        context = TaskContext(task_id="task-1")
        context.add_fragment(
            ContextFragment(source="ledger", content="test", relevance_score=0.8)
        )
        d = context.to_dict()
        assert d["task_id"] == "task-1"
        assert len(d["fragments"]) == 1
        assert "budget" in d
        assert d["exceeded"] is False

    @pytest.mark.asyncio
    async def test_budget_property(self):
        """Context has budget property."""
        budget = ContextBudget(max_tokens=5000)
        context = TaskContext(task_id="task-1", budget=budget)
        assert context.budget.max_tokens == 5000


class TestPhase8ContextBuilder:
    """Phase 8 Context Builder tests."""

    @pytest.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        test_paw_home = tmp_path / ".paw"
        test_paw_home.mkdir(parents=True, exist_ok=True)
        os.environ["PAW_PAW_HOME"] = str(test_paw_home)
        test_db_path = test_paw_home / "paw.db"
        await set_db_path(test_db_path)
        await db.initialize()
        yield
        await db.close()

    @pytest.mark.asyncio
    async def test_build_context(self, tmp_path):
        """Build context for a task."""
        builder = ContextBuilder()
        context = await builder.build_context("task-1")
        assert context.task_id == "task-1"
        assert isinstance(context.fragments, list)

    @pytest.mark.asyncio
    async def test_build_context_for_execution(self, tmp_path):
        """Build execution context."""
        builder = ContextBuilder()
        context = await builder.build_context_for_execution("task-1")
        assert context.task_id == "task-1"

    @pytest.mark.asyncio
    async def test_build_context_explain(self, tmp_path):
        """Build context with explain mode."""
        builder = ContextBuilder()
        context, report = await builder.build_context_explain("task-1")
        assert context.task_id == "task-1"
        assert isinstance(report, str)
        assert len(report) > 0

    @pytest.mark.asyncio
    async def test_build_context_with_budget(self, tmp_path):
        """Build context with custom budget."""
        budget = ContextBudget(max_tokens=1000, max_fragments=10)
        builder = ContextBuilder(budget=budget)
        context = await builder.build_context_with_budget("task-1", budget)
        assert context.task_id == "task-1"
        assert context.budget.max_tokens == 1000

    @pytest.mark.asyncio
    async def test_builder_with_custom_budget(self):
        """Builder respects custom budget."""
        budget = ContextBudget(max_tokens=5000, max_fragments=20)
        builder = ContextBuilder(budget=budget)
        assert builder.budget.max_tokens == 5000
        assert builder.budget.max_fragments == 20

    @pytest.mark.asyncio
    async def test_explain_mode_flag(self, tmp_path):
        """Explain mode flag is set."""
        builder = ContextBuilder()
        context = await builder.build_context("task-1", explain_mode=True)
        assert context.explain_mode is True


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
        # Try installed package first
        import paw
        return Path(paw.__file__).parent

    def test_no_qwenpaw(self, paw_source_root):
        """No QwenPaw references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            assert "qwenpaw" not in content.lower(), f"QwenPaw reference found in {file}"

    def test_no_deepseek(self, paw_source_root):
        """No DeepSeek Harness references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            # Allow "deepseek" in model context (e.g., model names)
            assert "deepseek" not in content.lower() or "model" in content.lower(), f"DeepSeek reference found in {file}"

    def test_no_notebooklm(self, paw_source_root):
        """No NotebookLM references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            assert "notebooklm" not in content.lower(), f"NotebookLM reference found in {file}"

    def test_no_antigravity(self, paw_source_root):
        """No Google Antigravity references in PAW source."""
        runtime_files = list(paw_source_root.rglob("*.py"))
        assert runtime_files, "Dependency scan examined zero PAW runtime files"
        for file in runtime_files:
            content = file.read_text()
            assert "antigravity" not in content.lower(), f"Antigravity reference found in {file}"
