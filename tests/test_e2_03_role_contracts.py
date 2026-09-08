"""E2-03 — Role-specific output, evidence, and uncertainty contracts (D1).

Verifies that every canonical role has a RoleContract defining output
schema, evidence expectations, and uncertainty handling. Contract
invariants must hold for reasoning-heavy roles and catch-all roles.
"""

import pytest
from paw.core.models import (
    CANONICAL_MODEL_ROLES,
    CANONICAL_ROLE_CONTRACTS,
    ModelRole,
    ModelManifest,
    RoleContract,
)


def test_canonical_contracts_keys_match_roles():
    """Every canonical role must have a RoleContract."""
    assert set(CANONICAL_ROLE_CONTRACTS.keys()) == set(CANONICAL_MODEL_ROLES.keys())


def test_contract_has_required_fields():
    """RoleContract must carry the E2-03 defined fields."""
    for role, contract in CANONICAL_ROLE_CONTRACTS.items():
        assert isinstance(contract, RoleContract)
        assert contract.role == role
        # output_schema must be a non-empty string
        assert isinstance(contract.output_schema, str)
        assert contract.output_schema, f"Role {role} missing output_schema"
        # escalation_mode must be one of the allowed values
        assert contract.escalation_mode in ("stop", "ask", "escalate")
        # escalation_confidence_threshold must be in [0.0, 1.0]
        assert 0.0 <= contract.escalation_confidence_threshold <= 1.0


def test_reasoning_contract_requires_evidence_and_citation():
    """REASONING role must require evidence and citation."""
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.REASONING]
    assert contract.requires_evidence is True
    assert contract.requires_citation is True
    assert contract.uncertainty_handled is True
    assert len(contract.allowed_evidence_types) > 0
    assert contract.escalation_mode == "escalate"
    assert contract.escalation_confidence_threshold == 0.5


def test_embedding_contract_handles_uncertainty():
    """EMBEDDING role must handle uncertainty."""
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.EMBEDDING]
    assert contract.output_schema == "float_vector"
    assert contract.uncertainty_handled is True


def test_fast_contract_is_minimal():
    """FAST role is minimal: no evidence, no uncertainty, stop-based."""
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.FAST]
    assert contract.requires_evidence is False
    assert contract.uncertainty_handled is False
    assert contract.escalation_mode == "stop"


def test_fallback_contract_is_plain_text():
    """FALLBACK role uses plain_text output."""
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.FALLBACK]
    assert contract.output_schema == "plain_text"
    assert contract.escalation_mode == "stop"


def test_coding_contract_escalates_on_low_confidence():
    """Coding role escalates to ask when confidence is below threshold."""
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.CODING]
    assert contract.escalation_mode == "ask"
    assert contract.escalation_confidence_threshold == 0.3


def test_manifest_role_can_lookup_contract():
    """ModelManifest.supports_role should work with canonical role names."""
    manifest = ModelManifest(
        name="reasoner",
        provider="local",
        roles=["reasoning"],
    )
    assert manifest.supports_role(ModelRole.REASONING)
    assert not manifest.supports_role(ModelRole.FAST)


def test_all_contracts_have_valid_escalation_mode():
    """All contracts must specify a valid escalation mode."""
    for role, contract in CANONICAL_ROLE_CONTRACTS.items():
        assert contract.escalation_mode in ("stop", "ask", "escalate"), (
            f"Role {role} has invalid escalation_mode: {contract.escalation_mode}"
        )
