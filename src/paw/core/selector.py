"""
PAW Core — Skill Selector

Matches skills to tasks based on capabilities, triggers, and semantic similarity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .logging import get_logger
from .models import Capability, SkillRisk
from .semantic import AdvancedSkillSelector
from .skills import Skill, SkillFabric
from .storage import db

logger = get_logger(__name__)


@dataclass
class SkillSelection:
    """Result of selecting skills for a task."""
    task_id: str = ""
    selected_skills: list[Skill] = field(default_factory=list)
    rejected_skills: list[Skill] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0
    policy_decisions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "selected_skills": [s.manifest.name for s in self.selected_skills],
            "rejected_skills": [s.manifest.name for s in self.rejected_skills],
            "reason": self.reason,
            "confidence": self.confidence,
            "policy_decisions": self.policy_decisions,
        }


class SkillSelector:
    """Compatibility result facade over ``AdvancedSkillSelector``.

    Skill ranking has one owner in :mod:`paw.core.semantic`. Policy is not a
    selection concern: the runtime evaluates the capabilities of the exact
    proposed operation after selection.
    """

    def __init__(self, fabric: SkillFabric | None = None):
        self.fabric = fabric or SkillFabric(__import__("pathlib").Path(__file__).parent.parent / "skills")
        self._canonical = AdvancedSkillSelector(
            self.fabric,
            embedding_provider=None,
            auto_attach_embeddings=False,
        )

    async def select(
        self,
        goal: str,
        requested_capabilities: list[Capability] | None = None,
        preferred_risk: SkillRisk | None = None,
    ) -> SkillSelection:
        """Adapt canonical ranked results to the legacy ``SkillSelection``."""
        selection = SkillSelection(task_id="", reason="", confidence=0.0)
        ranked = await self._canonical.select(
            goal,
            max_results=20,
            min_score=0.0,
            requested_capabilities=(
                [capability.value for capability in requested_capabilities]
                if requested_capabilities
                else None
            ),
        )
        candidates = [Skill(result.manifest) for result in ranked]
        await self._log_candidates_found(goal, candidates)

        risk_order = {SkillRisk.LOW: 0, SkillRisk.MEDIUM: 1, SkillRisk.HIGH: 2}
        selected_results = []
        rejected: list[Skill] = []
        policy_decisions: dict[str, str] = {}
        for result, skill in zip(ranked, candidates, strict=True):
            if (
                preferred_risk is not None
                and risk_order[skill.manifest.risk] > risk_order[preferred_risk]
            ):
                rejected.append(skill)
                policy_decisions[skill.manifest.name] = "risk_too_high"
                continue
            selected_results.append((result, skill))
            policy_decisions[skill.manifest.name] = "runtime_gate"

        rejected.extend(skill for _, skill in selected_results[5:])
        selected_results = selected_results[:5]
        selection.selected_skills = [skill for _, skill in selected_results]
        selection.rejected_skills = rejected
        selection.policy_decisions = policy_decisions
        selection.reason = (
            f"Selected {len(selected_results)} skills from {len(candidates)} candidates"
        )
        selection.confidence = (
            sum(result.final_score for result, _ in selected_results)
            / len(selected_results)
            if selected_results
            else 0.0
        )

        # Log selection
        for skill in selection.selected_skills:
            await self._log_skill_selected(skill.manifest.name, selection.reason)

        logger.info(
            "skill_selection_complete",
            selected=len(selection.selected_skills),
            rejected=len(rejected),
        )
        return selection

    async def _log_candidates_found(self, goal: str, candidates: list[Skill]) -> None:
        """Log candidate finding (via task ledger if task_id available)."""
        logger.info("skill_candidates_found", goal=goal[:50], count=len(candidates))

    async def _log_skill_selected(self, skill_name: str, reason: str) -> None:
        """Log skill selection."""
        logger.info("skill_selected", skill=skill_name, reason=reason)

    async def select_for_task(
        self,
        task_id: str,
        goal: str,
        requested_capabilities: list[Capability] | None = None,
    ) -> SkillSelection:
        """Select skills and associate with a task."""
        selection = await self.select(goal, requested_capabilities)
        selection.task_id = task_id

        # Persist skill selection
        if selection.selected_skills:
            await self._persist_selection(task_id, selection)

        return selection

    async def _persist_selection(self, task_id: str, selection: SkillSelection) -> None:
        """Persist skill selection to task."""
        skill_names = [s.manifest.name for s in selection.selected_skills]
        await db.execute(
            "UPDATE tasks SET selected_skills = ? WHERE id = ?",
            (json.dumps(skill_names), task_id),
        )
        logger.info("skill_selection_persisted", task_id=task_id, skills=skill_names)


# Global selector instance
_selector: SkillSelector | None = None


def get_skill_selector(fabric: SkillFabric | None = None) -> SkillSelector:
    """Get the global skill selector instance."""
    global _selector
    if _selector is None or fabric is not None:
        _selector = SkillSelector(fabric)
    return _selector
