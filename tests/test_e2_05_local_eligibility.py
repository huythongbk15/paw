"""E2-05 — Local eligibility and explicit out-of-distribution conditions per role (D0).

Verifies that every canonical cognitive role has a closed eligibility rule,
that OOD conditions are a closed set, and that ``evaluate_local_eligibility``
is deterministic and fail-closed for unknown roles.
"""

import pytest
from paw.core.models import ModelRole
from paw.core.reasoning_contracts import (
    CANONICAL_ELIGIBILITY_RULES,
    CANONICAL_ROLE_CONTRACTS,
    OODCondition,
    OOD_CONDITIONS,
    EligibilityResult,
    EligibilityRule,
    ProviderKind,
    evaluate_local_eligibility,
)


def test_eligibility_rules_cover_every_cognitive_role():
    """Every role in CANONICAL_ROLE_CONTRACTS has an eligibility rule."""
    assert set(CANONICAL_ELIGIBILITY_RULES) == set(CANONICAL_ROLE_CONTRACTS)


def test_eligibility_rule_set_is_immutable():
    """CANONICAL_ELIGIBILITY_RULES is a frozen mapping."""
    from types import MappingProxyType

    assert isinstance(CANONICAL_ELIGIBILITY_RULES, MappingProxyType)


def test_eligibility_rule_is_frozen():
    """EligibilityRule is a frozen dataclass."""
    rule = CANONICAL_ELIGIBILITY_RULES[ModelRole.FAST]
    with pytest.raises(AttributeError):
        rule.role = ModelRole.REASONING  # type: ignore[misc]


def test_ood_condition_set_is_closed():
    """OODCondition is a closed enum; OOD_CONDITIONS mirrors it exactly."""
    assert frozenset(OODCondition) == OOD_CONDITIONS
    for member in OODCondition:
        assert member in OOD_CONDITIONS


def test_ood_condition_values_are_strings():
    for member in OODCondition:
        assert isinstance(member.value, str)


def test_provider_kind_values():
    assert ProviderKind.LOCAL == "local"
    assert ProviderKind.CLOUD_APPROVED == "cloud_approved"
    assert ProviderKind.CLOUD_UNAPPROVED == "cloud_unapproved"


def test_fast_rule_is_bounded():
    """FAST only carries no-evidence / low-confidence OOD conditions."""
    rule = CANONICAL_ELIGIBILITY_RULES[ModelRole.FAST]
    assert OODCondition.MISSING_EVIDENCE not in rule.conditions
    assert OODCondition.LOW_CONFIDENCE not in rule.conditions
    assert OODCondition.NO_MATCHING_CAPABILITY in rule.conditions


def test_reasoning_rule_is_strict():
    """REASONING carries the full evidence/confidence/novelty/impact set."""
    rule = CANONICAL_ELIGIBILITY_RULES[ModelRole.REASONING]
    for cond in (
        OODCondition.MISSING_EVIDENCE,
        OODCondition.LOW_CONFIDENCE,
        OODCondition.NOVEL_TASK,
        OODCondition.HIGH_IMPACT,
    ):
        assert cond in rule.conditions


def test_coding_rule_matches_reasoning_strictness():
    """CODING has the same strictness as REASONING for source-backed work."""
    coding = CANONICAL_ELIGIBILITY_RULES[ModelRole.CODING].conditions
    reasoning = CANONICAL_ELIGIBILITY_RULES[ModelRole.REASONING].conditions
    assert set(coding) == set(reasoning)


def test_tools_rule_is_bounded():
    """TOOLS carries no evidence/confidence/novelty conditions."""
    rule = CANONICAL_ELIGIBILITY_RULES[ModelRole.TOOLS]
    assert OODCondition.MISSING_EVIDENCE not in rule.conditions
    assert OODCondition.LOW_CONFIDENCE not in rule.conditions
    assert OODCondition.NOVEL_TASK not in rule.conditions


def test_evaluate_eligible_when_no_overlap():
    result = evaluate_local_eligibility(
        ModelRole.FAST, frozenset({OODCondition.UNKNOWN})
    )
    assert isinstance(result, EligibilityResult)
    assert result.eligible is True
    assert result.conditions == ()
    assert result.matched_rule is not None


def test_evaluate_ineligible_when_overlap():
    result = evaluate_local_eligibility(
        ModelRole.REASONING,
        frozenset({OODCondition.MISSING_EVIDENCE, OODCondition.NOVEL_TASK}),
    )
    assert result.eligible is False
    assert set(result.conditions) == {
        OODCondition.MISSING_EVIDENCE,
        OODCondition.NOVEL_TASK,
    }


def test_evaluate_unknown_role_is_fail_closed():
    """A role without a rule is never eligible."""
    # ModelRole.FALLBACK has no cognitive-role contract and no eligibility rule.
    result = evaluate_local_eligibility(
        ModelRole.FALLBACK, frozenset()
    )
    assert result.eligible is False
    assert result.matched_rule is None
    assert OODCondition.UNKNOWN in result.conditions


def test_evaluate_is_deterministic():
    observed = frozenset({OODCondition.HIGH_IMPACT})
    a = evaluate_local_eligibility(ModelRole.REASONING, observed)
    b = evaluate_local_eligibility(ModelRole.REASONING, observed)
    assert a == b


def test_eligibility_result_is_frozen():
    result = evaluate_local_eligibility(ModelRole.FAST, frozenset())
    with pytest.raises(AttributeError):
        result.eligible = False  # type: ignore[misc]


def test_e2_05_does_not_expand_paw_core_root():
    """E2-05 stays in reasoning_contracts; core root stays at 11 symbols."""
    import paw.core

    assert "EligibilityRule" not in paw.core.__all__
    assert "OODCondition" not in paw.core.__all__
    assert len(paw.core.__all__) == 11


def test_e2_05_does_not_authorize_routing_or_escalation():
    """These symbols are value contracts only; no router/escalation imports."""
    import paw.core.reasoning_contracts as rc

    for name in ("route", "escalate", "select_model", "dispatch"):
        assert not hasattr(rc, name), f"reasoning_contracts must not expose {name}"