"""E2-02 — minimum cognitive roles for the engineering loop (D0)."""

from types import MappingProxyType

from paw.core.models import ModelManifest, ModelRole
from paw.core.reasoning_contracts import CANONICAL_ROLE_CONTRACTS


EXPECTED_COGNITIVE_ROLES = {
    ModelRole.FAST,
    ModelRole.REASONING,
    ModelRole.CODING,
    ModelRole.TOOLS,
}


def test_minimum_cognitive_roles_are_existing_router_roles() -> None:
    assert set(CANONICAL_ROLE_CONTRACTS) == EXPECTED_COGNITIVE_ROLES
    assert set(CANONICAL_ROLE_CONTRACTS).issubset(set(ModelRole))


def test_modalities_and_fallback_are_not_extra_cognitive_roles() -> None:
    assert ModelRole.VISION not in CANONICAL_ROLE_CONTRACTS
    assert ModelRole.EMBEDDING not in CANONICAL_ROLE_CONTRACTS
    assert ModelRole.FALLBACK not in CANONICAL_ROLE_CONTRACTS


def test_role_registry_is_immutable() -> None:
    assert isinstance(CANONICAL_ROLE_CONTRACTS, MappingProxyType)


def test_every_cognitive_role_has_engineering_scenarios() -> None:
    for role, contract in CANONICAL_ROLE_CONTRACTS.items():
        assert contract.role is role
        assert contract.description
        assert contract.scenario_tags


def test_historical_manifest_roles_remain_compatible() -> None:
    manifest = ModelManifest(
        name="test-model",
        provider="local",
        roles=["fast", "tools", "reasoning", "embedding"],
    )
    assert manifest.supports_role(ModelRole.FAST)
    assert manifest.supports_role(ModelRole.TOOLS)
    assert manifest.supports_role(ModelRole.REASONING)
    assert manifest.supports_role(ModelRole.EMBEDDING)


def test_reasoning_contract_covers_research_and_architecture() -> None:
    tags = CANONICAL_ROLE_CONTRACTS[ModelRole.REASONING].scenario_tags
    assert {"research", "diagnosis", "architecture"}.issubset(tags)


def test_coding_contract_covers_implementation_and_review() -> None:
    tags = CANONICAL_ROLE_CONTRACTS[ModelRole.CODING].scenario_tags
    assert {"implementation", "refactor", "review"}.issubset(tags)


def test_e2_contracts_do_not_expand_paw_core_root() -> None:
    import paw.core

    assert "RoleContract" not in paw.core.__all__
    assert "CANONICAL_ROLE_CONTRACTS" not in paw.core.__all__
