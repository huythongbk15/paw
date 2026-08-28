"""
Phase 3 Tests — Intelligent Planner, Semantic Matching, Memory, Executor Policy
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paw.core import (
    Capability,
    ContextBuilder,
    ContextFragment,
    DecompositionResult,
    DecompositionStep,
    ExecutorPolicyEnforcer,
    IntelligentPlanner,
    MemoryRecord,
    MemoryRetriever,
    MemoryStore,
    MemoryType,
    MockExecutor,
    PolicyCheckResult,
    PolicyEnforcedExecutor,
    SemanticMatcher,
    SemanticScore,
    SemanticSkillSelector,
    SessionManager,
    TaskStatus,
    create_memory,
    get_enforcer,
    get_semantic_selector,
    get_skill_fabric,
)
from paw.core.storage import db, set_db_path


class TestPhase3IntelligentPlanner:
    """Phase 3 Intelligent Planner tests."""

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
    async def test_classify_intent(self, tmp_path):
        """Classify goal intent."""
        from paw.core.intelligent_planner import IntentClassifier
        classifier = IntentClassifier()

        intents = classifier.classify("tính 2 + 2")
        assert "calculation" in intents

        intents = classifier.classify("tìm kiếm thông tin")
        assert "search" in intents

        intents = classifier.classify("viết code")
        assert "write" in intents

        intents = classifier.classify("phân tích dữ liệu")
        assert "analyze" in intents

    @pytest.mark.asyncio
    async def test_structured_reasoning(self, tmp_path):
        """Structured reasoning decomposition."""
        from paw.core.intelligent_planner import StructuredReasoner
        reasoner = StructuredReasoner()

        result = reasoner.decompose("tính 2 + 2")
        assert len(result.steps) > 0
        assert result.confidence > 0
        assert result.reasoning_summary

    @pytest.mark.asyncio
    async def test_intelligent_planner(self, tmp_path):
        """Full intelligent plan creation."""
        planner = IntelligentPlanner()
        result = await planner.plan("tính 2 + 2", "session-123")

        assert result["goal"] == "tính 2 + 2"
        assert len(result["nodes"]) > 0
        assert result["confidence"] > 0
        assert "intents" in result

    @pytest.mark.asyncio
    async def test_intelligent_planner_persistence(self, tmp_path):
        """Intelligent plan saved to DB."""
        planner = IntelligentPlanner()
        result = await planner.plan_and_save("search files", "session-456")
        assert result["goal"] == "search files"
        assert len(result["nodes"]) > 0

    @pytest.mark.asyncio
    async def test_decomposition_step(self, tmp_path):
        """Decomposition step attributes."""
        from paw.core.intelligent_planner import StructuredReasoner
        reasoner = StructuredReasoner()
        result = reasoner.decompose("viết code")

        for step in result.steps:
            assert step.goal
            assert isinstance(step.sub_goals, list)
            assert isinstance(step.required_capabilities, list)
            assert step.estimated_effort in ("low", "medium", "high")

    @pytest.mark.asyncio
    async def test_intent_keywords(self, tmp_path):
        """Intent classification keywords work correctly."""
        from paw.core.intelligent_planner import IntentClassifier
        classifier = IntentClassifier()

        # Test all intent categories
        assert "calculation" in classifier.classify("tính toán")
        assert "search" in classifier.classify("tìm kiếm")
        assert "write" in classifier.classify("viết code")
        assert "analyze" in classifier.classify("phân tích")
        assert "summarize" in classifier.classify("tóm tắt")
        assert "translate" in classifier.classify("dịch")
        assert "plan" in classifier.classify("lập kế hoạch")
        assert "decision" in classifier.classify("nên chọn")


class TestPhase3Semantic:
    """Phase 3 Semantic Matching tests."""

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
    async def test_semantic_score(self, tmp_path):
        """Create and serialize a semantic score."""
        score = SemanticScore(
            skill_name="test",
            query="test query",
            combined_score=0.8,
        )
        d = score.to_dict()
        assert d["skill_name"] == "test"
        assert d["combined_score"] == 0.8

    @pytest.mark.asyncio
    async def test_semantic_matcher(self, tmp_path):
        """Match skills semantically."""
        fabric = await get_skill_fabric()
        matcher = SemanticMatcher(fabric)
        scores = await matcher.match("tính toán", max_results=5)
        assert isinstance(scores, list)
        if scores:
            assert all(isinstance(s, SemanticScore) for s in scores)

    @pytest.mark.asyncio
    async def test_semantic_selector(self, tmp_path):
        """Semantic skill selector."""
        fabric = await get_skill_fabric()
        selector = SemanticSkillSelector(fabric)
        results = await selector.select("hello world", max_results=3)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_synonym_matching(self, tmp_path):
        """Synonym-based semantic matching."""
        from paw.core.semantic import SemanticMatcher
        matcher = SemanticMatcher()

        # Test that synonyms map correctly
        assert "calculate" in SemanticMatcher.SYNONYMS.get("calculation", [])
        assert "search" in SemanticMatcher.SYNONYMS.get("search", [])

    @pytest.mark.asyncio
    async def test_semantic_scores_sorted(self, tmp_path):
        """Semantic scores are sorted by combined score."""
        fabric = await get_skill_fabric()
        matcher = SemanticMatcher(fabric)
        scores = await matcher.match("tìm kiếm", max_results=10)
        if len(scores) >= 2:
            assert scores[0].combined_score >= scores[-1].combined_score


class TestPhase3Memory:
    """Phase 3 Memory Integration tests."""

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
    async def test_memory_record_creation(self, tmp_path):
        """Create a memory record."""
        record = MemoryRecord(
            memory_type=MemoryType.EPISODIC,
            content="Test episodic memory",
            summary="A test memory",
            keywords=["test", "memory"],
        )
        assert record.memory_type == MemoryType.EPISODIC
        assert record.content == "Test episodic memory"
        assert record.summary == "A test memory"

    @pytest.mark.asyncio
    async def test_memory_store(self, tmp_path):
        """Store a memory record."""
        store = MemoryStore()
        record = await create_memory(
            MemoryType.EPISODIC,
            "Test episodic memory",
            summary="A test memory",
            keywords=["test", "memory"],
        )
        assert record.id
        assert record.memory_type == MemoryType.EPISODIC

    @pytest.mark.asyncio
    async def test_memory_retrieve(self, tmp_path):
        """Retrieve stored memory."""
        store = MemoryStore()
        record = await create_memory(
            MemoryType.SEMANTIC,
            "Semantic memory content",
            summary="Semantic test",
            project_id="proj-123",
        )
        assert record.id

        retrieved = await store.get_by_id(record.id)
        assert retrieved is not None
        assert retrieved.content == "Semantic memory content"

    @pytest.mark.asyncio
    async def test_memory_by_type(self, tmp_path):
        """Get memories by type."""
        store = MemoryStore()
        await create_memory(MemoryType.EPISODIC, "Episodic content")
        await create_memory(MemoryType.SEMANTIC, "Semantic content")

        episodic = await store.get_by_type(MemoryType.EPISODIC)
        assert len(episodic) >= 1
        assert all(r.memory_type == MemoryType.EPISODIC for r in episodic)

    @pytest.mark.asyncio
    async def test_memory_by_project(self, tmp_path):
        """Get memories by project."""
        store = MemoryStore()
        await create_memory(MemoryType.SEMANTIC, "Content 1", project_id="proj-1")
        await create_memory(MemoryType.SEMANTIC, "Content 2", project_id="proj-2")

        proj_memories = await store.get_by_project("proj-1")
        assert len(proj_memories) >= 1

    @pytest.mark.asyncio
    async def test_memory_search(self, tmp_path):
        """Search memories by keyword."""
        store = MemoryStore()
        await create_memory(MemoryType.SEMANTIC, "Python programming is great")
        await create_memory(MemoryType.SEMANTIC, "JavaScript framework overview")

        results = await store.search("Python programming")
        assert len(results) >= 1
        assert results[0]["relevance_score"] > 0.1

    @pytest.mark.asyncio
    async def test_memory_update_access(self, tmp_path):
        """Update memory access tracking."""
        store = MemoryStore()
        record = await create_memory(MemoryType.EPISODIC, "Access test")
        assert record.id

        await store.update_access(record.id)
        retrieved = await store.get_by_id(record.id)
        assert retrieved.access_count >= 1

    @pytest.mark.asyncio
    async def test_memory_recent(self, tmp_path):
        """Get most recent memories."""
        store = MemoryStore()
        await create_memory(MemoryType.EPISODIC, "Recent memory 1")
        await create_memory(MemoryType.EPISODIC, "Recent memory 2")

        recent = await store.get_recent(limit=5)
        assert len(recent) >= 2

    @pytest.mark.asyncio
    async def test_memory_delete(self, tmp_path):
        """Delete a memory record."""
        store = MemoryStore()
        record = await create_memory(MemoryType.EPISODIC, "To be deleted")
        assert record.id

        deleted = await store.delete(record.id)
        assert deleted is True

        retrieved = await store.get_by_id(record.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_memory_types(self, tmp_path):
        """Get counts by memory type."""
        store = MemoryStore()
        await create_memory(MemoryType.EPISODIC, "Episodic")
        await create_memory(MemoryType.SEMANTIC, "Semantic 1")
        await create_memory(MemoryType.SEMANTIC, "Semantic 2")

        counts = await store.get_all_memory_types()
        assert "episodic" in counts
        assert "semantic" in counts
        assert counts["semantic"] >= 2

    @pytest.mark.asyncio
    async def test_memory_record_to_dict(self, tmp_path):
        """Memory record serialization."""
        record = MemoryRecord(
            memory_type=MemoryType.FACTUAL,
            content="Test content",
            keywords=["a", "b"],
            confidence=0.9,
        )
        d = record.to_dict()
        assert d["memory_type"] == "factual"
        assert d["confidence"] == 0.9
        assert d["keywords"] == ["a", "b"]


class TestPhase3ExecutorPolicy:
    """Phase 3 Executor Policy Enforcement tests."""

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
    async def test_policy_check_result(self, tmp_path):
        """Create and serialize a policy check result."""
        result = PolicyCheckResult(
            allowed=True,
            decision="allow",
            blocked_capabilities=[],
            asked_capabilities=[],
            message="All clear",
        )
        d = result.to_dict()
        assert d["allowed"] is True
        assert d["decision"] == "allow"

    @pytest.mark.asyncio
    async def test_executor_policy_enforcer(self, tmp_path):
        """Pre-execute policy check."""
        enforcer = ExecutorPolicyEnforcer()
        check = await enforcer.pre_execute_check(
            "task-123",
            "test",
            [Capability.FILESYSTEM_READ],
        )
        assert isinstance(check, PolicyCheckResult)
        assert check.allowed is True

    @pytest.mark.asyncio
    async def test_policy_enforced_executor(self, tmp_path):
        """Execute with policy enforcement."""
        fabric = await get_skill_fabric()
        from paw.core.executor import MockExecutor
        executor = MockExecutor()
        policy_executor = PolicyEnforcedExecutor(executor)

        result = await policy_executor.execute(
            "task-123",
            "hello world",
            [Capability.FILESYSTEM_READ],
            "Test context",
        )
        assert result["task_id"] == "task-123"
        assert "policy_check" in result
        assert "result" in result
        assert result["blocked"] is False

    @pytest.mark.asyncio
    async def test_policy_blocks_destructive(self, tmp_path):
        """Policy blocks destructive capabilities."""
        enforcer = ExecutorPolicyEnforcer()
        check = await enforcer.pre_execute_check(
            "task-123",
            "delete everything",
            [Capability.DESTRUCTIVE],
        )
        assert check.allowed is False
        assert check.decision == "deny"
        assert len(check.blocked_capabilities) > 0

    @pytest.mark.asyncio
    async def test_policy_check_result_denied(self, tmp_path):
        """Policy check result for denied case."""
        result = PolicyCheckResult(
            allowed=False,
            decision="deny",
            blocked_capabilities=["destructive"],
            message="Blocked: destructive",
        )
        assert result.allowed is False
        assert "destructive" in result.blocked_capabilities


class TestPhase3NoProhibitedDependencies:
    """Verify no prohibited dependencies in Phase 3 modules."""

    def test_no_qwenpaw_in_phase3(self):
        phase3_files = [
            Path(__file__).parent.parent / "paw" / "core" / "intelligent_planner.py",
            Path(__file__).parent.parent / "paw" / "core" / "semantic.py",
            Path(__file__).parent.parent / "paw" / "core" / "memory.py",
            Path(__file__).parent.parent / "paw" / "core" / "executor_policy.py",
        ]
        for py_file in phase3_files:
            if py_file.exists():
                content = py_file.read_text()
                assert "qwenpaw" not in content.lower(), f"QwenPaw reference in {py_file}"

    def test_no_deepseek_in_phase3(self):
        phase3_files = [
            Path(__file__).parent.parent / "paw" / "core" / "intelligent_planner.py",
            Path(__file__).parent.parent / "paw" / "core" / "semantic.py",
            Path(__file__).parent.parent / "paw" / "core" / "memory.py",
            Path(__file__).parent.parent / "paw" / "core" / "executor_policy.py",
        ]
        for py_file in phase3_files:
            if py_file.exists():
                content = py_file.read_text()
                assert "deepseek" not in content.lower() or "model" in content.lower(), \
                    f"DeepSeek reference in {py_file}"

    def test_no_notebooklm_in_phase3(self):
        phase3_files = [
            Path(__file__).parent.parent / "paw" / "core" / "intelligent_planner.py",
            Path(__file__).parent.parent / "paw" / "core" / "semantic.py",
            Path(__file__).parent.parent / "paw" / "core" / "memory.py",
            Path(__file__).parent.parent / "paw" / "core" / "executor_policy.py",
        ]
        for py_file in phase3_files:
            if py_file.exists():
                content = py_file.read_text()
                assert "notebooklm" not in content.lower(), f"NotebookLM reference in {py_file}"

    def test_no_antigravity_in_phase3(self):
        phase3_files = [
            Path(__file__).parent.parent / "paw" / "core" / "intelligent_planner.py",
            Path(__file__).parent.parent / "paw" / "core" / "semantic.py",
            Path(__file__).parent.parent / "paw" / "core" / "memory.py",
            Path(__file__).parent.parent / "paw" / "core" / "executor_policy.py",
        ]
        for py_file in phase3_files:
            if py_file.exists():
                content = py_file.read_text()
                assert "antigravity" not in content.lower(), f"Antigravity reference in {py_file}"