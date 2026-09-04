"""
PAW Core — Context Builder (Phase 8)

Assembles context from session history, task ledger, and memory.
Includes explain mode and budget management per prompt spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

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

@dataclass(frozen=True)
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
    # ``token_estimator`` is excluded from equality
    # because the dataclass ``==`` would otherwise
    # compare the estimator object by identity; the
    # estimator is a behavior, not a value.
    token_estimator: TokenEstimator = field(
        default_factory=TokenEstimator, compare=False
    )

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


# --- Context Builder compatibility facade ---

class ContextBuilder:
    """Compatibility facade over the canonical :class:`ContextCompiler`.

    New code must use ``ContextCompiler.compile`` directly. Keeping this thin
    adapter avoids a second context assembly algorithm for older callers.
    """

    def __init__(self, budget: ContextBudget | None = None):
        self.budget = budget or ContextBudget()
        self._compiler = None

    def _get_compiler(self):
        if self._compiler is None:
            from .context_compiler import ContextCompiler
            self._compiler = ContextCompiler(
                budget=self.budget,
                auto_attach_embeddings=False,
            )
        return self._compiler

    async def build_context(
        self,
        task_id: str,
        session_id: str | None = None,
        explain_mode: bool = False,
    ) -> TaskContext:
        context, _ = await self._get_compiler().compile(
            task_id, f"task:{task_id}", session_id=session_id,
            explain_mode=explain_mode,
        )
        return context

    async def build_context_for_execution(
        self,
        task_id: str,
        explain_mode: bool = False,
    ) -> TaskContext:
        context, _ = await self._get_compiler().compile(
            task_id, f"task:{task_id}", explain_mode=explain_mode,
        )
        return context

    async def build_context_explain(
        self,
        task_id: str,
        session_id: str | None = None,
    ) -> tuple[TaskContext, str]:
        context = await self.build_context(task_id, session_id, explain_mode=True)
        return context, context.get_explain_report()

    async def build_context_with_budget(
        self,
        task_id: str,
        budget: ContextBudget,
    ) -> TaskContext:
        from .context_compiler import ContextCompiler
        context, _ = await ContextCompiler(
            budget=budget, auto_attach_embeddings=False,
        ).compile(task_id, f"task:{task_id}")
        return context

    async def get_citations_for_task(self, task_id: str) -> list[dict]:
        rows = await db.fetchall(
            "SELECT * FROM citations WHERE task_id = ? ORDER BY position",
            (task_id,),
        )
        return [dict(row) for row in rows]


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
