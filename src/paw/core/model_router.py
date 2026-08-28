"""
PAW Core — Model Router (Phase 4)

Selects the best model for a task based on role, capability fit, cost,
latency, complexity, and privacy requirements.

Per prompt spec: Model Router and Capability Router are completely separate.
Model Router selects the best model; Capability Router selects the best executor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .logging import get_logger
from .models import (
    ModelCapability,
    ModelManifest,
    ModelRole,
    ModelSelection,
)
from .storage import db

logger = get_logger(__name__)


# --- Model Scoring ---

@dataclass
class ModelScore:
    """Score for a model candidate in the routing decision."""
    model_name: str = ""
    score: float = 0.0
    capability_fit: float = 0.0
    complexity_fit: float = 0.0
    privacy_fit: float = 0.0
    cost_fit: float = 0.0
    latency_fit: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "score": self.score,
            "capability_fit": self.capability_fit,
            "complexity_fit": self.complexity_fit,
            "privacy_fit": self.privacy_fit,
            "cost_fit": self.cost_fit,
            "latency_fit": self.latency_fit,
            "reason": self.reason,
        }


class ModelScorer:
    """Scores models based on multiple dimensions per prompt spec."""

    def score(
        self,
        manifest: ModelManifest,
        role: str = "fast",
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
        prefer_cheap: bool = True,
    ) -> ModelScore:
        """Score a model across all dimensions."""
        capability_fit = self._score_capability(manifest, role)
        complexity_fit = self._score_complexity(manifest, complexity)
        privacy_fit = self._score_privacy(manifest, privacy_required)
        cost_fit = self._score_cost(manifest, prefer_cheap)
        latency_fit = self._score_latency(manifest, context_size)

        # Weighted composite score
        weights = {
            "capability": 0.35,
            "complexity": 0.15,
            "privacy": 0.20,
            "cost": 0.15,
            "latency": 0.15,
        }

        total = (
            capability_fit * weights["capability"]
            + complexity_fit * weights["complexity"]
            + privacy_fit * weights["privacy"]
            + cost_fit * weights["cost"]
            + latency_fit * weights["latency"]
        )

        score = min(max(total, 0.0), 1.0)

        reason = self._generate_reason(manifest, role, score, capability_fit, complexity_fit, privacy_fit, cost_fit, latency_fit)

        return ModelScore(
            model_name=manifest.name,
            score=score,
            capability_fit=capability_fit,
            complexity_fit=complexity_fit,
            privacy_fit=privacy_fit,
            cost_fit=cost_fit,
            latency_fit=latency_fit,
            reason=reason,
        )

    def _score_capability(self, manifest: ModelManifest, role: str) -> float:
        """Score capability fit: role match + model capability scores."""
        score = 0.0

        # Role match (primary factor)
        if role in manifest.roles:
            score += 0.4
        elif ModelRole.FALLBACK.value in manifest.roles:
            score += 0.2

        # Model capability match
        if manifest.model_capabilities:
            cap_scores = list(manifest.model_capabilities.values())
            if cap_scores:
                avg_cap = sum(cap_scores) / len(cap_scores)
                score += (avg_cap / 10.0) * 0.3  # normalize to 0-1

        # Role-specific bonus
        if (role == ModelRole.REASONING.value and "reasoning" in manifest.roles) or (role == ModelRole.CODING.value and "coding" in manifest.roles) or (role == ModelRole.TOOLS.value and "tools" in manifest.roles):
            score += 0.2

        return min(score, 1.0)

    def _score_complexity(self, manifest: ModelManifest, complexity: str) -> float:
        """Score complexity fit."""
        score = 0.5  # neutral

        if complexity == "low":
            # Simple tasks don't need powerful models
            if manifest.latency_tier == "low":
                score = 0.8
            elif manifest.latency_tier == "medium":
                score = 0.6
            else:
                score = 0.4
        elif complexity == "medium":
            score = 0.6
            if manifest.max_context_tokens >= 8000:
                score += 0.1
        elif complexity == "high":
            # Complex tasks need powerful models
            score = 0.3
            if manifest.max_context_tokens >= 32000:
                score += 0.2
            if "reasoning" in manifest.roles or "coding" in manifest.roles:
                score += 0.2
            if manifest.latency_tier != "low":
                score += 0.1

        return min(score, 1.0)

    def _score_privacy(self, manifest: ModelManifest, privacy_required: bool) -> float:
        """Score privacy fit."""
        if not privacy_required:
            return 0.7  # neutral when no privacy needed

        # Local/private models score higher
        provider = manifest.provider.lower()
        if provider in ("local", "ollama", "vllm", "offline"):
            return 1.0
        elif provider == "direct":
            return 0.8
        elif provider == "openrouter":
            return 0.4
        else:
            return 0.3

    def _score_cost(self, manifest: ModelManifest, prefer_cheap: bool) -> float:
        """Score cost fit."""
        if not prefer_cheap:
            return 0.7  # neutral when cost doesn't matter

        cost = manifest.cost.get("compute", "medium")
        if cost == "low":
            return 0.9
        elif cost == "medium":
            return 0.6
        elif cost == "high":
            return 0.3
        else:
            return 0.5

    def _score_latency(self, manifest: ModelManifest, context_size: int) -> float:
        """Score latency fit."""
        tier = manifest.latency_tier
        if tier == "low":
            base = 0.9
        elif tier == "medium":
            base = 0.6
        else:
            base = 0.4

        # Penalize if context exceeds capacity
        if context_size > manifest.max_context_tokens:
            base -= 0.3
        elif context_size > manifest.max_context_tokens * 0.8:
            base -= 0.1

        return min(max(base, 0.0), 1.0)

    def _generate_reason(
        self,
        manifest: ModelManifest,
        role: str,
        score: float,
        capability_fit: float,
        complexity_fit: float,
        privacy_fit: float,
        cost_fit: float,
        latency_fit: float,
    ) -> str:
        """Generate human-readable routing reason."""
        parts = []
        parts.append(f"{manifest.name}")
        parts.append(f"role={role}")
        parts.append(f"score={score:.2f}")
        parts.append(f"cap={capability_fit:.2f}")
        parts.append(f"complexity={complexity_fit:.2f}")
        parts.append(f"privacy={privacy_fit:.2f}")
        parts.append(f"cost={cost_fit:.2f}")
        parts.append(f"latency={latency_fit:.2f}")
        return " | ".join(parts)


# --- Model Registry ---

class ModelRegistry:
    """Registry of available models with full CRUD and query support."""

    def __init__(self):
        self._models: dict[str, ModelManifest] = {}
        self._scorer = ModelScorer()

    def register(self, manifest: ModelManifest) -> None:
        """Register a model."""
        self._models[manifest.name] = manifest
        logger.info("model_registered", name=manifest.name, provider=manifest.provider)

    def unregister(self, name: str) -> bool:
        """Remove a model from registry."""
        if name in self._models:
            del self._models[name]
            logger.info("model_unregistered", name=name)
            return True
        return False

    def get(self, name: str) -> ModelManifest | None:
        """Get a model manifest by name."""
        return self._models.get(name)

    def list(self) -> list[ModelManifest]:
        """List all registered models."""
        return list(self._models.values())

    def list_by_role(self, role: str) -> list[ModelManifest]:
        """List models supporting a specific role."""
        return [
            m for m in self._models.values()
            if role in m.roles and m.enabled
        ]

    def list_enabled(self) -> list[ModelManifest]:
        """List all enabled models."""
        return [m for m in self._models.values() if m.enabled]

    def find_for_role(self, role: str, exclude: list[str] | None = None) -> list[ModelManifest]:
        """Find models for a role, sorted by cost preference."""
        exclude = exclude or []
        candidates = [
            m for m in self._models.values()
            if role in m.roles and m.enabled and m.name not in exclude
        ]
        tier_order = {"low": 0, "medium": 1, "high": 2}
        candidates.sort(key=lambda m: tier_order.get(m.latency_tier, 1))
        return candidates

    def find_by_capability(self, capability: str) -> list[ModelManifest]:
        """Find models supporting a specific capability."""
        return [
            m for m in self._models.values()
            if capability in m.model_capabilities
            and m.enabled
            and m.model_capabilities[capability] >= 5.0
        ]

    def find_best_for_task(
        self,
        role: str = "fast",
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
        prefer_cheap: bool = True,
        exclude: list[str] | None = None,
    ) -> list[tuple[ModelManifest, ModelScore]]:
        """Find and score all models for a task."""
        candidates = self.find_for_role(role, exclude)
        scored: list[tuple[ModelManifest, ModelScore]] = []

        for manifest in candidates:
            score = self._scorer.score(
                manifest, role, context_size, complexity, privacy_required, prefer_cheap
            )
            scored.append((manifest, score))

        scored.sort(key=lambda x: x[1].score, reverse=True)
        return scored

    def fallback_chain(self, role: str) -> list[str]:
        """Build a fallback chain for a role."""
        models = self.find_for_role(role)
        return [m.name for m in models]

    async def load_from_db(self) -> int:
        """Load models from database. Returns count loaded."""
        rows = await db.fetchall("SELECT * FROM model_registry WHERE enabled = 1")
        count = 0
        for row in dict(rows) if rows else []:
            manifest = ModelManifest(
                name=row["name"],
                provider=row.get("provider", ""),
                roles=row.get("roles", []) if row.get("roles") else [],
                model_capabilities=row.get("model_capabilities", {}) if row.get("model_capabilities") else {},
                cost=row.get("cost", {}) if row.get("cost") else {},
                features=row.get("features", {}) if row.get("features") else {},
                max_context_tokens=row.get("max_context_tokens", 128000),
                latency_tier=row.get("latency_tier", "medium"),
                enabled=bool(row.get("enabled", True)),
            )
            self.register(manifest)
            count += 1
        return count

    def register_defaults(self) -> None:
        """Register default models if registry is empty."""
        if self._models:
            return

        defaults = [
            ModelManifest(
                name="local-fast",
                provider="local",
                roles=["fast", "tools"],
                model_capabilities={
                    ModelCapability.REASONING: 6.0,
                    ModelCapability.TOOL_CALLING: 7.0,
                    ModelCapability.STRUCTURED_OUTPUT: 8.0,
                    ModelCapability.LONG_CONTEXT: 5.0,
                },
                cost={"compute": "low", "monetary": "free"},
                features={"resumable": True, "streaming": True, "subagents": False},
                max_context_tokens=8000,
                latency_tier="low",
                enabled=True,
            ),
            ModelManifest(
                name="local-reasoning",
                provider="local",
                roles=["reasoning", "coding"],
                model_capabilities={
                    ModelCapability.REASONING: 9.0,
                    ModelCapability.CODING: 9.0,
                    ModelCapability.TOOL_CALLING: 8.0,
                    ModelCapability.STRUCTURED_OUTPUT: 8.0,
                    ModelCapability.LONG_CONTEXT: 8.0,
                    ModelCapability.PLANNING: 8.0,
                },
                cost={"compute": "low", "monetary": "free"},
                features={"resumable": True, "streaming": True, "subagents": True},
                max_context_tokens=32000,
                latency_tier="medium",
                enabled=True,
            ),
            ModelManifest(
                name="local-embedding",
                provider="local",
                roles=["embedding"],
                model_capabilities={
                    ModelCapability.EMBEDDING: 9.0,
                    ModelCapability.CLASSIFICATION: 7.0,
                    ModelCapability.EXTRACTION: 6.0,
                },
                cost={"compute": "low", "monetary": "free"},
                features={"resumable": False, "streaming": False, "subagents": False},
                max_context_tokens=2048,
                latency_tier="low",
                enabled=True,
            ),
        ]
        for m in defaults:
            self.register(m)
        logger.info("default_models_registered", count=len(defaults))


# --- Model Router ---

class ModelRouter:
    """Selects the best model for a task based on multi-dimensional scoring."""

    def __init__(self, registry: ModelRegistry | None = None):
        self.registry = registry or ModelRegistry()
        self._custom_registry = registry is not None
        self._selections: dict[str, ModelSelection] = {}
        self._scores: dict[str, list[ModelScore]] = {}
        self._scorer = ModelScorer()

    async def route(
        self,
        task_id: str,
        goal: str,
        role: str = "fast",
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
        prefer_cheap: bool = True,
    ) -> ModelSelection:
        """Route a task to the best model using multi-dimensional scoring."""
        # Only register defaults if using default registry
        if not self._custom_registry:
            self.registry.register_defaults()

        scored = self.registry.find_best_for_task(
            role, context_size, complexity, privacy_required, prefer_cheap
        )

        if not scored:
            logger.warning("no_model_for_role", role=role)
            return ModelSelection(
                model_name="",
                reason=f"No model available for role: {role}",
                role=role,
            )

        # Store all scores for this task
        self._scores[task_id] = [s for _, s in scored]

        best_manifest, best_score = scored[0]
        fallback_chain = self.registry.fallback_chain(role)

        selection = ModelSelection(
            model_name=best_manifest.name,
            model_manifest=best_manifest,
            role=role,
            reason=best_score.reason,
            fallback_chain=fallback_chain,
            score=best_score.score,
        )

        self._selections[task_id] = selection

        # Persist to DB
        await self.persist_selection(task_id, selection)

        logger.info("model_routed", task_id=task_id, model=best_manifest.name, score=best_score.score)
        return selection

    async def route_with_explain(
        self,
        task_id: str,
        goal: str,
        role: str = "fast",
        context_size: int = 0,
        complexity: str = "medium",
        privacy_required: bool = False,
        prefer_cheap: bool = True,
    ) -> tuple[ModelSelection, list[ModelScore]]:
        """Route with full explainability (all scores returned)."""
        self.registry.register_defaults()

        scored = self.registry.find_best_for_task(
            role, context_size, complexity, privacy_required, prefer_cheap
        )

        self._scores[task_id] = [s for _, s in scored]

        if not scored:
            return ModelSelection(model_name="", reason="No models available", role=role), []

        best_manifest, best_score = scored[0]
        fallback_chain = self.registry.fallback_chain(role)

        selection = ModelSelection(
            model_name=best_manifest.name,
            model_manifest=best_manifest,
            role=role,
            reason=best_score.reason,
            fallback_chain=fallback_chain,
            score=best_score.score,
        )

        self._selections[task_id] = selection
        await self.persist_selection(task_id, selection)

        return selection, [s for _, s in scored]

    def get_scores(self, task_id: str) -> list[ModelScore] | None:
        """Retrieve scores for a task."""
        return self._scores.get(task_id)

    def get_selection(self, task_id: str) -> ModelSelection | None:
        """Retrieve a previous selection."""
        return self._selections.get(task_id)

    async def persist_selection(self, task_id: str, selection: ModelSelection) -> None:
        """Persist model selection to DB."""
        await db.execute(
            """
            INSERT OR REPLACE INTO model_selections (task_id, model_name, role, reason, score, fallback_chain, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                selection.model_name,
                selection.role,
                selection.reason,
                selection.score,
                json.dumps(selection.fallback_chain),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    async def get_routing_history(self, task_id: str) -> list[dict]:
        """Get routing history for a task."""
        rows = await db.fetchall(
            "SELECT * FROM model_selections WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        )
        return [dict(r) for r in rows]


# Initialize model_selections table
async def ensure_model_selections_table() -> None:
    """Ensure model_selections table exists."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS model_selections (
            task_id TEXT,
            model_name TEXT NOT NULL,
            role TEXT NOT NULL,
            reason TEXT,
            score REAL NOT NULL DEFAULT 0.0,
            fallback_chain TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (task_id, role, created_at)
        )
    """)


# Global instances
_model_registry: ModelRegistry | None = None
_model_router: ModelRouter | None = None


def get_model_registry() -> ModelRegistry:
    """Get the global model registry."""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
        _model_registry.register_defaults()
    return _model_registry


def get_model_router() -> ModelRouter:
    """Get the global model router."""
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router
