"""E2-03 — role-specific output, evidence and uncertainty contracts (D1)."""

from dataclasses import FrozenInstanceError, replace

import pytest
from paw.core.models import ModelRole
from paw.core.reasoning_contracts import (
    CANONICAL_ROLE_CONTRACTS,
    RoleContract,
    UncertaintyDisposition,
)


def test_every_contract_has_a_typed_output_and_uncertainty_boundary() -> None:
    for role, contract in CANONICAL_ROLE_CONTRACTS.items():
        assert isinstance(contract, RoleContract)
        assert contract.role is role
        assert contract.output_schema
        assert contract.reports_uncertainty is True
        assert contract.minimum_confidence is not None
        assert 0.0 <= contract.minimum_confidence <= 1.0


def test_contracts_are_frozen() -> None:
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.REASONING]
    with pytest.raises(FrozenInstanceError):
        contract.description = "changed"  # type: ignore[misc]


def test_reasoning_returns_an_assessment_not_hidden_chain_of_thought() -> None:
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.REASONING]
    assert contract.output_schema == "reasoning_assessment"
    assert "trace" not in contract.output_schema
    assert contract.requires_evidence is True
    assert contract.requires_citation is True
    assert contract.low_confidence_disposition is UncertaintyDisposition.ESCALATE


def test_coding_requires_project_evidence_and_citations() -> None:
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.CODING]
    assert contract.output_schema == "implementation_proposal"
    assert contract.requires_evidence is True
    assert contract.requires_citation is True
    assert "project_source" in contract.allowed_evidence_types
    assert "test" in contract.allowed_evidence_types


def test_tool_role_proposes_but_does_not_authorize_execution() -> None:
    contract = CANONICAL_ROLE_CONTRACTS[ModelRole.TOOLS]
    assert contract.output_schema == "operation_proposal"
    assert "never execution authority" in contract.description
    assert contract.low_confidence_disposition is UncertaintyDisposition.STOP


def test_evidence_role_must_name_allowed_evidence_types() -> None:
    source = CANONICAL_ROLE_CONTRACTS[ModelRole.REASONING]
    with pytest.raises(ValueError, match="evidence types"):
        replace(source, allowed_evidence_types=())


def test_citation_cannot_be_required_without_evidence() -> None:
    source = CANONICAL_ROLE_CONTRACTS[ModelRole.REASONING]
    with pytest.raises(ValueError, match="without evidence"):
        replace(source, requires_evidence=False)


def test_confidence_threshold_requires_uncertainty_output() -> None:
    source = CANONICAL_ROLE_CONTRACTS[ModelRole.FAST]
    with pytest.raises(ValueError, match="requires uncertainty"):
        replace(source, reports_uncertainty=False)


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_confidence_threshold_is_bounded(value: float) -> None:
    source = CANONICAL_ROLE_CONTRACTS[ModelRole.FAST]
    with pytest.raises(ValueError, match="between"):
        replace(source, minimum_confidence=value)
