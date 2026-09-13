"""E3-20: Per-version selection metrics — precision, failures, maintenance cost.

Contract tests (D2):
  - SkillVersionMetrics data model
  - record_skill_selection increments counter
  - record_skill_outcome updates success/failure
  - running averages for tokens/duration
  - selection_precision property
  - get_skill_metrics round-trip
  - failure_reason accumulation
  - outcome without prior selection (auto-initialize)
  - selection without outcome (returns None metrics)
"""

import json
from datetime import datetime, UTC

import pytest

from paw.core.models import SkillVersionMetrics
from paw.core.skills import BUILTIN_SKILLS, SkillFabric
from paw.core.storage import set_db_path, db


@pytest.fixture
async def fabric(tmp_path):
    """A fresh SkillFabric seeded with one skill."""
    paw_home = tmp_path / ".paw"
    paw_home.mkdir(parents=True, exist_ok=True)
    await set_db_path(paw_home / "paw.db")
    await db.initialize()
    f = SkillFabric(tmp_path / "skills")
    await f.initialize()
    return f


# Note: TestSkillVersionMetrics uses sync tests (no asyncio mark);
# TestRecordSelection/TestRecordOutcome/TestGetMetrics use async tests.


class TestSkillVersionMetrics:
    def test_dataclass_defaults(self):
        m = SkillVersionMetrics(skill_name="echo", version="1.0.0")
        assert m.skill_name == "echo"
        assert m.version == "1.0.0"
        assert m.times_selected == 0
        assert m.successful_completions == 0
        assert m.failure_cases == []
        assert m.avg_tokens_consumed == 0.0
        assert m.avg_duration_seconds == 0.0
        assert m.total_selections == 0
        assert m.last_evaluated is None

    def test_selection_precision_zero(self):
        m = SkillVersionMetrics(skill_name="echo", version="1.0.0")
        assert m.selection_precision == 0.0

    def test_selection_precision_calculation(self):
        m = SkillVersionMetrics(
            skill_name="echo", version="1.0.0",
            times_selected=10, successful_completions=8,
        )
        assert m.selection_precision == 0.8


class TestRecordSelection:
    async def test_record_selection_creates_row(self, fabric):
        await fabric.record_skill_selection("echo", "1.0.0")
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m is not None
        assert m.times_selected == 1
        assert m.successful_completions == 0

    async def test_record_multiple_selections(self, fabric):
        await fabric.record_skill_selection("echo", "1.0.0")
        await fabric.record_skill_selection("echo", "1.0.0")
        await fabric.record_skill_selection("echo", "1.0.0")
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m.times_selected == 3
        assert m.total_selections == 0  # no outcomes recorded yet


class TestRecordOutcome:
    async def test_record_successful_outcome(self, fabric):
        await fabric.record_skill_selection("echo", "1.0.0")
        await fabric.record_skill_outcome(
            "echo", "1.0.0", success=True,
            tokens_consumed=100.0, duration_seconds=0.5,
        )
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m.successful_completions == 1
        assert m.failure_cases == []
        assert m.avg_tokens_consumed == 100.0
        assert m.avg_duration_seconds == 0.5
        assert m.last_evaluated is not None

    async def test_record_failed_outcome(self, fabric):
        await fabric.record_skill_selection("echo", "1.0.0")
        await fabric.record_skill_outcome(
            "echo", "1.0.0", success=False,
            failure_reason="timeout",
        )
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m.successful_completions == 0
        assert len(m.failure_cases) == 1
        assert m.failure_cases[0] == "timeout"
        assert m.selection_precision == 0.0

    async def test_running_average_tokens(self, fabric):
        await fabric.record_skill_selection("echo", "1.0.0")
        await fabric.record_skill_outcome("echo", "1.0.0", success=True, tokens_consumed=100.0)
        await fabric.record_skill_outcome("echo", "1.0.0", success=True, tokens_consumed=200.0)
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m.avg_tokens_consumed == 150.0

    async def test_running_average_duration(self, fabric):
        await fabric.record_skill_selection("echo", "1.0.0")
        await fabric.record_skill_outcome("echo", "1.0.0", success=True, duration_seconds=1.0)
        await fabric.record_skill_outcome("echo", "1.0.0", success=True, duration_seconds=3.0)
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m.avg_duration_seconds == 2.0

    async def test_failure_reason_accumulation(self, fabric):
        await fabric.record_skill_selection("echo", "1.0.0")
        await fabric.record_skill_outcome("echo", "1.0.0", success=False, failure_reason="timeout")
        await fabric.record_skill_outcome("echo", "1.0.0", success=False, failure_reason="tool_error")
        await fabric.record_skill_outcome("echo", "1.0.0", success=True, tokens_consumed=50.0)
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert len(m.failure_cases) == 2
        assert "timeout" in m.failure_cases
        assert "tool_error" in m.failure_cases
        assert m.successful_completions == 1
        assert m.times_selected == 1
        # precision = 1 success / 1 selection = 1.0
        assert m.selection_precision == 1.0

    async def test_outcome_without_prior_selection(self, fabric):
        """Record outcome without explicit selection — auto-initializes."""
        await fabric.record_skill_outcome(
            "echo", "1.0.0", success=True, tokens_consumed=50.0,
        )
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m is not None
        assert m.successful_completions == 1
        assert m.avg_tokens_consumed == 50.0


class TestGetMetrics:
    async def test_get_metrics_returns_none_for_unknown(self, fabric):
        m = await fabric.get_skill_metrics("nonexistent", "1.0.0")
        assert m is None

    async def test_selection_without_outcome(self, fabric):
        """Select but don't execute outcome — metrics show 0 completions."""
        await fabric.record_skill_selection("echo", "1.0.0")
        m = await fabric.get_skill_metrics("echo", "1.0.0")
        assert m.times_selected == 1
        assert m.successful_completions == 0
        assert m.last_evaluated is None
