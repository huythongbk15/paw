"""
PAW Core — Semantic Skill Matching (Phase 3)

Better skill matching using word overlap and TF-IDF-like scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .logging import get_logger
from .skills import Skill, SkillFabric, SkillManifest

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
    SYNONYMS: dict[str, list[str]] = {
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
            query=query,
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
    """Semantic-based skill selector."""

    def __init__(self, fabric: SkillFabric | None = None):
        self.matcher = SemanticMatcher(fabric)
        self.fabric = fabric or self.matcher.fabric

    async def select(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
        requested_capabilities: list[str] | None = None,
    ) -> list[dict]:
        """Select skills using semantic matching."""
        results = await self.matcher.match_for_skill_selection(
            query, requested_capabilities
        )

        # Filter by min score
        filtered = [r for r in results if r["combined_score"] >= min_score]

        # Limit results
        return filtered[:max_results]


# Global instance
_semantic_selector: SemanticSkillSelector | None = None


def get_semantic_selector(fabric: SkillFabric | None = None) -> SemanticSkillSelector:
    """Get the global semantic skill selector."""
    global _semantic_selector
    if _semantic_selector is None or fabric is not None:
        _semantic_selector = SemanticSkillSelector(fabric)
    return _semantic_selector