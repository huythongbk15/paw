"""
PAW Core — Context Builder (Phase 8)

Assembles context from session history, task ledger, and memory.
Includes explain mode and budget management per prompt spec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .ledger import TaskLedger
from .logging import get_logger
from .models import TaskEventType
from .storage import db

logger = get_logger(__name__)


# --- Token Estimator ---

class TokenEstimator:
    """Simple token estimator. Can be replaced with model-specific tokenizer."""

    def estimate(self, text: str) -> int:
        """Estimate token count for text.

        Uses simple heuristic: ~3 characters per token for English.
        """
        if not text:
            return 0
        # Rough approximation: 3 chars per token
        return max(1, len(text) // 3)


# --- Context Budget ---

@dataclass
class ContextBudget:
    """Budget constraints for context assembly."""
    max_tokens: int = 12000
    max_fragments: int = 50
    max_sources: int = 10
    max_content_length: int = 50000  # characters
    dedup_threshold: float = 0.85  # lexical/semantic similarity to treat as duplicate
    dedup_enabled: bool = True
    priority_weights: dict[str, float] = field(default_factory=lambda: {
        "ledger": 0.3,
        "memory": 0.25,
        "session": 0.2,
        "skill": 0.15,
        "knowledge": 0.1,
    })
    token_estimator: TokenEstimator = field(default_factory=TokenEstimator)

    def estimate_fragment_tokens(self, fragment: ContextFragment) -> int:
        """Estimate tokens for a fragment."""
        return self.token_estimator.estimate(fragment.content)

    def can_add_fragment(
        self,
        current_tokens: int,
        current_fragments: int,
        current_sources: int,
        candidate_fragment: ContextFragment | None = None,
    ) -> bool:
        """Check if adding a fragment would exceed budget.

        Considers the candidate fragment's estimated tokens.
        """
        if current_fragments >= self.max_fragments:
            return False
        if current_sources >= self.max_sources:
            return False

        if candidate_fragment is not None:
            estimated = self.estimate_fragment_tokens(candidate_fragment)
            if current_tokens + estimated > self.max_tokens:
                return False
        elif current_tokens >= self.max_tokens:
            return False

        return True


# --- Context Fragment with Explain ---

@dataclass
class ContextFragment:
    """A fragment of context from a specific source."""
    source: str
    event_type: TaskEventType | None = None
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    relevance_score: float = 0.5
    explanation: str = ""  # Phase 8: why this fragment was included

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_type": self.event_type.value if self.event_type else None,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "relevance_score": self.relevance_score,
            "explanation": self.explanation,
        }

    def explain(self) -> str:
        """Generate explanation for why this fragment was included."""
        if self.explanation:
            return self.explanation

        parts = [f"From {self.source}"]
        if self.event_type:
            parts.append(f"event type: {self.event_type.value}")
        parts.append(f"relevance: {self.relevance_score:.2f}")
        if self.metadata:
            keys = list(self.metadata.keys())[:3]
            if keys:
                parts.append(f"meta: {', '.join(keys)}")
        return "; ".join(parts)


# --- Task Context with Budget ---

@dataclass
class TaskContext:
    """Complete context assembled for a task with budget tracking."""
    task_id: str = ""
    fragments: list[ContextFragment] = field(default_factory=list)
    summary: str = ""
    token_count: int = 0
    budget: ContextBudget = field(default_factory=ContextBudget)
    exceeded: bool = False
    explain_mode: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "fragments": [f.to_dict() for f in self.fragments],
            "summary": self.summary,
            "token_count": self.token_count,
            "budget": {
                "max_tokens": self.budget.max_tokens,
                "max_fragments": self.budget.max_fragments,
                "max_sources": self.budget.max_sources,
                "max_content_length": self.budget.max_content_length,
            },
            "exceeded": self.exceeded,
            "explain_mode": self.explain_mode,
            "created_at": self.created_at.isoformat(),
        }

    def add_fragment(self, fragment: ContextFragment) -> bool:
        """Add a context fragment, respecting budget. Returns True if added."""
        if not self.budget.can_add_fragment(
            self.token_count,
            len(self.fragments),
            self._source_count(),
            fragment,  # pass candidate for token estimation
        ):
            self.exceeded = True
            return False

        self.fragments.append(fragment)
        self.fragments.sort(key=lambda f: f.relevance_score, reverse=True)
        self._update_summary()
        self._count_tokens()
        return True

    def add_fragment_unlimited(self, fragment: ContextFragment) -> None:
        """Add a fragment without budget check (for internal use)."""
        self.fragments.append(fragment)
        self.fragments.sort(key=lambda f: f.relevance_score, reverse=True)
        self._update_summary()
        self._count_tokens()

    def get_explain_report(self) -> str:
        """Generate explain mode report."""
        if not self.fragments:
            return "No context fragments."

        lines = [
            f"Task Context Report for {self.task_id}",
            f"Total fragments: {len(self.fragments)}",
            f"Token count: {self.token_count}",
            f"Budget: {self.budget.max_tokens} tokens, {self.budget.max_fragments} fragments",
            f"Exceeded: {self.exceeded}",
            "",
            "=== Fragment Details ===",
        ]

        for i, frag in enumerate(self.fragments, 1):
            lines.append(f"{i}. [{frag.source}] {frag.explain()}")
            if self.explain_mode and frag.content:
                lines.append(f"   Content: {frag.content[:100]}...")

        return "\n".join(lines)

    def _source_count(self) -> int:
        return len({f.source for f in self.fragments})

    def _update_summary(self) -> None:
        if not self.fragments:
            self.summary = ""
            return
        sources = {f.source for f in self.fragments}
        self.summary = f"Context from {', '.join(sources)}: {len(self.fragments)} fragments"

    def _count_tokens(self) -> None:
        total = sum(len(f.content.split()) for f in self.fragments)
        self.token_count = max(1, total // 3)


# --- Explain Mode Context ---

@dataclass
class ExplainEntry:
    """Single explanation entry for context assembly."""
    fragment_index: int
    source: str
    reason: str
    score: float
    content_preview: str = ""


# --- Context Builder ---

class ContextBuilder:
    """Builds complete task context from multiple sources with budget."""

    def __init__(self, budget: ContextBudget | None = None):
        self.budget = budget or ContextBudget()
        self._explain_entries: list[ExplainEntry] = []

    async def build_context(
        self,
        task_id: str,
        session_id: str | None = None,
        explain_mode: bool = False,
    ) -> TaskContext:
        """Build complete context for a task."""
        context = TaskContext(task_id=task_id)
        context.explain_mode = explain_mode
        self._explain_entries = []

        # 1. Load ledger events
        events = await TaskLedger.get_events(task_id, limit=100)
        for event in events:
            if not context.add_fragment(ContextFragment(
                source="ledger",
                event_type=event.event_type,
                content=json.dumps(event.payload) if event.payload else "",
                metadata={"event_type": event.event_type.value},
                relevance_score=self._event_relevance(event.event_type),
                explanation=f"Ledger event: {event.event_type.value}",
            )):
                logger.warning("context_budget_exceeded", source="ledger")
                break

        # 2. Load session context
        if session_id:
            session_ctx = await self._load_session_context(session_id)
            context.add_fragment(session_ctx)

        # 3. Load memory context
        memory_ctx = await self._load_memory_context(task_id)
        context.add_fragment(memory_ctx)

        # 4. Load knowledge context
        knowledge_ctx = await self._load_knowledge_context(task_id)
        context.add_fragment(knowledge_ctx)

        logger.info("context_built", task_id=task_id, fragments=len(context.fragments))
        return context

    async def build_context_for_execution(
        self,
        task_id: str,
        explain_mode: bool = False,
    ) -> TaskContext:
        """Build context specifically for executor execution."""
        context = await self.build_context(task_id, explain_mode=explain_mode)

        # Filter to only relevant fragments
        relevant = [
            f for f in context.fragments
            if f.source in ("ledger", "memory", "knowledge")
            and f.relevance_score >= 0.3
        ][:self.budget.max_fragments]

        exec_context = TaskContext(task_id=task_id, budget=self.budget)
        exec_context.explain_mode = explain_mode
        for frag in relevant:
            exec_context.add_fragment(frag)

        return exec_context

    async def build_context_explain(
        self,
        task_id: str,
        session_id: str | None = None,
    ) -> tuple[TaskContext, str]:
        """Build context with full explain mode."""
        context = await self.build_context(task_id, session_id, explain_mode=True)
        report = context.get_explain_report()
        return context, report

    async def build_context_with_budget(
        self,
        task_id: str,
        budget: ContextBudget,
    ) -> TaskContext:
        """Build context with custom budget."""
        context = TaskContext(task_id=task_id, budget=budget)

        # Load and add fragments respecting budget
        events = await TaskLedger.get_events(task_id, limit=100)
        for event in events:
            frag = ContextFragment(
                source="ledger",
                event_type=event.event_type,
                content=json.dumps(event.payload) if event.payload else "",
                metadata={"event_type": event.event_type.value},
                relevance_score=self._event_relevance(event.event_type),
            )
            if not context.add_fragment(frag):
                break

        return context

    def _event_relevance(self, event_type: TaskEventType) -> float:
        scores = {
            TaskEventType.EXECUTION_COMPLETED: 0.9,
            TaskEventType.TASK_COMPLETED: 0.9,
            TaskEventType.EXECUTION_STARTED: 0.7,
            TaskEventType.EXECUTOR_SELECTED: 0.8,
            TaskEventType.MODEL_SELECTED: 0.7,
            TaskEventType.POLICY_CHECKED: 0.6,
            TaskEventType.TOOL_CALLED: 0.5,
            TaskEventType.SKILL_SELECTED: 0.8,
            TaskEventType.PLAN_CREATED: 0.7,
            TaskEventType.SKILL_CANDIDATES_FOUND: 0.6,
            TaskEventType.CONTEXT_BUILT: 0.5,
            TaskEventType.MEMORY_PROPOSED: 0.4,
            TaskEventType.MEMORY_ACCEPTED: 0.4,
            TaskEventType.ARTIFACT_CREATED: 0.5,
            TaskEventType.TASK_CREATED: 0.3,
        }
        return scores.get(event_type, 0.2)

    async def _load_session_context(self, session_id: str) -> ContextFragment:
        row = await db.fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if row:
            return ContextFragment(
                source="session",
                content=f"Session {session_id}",
                metadata={"project_id": row.get("project_id")},
                relevance_score=0.4,
                explanation=f"Session context for {session_id}",
            )
        return ContextFragment(source="session", content="", relevance_score=0.1)

    async def _load_memory_context(self, task_id: str) -> ContextFragment:
        rows = await db.fetchall(
            """
            SELECT * FROM memory_records
            WHERE project_id IN (
                SELECT project_id FROM tasks WHERE id = ?
            ) OR id IN (
                SELECT memory_id FROM memory_task_map WHERE task_id = ?
            )
            ORDER BY created_at DESC LIMIT 10
            """,
            (task_id, task_id),
        )
        if rows:
            contents = [r["content"] for r in rows if r["content"]]
            if contents:
                return ContextFragment(
                    source="memory",
                    content="; ".join(contents[:5]),
                    metadata={"count": len(contents)},
                    relevance_score=0.6,
                    explanation=f"Loaded {len(contents)} memory records",
                )
        return ContextFragment(source="memory", content="", relevance_score=0.1)

    async def _load_knowledge_context(self, task_id: str) -> ContextFragment:
        """Load knowledge context for a task."""
        try:
            from paw.knowledge.index import get_knowledge_index
            idx = get_knowledge_index()
            citations = await idx.get_citations_for_task(task_id)
            if citations:
                return ContextFragment(
                    source="knowledge",
                    content=f"Citations for task {task_id}: {len(citations)} entries",
                    metadata={"citation_count": len(citations)},
                    relevance_score=0.5,
                    explanation="Knowledge citations linked to task",
                )
        except Exception as e:
            logger.warning("knowledge_context_failed", error=str(e))
        return ContextFragment(source="knowledge", content="", relevance_score=0.1)

    async def get_citations_for_task(self, task_id: str) -> list[dict]:
        """Get citations for a task from DB."""
        rows = await db.fetchall(
            "SELECT * FROM citations WHERE task_id = ? ORDER BY position",
            (task_id,),
        )
        return [dict(r) for r in rows]


# Global instance
_context_builder: ContextBuilder | None = None


def get_context_builder(budget: ContextBudget | None = None) -> ContextBuilder:
    """Get global context builder."""
    global _context_builder
    if _context_builder is None or budget is not None:
        _context_builder = ContextBuilder(budget)
    return _context_builder

# Alias for backward compatibility with tests
ContextItem = ContextFragment
