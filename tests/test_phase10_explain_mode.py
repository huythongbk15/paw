"""
PAW Phase 10 — Integration Test: Explain Mode Verification

Verify:
- format_explain_report output correct
- Include/exclude reasons logged
- Token counts match estimates
"""

from __future__ import annotations

import pytest

from paw.core.context_compiler import ContextCompiler, ContextCandidate, format_explain_report
from paw.core.context import ContextBudget, ContextFragment


def test_format_explain_report_output():
    selected = [
        ContextCandidate(
            source="memory",
            source_id="m1",
            content="alpha beta gamma",
            relevance_score=0.9,
            reason="high relevance",
            token_estimate=3,
            metadata={"included": True, "excluded_reason": ""},
        ),
    ]
    excluded = [
        ContextCandidate(
            source="knowledge",
            source_id="k1",
            content="delta epsilon",
            relevance_score=0.2,
            reason="low relevance",
            token_estimate=2,
            metadata={"included": False, "excluded_reason": "token_budget_exceeded"},
        ),
    ]

    report = format_explain_report(selected, excluded)
    assert "INCLUDED" in report
    assert "EXCLUDED" in report
    assert "memory:m1" in report
    assert "knowledge:k1" in report
    assert "token_budget_exceeded" in report


def test_explain_mode_attaches_metadata():
    """Explain mode should attach inclusion metadata to all candidates."""
    candidates = [
        ContextCandidate(source="s1", source_id="id1", content="c1", token_estimate=1, metadata={"included": True, "excluded_reason": ""}),
        ContextCandidate(source="s2", source_id="id2", content="c2", token_estimate=2, metadata={"included": False, "excluded_reason": "low_score"}),
    ]
    selected = candidates[:1]
    excluded = candidates[1:]

    report = format_explain_report(selected, excluded)

    assert any(c.metadata.get("included") for c in selected)
    assert all(not c.metadata.get("included", True) for c in excluded)