"""
PAW Core — Semantic Skill Matching (Phase 3)

Better skill matching using word overlap and TF-IDF-like scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

from .embeddings import cosine_similarity
from .logging import get_logger
from .skills import Skill, SkillFabric, SkillManifest, get_skill_fabric

logger = get_logger(__name__)


@dataclass
class SemanticScore:
    """Semantic similarity score between a query and a skill."""
    skill_name: str = ""
    skill_description: str = ""
    skill_trigger: str = ""
    query: str = ""
    word_overlap_score: float = 0.0
    trigger_match_score: float = 0.0
    semantic_score: float = 0.0
    combined_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "word_overlap_score": self.word_overlap_score,
            "trigger_match_score": self.trigger_match_score,
            "semantic_score": self.semantic_score,
            "combined_score": self.combined_score,
        }


class SemanticMatcher:
    """Semantic matching between queries and skills using word overlap and TF-IDF-like scoring."""

    # Synonym map for common terms
    SYNONYMS: ClassVar[dict[str, list[str]]] = {
        "calculate": ["tính", "compute", "con số", "số", "math"],
        "calculation": ["calculate", "tính", "compute"],
        "search": ["tìm", "search", "tìm kiếm", "look", "find", "dữ liệu"],
        "write": ["viết", "write", "lập trình", "code", "tạo"],
        "analyze": ["phân tích", "analyze", "review", "exam"],
        "summarize": ["tóm tắt", "summary", "tổng hợp", "rút gọn"],
        "translate": ["dịch", "translate", "chuyển"],
        "plan": ["kế hoạch", "plan", "organize", "schedule"],
        "read": ["đọc", "read", "xem", "tải"],
        "delete": ["xóa", "delete", "remove"],
        "network": ["mạng", "network", "internet", "web"],
        "file": ["file", "tệp", "tài liệu", "folder"],
    }

    def __init__(self, fabric: SkillFabric | None = None):
        self.fabric = fabric or SkillFabric(__import__("pathlib").Path(__file__).parent.parent / "skills")

    async def match(
        self,
        query: str,
        max_results: int = 10,
        min_score: float = 0.1,
    ) -> list[SemanticScore]:
        """Match skills to a query using semantic scoring."""
        candidates = self.fabric.find_candidates(query, max_results=50)
        scores: list[SemanticScore] = []

        query_tokens = self._tokenize(query)
        query_lower = query.lower()

        for candidate in candidates:
            score = self._score_skill(candidate, query_tokens, query_lower)
            if score.combined_score >= min_score:
                scores.append(score)

        # Sort by combined score descending
        scores.sort(key=lambda s: s.combined_score, reverse=True)
        return scores[:max_results]

    def _score_skill(
        self,
        skill: Skill,
        query_tokens: list[str],
        query_lower: str,
    ) -> SemanticScore:
        """Calculate semantic score for a skill."""
        manifest = skill.manifest
        name_tokens = self._tokenize(manifest.name)
        desc_tokens = self._tokenize(manifest.description)
        trigger_tokens = self._tokenize(manifest.trigger)

        # Word overlap score
        word_overlap = self._word_overlap(query_tokens, name_tokens + desc_tokens + trigger_tokens)

        # Trigger match score (exact or partial match)
        trigger_match = self._trigger_match(query_lower, manifest)

        # Semantic score (using synonyms)
        semantic = self._semantic_similarity(query_tokens, manifest)

        # Combined score (weighted)
        combined = (
            word_overlap * 0.3 +
            trigger_match * 0.3 +
            semantic * 0.4
        )

        return SemanticScore(
            skill_name=manifest.name,
            skill_description=manifest.description,
            skill_trigger=manifest.trigger,
            query=query_lower,
            word_overlap_score=round(word_overlap, 3),
            trigger_match_score=round(trigger_match, 3),
            semantic_score=round(semantic, 3),
            combined_score=round(combined, 3),
        )

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric."""
        if not text:
            return []
        return re.findall(r'\w+', text.lower())

    def _word_overlap(self, query_tokens: list[str], skill_tokens: list[str]) -> float:
        """Calculate word overlap ratio."""
        if not query_tokens or not skill_tokens:
            return 0.0

        query_set = set(query_tokens)
        skill_set = set(skill_tokens)

        intersection = query_set & skill_set
        if not intersection:
            return 0.0

        # Jaccard-like similarity
        union = query_set | skill_set
        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _trigger_match(self, query_lower: str, manifest: SkillManifest) -> float:
        """Calculate trigger match score."""
        trigger = manifest.trigger.lower()
        if not trigger:
            return 0.0

        # Exact match
        if trigger in query_lower:
            return 1.0

        # Word-level match
        trigger_words = self._tokenize(trigger)
        query_words = self._tokenize(query_lower)

        if not trigger_words:
            return 0.0

        matches = sum(1 for tw in trigger_words if tw in query_words)
        return matches / len(trigger_words)

    def _semantic_similarity(self, query_tokens: list[str], manifest: SkillManifest) -> float:
        """Calculate semantic similarity using synonyms."""
        if not query_tokens:
            return 0.0

        all_skill_text = (
            manifest.name + " " +
            manifest.description + " " +
            manifest.trigger + " " +
            " ".join(manifest.category)
        ).lower()
        skill_tokens = self._tokenize(all_skill_text)

        matched = 0
        total = len(query_tokens)

        for qt in query_tokens:
            # Direct match
            if qt in skill_tokens:
                matched += 1
            else:
                # Synonym match
                for synonyms in self.SYNONYMS.values():
                    if qt in synonyms or qt in self._tokenize(" ".join(synonyms)):
                        # Check if any synonym is in skill text
                        skill_text = " ".join(skill_tokens)
                        if any(s in skill_text for s in synonyms):
                            matched += 0.5
                            break

        return matched / total if total > 0 else 0.0

    async def match_for_skill_selection(
        self,
        query: str,
        requested_capabilities: list[str] | None = None,
    ) -> list[dict]:
        """Match skills for skill selection with capabilities filter."""
        scores = await self.match(query)

        results = []
        for score in scores:
            # Find the skill manifest
            manifest = self.fabric._manifest_index.get(score.skill_name)
            if not manifest:
                continue

            result = score.to_dict()
            result["description"] = manifest.description
            result["category"] = manifest.category
            result["capabilities"] = [c.value for c in manifest.capabilities]
            result["risk"] = manifest.risk.value

            # Filter by requested capabilities
            if requested_capabilities:
                cap_set = set(requested_capabilities)
                skill_caps = set(manifest.capabilities)
                if not cap_set.isdisjoint(skill_caps):
                    results.append(result)
            else:
                results.append(result)

        return results


class SemanticSkillSelector:
    """Compatibility dictionary facade over ``AdvancedSkillSelector``."""

    def __init__(self, fabric: SkillFabric | None = None):
        self.matcher = SemanticMatcher(fabric)
        self.fabric = fabric or self.matcher.fabric
        self._canonical = AdvancedSkillSelector(
            self.fabric,
            embedding_provider=None,
            auto_attach_embeddings=False,
        )

    async def select(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
        requested_capabilities: list[str] | None = None,
    ) -> list[dict]:
        """Adapt canonical results to the legacy list-of-dicts shape."""
        results = await self._canonical.select(
            query,
            max_results=max_results,
            min_score=min_score,
            requested_capabilities=requested_capabilities,
        )
        adapted = []
        for result in results:
            payload = result.to_dict()
            payload["combined_score"] = result.final_score
            payload["word_overlap_score"] = result.lexical_score
            payload["trigger_match_score"] = 0.0
            adapted.append(payload)
        return adapted


# Global instance
_semantic_selector: SemanticSkillSelector | None = None


def get_semantic_selector(fabric: SkillFabric | None = None) -> SemanticSkillSelector:
    """Get the global semantic skill selector."""
    global _semantic_selector
    if _semantic_selector is None or fabric is not None:
        _semantic_selector = SemanticSkillSelector(fabric)
    return _semantic_selector


# --- Advanced Semantic Skill Selector with Embeddings (Phase 11 deferred / Phase 12 pattern) ---


@dataclass
class AdvancedSkillResult:
    """A skill match with transparent lexical/semantic component scores."""

    manifest: SkillManifest
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    final_score: float = 0.0
    has_embedding: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.manifest.name,
            "category": self.manifest.category,
            "description": self.manifest.description,
            "capabilities": [c.value for c in self.manifest.capabilities],
            "risk": self.manifest.risk.value,
            "lexical_score": round(self.lexical_score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "final_score": round(self.final_score, 4),
            "has_embedding": self.has_embedding,
        }


class AdvancedSkillSelector:
    """Hybrid skill selector: lexical (SemanticMatcher) + semantic embeddings.

    Reuses the ``AdvancedMemoryRetriever`` pattern from Phase 12. When an
    ``EmbeddingProvider`` is configured, every enabled skill is scored by
    semantic similarity (so lexically-distant but semantically relevant skills
    surface). Without a provider it degrades to lexical-only scoring.
    """

    def __init__(
        self,
        fabric: SkillFabric | None = None,
        embedding_provider: Any | None = None,
        lexical_weight: float = 0.5,
        semantic_weight: float = 0.5,
        auto_attach_embeddings: bool = True,
    ):
        self.fabric = fabric or get_skill_fabric()
        self.matcher = SemanticMatcher(self.fabric)
        self.embedding_provider = embedding_provider
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight
        self.auto_attach_embeddings = auto_attach_embeddings
        self._embedding_resolved = False

    async def _resolve_embedding_provider(self) -> None:
        """Lazily attach a local Ollama embedding provider if none was given.

        Runs at most once per selector instance, only when ``embedding_provider``
        is ``None`` and ``auto_attach_embeddings`` is enabled. If Ollama is not
        running the provider stays ``None`` and scoring degrades to lexical-only.
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
                logger.info("skill_selector_embedding_auto_attached", name=provider.name)
        except Exception as exc:
            logger.warning("skill_selector_embedding_auto_attach_failed", error=str(exc))

    @staticmethod
    def _skill_doc(manifest: SkillManifest) -> str:
        caps = " ".join(c.value for c in manifest.capabilities)
        return f"{manifest.name} {manifest.category} {manifest.description} {manifest.trigger} {caps}"

    async def select(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
        requested_capabilities: list[str] | None = None,
    ) -> list[AdvancedSkillResult]:
        await self._resolve_embedding_provider()
        raw_skills = self.fabric.list_skills(enabled_only=True)
        # list_skills() returns SkillManifest; wrap defensively in case a
        # caller (or test double) returns Skill objects already.
        skills = [s if isinstance(s, Skill) else Skill(s) for s in raw_skills]

        # Capability filter
        if requested_capabilities:
            req_set = set(requested_capabilities)
            skills = [
                s for s in skills
                if not req_set.isdisjoint({c.value for c in s.manifest.capabilities})
            ]
        if not skills:
            return []

        # Lexical scores for ALL enabled skills (no lexical pre-filter, so
        # semantic recall can override weak lexical overlap)
        query_tokens = self.matcher._tokenize(query)
        query_lower = query.lower()
        lexical: dict[str, float] = {}
        for s in skills:
            sc = self.matcher._score_skill(s, query_tokens, query_lower)
            lexical[s.manifest.name] = sc.combined_score

        # Semantic scores
        semantic: dict[str, float] = {}
        if self.embedding_provider is not None:
            docs = [self._skill_doc(s.manifest) for s in skills]
            try:
                vecs = await self.embedding_provider.embed(docs)
                qvecs = await self.embedding_provider.embed([query])
                qvec = qvecs[0] if qvecs else None
                if qvec:
                    for s, vec in zip(skills, vecs, strict=False):
                        if vec:
                            semantic[s.manifest.name] = max(cosine_similarity(qvec, vec), 0.0)
            except Exception as exc:
                logger.warning("skill_embedding_failed", error=str(exc))

        results: list[AdvancedSkillResult] = []
        for s in skills:
            name = s.manifest.name
            lex = lexical.get(name, 0.0)
            sem = semantic.get(name, 0.0)
            has_emb = name in semantic
            final = (
                self.lexical_weight * lex + self.semantic_weight * sem
                if has_emb
                else lex
            )
            results.append(AdvancedSkillResult(s.manifest, lex, sem, final, has_emb))

        results.sort(key=lambda r: r.final_score, reverse=True)
        return [r for r in results if r.final_score >= min_score][:max_results]


_semantic_selector_v2: AdvancedSkillSelector | None = None


def get_advanced_skill_selector(
    fabric: SkillFabric | None = None, embedding_provider: Any | None = None
) -> AdvancedSkillSelector:
    """Get (or build) the advanced semantic skill selector."""
    global _semantic_selector_v2
    if _semantic_selector_v2 is None or fabric is not None or embedding_provider is not None:
        _semantic_selector_v2 = AdvancedSkillSelector(fabric, embedding_provider=embedding_provider)
    return _semantic_selector_v2
