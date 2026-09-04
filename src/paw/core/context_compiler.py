"""
PAW Core — Context Compiler (Phase 10)

Compiles task context from multiple sources with planning, budgeting, and explainability.
Replaces the simpler ContextBuilder with a more sophisticated compilation pipeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .context import ContextBudget, ContextFragment, TokenEstimator
from .embeddings import cosine_similarity
from .ledger import TaskEventType, TaskLedger
from .logging import get_logger
from .memory import AdvancedMemoryRetriever, MemoryRecord
from .semantic import AdvancedSkillSelector
from .skills import get_skill_fabric
from .storage import db

if TYPE_CHECKING:
    from .context import TaskContext
    from .execution_profile import ExecutionProfile
    from .repo_filter import RepoFilter

logger = get_logger(__name__)


# --- ContextPlan ---

@dataclass
class ContextPlan:
    """Planning object that decides what context should be gathered BEFORE gathering."""
    task_id: str
    query: str
    token_budget: int

    # Source selection
    sources: list[str] = field(default_factory=lambda: [
        "ledger", "memory", "knowledge", "skills", "session", "repository"
    ])
    priorities: dict[str, float] = field(default_factory=lambda: {
        "ledger": 0.3,
        "memory": 0.25,
        "knowledge": 0.2,
        "skills": 0.15,
        "session": 0.1,
        "repository": 0.05,
    })

    # Feature flags
    include_memory: bool = True
    include_knowledge: bool = True
    include_session: bool = True
    include_ledger: bool = True
    include_repo: bool = False
    include_skills: bool = True

    # Skill filtering
    selected_skills: list[str] = field(default_factory=list)
    skill_categories: list[str] = field(default_factory=list)  # empty = all
    max_skills: int = 5

    # Knowledge filtering
    knowledge_query: str = ""
    max_knowledge_chunks: int = 10

    # Repository filtering
    repo_paths: list[str] = field(default_factory=list)
    # E1-04: optional deterministic include/exclude rule
    # applied to ``repo_paths`` when ``include_repo`` is True.
    # ``None`` means "no filter"; ``ContextCompiler`` falls
    # back to ``RepoFilter.safe_default()`` when
    # ``include_repo`` is True and the plan has no explicit
    # filter, so the runtime never loads ``__pycache__`` /
    # ``.git`` / etc. into a context by accident.
    repo_filter: RepoFilter | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# --- ContextCandidate ---

@dataclass
class ContextCandidate:
    """A candidate context item with metadata for ranking and budgeting."""
    source: str                      # "ledger", "memory", "knowledge", "skill", "session", "repository"
    source_id: str                   # Unique identifier within source
    content: str                     # Actual content (or reference for large content)
    reference: str | None = None     # Reference for lazy loading (e.g., file path, chunk ID)
    relevance_score: float = 0.5     # 0.0 to 1.0
    reason: str = ""                 # Why this candidate was selected
    token_estimate: int = 0          # Estimated tokens
    priority: float = 1.0            # Source priority weight
    metadata: dict[str, Any] = field(default_factory=dict)

    # Skill-specific
    skill_level: int = 0             # 0=metadata only, 1=body, 2=resources

    def __lt__(self, other: ContextCandidate) -> bool:
        """For sorting: higher relevance * priority first."""
        return (self.relevance_score * self.priority) > (other.relevance_score * other.priority)


# --- ContextCompiler ---

class ContextCompiler:
    """
    Compiles context from multiple sources through a pipeline:

    Task Goal → ContextPlan → Candidate Retrieval → Relevance Ranking →
    Deduplication → Budget Allocation → Context Selection → Optional Compression → TaskContext
    """

    def __init__(
        self,
        budget: ContextBudget | None = None,
        embedding_provider: Any | None = None,
        auto_attach_embeddings: bool = True,
    ):
        self.budget = budget or ContextBudget()
        self.embedding_provider = embedding_provider
        self.auto_attach_embeddings = auto_attach_embeddings
        self._embedding_resolved = False
        self._token_estimator = TokenEstimator()
        self._memory_retriever = AdvancedMemoryRetriever(
            embedding_provider=embedding_provider
        )

    async def _resolve_embedding_provider(self) -> None:
        """Lazily attach a local Ollama embedding provider if none was given.

        Runs at most once per compiler instance, only when ``embedding_provider``
        is ``None`` and ``auto_attach_embeddings`` is enabled. If Ollama is not
        running the provider stays ``None`` and retrieval degrades to lexical-only.
        """
        if self._embedding_resolved:
            return
        self._embedding_resolved = True
        if self.embedding_provider is not None:
            return
        if not self.auto_attach_embeddings:
            return
        try:
            from .embeddings import try_ollama_embedding_provider

            provider = await try_ollama_embedding_provider()
            if provider is not None:
                self.embedding_provider = provider
                self._memory_retriever.embedding_provider = provider
                logger.info("embedding_provider_auto_attached", name=provider.name)
        except Exception as exc:
            logger.warning("embedding_provider_auto_attach_failed", error=str(exc))

    async def compile(
        self,
        task_id: str,
        query: str,
        session_id: str | None = None,
        budget: ContextBudget | None = None,
        explain_mode: bool = False,
        execution_profile: ExecutionProfile | None = None,
    ) -> tuple[TaskContext, list[ContextCandidate]]:
        """
        Main compilation pipeline.

        Returns:
            Tuple of (TaskContext with selected fragments, all candidates with inclusion status)
        """
        if budget:
            self.budget = budget
        elif execution_profile:
            self.budget = execution_profile.resolved_context_budget()

        # 0. Resolve embedding provider (lazy auto-attach to local Ollama)
        await self._resolve_embedding_provider()

        # 1. Create ContextPlan
        plan = await self._create_plan(task_id, query, session_id, execution_profile)

        # 2. Candidate Retrieval
        candidates = await self._retrieve_candidates(plan, session_id)

        # 3. Relevance Ranking
        candidates = self._rank_candidates(candidates, query)

        # 4. Deduplication
        candidates = await self._deduplicate(candidates)

        # 5. Budget Allocation & Selection
        selected, excluded = self._allocate_budget(candidates)

        # 6. Build TaskContext (upgrades skills L0->L1 and re-budgets payload)
        context = await self._build_context(task_id, selected, excluded, explain_mode)

        # 7. Add explain entries for all candidates
        if explain_mode:
            self._add_explanations(context, selected, excluded)

        return context, candidates

    async def _create_plan(
        self,
        task_id: str,
        query: str,
        session_id: str | None,
        execution_profile: ExecutionProfile | None = None,
    ) -> ContextPlan:
        """Create a context plan based on task and available sources."""
        # In future, this could use LLM to decide sources
        # For now, use sensible defaults
        plan = ContextPlan(
            task_id=task_id,
            query=query,
            token_budget=self.budget.max_tokens,
            knowledge_query=query,
        )
        # Apply skill category filter from execution profile
        if execution_profile and execution_profile.skill_categories:
            plan.skill_categories = execution_profile.skill_categories
        return plan

    async def _retrieve_candidates(
        self,
        plan: ContextPlan,
        session_id: str | None,
    ) -> list[ContextCandidate]:
        """Retrieve candidate context items from all selected sources."""
        candidates = []

        # --- Ledger events ---
        if plan.include_ledger:
            ledger_candidates = await self._retrieve_ledger_candidates(plan.task_id)
            candidates.extend(ledger_candidates)

        # --- Session context ---
        if plan.include_session and session_id:
            session_cand = await self._retrieve_session_candidate(session_id)
            if session_cand:
                candidates.append(session_cand)

        # --- Memory ---
        if plan.include_memory:
            memory_candidates = await self._retrieve_memory_candidates(plan)
            candidates.extend(memory_candidates)

        # --- Knowledge ---
        if plan.include_knowledge:
            knowledge_candidates = await self._retrieve_knowledge_candidates(plan)
            candidates.extend(knowledge_candidates)

        # --- Skills ---
        if plan.include_skills:
            skill_candidates = await self._retrieve_skill_candidates(plan)
            candidates.extend(skill_candidates)

        # --- Repository ---
        if plan.include_repo and plan.repo_paths:
            repo_candidates = await self._retrieve_repo_candidates(plan)
            candidates.extend(repo_candidates)

        return candidates

    async def _retrieve_ledger_candidates(self, task_id: str) -> list[ContextCandidate]:
        """Retrieve ledger events as candidates."""
        events = await TaskLedger.get_events(task_id, limit=100)
        candidates = []

        for event in events:
            content = event.payload if event.payload else {}
            content_str = json.dumps(content) if isinstance(content, dict) else str(content)

            candidates.append(ContextCandidate(
                source="ledger",
                source_id=event.id,
                content=content_str,
                relevance_score=self._event_relevance(event.event_type),
                reason=f"Ledger event: {event.event_type.value}",
                token_estimate=self._token_estimator.estimate(content_str),
                priority=self.budget.priority_weights.get("ledger", 0.3),
                metadata={"event_type": event.event_type.value, "created_at": event.created_at.isoformat()},
            ))

        return candidates

    async def _retrieve_session_candidate(self, session_id: str) -> ContextCandidate | None:
        """Retrieve session as single candidate."""
        row = await db.fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if not row:
            return None

        row = dict(row)
        content = f"Session {session_id}"
        if row.get("project_id"):
            content += f" (project: {row['project_id']})"

        return ContextCandidate(
            source="session",
            source_id=session_id,
            content=content,
            relevance_score=0.4,
            reason=f"Session context for {session_id}",
            token_estimate=self._token_estimator.estimate(content),
            priority=self.budget.priority_weights.get("session", 0.2),
            metadata={"project_id": row.get("project_id")},
        )

    async def _retrieve_memory_candidates(self, plan: ContextPlan) -> list[ContextCandidate]:
        """Retrieve memory records as candidates."""
        # Get project_id from task
        task_row = await db.fetchone("SELECT project_id FROM tasks WHERE id = ?", (plan.task_id,))
        project_id = task_row["project_id"] if task_row else None

        rows = await db.fetchall(
            """
            SELECT * FROM memory_records
            WHERE project_id = ? OR id IN (
                SELECT memory_id FROM memory_task_map WHERE task_id = ?
            )
            LIMIT 50
            """,
            (project_id, plan.task_id),
        )

        candidates = []
        records: list[MemoryRecord] = []
        for row in rows:
            row = dict(row)
            content = row.get("content", "")
            if not content:
                continue
            records.append(MemoryRecord.from_row(row))

        # Score with AdvancedMemoryRetriever (hybrid lexical + semantic, with
        # graceful degradation to lexical-only when no embedding provider).
        scored = await self._memory_retriever.score_records(plan.query, records)

        for res in scored:
            row = res.record
            reason_kind = "semantic+lexical" if res.has_embedding else "lexical"
            candidates.append(ContextCandidate(
                source="memory",
                source_id=row.id,
                content=row.content,
                relevance_score=res.final_score,
                reason=f"Memory record ({reason_kind}): {row.summary[:50]}",
                token_estimate=self._token_estimator.estimate(row.content),
                priority=self.budget.priority_weights.get("memory", 0.25),
                metadata={
                    "memory_type": row.memory_type.value,
                    "confidence": row.confidence,
                    "created_at": (
                        row.created_at.isoformat()
                        if isinstance(row.created_at, datetime)
                        else str(row.created_at)
                    ),
                    "access_count": row.access_count,
                    "lexical_score": round(res.lexical_score, 4),
                    "semantic_score": round(res.semantic_score, 4),
                    "has_embedding": res.has_embedding,
                },
            ))

        return candidates

    async def _retrieve_knowledge_candidates(self, plan: ContextPlan) -> list[ContextCandidate]:
        """Retrieve knowledge chunks/evidence as candidates."""
        try:
            from paw.knowledge.index import get_knowledge_index
            idx = get_knowledge_index()

            # Search for relevant chunks
            results = await idx.search_chunks(plan.knowledge_query, limit=plan.max_knowledge_chunks)

            candidates = []
            for result in results:
                # Fetch the chunk together with its linked evidence/citations via
                # the chunk_id foreign key. (Joining by chunk_id here — not by
                # textually matching the chunk id inside an evidence claim — is
                # the correct, reliable linkage.)
                chunk = await idx.get_chunk_with_evidence(result.chunk_id)
                if not chunk:
                    continue
                chunk_dict = chunk.get("chunk", {})
                content = chunk_dict.get("content", "")
                if not content:
                    continue

                evidence_list = chunk.get("evidence", [])
                citation_list = chunk.get("citations", [])

                evidence_text = ""
                for ev in evidence_list[:3]:
                    claim = ev.get("claim", "")
                    if not claim:
                        continue
                    confidence = ev.get("confidence")
                    evidence_text += f"\nEvidence: {claim} (confidence={confidence})"

                full_content = content + evidence_text

                candidates.append(ContextCandidate(
                    source="knowledge",
                    source_id=result.chunk_id,
                    content=full_content,
                    relevance_score=result.score,
                    reason=f"Knowledge chunk from {result.source_id}",
                    token_estimate=self._token_estimator.estimate(full_content),
                    priority=self.budget.priority_weights.get("knowledge", 0.2),
                    metadata={
                        "source_id": result.source_id,
                        "evidence_count": len(evidence_list),
                        "citations": result.citations,
                        "citation_count": len(citation_list),
                    },
                    reference=result.chunk_id,
                ))
            return candidates
        except Exception as e:
            logger.warning("knowledge_retrieval_failed", error=str(e))
            return []

    async def _retrieve_skill_candidates(self, plan: ContextPlan) -> list[ContextCandidate]:
        """Retrieve skills as candidates, ranked by hybrid (lexical+semantic) relevance."""
        fabric = await get_skill_fabric()

        # Honor explicit category filter from execution profile if set
        selector = AdvancedSkillSelector(
            fabric,
            embedding_provider=self.embedding_provider,
            auto_attach_embeddings=self.auto_attach_embeddings,
        )
        selected = await selector.select(
            plan.query, max_results=plan.max_skills, min_score=0.0
        )
        if plan.skill_categories:
            selected = [s for s in selected if s.manifest.category in plan.skill_categories]

        candidates = []
        for res in selected:
            manifest = res.manifest
            reason_kind = "semantic+lexical" if res.has_embedding else "lexical"
            metadata_content = (
                f"Skill: {manifest.name}\n"
                f"Category: {manifest.category}\n"
                f"Description: {manifest.description}\n"
                f"Capabilities: {[c.value for c in manifest.capabilities]}"
            )

            candidates.append(ContextCandidate(
                source="skill",
                source_id=manifest.name,
                content=metadata_content,
                relevance_score=res.final_score,
                reason=f"Skill ({reason_kind}): {manifest.name}",
                token_estimate=self._token_estimator.estimate(metadata_content),
                priority=self.budget.priority_weights.get("skills", 0.15),
                metadata={
                    "category": manifest.category,
                    "risk": manifest.risk.value,
                    "capabilities": [c.value for c in manifest.capabilities],
                    "executors": manifest.executors,
                    "lexical_score": round(res.lexical_score, 4),
                    "semantic_score": round(res.semantic_score, 4),
                    "has_embedding": res.has_embedding,
                },
                skill_level=0,  # metadata only
            ))

        return candidates

    async def _retrieve_repo_candidates(self, plan: ContextPlan) -> list[ContextCandidate]:
        """Retrieve repository files as candidates (E1-04).

        Resolves the active filter (plan.repo_filter if set,
        else ``RepoFilter.safe_default()`` as the fail-closed
        default), runs it over ``plan.repo_paths``, and
        returns one ``ContextCandidate`` per surviving path.
        The candidate is lazy: ``content`` is empty, the
        path is the ``source_id`` and ``reference``, and
        the filter's repr is recorded in
        ``metadata["filter"]`` so the E1-17 manifest
        inspector can show why a path was included.
        """
        from .repo_filter import RepoFilter

        active_filter: RepoFilter = (
            plan.repo_filter if plan.repo_filter is not None
            else RepoFilter.safe_default()
        )
        kept = active_filter.filter_paths(plan.repo_paths)
        candidates: list[ContextCandidate] = []
        for path in kept:
            candidates.append(
                ContextCandidate(
                    source="repository",
                    source_id=path,
                    content="",
                    reference=path,
                    relevance_score=0.5,
                    reason="repo_filter:match",
                    token_estimate=0,
                    priority=1.0,
                    metadata={
                        "filter": repr(active_filter),
                        "kind": "repository_path",
                    },
                )
            )
        return candidates

    def _rank_candidates(self, candidates: list[ContextCandidate], query: str) -> list[ContextCandidate]:
        """Rank candidates by relevance to query."""
        if not query:
            return sorted(candidates, reverse=True)

        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        for cand in candidates:
            # Boost relevance based on content match
            content_lower = cand.content.lower()
            content_tokens = set(content_lower.split())

            # Token overlap
            overlap = len(query_tokens & content_tokens)
            token_boost = min(overlap / max(len(query_tokens), 1), 1.0) * 0.3

            # Source-specific boosting
            if cand.source == "skill":
                # Check if query matches skill trigger/description
                metadata = cand.metadata
                if isinstance(metadata, dict):
                    trigger = metadata.get("trigger", "").lower()
                    if trigger and trigger in query_lower:
                        token_boost += 0.4

            cand.relevance_score = min(cand.relevance_score + token_boost, 1.0)

        return sorted(candidates, reverse=True)

    def _content_tokens(self, text: str) -> set[str]:
        """Normalized token set for lexical similarity comparison."""
        return set(re.findall(r"\w+", (text or "").lower()))

    def _lexical_similarity(self, a: str, b: str) -> float:
        """Jaccard similarity over content tokens."""
        ta, tb = self._content_tokens(a), self._content_tokens(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    async def _semantic_similarity(self, a: str, b: str) -> float | None:
        """Embedding cosine similarity if a provider is configured, else None."""
        if self.embedding_provider is None:
            return None
        try:
            vecs = await self.embedding_provider.embed([a, b])
            if vecs and vecs[0] and vecs[1]:
                return max(cosine_similarity(vecs[0], vecs[1]), 0.0)
        except Exception as exc:
            logger.warning("dedup_embedding_failed", error=str(exc))
        return None

    async def _deduplicate(self, candidates: list[ContextCandidate]) -> list[ContextCandidate]:
        """Remove duplicates: exact (source, source_id) plus near-duplicate content.

        Near-duplicate detection works across sources (e.g. a memory fragment
        and a knowledge chunk restating the same fact) using lexical Jaccard
        similarity, upgraded to embedding cosine similarity when an
        ``embedding_provider`` is configured. The lower-priority (relevance *
        priority) duplicate is dropped and its exclusion reason recorded.
        """
        # 1. Exact (source, source_id) dedup
        seen_keys: set[tuple[str, str]] = set()
        exact_unique: list[ContextCandidate] = []
        for cand in candidates:
            key = (cand.source, cand.source_id)
            if key not in seen_keys:
                seen_keys.add(key)
                exact_unique.append(cand)

        # 2. Near-duplicate (cross-source) dedup
        if not getattr(self.budget, "dedup_enabled", True):
            return exact_unique
        threshold = getattr(self.budget, "dedup_threshold", 0.85)
        kept: list[ContextCandidate] = []
        for cand in exact_unique:
            dropped: ContextCandidate | None = None
            winner: ContextCandidate = cand
            best_sim = 0.0
            for kept_cand in list(kept):
                sim = self._lexical_similarity(cand.content, kept_cand.content)
                if sim < threshold:
                    sem = await self._semantic_similarity(cand.content, kept_cand.content)
                    if sem is not None:
                        sim = max(sim, sem)
                if sim >= threshold:
                    cand_rank = cand.relevance_score * cand.priority
                    kept_rank = kept_cand.relevance_score * kept_cand.priority
                    if cand_rank <= kept_rank:
                        # Drop the incoming candidate (lowest priority)
                        dropped = cand
                        winner = kept_cand
                        best_sim = sim
                        break
                    else:
                        # Incoming wins: drop the previously kept one instead
                        kept.remove(kept_cand)
                        kept_cand.metadata["excluded_reason"] = (
                            f"duplicate_of:{cand.source}:{cand.source_id}"
                        )
                        kept_cand.metadata["duplicate_similarity"] = round(sim, 3)
                        best_sim = sim
                        # winner stays cand; continue scanning remaining kept
            if dropped is not None:
                dropped.metadata["excluded_reason"] = (
                    f"duplicate_of:{winner.source}:{winner.source_id}"
                )
                dropped.metadata["duplicate_similarity"] = round(best_sim, 3)
                continue
            kept.append(cand)
        return kept

    def _allocate_budget(
        self,
        candidates: list[ContextCandidate],
    ) -> tuple[list[ContextCandidate], list[ContextCandidate]]:
        """Allocate token budget to candidates. Returns (selected, excluded)."""
        selected = []
        excluded = []

        current_tokens = 0
        current_fragments = 0
        current_sources = set()

        for cand in candidates:
            # Check budget constraints
            if current_fragments >= self.budget.max_fragments:
                excluded.append(cand)
                cand.metadata["excluded_reason"] = "max_fragments_exceeded"
                continue

            if len(current_sources) >= self.budget.max_sources and cand.source not in current_sources:
                excluded.append(cand)
                cand.metadata["excluded_reason"] = "max_sources_exceeded"
                continue

            if current_tokens + cand.token_estimate > self.budget.max_tokens:
                excluded.append(cand)
                cand.metadata["excluded_reason"] = "token_budget_exceeded"
                continue

            if cand.token_estimate > self.budget.max_content_length:
                # Too large, try reference-only
                if cand.reference:
                    # Use reference instead of content
                    cand.content = f"[Reference: {cand.reference}]"
                    cand.token_estimate = self._token_estimator.estimate(cand.content)
                else:
                    excluded.append(cand)
                    cand.metadata["excluded_reason"] = "content_too_large"
                    continue

            # Add to selected
            selected.append(cand)
            cand.metadata["included"] = True
            current_tokens += cand.token_estimate
            current_fragments += 1
            current_sources.add(cand.source)

        return selected, excluded

    async def _build_context(
        self,
        task_id: str,
        selected: list[ContextCandidate],
        excluded: list[ContextCandidate],
        explain_mode: bool,
    ) -> TaskContext:
        """Build TaskContext from selected candidates."""
        from .context import TaskContext

        context = TaskContext(
            task_id=task_id,
            budget=self.budget,
            explain_mode=explain_mode,
        )

        # 1. Progressive disclosure: selected Level-0 skills are upgraded to
        #    Level 1 (load the skill body so the context carries actionable
        #    instructions, not just metadata).
        for cand in selected:
            if cand.source == "skill" and cand.skill_level == 0:
                fabric = await get_skill_fabric()
                skill = fabric.get_skill(cand.source_id)
                if skill is not None and skill.manifest.body:
                    body = skill.manifest.body
                    body_tokens = self._token_estimator.estimate(body)
                    # Respect max content length; otherwise keep metadata summary
                    if body_tokens <= self.budget.max_content_length:
                        cand.content = body
                        cand.skill_level = 1
                        cand.token_estimate = body_tokens
                        cand.metadata["body_loaded"] = True
                    else:
                        cand.metadata["body_skipped"] = "exceeds_max_content_length"

        # 2. Re-budget the final payload. Upgrading skill bodies can push the
        #    total token count over ``max_tokens``; re-allocate and drop the
        #    lowest-priority survivors so the assembled context stays within
        #    budget. ``excluded`` is extended so explain reports stay accurate.
        selected, newly_excluded = self._allocate_budget(selected)
        excluded.extend(newly_excluded)

        # 3. Build fragments from the final (post-re-budget) selected set.
        for cand in selected:
            fragment = ContextFragment(
                source=cand.source,
                content=cand.content,
                metadata=cand.metadata,
                relevance_score=cand.relevance_score,
                explanation=cand.reason,
            )
            context.add_fragment_unlimited(fragment)

        return context

    def _add_explanations(
        self,
        context: TaskContext,
        selected: list[ContextCandidate],
        excluded: list[ContextCandidate],
    ) -> None:
        """Add explain entries to context for debugging."""
        for cand in selected:
            cand.metadata["included"] = True
            cand.metadata["explanation"] = cand.reason

        for cand in excluded:
            cand.metadata["included"] = False
            cand.metadata["explanation"] = cand.metadata.get("excluded_reason", "low relevance")

    def _event_relevance(self, event_type: TaskEventType) -> float:
        """Score ledger event relevance."""
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


# --- Explain Report ---

def format_explain_report(
    selected: list[ContextCandidate],
    excluded: list[ContextCandidate],
) -> str:
    """Format an explain report showing included and excluded candidates."""
    lines = [
        "=== CONTEXT COMPILER EXPLAIN REPORT ===",
        f"Selected: {len(selected)}, Excluded: {len(excluded)}",
        "",
        "--- INCLUDED ---",
    ]

    for cand in selected:
        lines.append(
            f"  ✓ [{cand.source}:{cand.source_id}] "
            f"score={cand.relevance_score:.2f} "
            f"tokens={cand.token_estimate} "
            f"reason={cand.reason}"
        )

    lines.append("\n--- EXCLUDED ---")
    for cand in excluded:
        reason = cand.metadata.get("excluded_reason", "low relevance")
        lines.append(
            f"  ✗ [{cand.source}:{cand.source_id}] "
            f"score={cand.relevance_score:.2f} "
            f"tokens={cand.token_estimate} "
            f"reason={reason}"
        )

    return "\n".join(lines)
