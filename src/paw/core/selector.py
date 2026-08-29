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
from .policy import get_policy_guard
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
    """Selects appropriate skills for a task."""

    def __init__(self, fabric: SkillFabric | None = None):
        self.fabric = fabric or SkillFabric(__import__("pathlib").Path(__file__).parent.parent / "skills")
        self.policy_guard = get_policy_guard()

    async def select(
        self,
        goal: str,
        requested_capabilities: list[Capability] | None = None,
        preferred_risk: SkillRisk | None = None,
    ) -> SkillSelection:
        """Select the best skills for a task."""
        selection = SkillSelection(task_id="", reason="", confidence=0.0)

        # 1. Find candidate skills
        candidates = self.fabric.find_candidates(goal, max_results=20)
        await self._log_candidates_found(goal, candidates)

        if not candidates:
            selection.reason = "No candidate skills found for this goal"
            return selection

        # 2. Filter by capability requirements
        cap_set = set(requested_capabilities) if requested_capabilities else set()
        filtered: list[Skill] = []
        for candidate in candidates:
            # Check if skill's capabilities overlap with requested
            if not cap_set or any(c in cap_set for c in candidate.capabilities):
                filtered.append(candidate)

        if not filtered:
            selection.reason = "No skills match the requested capabilities"
            return selection

        # 3. Apply policy guard
        selected: list[Skill] = []
        rejected: list[Skill] = []
        policy_decisions: dict[str, str] = {}

        for skill in filtered:
            # Check skill risk level
            if preferred_risk and skill.manifest.risk.value > preferred_risk.value:
                rejected.append(skill)
                policy_decisions[skill.manifest.name] = "risk_too_high"
                continue

            # Check policy for skill's capabilities
            decision = "allow"
            if skill.manifest.capabilities:
                for cap in skill.manifest.capabilities:
                    guard_decision = await self.policy_guard.check(cap)
                    if guard_decision.value == "deny":
                        decision = "deny"
                        break
                    elif guard_decision.value == "ask":
                        decision = "ask"

            policy_decisions[skill.manifest.name] = decision

            if decision == "deny":
                rejected.append(skill)
            else:
                selected.append(skill)

        # 4. Sort by confidence (risk + trigger match)
        selected.sort(key=lambda s: self._confidence_score(s, goal))

        # 5. Limit selections
        if len(selected) > 5:
            rejected.extend(selected[5:])
            selected = selected[:5]

        selection.selected_skills = selected
        selection.rejected_skills = rejected
        selection.policy_decisions = policy_decisions
        selection.reason = f"Selected {len(selected)} skills from {len(candidates)} candidates"
        selection.confidence = self._overall_confidence(selected, goal)

        # Log selection
        for skill in selected:
            await self._log_skill_selected(skill.manifest.name, selection.reason)

        logger.info("skill_selection_complete", selected=len(selected), rejected=len(rejected))
        return selection

    def _confidence_score(self, skill: Skill, goal: str) -> float:
        """Calculate confidence score for a skill."""
        score = 0.5

        # Trigger match bonus
        if skill.matches_query(goal):
            score += 0.3

        # Risk bonus
        risk_scores = {"low": 0.1, "medium": 0.0, "high": -0.2}
        score += risk_scores.get(skill.manifest.risk.value, 0.0)

        # Capability match bonus
        if skill.manifest.capabilities:
            score += 0.1

        return min(score, 1.0)

    def _overall_confidence(self, selected: list[Skill], goal: str) -> float:
        """Calculate overall confidence for the selection."""
        if not selected:
            return 0.0
        total = sum(self._confidence_score(s, goal) for s in selected)
        return total / len(selected)

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
