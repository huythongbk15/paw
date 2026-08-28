"""
PAW Core — Intelligent Planner (Phase 3)

LLM-style goal decomposition using structured reasoning patterns.
No external API calls — local-first structured reasoning.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .logging import get_logger
from .storage import db

logger = get_logger(__name__)


@dataclass
class DecompositionStep:
    """A single step in goal decomposition."""
    id: str = ""
    goal: str = ""
    reasoning: str = ""
    sub_goals: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    estimated_effort: str = "medium"  # 'low', 'medium', 'high'
    order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "reasoning": self.reasoning,
            "sub_goals": self.sub_goals,
            "required_capabilities": self.required_capabilities,
            "estimated_effort": self.estimated_effort,
            "order": self.order,
        }


@dataclass
class DecompositionResult:
    """Result of intelligent goal decomposition."""
    original_goal: str = ""
    steps: list[DecompositionStep] = field(default_factory=list)
    confidence: float = 0.0
    reasoning_summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_goal": self.original_goal,
            "steps": [s.to_dict() for s in self.steps],
            "confidence": self.confidence,
            "reasoning_summary": self.reasoning_summary,
            "created_at": self.created_at.isoformat(),
        }


class IntentClassifier:
    """Classify user intent into categories for decomposition."""

    INTENT_PATTERNS: dict[str, list[str]] = {
        "calculation": [
            "tính", "calculate", "compute", "cộng", "trừ", "nhân", "chia",
            "sum", "total", "result", "con số", "số", "math", "equation",
        ],
        "search": [
            "tìm", "search", "tìm kiếm", "look for", "find", "search",
            "information", "info", "dữ liệu", "data",
        ],
        "write": [
            "viết", "write", "code", "lập trình", "create", "gen", "tạo",
            "file", "document", "script", "function", "program",
        ],
        "analyze": [
            "phân tích", "analyze", "review", "exam", "kiểm tra", "evaluate",
            "tỉnh", "understand", "explain", "what is", "how does",
        ],
        "summarize": [
            "tóm tắt", "summary", "summarize", "tổng hợp", "gộp", "compress",
            "rút gọn", "brief", "digest",
        ],
        "translate": [
            "dịch", "translate", "chuyển", "convert", "thành", "to",
            "from", "language", "ngôn ngữ",
        ],
        "plan": [
            "lập kế hoạch", "plan", "kế hoạch", "organize", "schedule",
            "bước", "step", "timeline", "thời gian", "quy trình",
        ],
        "decision": [
            "nên", "should", "choosing", "lựa chọn", "chọn", "decide",
            "best", "optimal", "phù hợp", "good", "better",
        ],
    }

    def classify(self, goal: str) -> list[str]:
        """Classify goal into intent categories."""
        goal_lower = goal.lower()
        intents = []
        for intent, keywords in self.INTENT_PATTERNS.items():
            if any(kw in goal_lower for kw in keywords):
                intents.append(intent)
        if not intents:
            intents = ["general"]
        return intents


class StructuredReasoner:
    """Perform structured reasoning for goal decomposition."""

    def decompose(self, goal: str) -> DecompositionResult:
        """Decompose a goal into structured reasoning steps."""
        classifier = IntentClassifier()
        intents = classifier.classify(goal)

        steps = self._generate_steps(goal, intents)
        confidence = self._calculate_confidence(goal, steps)
        reasoning_summary = self._generate_summary(goal, intents, steps)

        return DecompositionResult(
            original_goal=goal,
            steps=steps,
            confidence=confidence,
            reasoning_summary=reasoning_summary,
        )

    def _generate_steps(self, goal: str, intents: list[str]) -> list[DecompositionStep]:
        """Generate decomposition steps based on intent."""
        steps: list[DecompositionStep] = []
        goal_words = goal.lower().split()

        if "calculation" in intents:
            steps = self._decompose_calculation(goal)
        elif "search" in intents:
            steps = self._decompose_search(goal)
        elif "write" in intents:
            steps = self._decompose_write(goal)
        elif "analyze" in intents:
            steps = self._decompose_analyze(goal)
        elif "summarize" in intents:
            steps = self._decompose_summarize(goal)
        elif "plan" in intents:
            steps = self._decompose_plan(goal)
        elif "translate" in intents:
            steps = self._decompose_translate(goal)
        elif "decision" in intents:
            steps = self._decompose_decision(goal)
        else:
            steps = self._decompose_general(goal)

        # Add ordering
        for i, step in enumerate(steps):
            step.order = i
            if not step.id:
                step.id = uuid.uuid4().hex[:16]

        return steps

    def _decompose_calculation(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Parse and understand the calculation request",
                reasoning="Identify the mathematical operation and operands",
                sub_goals=[goal],
                required_capabilities=["shell.execute"],
                estimated_effort="low",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Execute the calculation",
                reasoning="Perform the mathematical operation",
                sub_goals=["Compute result"],
                required_capabilities=["shell.execute"],
                estimated_effort="low",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Return the result",
                reasoning="Format and present the calculation result",
                sub_goals=["Format output"],
                required_capabilities=[],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _decompose_search(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Identify search query and sources",
                reasoning="Extract keywords and determine search sources",
                sub_goals=[goal],
                required_capabilities=["network.http"],
                estimated_effort="low",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Execute the search",
                reasoning="Perform the search operation",
                sub_goals=["Search for information"],
                required_capabilities=["network.http"],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Process and return results",
                reasoning="Filter and format search results",
                sub_goals=["Process results"],
                required_capabilities=[],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _decompose_write(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Understand the writing requirements",
                reasoning="Determine what type of content to generate",
                sub_goals=[goal],
                required_capabilities=["filesystem.write"],
                estimated_effort="low",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Generate the content",
                reasoning="Create the requested content",
                sub_goals=["Generate content"],
                required_capabilities=["filesystem.write"],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Save and verify",
                reasoning="Write to file and verify",
                sub_goals=["Save file"],
                required_capabilities=["filesystem.write", "filesystem.read"],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _decompose_analyze(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Gather information for analysis",
                reasoning="Collect relevant data and context",
                sub_goals=[goal],
                required_capabilities=["filesystem.read", "network.http"],
                estimated_effort="medium",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Perform analysis",
                reasoning="Apply analytical methods",
                sub_goals=["Analyze data"],
                required_capabilities=["filesystem.read"],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Present findings",
                reasoning="Format and present analysis results",
                sub_goals=["Format output"],
                required_capabilities=[],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _decompose_summarize(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Read and understand the source material",
                reasoning="Gather content to summarize",
                sub_goals=[goal],
                required_capabilities=["filesystem.read"],
                estimated_effort="medium",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Extract key points",
                reasoning="Identify main themes and important details",
                sub_goals=["Extract key points"],
                required_capabilities=["filesystem.read"],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Generate summary",
                reasoning="Create concise summary",
                sub_goals=["Generate summary"],
                required_capabilities=["filesystem.write"],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _decompose_plan(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Define the plan scope and objectives",
                reasoning="Understand what the plan should cover",
                sub_goals=[goal],
                required_capabilities=[],
                estimated_effort="low",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Create step-by-step plan",
                reasoning="Break down into actionable steps",
                sub_goals=["Define steps"],
                required_capabilities=[],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Add timeline and dependencies",
                reasoning="Schedule steps and identify dependencies",
                sub_goals=["Add schedule"],
                required_capabilities=[],
                estimated_effort="medium",
                order=2,
            ),
        ]

    def _decompose_translate(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Identify source and target languages",
                reasoning="Determine languages for translation",
                sub_goals=[goal],
                required_capabilities=[],
                estimated_effort="low",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Perform translation",
                reasoning="Translate content",
                sub_goals=["Translate"],
                required_capabilities=[],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Verify and format output",
                reasoning="Review and format translated content",
                sub_goals=["Verify"],
                required_capabilities=[],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _decompose_decision(self, goal: str) -> list[DecompositionStep]:
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Identify options and criteria",
                reasoning="Determine what options exist and evaluation criteria",
                sub_goals=[goal],
                required_capabilities=[],
                estimated_effort="low",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Evaluate options",
                reasoning="Compare options against criteria",
                sub_goals=["Evaluate"],
                required_capabilities=[],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Recommend best option",
                reasoning="Select and justify the best choice",
                sub_goals=["Recommend"],
                required_capabilities=[],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _decompose_general(self, goal: str) -> list[DecompositionStep]:
        # Simple general decomposition
        words = goal.split()
        if len(words) <= 5:
            return [
                DecompositionStep(
                    id=uuid.uuid4().hex[:16],
                    goal=goal,
                    reasoning="Simple goal, direct execution",
                    sub_goals=[goal],
                    required_capabilities=[],
                    estimated_effort="low",
                    order=0,
                )
            ]
        # Split into understanding, execution, and output
        return [
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Understand the request",
                reasoning="Analyze the goal and requirements",
                sub_goals=[goal],
                required_capabilities=[],
                estimated_effort="low",
                order=0,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Execute the main task",
                reasoning="Perform the core action",
                sub_goals=["Execute"],
                required_capabilities=[],
                estimated_effort="medium",
                order=1,
            ),
            DecompositionStep(
                id=uuid.uuid4().hex[:16],
                goal="Format and return result",
                reasoning="Present the output",
                sub_goals=["Format"],
                required_capabilities=[],
                estimated_effort="low",
                order=2,
            ),
        ]

    def _calculate_confidence(self, goal: str, steps: list[DecompositionStep]) -> float:
        """Calculate confidence in the decomposition."""
        if not steps:
            return 0.0
        base = 0.5
        # More steps = more confident in decomposition
        step_bonus = min(len(steps) * 0.1, 0.3)
        # Has sub-goals = more confident
        has_subgoals = any(s.sub_goals for s in steps)
        subgoal_bonus = 0.1 if has_subgoals else 0.0
        return min(base + step_bonus + subgoal_bonus, 1.0)

    def _generate_summary(self, goal: str, intents: list[str], steps: list[DecompositionStep]) -> str:
        """Generate a human-readable reasoning summary."""
        intent_str = ", ".join(intents) if intents else "general"
        return f"Decomposed '{goal}' into {len(steps)} steps based on {intent_str} intent"


class IntelligentPlanner:
    """Intelligent planner with structured reasoning for goal decomposition."""

    def __init__(self):
        self.reasoner = StructuredReasoner()
        self.classifier = IntentClassifier()

    async def plan(self, goal: str, session_id: str, project_id: str | None = None) -> dict:
        """Create an intelligent plan from a goal using structured reasoning."""
        # 1. Classify intent
        intents = self.classifier.classify(goal)

        # 2. Decompose using structured reasoning
        decomposition = self.reasoner.decompose(goal)

        # 3. Convert to task nodes
        nodes = self._decomposition_to_nodes(decomposition, session_id)

        # 4. Build result
        result = {
            "goal": goal,
            "session_id": session_id,
            "project_id": project_id,
            "intents": intents,
            "decomposition": decomposition.to_dict(),
            "nodes": [n.to_dict() for n in nodes],
            "confidence": decomposition.confidence,
            "reasoning_summary": decomposition.reasoning_summary,
        }

        logger.info("intelligent_plan_created", goal=goal[:50], steps=len(nodes))
        return result

    def _decomposition_to_nodes(self, decomposition: DecompositionResult, session_id: str) -> list:
        """Convert decomposition steps to task nodes."""
        nodes = []
        for step in decomposition.steps:
            nodes.append(DecompositionStep(
                id=step.id,
                goal=step.goal,
                reasoning=step.reasoning,
                sub_goals=step.sub_goals,
                required_capabilities=step.required_capabilities,
                estimated_effort=step.estimated_effort,
                order=step.order,
            ))
        return nodes

    async def plan_and_save(self, goal: str, session_id: str, project_id: str | None = None) -> dict:
        """Create plan and save to database."""
        result = await self.plan(goal, session_id, project_id)

        # Save to DB
        await self._save_plan(result, session_id)

        return result

    async def _save_plan(self, result: dict, session_id: str) -> None:
        """Save intelligent plan to database."""
        plan_id = uuid.uuid4().hex[:16]

        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO plans (id, task_id, session_id, goal, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plan_id, "", session_id, result["goal"],
                 datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )

            # Save nodes
            for node in result["nodes"]:
                await conn.execute(
                    """
                    INSERT INTO task_nodes (
                        id, task_id, goal, dependencies, skills,
                        context_requirements, capability_requirements,
                        policy_requirements, executor, model, result,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node["id"],
                        "",
                        node["goal"],
                        json.dumps([]),
                        json.dumps([]),
                        json.dumps({}),
                        json.dumps(node.get("required_capabilities", [])),
                        json.dumps([]),
                        None,
                        None,
                        None,
                        "pending",
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

    async def get_reasoning(self, goal: str) -> DecompositionResult:
        """Get reasoning for a goal without creating a full plan."""
        return self.reasoner.decompose(goal)


# Initialize plans table if needed
async def ensure_intelligent_planner_table() -> None:
    """Ensure tables exist."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS intelligent_plans (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            goal TEXT NOT NULL,
            intents TEXT, -- JSON
            confidence REAL,
            reasoning_summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)