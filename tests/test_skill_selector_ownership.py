"""Structural regression for one canonical skill-selection algorithm."""

from __future__ import annotations

import inspect

from paw.core.selector import SkillSelector
from paw.core.semantic import SemanticSkillSelector


def test_legacy_skill_selector_delegates_without_running_policy() -> None:
    source = inspect.getsource(SkillSelector.select)

    assert "self._canonical.select" in source
    assert "policy_guard" not in source


def test_legacy_semantic_selector_delegates_to_canonical_selector() -> None:
    source = inspect.getsource(SemanticSkillSelector.select)

    assert "self._canonical.select" in source
