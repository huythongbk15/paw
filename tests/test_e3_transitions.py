"""E3-03: Legal skill state transitions.

Tests that the LEGAL_SKILL_TRANSITIONS table is closed and that
SkillFabric lifecycle methods enforce it.
"""
import pytest

from paw.core.models import LEGAL_SKILL_TRANSITIONS, SkillState
from paw.core.skills import validate_skill_transition


class TestLegalTransitions:
    def test_transition_table_is_closed(self):
        """E3-03: The legal transitions table must list every valid (from, to) pair."""
        expected_pairs = {
            (SkillState.CANDIDATE, SkillState.REVIEWED),
            (SkillState.REVIEWED, SkillState.ACTIVE),
            (SkillState.CANDIDATE, SkillState.REJECTED),
            (SkillState.REVIEWED, SkillState.REJECTED),
            (SkillState.ACTIVE, SkillState.DEPRECATED),
            (SkillState.ACTIVE, SkillState.SUPERSEDED),
            (SkillState.DEPRECATED, SkillState.ACTIVE),
            (SkillState.SUPERSEDED, SkillState.ACTIVE),
        }
        assert set(LEGAL_SKILL_TRANSITIONS.keys()) == expected_pairs

    def test_each_transition_has_required_evidence(self):
        """E3-03: Each transition maps to a required evidence key."""
        for (from_state, to_state), required_evidence in LEGAL_SKILL_TRANSITIONS.items():
            assert isinstance(required_evidence, str)
            assert len(required_evidence) > 0

    @pytest.mark.parametrize("from_state,to_state", [
        (SkillState.CANDIDATE, SkillState.ACTIVE),
        (SkillState.ACTIVE, SkillState.REVIEWED),
        (SkillState.REJECTED, SkillState.ACTIVE),
        (SkillState.DEPRECATED, SkillState.REVIEWED),
        (SkillState.SUPERSEDED, SkillState.DEPRECATED),
        (SkillState.REJECTED, SkillState.REJECTED),
    ])
    def test_illegal_transitions_rejected(self, from_state, to_state):
        """E3-03: Transitions not in the table are rejected."""
        valid, evidence = validate_skill_transition(from_state, to_state)
        assert not valid

    @pytest.mark.parametrize("from_state,to_state", [
        (SkillState.CANDIDATE, SkillState.REVIEWED),
        (SkillState.REVIEWED, SkillState.ACTIVE),
        (SkillState.CANDIDATE, SkillState.REJECTED),
        (SkillState.REVIEWED, SkillState.REJECTED),
        (SkillState.ACTIVE, SkillState.DEPRECATED),
        (SkillState.ACTIVE, SkillState.SUPERSEDED),
        (SkillState.DEPRECATED, SkillState.ACTIVE),
        (SkillState.SUPERSEDED, SkillState.ACTIVE),
    ])
    def test_legal_transitions_accepted(self, from_state, to_state):
        """E3-03: Legal transitions are accepted with correct evidence key."""
        valid, evidence = validate_skill_transition(from_state, to_state)
        assert valid
        assert evidence in LEGAL_SKILL_TRANSITIONS[(from_state, to_state)]

    def test_self_transitions_rejected(self):
        """E3-03: Self-transitions are not in the table."""
        for state in SkillState:
            valid, _ = validate_skill_transition(state, state)
            assert not valid
