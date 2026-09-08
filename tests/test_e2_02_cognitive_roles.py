"""E2-02 — Canonical cognitive roles for ModelManifest (D0).

Verifies that PAW defines the minimum cognitive roles as typed constants
and that every canonical role has a documented definition. The set of
keys in CANONICAL_MODEL_ROLES must match ModelRole exactly.
"""

import pytest
from paw.core.models import (
    CANONICAL_MODEL_ROLES,
    ModelRole,
    ModelManifest,
    RoleDefinition,
)


def test_model_role_enum_has_seven_values():
    """E0 cases use fast/reasoning/coding/tools/vision/embedding; fallback is catch-all."""
    assert len(list(ModelRole)) == 7
    assert ModelRole.FAST == "fast"
    assert ModelRole.REASONING == "reasoning"
    assert ModelRole.CODING == "coding"
    assert ModelRole.TOOLS == "tools"
    assert ModelRole.VISION == "vision"
    assert ModelRole.EMBEDDING == "embedding"
    assert ModelRole.FALLBACK == "fallback"


def test_canonical_roles_keys_match_enum():
    """Every ModelRole value must have a RoleDefinition, and vice versa."""
    enum_values = {r.value for r in ModelRole}
    canonical_keys = set(CANONICAL_MODEL_ROLES.keys())
    assert canonical_keys == enum_values


def test_role_definition_has_description():
    """Every role definition must carry a human-readable description."""
    for role, defn in CANONICAL_MODEL_ROLES.items():
        assert isinstance(defn, RoleDefinition)
        assert defn.role == role
        assert defn.description, f"Role {role} missing description"


def test_preferred_by_contains_scenario_tags():
    """Each role should declare which scenario tags prefer it."""
    for role, defn in CANONICAL_MODEL_ROLES.items():
        assert isinstance(defn.preferred_by, list)
        assert len(defn.preferred_by) > 0, f"Role {role} has no preferred_by tags"


def test_reasoning_role_requires_evidence():
    """REASONING role must flag requires_evidence since it produces traces."""
    rd = CANONICAL_MODEL_ROLES[ModelRole.REASONING]
    assert rd.requires_evidence is True
    assert rd.uncertainty_handled is True


def test_embedding_role_handles_uncertainty():
    """EMBEDDING role should support uncertainty (confidence in vectors)."""
    rd = CANONICAL_MODEL_ROLES[ModelRole.EMBEDDING]
    assert rd.uncertainty_handled is True


def test_model_manifest_roles_can_use_canonical():
    """ModelManifest should accept canonical role strings."""
    manifest = ModelManifest(
        name="test-model",
        provider="local",
        roles=["fast", "tools", "reasoning"],
    )
    assert manifest.supports_role("fast")
    assert manifest.supports_role("tools")
    assert manifest.supports_role("reasoning")
    assert not manifest.supports_role("vision")


def test_canonical_roles_are_stable():
    """The set of canonical roles must not change without a deliberate review."""
    expected = {"fast", "reasoning", "coding", "tools", "vision", "embedding", "fallback"}
    assert set(CANONICAL_MODEL_ROLES.keys()) == expected
