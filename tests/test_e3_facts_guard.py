"""E3-07: Facts/preferences cannot be normalized into active skills.

Memory facts and user preferences are context records, not executable
procedures. Calling normalize_fact_to_skill must always fail.
"""
import pytest

from paw.core.skills import normalize_fact_to_skill
from paw.core.models import Capability


class TestFactCannotBecomesSkill:
    def test_fact_rejected(self):
        """E3-07: A memory fact with valid capabilities cannot become a skill."""
        with pytest.raises(ValueError, match="intentionally refused"):
            normalize_fact_to_skill(
                "User prefers dark mode after 8pm",
                capabilities=[Capability.FILESYSTEM_READ],
            )

    def test_user_preference_rejected(self):
        """E3-07: A user preference cannot become a skill."""
        with pytest.raises(ValueError, match="E3-07"):
            normalize_fact_to_skill(
                "Always use --provider ollama for coding tasks",
                capabilities=[Capability.MODEL_INFERENCE],
            )

    def test_arbitrary_fact_rejected(self):
        """E3-07: Any fact text with any capabilities is refused."""
        for fact in ["TODO: fix the bug", "Remember to water the plant"]:
            with pytest.raises(ValueError, match="intentionally refused"):
                normalize_fact_to_skill(fact, capabilities=[])
