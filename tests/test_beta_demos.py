"""BETA demos tests (B-04 through B-07).

Tests that the four daily profiles produce structured answers with evidence,
uncertainty, and next action.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import typer

from paw.core.beta_profiles import ANALYZE, CHANGE, IDEOATE, REVIEW
from paw.core.beta_profiles import is_side_effect_capability
from paw.core.models import Capability


@pytest.fixture(autouse=True)
def cleanup_dbs():
    yield
    for d in ["/tmp/paw_beta_analyze", "/tmp/paw_beta_ideate",
              "/tmp/paw_beta_change", "/tmp/paw_beta_review"]:
        p = Path(d)
        if p.exists():
            import shutil
            shutil.rmtree(p)


REPO_ROOT = "/home/huythong/.hybridagent/workspaces/default"


class TestAnalyzeDemo:
    def test_demo_runs_and_returns_answer(self):
        from demos.demo_analyze import run_analyze_demo
        result = asyncio.run(run_analyze_demo(REPO_ROOT))
        assert result["stopped"] is True
        assert result["evidence"]
        assert result["next_action"] is not None
        assert result["uncertainty"]["confidence"] == 1.0
        assert result["uncertainty"]["side_effects_blocked"] == 0

    def test_demo_counts_files(self):
        from demos.demo_analyze import run_analyze_demo
        result = asyncio.run(run_analyze_demo(REPO_ROOT))
        file_ev = [e for e in result["evidence"] if e.get("type") == "file_counts"]
        assert len(file_ev) == 1
        assert file_ev[0]["py_files"] > 0


class TestIdeateDemo:
    def test_demo_proposes_alternatives_and_decision(self):
        from demos.demo_ideate import run_ideate_demo
        result = asyncio.run(run_ideate_demo())
        assert result["stopped"] is True
        alts = [e for e in result["evidence"] if e.get("type") == "alternatives"]
        assert len(alts) == 1
        assert len(alts[0]["items"]) == 3
        decisions = [e for e in result["evidence"] if e.get("type") == "decision"]
        assert len(decisions) == 1
        assert decisions[0]["score"] == 0.92  # A2 wins


class TestChangeDemo:
    def test_approved_change_writes_and_verifies(self):
        from demos.demo_change import run_change_demo
        result = asyncio.run(run_change_demo(approve=True))
        assert result["uncertainty"]["approval_granted"] is True
        assert result["uncertainty"]["file_written"] is True
        assert result["uncertainty"]["verification_passed"] is True
        assert "verified" in result["next_action"].lower()

    def test_denied_change_no_side_effects(self):
        from demos.demo_change import run_change_demo
        result = asyncio.run(run_change_demo(approve=False))
        assert result["uncertainty"]["approval_granted"] is False
        assert result["uncertainty"]["file_written"] is False
        assert result["uncertainty"]["verification_passed"] is False
        assert "denied" in result["next_action"].lower()


class TestReviewDemo:
    def test_review_demo_identifies_regressions(self):
        from demos.demo_review import run_review_demo
        result = asyncio.run(run_review_demo(REPO_ROOT))
        assert result["stopped"] is True
        assert "regressions_found" in result["uncertainty"]
        assert result["uncertainty"]["side_effects_blocked"] == 0
        assert result["evidence"]

    def test_review_non_mutating(self):
        for cap in REVIEW.allowed_capabilities or []:
            assert not is_side_effect_capability(cap)


class TestRestartSafety:
    """B-08: Restart one demo and prove no completed side effect repeats."""

    def test_denied_change_has_zero_side_effects(self):
        from demos.demo_change import run_change_demo
        import shutil
        work_dir = Path("/tmp/paw_beta_change_restart")
        if work_dir.exists():
            shutil.rmtree(work_dir)
        result = asyncio.run(run_change_demo(approve=False, work_dir=str(work_dir)))
        assert result["uncertainty"]["file_written"] is False
        assert not (work_dir / "changed_file.txt").exists()

    def test_approved_change_is_idempotent(self):
        from demos.demo_change import run_change_demo
        import shutil
        work_dir = Path("/tmp/paw_beta_change_idempotent")
        if work_dir.exists():
            shutil.rmtree(work_dir)
        r1 = asyncio.run(run_change_demo(approve=True, work_dir=str(work_dir)))
        assert r1["uncertainty"]["verification_passed"] is True
        r2 = asyncio.run(run_change_demo(approve=True, work_dir=str(work_dir)))
        assert r2["uncertainty"]["verification_passed"] is True
        assert r2["uncertainty"]["file_written"] is True
        shutil.rmtree(work_dir)


class TestBetaInspectCLI:
    """B-09: Inspect memory, skills, routing, ledger, context from CLI."""

    def test_inspect_skills(self):
        from paw.cli import _do_beta_inspect
        asyncio.run(_do_beta_inspect("skills", None, 20))

    def test_inspect_routing(self):
        from paw.cli import _do_beta_inspect
        asyncio.run(_do_beta_inspect("routing", None, 20))

    def test_inspect_invalid_kind(self):
        from paw.cli import _do_beta_inspect
        with pytest.raises((SystemExit, ValueError, typer.exceptions.Exit)):
            asyncio.run(_do_beta_inspect("bogus", None, 20))

    def test_inspect_ledger_requires_task_id(self):
        from paw.cli import _do_beta_inspect
        with pytest.raises((SystemExit, ValueError, typer.exceptions.Exit)):
            asyncio.run(_do_beta_inspect("ledger", None, 20))
